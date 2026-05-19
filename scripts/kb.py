#!/usr/bin/env python3
"""Markdown-first personal knowledge base CLI.

The knowledge source is Markdown under knowledge/. SQLite is only an index.
Search commands must use SQLite FTS5 and must not scan Markdown files.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from knowledge_core import indexer, lifecycle, quality
from knowledge_core import paths as core_paths
from knowledge_core.benchmark import run_benchmark
from knowledge_core.config import (
    DEFAULT_CONFIG_FILES,
    category_choices,
    ensure_list_text,
    load_sources_config,
)
from knowledge_core.doctor import run_doctor
from knowledge_core.frontmatter import (
    CONFIDENCE_VALUES,
    SOURCE_TYPE_VALUES,
    STATUS_VALUES,
    bool_value,
)
from knowledge_core.indexer import (
    IndexerError,
    connect_db,
    ensure_schema,
    iter_markdown_files,
    list_documents,
    perform_index,
    perform_reindex,
    query_documents,
)
from knowledge_core.lifecycle import LifecycleError
from knowledge_core.paths import (
    CONFIG_DIR,
    DB_PATH,
    EXPLORATORY_LAYERS,
    FORMAL_LAYERS,
    KB_DIR,
    KNOWLEDGE_DIR,
    LAYERS,
    REPORTS_DIR,
    ROOT,
    TEMPLATES_DIR,
    PathConfigError,
    ensure_directories,
    resolve_user_path,
    write_if_missing,
)
from knowledge_core.quality import (
    build_dedupe_groups,
    canonical_file_for,
    conflict_matches_topic,
    possible_conflicts,
    row_summary,
)
from knowledge_core.reports import (
    generate_digest,
    generate_learning_queue,
    generate_weekly_report,
    run_maintenance,
    priority_rank,
    run_monthly_maintenance,
)
from knowledge_core.security import run_secret_scan
from knowledge_core.search import DEFAULT_TOP_K, SearchError, run_search
from knowledge_app.services.archive_metadata_service import ArchiveMetadataService
from knowledge_app.services.category_service import CategoryService
from knowledge_app.services.document_service import DocumentService
from knowledge_app.services.review_queue_service import ReviewQueueService
from knowledge_app.services.search_service import SearchService
from knowledge_app.services.workspace_status_service import WorkspaceStatusService


def configure_core_root(root: Path) -> None:
    core_paths.configure_root(root)
    globals().update(
        ROOT=core_paths.ROOT,
        KNOWLEDGE_DIR=core_paths.KNOWLEDGE_DIR,
        CONFIG_DIR=core_paths.CONFIG_DIR,
        TEMPLATES_DIR=core_paths.TEMPLATES_DIR,
        REPORTS_DIR=core_paths.REPORTS_DIR,
        KB_DIR=core_paths.KB_DIR,
        DB_PATH=core_paths.DB_PATH,
    )


DEFAULT_TEMPLATE_FILES = {
    "templates/knowledge-card.md": """---
title: ""
category: ""
type: rule
status: experimental
confidence: medium
source_type: ""
source_url: ""
created_at: ""
last_reviewed: ""
reviewed_by: ""
valid_for: []
not_valid_for: []
project_scope: ""
topic_id: ""
canonical_id: ""
source_hash: ""
content_hash: ""
supersedes: []
superseded_by: ""
deprecated_reason: ""
rejected_reason: ""
quarantined_reason: ""
risk_level: medium
verification_method: ""
review_required: true
review_cycle_days: ""
---

# 一句话结论

## 适用场景

## 不适用场景

## 背景

## 核心要点

## 推荐做法

## 反例

## 对我的项目有什么影响

## 可执行规则

## 可给 Codex / Agent 使用的指令

## 验证方式

## 来源与备注
""",
    "templates/raw-note.md": """---
title: ""
category: ""
type: raw
status: experimental
confidence: low
source_type: ""
source_url: ""
created_at: ""
last_reviewed: ""
reviewed_by: ""
valid_for: []
not_valid_for: []
project_scope: ""
topic_id: ""
canonical_id: ""
source_hash: ""
content_hash: ""
supersedes: []
superseded_by: ""
deprecated_reason: ""
rejected_reason: ""
quarantined_reason: ""
risk_level: medium
verification_method: ""
review_required: true
review_cycle_days: ""
---

# 原始摘录

raw 只能作为参考，不得直接作为正式规则。

## 来源

## 原文摘录或摘要

## 我的初步理解

## 适用场景

## 风险与待验证

## 审核信息
""",
}


class KBError(Exception):
    """Controlled CLI error."""


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_service_result(result: Any) -> None:
    if getattr(result, "data", None) is not None:
        data = result.data
        print_json(data.to_dict() if hasattr(data, "to_dict") else data)
    else:
        print_json(result.to_dict())
    if not getattr(result, "success", False):
        raise SystemExit(1)


def die(message: str, code: int = 1) -> None:
    raise KBError(message)


def command_init(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    ensure_directories()
    created_files: List[str] = []
    for rel_path, content in {**DEFAULT_CONFIG_FILES, **DEFAULT_TEMPLATE_FILES}.items():
        if write_if_missing(rel_path, content):
            created_files.append(rel_path)
    result = {
        "status": "ok",
        "root": str(ROOT),
        "created_files": created_files,
        "elapsed_ms": elapsed_ms(start),
    }
    print_json(result)


def command_new_card(args: argparse.Namespace) -> None:
    print_json(
        lifecycle.new_card(
            title=args.title,
            category=args.category,
            card_type=args.type,
            status=args.status,
            source_url=args.source_url or "",
        )
    )


def command_add_raw(args: argparse.Namespace) -> None:
    print_json(
        lifecycle.add_raw(
            category=args.category,
            title=args.title,
            source_url=args.source_url or "",
            text=args.text or "",
        )
    )


def command_promote(args: argparse.Namespace) -> None:
    print_json(
        lifecycle.promote(
            path_text=args.path,
            target_layer=args.target_layer,
            reviewed_by=args.reviewed_by,
            confidence=args.confidence,
            valid_for=args.valid_for,
            verification_method=args.verification_method,
            review_note=args.review_note,
        )
    )


def command_index(args: argparse.Namespace) -> None:
    print_json(perform_index(force_hash=bool(getattr(args, "force_hash", False))))


def command_reindex(_: argparse.Namespace) -> None:
    print_json(perform_reindex())


def command_search(args: argparse.Namespace) -> None:
    print_json(run_search(args))


def command_open(args: argparse.Namespace) -> None:
    result = DocumentService().open_document(document_id=args.id, path=args.path)
    if not result.success or not result.data:
        die("; ".join(result.errors) or "open failed")
    payload = result.data
    metadata = dict(payload.get("metadata") or {"path": payload["path"]})
    print("--- kb-open-meta ---")
    print_json({**metadata, "elapsed_ms": payload["elapsed_ms"]})
    print("--- kb-open-content ---")
    print(payload["content"])


def command_list(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = [dict(row) for row in list_documents(conn, args.category, args.layer, args.limit)]
    print_json({"elapsed_ms": elapsed_ms(start), "count": len(rows), "results": rows})


def command_workspace_status(_: argparse.Namespace) -> None:
    result = WorkspaceStatusService().get_status()
    if result.data is None:
        print_json(result.to_dict())
        return
    print_json(result.data.to_dict())


def command_search_service(args: argparse.Namespace) -> None:
    filters = {
        "category": args.category,
        "layer": args.layer,
        "type": args.type,
        "status": args.status,
        "confidence": args.confidence,
        "source_type": args.source_type,
    }
    include_options = {
        "include_distilled": args.include_distilled,
        "include_raw": args.include_raw,
        "include_deprecated": args.include_deprecated,
        "force": args.force,
    }
    result = SearchService().search(
        query=args.query,
        filters=filters,
        top_k=args.top_k,
        include_options=include_options,
        explain_score=args.explain_score,
    )
    print_service_result(result)


def command_category_summary(args: argparse.Namespace) -> None:
    service = CategoryService()
    result = service.get_category_summary(args.category) if args.category else service.list_categories()
    print_service_result(result)


def command_review_queue_list(args: argparse.Namespace) -> None:
    result = ReviewQueueService().list_review_queue(limit=args.limit, offset=args.offset, category_id=args.category)
    print_service_result(result)


def command_archive_list(args: argparse.Namespace) -> None:
    service = ArchiveMetadataService()
    if args.kind == "deprecated":
        result = service.list_deprecated(limit=args.limit, offset=args.offset, category_id=args.category)
    elif args.kind == "quarantine":
        result = service.list_quarantine(limit=args.limit, offset=args.offset, category_id=args.category)
    else:
        result = service.list_archived(limit=args.limit, offset=args.offset, category_id=args.category)
    print_service_result(result)


def command_document_open(args: argparse.Namespace) -> None:
    result = DocumentService().open_document(document_id=args.id, path=args.path)
    print_service_result(result)


def resolve_document_path(path_text: Optional[str], document_id: Optional[int]) -> Path:
    if document_id is not None:
        conn = connect_db(must_exist=True)
        ensure_schema(conn)
        row = conn.execute("SELECT path FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            die(f"No document with id={document_id}")
        return (ROOT / row["path"]).resolve()
    if path_text:
        return resolve_user_path(path_text)
    die("This command requires --path or --id")


def command_lint(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    result = quality.lint(iter_markdown_files(), args.category, args.layer, args.limit)
    result["elapsed_ms"] = elapsed_ms(start)
    print_json(result)


def command_audit(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)
    result = quality.audit(conn, rows, args.days, args.limit)
    result["elapsed_ms"] = elapsed_ms(start)
    print_json(result)


def command_review_queue(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)
    result = quality.review_queue(rows, args.days, args.limit)
    result["elapsed_ms"] = elapsed_ms(start)
    print_json(result)


def command_stale(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)
    result = quality.stale(rows, args.days, args.limit)
    result["elapsed_ms"] = elapsed_ms(start)
    print_json(result)


def command_conflicts(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)
    result = quality.conflicts(conn, rows, args.limit)
    result["elapsed_ms"] = elapsed_ms(start)
    print_json(result)


def command_dedupe(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)
    result = quality.dedupe(rows, args.limit)
    result["elapsed_ms"] = elapsed_ms(start)
    print_json(result)


def command_canonical_report(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)
    dedupe_groups = build_dedupe_groups(rows, 10000)
    conflicts = possible_conflicts(conn, rows, 10000)

    by_topic: Dict[Tuple[str, str], List[sqlite3.Row]] = {}
    for row in rows:
        topic_id = str(row["topic_id"] or "").strip()
        if topic_id:
            by_topic.setdefault((str(row["category"]), topic_id), []).append(row)

    topics: List[Dict[str, Any]] = []
    for (category, topic_id), bucket in sorted(by_topic.items()):
        paths = {str(row["path"]) for row in bucket}
        unresolved_duplicates = [
            group
            for group in dedupe_groups
            if any(str(item.get("path") or "") in paths for item in group.get("duplicate_group", []))
        ]
        unresolved_conflicts = [conflict for conflict in conflicts if conflict_matches_topic(conflict, topic_id, paths)]
        topics.append(
            {
                "category": category,
                "topic_id": topic_id,
                "canonical_rule": canonical_file_for(bucket, "rules"),
                "canonical_checklist": canonical_file_for(bucket, "checklists"),
                "active_files": [row_summary(row) for row in bucket if row["status"] == "active"],
                "deprecated_files": [row_summary(row) for row in bucket if row["status"] == "deprecated" or row["layer"] == "deprecated"],
                "raw_supporting_files": [row_summary(row) for row in bucket if row["layer"] == "raw"],
                "unresolved_duplicates": unresolved_duplicates[: args.limit],
                "unresolved_conflicts": unresolved_conflicts[: args.limit],
            }
        )

    print_json({"topic_count": len(topics), "topics": topics[: args.limit], "elapsed_ms": elapsed_ms(start)})


def command_deprecate(args: argparse.Namespace) -> None:
    path = resolve_document_path(args.path, args.id)
    print_json(lifecycle.deprecate(path, args.reason, args.superseded_by, args.reviewed_by))


def command_quarantine(args: argparse.Namespace) -> None:
    path = resolve_document_path(args.path, args.id)
    print_json(lifecycle.quarantine(path, args.reason))


def command_research(args: argparse.Namespace) -> None:
    args.research = True
    result = run_search(args)
    result["warning"] = "以下内容未经审核，不能作为正式项目规则。"
    print_json(result)


def command_sources(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    rows = []
    for source in load_sources_config():
        if args.category and source.get("category") != args.category:
            continue
        if args.enabled_only and not bool_value(source.get("enabled")):
            continue
        rows.append(
            {
                "name": source.get("name", ""),
                "category": source.get("category", ""),
                "type": source.get("type", ""),
                "priority": source.get("priority", ""),
                "enabled": bool_value(source.get("enabled")),
                "url": source.get("url", ""),
                "learn_focus": ensure_list_text(source.get("learn_focus")),
            }
        )
    rows.sort(key=lambda item: (priority_rank(str(item["priority"])), str(item["category"]), str(item["name"])))
    print_json({"count": len(rows), "results": rows, "elapsed_ms": elapsed_ms(start)})


def command_learning_queue(_: argparse.Namespace) -> None:
    print_json(generate_learning_queue())


def command_distill_plan(args: argparse.Namespace) -> None:
    print_json(lifecycle.distill_plan(args.path))


def command_digest(_: argparse.Namespace) -> None:
    print_json(generate_digest())


def command_stats(_: argparse.Namespace) -> None:
    print_json(indexer.stats())


def command_doctor(_: argparse.Namespace) -> None:
    print_json(run_doctor())


def command_vacuum(_: argparse.Namespace) -> None:
    print_json(indexer.vacuum())


def command_secret_scan(args: argparse.Namespace) -> None:
    result = run_secret_scan(args.limit)
    print_json(result)
    if result["high_risk_count"]:
        raise SystemExit(1)


def command_benchmark(args: argparse.Namespace) -> None:
    print_json(run_benchmark(args.query, args.top_k))


def command_weekly_report(_: argparse.Namespace) -> None:
    print_json(generate_weekly_report())


def command_monthly_maintenance(args: argparse.Namespace) -> None:
    result = run_monthly_maintenance(args.days, args.limit, args.force_hash)
    print_json(result)
    if result["summary"]["high_risk_secret_findings"]:
        raise SystemExit(1)


def command_maintenance(args: argparse.Namespace) -> None:
    result = run_maintenance(args.days, args.limit, args.force_hash, args.vacuum)
    print_json(result)
    if result["summary"]["high_risk_secret_findings"]:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kb.py",
        description="Markdown-first personal development knowledge base with SQLite FTS5 indexing.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize directories, config, templates, and .kb without overwriting files.")
    p_init.set_defaults(func=command_init)

    p_new = sub.add_parser("new-card", help="Create a distilled knowledge card.")
    p_new.add_argument("--category", required=True, choices=category_choices())
    p_new.add_argument("--type", required=True, choices=["rule", "pattern", "pitfall", "changelog", "snippet", "checklist", "case", "adr"])
    p_new.add_argument("--title", required=True)
    p_new.add_argument("--status", required=True, choices=sorted(STATUS_VALUES))
    p_new.add_argument("--source-url", default="")
    p_new.set_defaults(func=command_new_card)

    p_raw = sub.add_parser("add-raw", help="Add a raw note that requires review.")
    p_raw.add_argument("--category", required=True, choices=category_choices())
    p_raw.add_argument("--title", required=True)
    p_raw.add_argument("--source-url", default="")
    p_raw.add_argument("--text", default="")
    p_raw.set_defaults(func=command_add_raw)

    p_promote = sub.add_parser("promote", help="Promote a distilled card into rules, snippets, or checklists.")
    p_promote.add_argument("--path", required=True)
    p_promote.add_argument("--target-layer", required=True, choices=["rules", "snippets", "checklists"])
    p_promote.add_argument("--reviewed-by", required=True, help="Human reviewer name or handle.")
    p_promote.add_argument("--confidence", required=True, choices=sorted(CONFIDENCE_VALUES))
    p_promote.add_argument("--valid-for", required=True, help="Comma-separated reviewed applicability scope.")
    p_promote.add_argument("--verification-method", required=True, help="How this knowledge was verified.")
    p_promote.add_argument("--review-note", required=True, help="Human review note explaining why promotion is safe.")
    p_promote.set_defaults(func=command_promote)

    p_index = sub.add_parser("index", help="Incrementally index changed Markdown files.")
    p_index.add_argument("--force-hash", action="store_true", help="Compute sha256 even when mtime/size are unchanged.")
    p_index.set_defaults(func=command_index)

    p_reindex = sub.add_parser("reindex", help="Delete .kb/index.sqlite and rebuild the full index explicitly.")
    p_reindex.set_defaults(func=command_reindex)

    p_search = sub.add_parser("search", help="Search via SQLite FTS5. Does not scan Markdown files.")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--category", choices=category_choices())
    p_search.add_argument("--layer", choices=LAYERS)
    p_search.add_argument("--type")
    p_search.add_argument("--status", choices=sorted(STATUS_VALUES))
    p_search.add_argument("--confidence", choices=sorted(CONFIDENCE_VALUES))
    p_search.add_argument("--source-type", dest="source_type", choices=sorted(SOURCE_TYPE_VALUES))
    p_search.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    p_search.add_argument("--include-distilled", action="store_true", help="Explicitly include distilled content in search.")
    p_search.add_argument("--include-raw", action="store_true", help="Explicitly include raw content in search.")
    p_search.add_argument("--include-deprecated", action="store_true")
    p_search.add_argument("--slow-scan", action="store_true", help="Explicit emergency fallback that reads Markdown files.")
    p_search.add_argument("--force", action="store_true", help="Allow --top-k above 50.")
    p_search.add_argument("--explain-score", action="store_true", help="Include per-result score component breakdown for search tuning.")
    p_search.set_defaults(func=command_search)

    p_open = sub.add_parser("open", help="Open exactly one Markdown document by path or document id.")
    group = p_open.add_mutually_exclusive_group(required=True)
    group.add_argument("--path")
    group.add_argument("--id", type=int)
    p_open.set_defaults(func=command_open)

    p_list = sub.add_parser("list", help="List documents from index metadata only.")
    p_list.add_argument("--category", choices=category_choices())
    p_list.add_argument("--layer", choices=LAYERS)
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(func=command_list)

    p_workspace_status = sub.add_parser(
        "workspace-status",
        help="Show startup-safe workspace/index status from SQLite metadata only.",
    )
    p_workspace_status.set_defaults(func=command_workspace_status)

    p_search_service = sub.add_parser(
        "search-service",
        help="Service-layer SQLite FTS search wrapper for future GUI/EXE callers.",
    )
    p_search_service.add_argument("--query", required=True)
    p_search_service.add_argument("--category", choices=category_choices())
    p_search_service.add_argument("--layer", choices=LAYERS)
    p_search_service.add_argument("--type")
    p_search_service.add_argument("--status", choices=sorted(STATUS_VALUES))
    p_search_service.add_argument("--confidence", choices=sorted(CONFIDENCE_VALUES))
    p_search_service.add_argument("--source-type", dest="source_type", choices=sorted(SOURCE_TYPE_VALUES))
    p_search_service.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    p_search_service.add_argument("--include-distilled", action="store_true")
    p_search_service.add_argument("--include-raw", action="store_true")
    p_search_service.add_argument("--include-deprecated", action="store_true")
    p_search_service.add_argument("--force", action="store_true")
    p_search_service.add_argument("--explain-score", action="store_true")
    p_search_service.set_defaults(func=command_search_service)

    p_category_summary = sub.add_parser(
        "category-summary",
        help="Service-layer category counts from config and SQLite metadata.",
    )
    p_category_summary.add_argument("--category", choices=category_choices())
    p_category_summary.set_defaults(func=command_category_summary)

    p_review_queue_list = sub.add_parser(
        "review-queue-list",
        help="Service-layer paginated review queue from SQLite metadata.",
    )
    p_review_queue_list.add_argument("--category", choices=category_choices())
    p_review_queue_list.add_argument("--limit", type=int, default=50)
    p_review_queue_list.add_argument("--offset", type=int, default=0)
    p_review_queue_list.set_defaults(func=command_review_queue_list)

    p_archive_list = sub.add_parser(
        "archive-list",
        help="Service-layer archive/deprecated/quarantine metadata listing.",
    )
    p_archive_list.add_argument("--kind", choices=["archived", "deprecated", "quarantine"], default="archived")
    p_archive_list.add_argument("--category", choices=category_choices())
    p_archive_list.add_argument("--limit", type=int, default=50)
    p_archive_list.add_argument("--offset", type=int, default=0)
    p_archive_list.set_defaults(func=command_archive_list)

    p_document_open = sub.add_parser(
        "document-open",
        help="Service-layer explicit single-document Markdown open.",
    )
    document_group = p_document_open.add_mutually_exclusive_group(required=True)
    document_group.add_argument("--path")
    document_group.add_argument("--id", type=int)
    p_document_open.set_defaults(func=command_document_open)

    p_sources = sub.add_parser("sources", help="List configured learning sources without fetching content.")
    p_sources.add_argument("--category", choices=category_choices())
    p_sources.add_argument("--enabled-only", action="store_true")
    p_sources.set_defaults(func=command_sources)

    p_learning_queue = sub.add_parser("learning-queue", help="Generate a learning queue report from sources and radar config.")
    p_learning_queue.set_defaults(func=command_learning_queue)

    p_distill_plan = sub.add_parser("distill-plan", help="Read one raw file and output a distillation plan.")
    p_distill_plan.add_argument("--path", required=True)
    p_distill_plan.set_defaults(func=command_distill_plan)

    p_digest = sub.add_parser("digest", help="Generate a category digest from SQLite index metadata.")
    p_digest.set_defaults(func=command_digest)

    p_lint = sub.add_parser("lint", help="Lint frontmatter schema and quality gates.")
    p_lint.add_argument("--category", choices=category_choices())
    p_lint.add_argument("--layer", choices=LAYERS)
    p_lint.add_argument("--limit", type=int, default=200)
    p_lint.set_defaults(func=command_lint)

    p_audit = sub.add_parser("audit", help="Output a full quality governance report from index metadata.")
    p_audit.add_argument("--days", type=int, default=180, help="Default stale threshold when review_cycle_days is absent.")
    p_audit.add_argument("--limit", type=int, default=50)
    p_audit.set_defaults(func=command_audit)

    p_review = sub.add_parser("review-queue", help="List content that should receive human review.")
    p_review.add_argument("--days", type=int, default=14, help="Recent raw window in days.")
    p_review.add_argument("--limit", type=int, default=50)
    p_review.set_defaults(func=command_review_queue)

    p_stale = sub.add_parser("stale", help="Find active knowledge past last_reviewed/review_cycle_days.")
    p_stale.add_argument("--days", type=int, default=180)
    p_stale.add_argument("--limit", type=int, default=100)
    p_stale.set_defaults(func=command_stale)

    p_conflicts = sub.add_parser("conflicts", help="Detect basic duplicate and conflicting active rules.")
    p_conflicts.add_argument("--limit", type=int, default=50)
    p_conflicts.set_defaults(func=command_conflicts)

    p_dedupe = sub.add_parser("dedupe", help="Detect duplicate titles, URLs, hashes, and similar filenames.")
    p_dedupe.add_argument("--limit", type=int, default=50)
    p_dedupe.set_defaults(func=command_dedupe)

    p_canonical = sub.add_parser("canonical-report", help="Report canonical files and unresolved issues per topic_id.")
    p_canonical.add_argument("--limit", type=int, default=100)
    p_canonical.set_defaults(func=command_canonical_report)

    p_deprecate = sub.add_parser("deprecate", help="Mark a rule as deprecated and move it to deprecated/.")
    dep_group = p_deprecate.add_mutually_exclusive_group(required=True)
    dep_group.add_argument("--path")
    dep_group.add_argument("--id", type=int)
    p_deprecate.add_argument("--reason", required=True)
    p_deprecate.add_argument("--superseded-by", default="")
    p_deprecate.add_argument("--reviewed-by", required=True)
    p_deprecate.set_defaults(func=command_deprecate)

    p_quarantine = sub.add_parser("quarantine", help="Move questionable content into quarantine/.")
    q_group = p_quarantine.add_mutually_exclusive_group(required=True)
    q_group.add_argument("--path")
    q_group.add_argument("--id", type=int)
    p_quarantine.add_argument("--reason", required=True)
    p_quarantine.set_defaults(func=command_quarantine)

    p_research = sub.add_parser("research", help="Explore raw/distilled content. Results are not formal rules.")
    p_research.add_argument("--query", required=True)
    p_research.add_argument("--category", choices=category_choices())
    p_research.add_argument("--layer", choices=sorted(EXPLORATORY_LAYERS))
    p_research.add_argument("--type")
    p_research.add_argument("--status", choices=sorted(STATUS_VALUES))
    p_research.add_argument("--confidence", choices=sorted(CONFIDENCE_VALUES))
    p_research.add_argument("--source-type", dest="source_type", choices=sorted(SOURCE_TYPE_VALUES))
    p_research.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    p_research.add_argument("--include-distilled", action="store_true")
    p_research.add_argument("--include-raw", action="store_true")
    p_research.add_argument("--include-deprecated", action="store_true")
    p_research.add_argument("--slow-scan", action="store_true")
    p_research.add_argument("--force", action="store_true")
    p_research.set_defaults(func=command_research, research=True)

    p_stats = sub.add_parser("stats", help="Show index statistics.")
    p_stats.set_defaults(func=command_stats)

    p_doctor = sub.add_parser("doctor", help="Validate index, lifecycle metadata, and frontmatter quality.")
    p_doctor.set_defaults(func=command_doctor)

    p_vacuum = sub.add_parser("vacuum", help="VACUUM the SQLite index.")
    p_vacuum.set_defaults(func=command_vacuum)

    p_secret = sub.add_parser("secret-scan", help="Scan repository files for common high-risk secrets.")
    p_secret.add_argument("--limit", type=int, default=200, help="Maximum findings to print.")
    p_secret.set_defaults(func=command_secret_scan)

    p_bench = sub.add_parser("benchmark", help="Run several FTS5 search benchmark queries.")
    p_bench.add_argument("--query", action="append", help="Custom query. Can be repeated.")
    p_bench.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    p_bench.set_defaults(func=command_benchmark)

    p_report = sub.add_parser("weekly-report", help="Generate a weekly report from index metadata.")
    p_report.set_defaults(func=command_weekly_report)

    p_monthly = sub.add_parser("monthly-maintenance", help="Run index/lint/audit/dedupe/conflicts/stale/secret-scan and write a monthly report.")
    p_monthly.add_argument("--days", type=int, default=180)
    p_monthly.add_argument("--limit", type=int, default=100)
    p_monthly.add_argument("--force-hash", action="store_true", help="Force sha256 recomputation during monthly index.")
    p_monthly.set_defaults(func=command_monthly_maintenance)

    p_maintenance = sub.add_parser(
        "maintenance",
        help="Run long-term maintenance checks and write reports/maintenance/YYYY-MM-maintenance.md.",
    )
    p_maintenance.add_argument("--days", type=int, default=180)
    p_maintenance.add_argument("--limit", type=int, default=100)
    p_maintenance.add_argument("--force-hash", action="store_true", help="Force sha256 recomputation during index.")
    p_maintenance.add_argument("--vacuum", action="store_true", help="Explicitly VACUUM the SQLite index after checks.")
    p_maintenance.set_defaults(func=command_maintenance)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except KBError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except PathConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except LifecycleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except IndexerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except SearchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except sqlite3.Error as exc:
        print(f"SQLite ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
