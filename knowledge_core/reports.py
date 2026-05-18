"""Report command cores."""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import paths as core_paths
from .config import ensure_list_text, load_categories, load_learning_radar, load_sources_config
from .frontmatter import bool_value
from .indexer import connect_db, ensure_schema, iter_markdown_files, perform_index, query_documents
from .paths import EXPLORATORY_LAYERS, FORMAL_LAYERS, to_relative_posix
from .quality import (
    build_dedupe_groups,
    collect_audit_summary,
    collect_lint_issues,
    is_stale_row,
    possible_conflicts,
)
from .security import run_secret_scan


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def today_iso() -> str:
    return datetime.now().date().isoformat()


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    value = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None


def priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 9)


def markdown_list(items: Sequence[str]) -> str:
    if not items:
        return "未配置"
    return ", ".join(str(item) for item in items)


def learning_quality_warning(source: Dict[str, Any]) -> str:
    source_type = str(source.get("type") or "")
    priority = str(source.get("priority") or "")
    if source_type in {"manual", "rss"}:
        return "只生成学习任务，不抓取全文；进入 raw 后仍需人工审核，不能直接进入 rules。"
    if priority == "low":
        return "低优先级来源只适合补充参考，默认不得影响正式规则。"
    return "即使是高优先级来源，也必须 raw -> distilled -> review-queue -> promote 后才可进入正式知识。"


def generate_learning_queue() -> Dict[str, Any]:
    start = time.perf_counter()
    sources = [source for source in load_sources_config() if bool_value(source.get("enabled"))]
    radar = load_learning_radar()
    sources.sort(key=lambda source: (priority_rank(str(source.get("priority"))), str(source.get("category")), str(source.get("name"))))
    today = today_iso()
    lines = [
        "---",
        f'title: "Learning Queue {today}"',
        "type: learning_queue",
        "status: experimental",
        "source_type: internal_practice",
        f'created_at: "{now_iso()}"',
        "review_required: true",
        "---",
        "",
        f"# Learning Queue {today}",
        "",
        "本报告只生成待学习任务，不抓取全文，不创建 raw/distilled/rules。所有学习结果必须先进入 raw，不能直接进入正式规则层。",
        "",
    ]
    task_count = 0
    current_group: Optional[Tuple[str, str]] = None
    for source in sources:
        category = str(source.get("category") or "unknown")
        priority = str(source.get("priority") or "unknown")
        group = (priority, category)
        if group != current_group:
            lines.extend([f"## {priority.upper()} / {category}", ""])
            current_group = group
        radar_meta = radar.get(category, {})
        learn_focus = ensure_list_text(source.get("learn_focus")) or ensure_list_text(radar_meta.get("focus"))
        expected = ensure_list_text(source.get("output_targets")) or ensure_list_text(radar_meta.get("preferred_outputs"))
        lines.extend(
            [
                f"### {source.get('name', '')}",
                "",
                f"- source name: {source.get('name', '')}",
                f"- category: {category}",
                f"- url: {source.get('url', '')}",
                f"- learn_focus: {markdown_list(learn_focus)}",
                f"- expected output: {markdown_list(expected)}",
                f"- quality warning: {learning_quality_warning(source)}",
                f"- radar goal: {radar_meta.get('learning_goal', '未配置')}",
                "",
            ]
        )
        task_count += 1
    core_paths.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = core_paths.REPORTS_DIR / f"learning-queue-{today}.md"
    report_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return {"report": to_relative_posix(report_path), "task_count": task_count, "elapsed_ms": elapsed_ms(start)}


def generate_digest() -> Dict[str, Any]:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    docs = query_documents(conn)
    radar = load_learning_radar()
    sources = load_sources_config()
    high_sources_by_category: Dict[str, List[str]] = {}
    for source in sources:
        if source.get("priority") == "high" and bool_value(source.get("enabled")):
            high_sources_by_category.setdefault(str(source.get("category") or "unknown"), []).append(str(source.get("name") or ""))
    categories = sorted(load_categories().keys())
    rows: List[Dict[str, Any]] = []
    for category in categories:
        category_docs = [row for row in docs if row["category"] == category]
        rows.append(
            {
                "category": category,
                "raw": sum(1 for row in category_docs if row["layer"] == "raw"),
                "distilled": sum(1 for row in category_docs if row["layer"] == "distilled"),
                "rules": sum(1 for row in category_docs if row["layer"] == "rules"),
                "pending_review": sum(1 for row in category_docs if bool_value(row["review_required"]) or row["layer"] in EXPLORATORY_LAYERS),
                "stale": sum(1 for row in category_docs if row["status"] == "active" and is_stale_row(row, 180)),
                "high_priority_sources": high_sources_by_category.get(category, []),
                "learning_frequency": radar.get(category, {}).get("frequency", ""),
            }
        )

    today = today_iso()
    lines = [
        "---",
        f'title: "Category Digest {today}"',
        "type: category_digest",
        "status: active",
        "source_type: internal_practice",
        f'created_at: "{now_iso()}"',
        "review_required: false",
        "---",
        "",
        f"# Category Digest {today}",
        "",
        "本摘要基于 SQLite 索引元数据生成，不全量读取 Markdown 正文。",
        "",
        "| category | raw | distilled | rules | pending_review | stale | high_priority_sources | frequency |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {category} | {raw} | {distilled} | {rules} | {pending_review} | {stale} | {sources} | {frequency} |".format(
                category=row["category"],
                raw=row["raw"],
                distilled=row["distilled"],
                rules=row["rules"],
                pending_review=row["pending_review"],
                stale=row["stale"],
                sources=", ".join(row["high_priority_sources"]),
                frequency=row["learning_frequency"],
            )
        )
    report_path = core_paths.REPORTS_DIR / f"category-digest-{today}.md"
    core_paths.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return {"report": to_relative_posix(report_path), "categories": rows, "elapsed_ms": elapsed_ms(start)}


def is_current_iso_week(value: str, year: int, week: int) -> bool:
    parsed = parse_date(value)
    if not parsed:
        return False
    iso = parsed.isocalendar()
    return iso.year == year and iso.week == week


def stale_or_missing_review(value: str) -> bool:
    parsed = parse_date(value)
    if not parsed:
        return True
    return datetime.now() - parsed.replace(tzinfo=None) > timedelta(days=90)


def markdown_table(rows: Sequence[sqlite3.Row], fields: Sequence[str]) -> str:
    if not rows:
        return "_无_\n"
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in rows:
        values = [str(row[field] or "").replace("|", "\\|") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def generate_weekly_report() -> Dict[str, Any]:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    today = datetime.now()
    iso = today.isocalendar()
    year, week = iso.year, iso.week

    docs = conn.execute(
        """
        SELECT id, path, title, category, layer, type, status, confidence,
               source_type, created_at, last_reviewed, reviewed_at, promoted_from
        FROM documents
        ORDER BY category, layer, title
        """
    ).fetchall()

    new_raw = [row for row in docs if row["layer"] == "raw" and is_current_iso_week(row["created_at"], year, week)]
    new_distilled = [row for row in docs if row["layer"] == "distilled" and is_current_iso_week(row["created_at"], year, week)]
    promoted = [
        row
        for row in docs
        if row["layer"] in FORMAL_LAYERS and (is_current_iso_week(row["reviewed_at"], year, week) or row["promoted_from"])
    ]
    pending = [
        row
        for row in docs
        if row["layer"] in {"raw", "distilled"} and row["status"] in {"experimental", "rejected"}
    ][:50]
    stale = [
        row
        for row in docs
        if row["status"] == "active" and stale_or_missing_review(row["last_reviewed"])
    ][:50]

    report = f"""---
title: "{year}-{week:02d} Weekly Knowledge Report"
category: ""
type: report
status: active
confidence: medium
source_type: internal_practice
source_url: ""
created_at: "{now_iso()}"
last_reviewed: "{today_iso()}"
week: "{year}-{week:02d}"
---

# {year}-{week:02d} 本周知识报告

本报告基于 SQLite 索引元数据生成，不全量读取 Markdown 正文。

## 本周新增 raw

{markdown_table(new_raw, ["id", "path", "title", "category", "status", "source_type"])}

## 本周新增 distilled

{markdown_table(new_distilled, ["id", "path", "title", "category", "status", "confidence"])}

## 本周 promoted 到 rules/snippets/checklists

{markdown_table(promoted, ["id", "path", "title", "category", "layer", "reviewed_at"])}

## 高优先级待审核内容

{markdown_table(pending, ["id", "path", "title", "category", "layer", "confidence"])}

## 过期或待复查内容

{markdown_table(stale, ["id", "path", "title", "category", "layer", "last_reviewed"])}
"""
    core_paths.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = core_paths.REPORTS_DIR / f"{year}-{week:02d}-weekly-report.md"
    report_path.write_text(report, encoding="utf-8", newline="\n")
    return {
        "report": to_relative_posix(report_path),
        "new_raw": len(new_raw),
        "new_distilled": len(new_distilled),
        "promoted": len(promoted),
        "pending_review": len(pending),
        "stale_or_missing_review": len(stale),
        "elapsed_ms": elapsed_ms(start),
    }


def json_block(data: Any) -> str:
    return "```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```"


def run_monthly_maintenance(days: int, limit: int, force_hash: bool) -> Dict[str, Any]:
    start = time.perf_counter()
    month = datetime.now().strftime("%Y-%m")
    index_result = perform_index(force_hash=force_hash)
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)

    lint_result = collect_lint_issues(iter_markdown_files(), limit)
    audit_result = collect_audit_summary(conn, rows, days, limit)
    dedupe_groups = build_dedupe_groups(rows, limit)
    conflicts = possible_conflicts(conn, rows, limit)
    stale_rows = [dict(row) for row in rows if row["status"] == "active" and is_stale_row(row, days)]
    secret_result = run_secret_scan(limit)

    summary = {
        "month": month,
        "index": index_result,
        "lint_errors": lint_result["error_count"],
        "lint_warnings": lint_result["warning_count"],
        "audit": {
            "documents": audit_result["documents"],
            "formal_missing_source_count": audit_result["formal_missing_source_count"],
            "missing_formal_review_count": audit_result["missing_formal_review_count"],
            "stale_active_count": audit_result["stale_active_count"],
            "raw_in_formal_layer_count": audit_result["raw_in_formal_layer_count"],
        },
        "dedupe_groups": len(dedupe_groups),
        "conflicts": len(conflicts),
        "stale": len(stale_rows),
        "secret_findings": secret_result["findings_count"],
        "high_risk_secret_findings": secret_result["high_risk_count"],
    }

    report = f"""---
title: "Monthly Maintenance {month}"
type: monthly_maintenance
status: active
source_type: internal_practice
created_at: "{now_iso()}"
review_required: false
---

# Monthly Maintenance {month}

本报告基于索引元数据和 frontmatter 检查生成。它不会把 raw/distilled 提升为正式规则，也不会删除历史知识。

## Summary

{json_block(summary)}

## Index

{json_block(index_result)}

## Lint

{json_block(lint_result)}

## Audit

{json_block(audit_result)}

## Dedupe

{json_block({"count": len(dedupe_groups), "groups": dedupe_groups})}

## Conflicts

{json_block({"count": len(conflicts), "results": conflicts})}

## Stale

{json_block({"days": days, "count": len(stale_rows), "results": stale_rows[:limit]})}

## Secret Scan

{json_block(secret_result)}
"""
    core_paths.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = core_paths.REPORTS_DIR / f"monthly-maintenance-{month}.md"
    report_path.write_text(report, encoding="utf-8", newline="\n")

    return {
        "report": to_relative_posix(report_path),
        "summary": summary,
        "elapsed_ms": elapsed_ms(start),
    }
