#!/usr/bin/env python3
"""Markdown-first personal knowledge base CLI.

The knowledge source is Markdown under knowledge/. SQLite is only an index.
Search commands must use SQLite FTS5 and must not scan Markdown files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from knowledge_core import paths as core_paths
from knowledge_core import lifecycle, quality
from knowledge_core.config import (
    DEFAULT_CONFIG_FILES,
    category_choices,
    ensure_list_text,
    load_categories,
    load_learning_radar,
    load_sources_config,
)
from knowledge_core.frontmatter import (
    CONFIDENCE_VALUES,
    REQUIRED_SCHEMA_FIELDS,
    SOURCE_TYPE_VALUES,
    STATUS_VALUES,
    bool_value,
    metadata_string,
    parse_frontmatter,
)
from knowledge_core.lifecycle import LifecycleError
from knowledge_core.markdown import (
    SEARCHABLE_EXTENSIONS,
    chunk_markdown,
    first_heading,
    normalized_hash_text,
    read_single_markdown,
    sha256_file,
    sha256_text,
)
from knowledge_core.paths import (
    CONFIG_DIR,
    DB_PATH,
    DEFAULT_SEARCH_LAYERS,
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
    infer_category_layer,
    resolve_user_path,
    to_relative_posix,
    write_if_missing,
)
from knowledge_core.quality import (
    build_dedupe_groups,
    canonical_file_for,
    collect_audit_summary,
    collect_lint_issues,
    conflict_matches_topic,
    is_stale_row,
    possible_conflicts,
    row_summary,
)
from knowledge_core.security import run_secret_scan


MAX_SNIPPET_CHARS = 500
DEFAULT_TOP_K = 10
MAX_TOP_K = 50


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


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def today_iso() -> str:
    return datetime.now().date().isoformat()


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def die(message: str, code: int = 1) -> None:
    raise KBError(message)


def normalize_document_meta(path: Path, frontmatter: Dict[str, Any], body: str) -> Dict[str, Any]:
    category, layer = infer_category_layer(path)
    title = str(frontmatter.get("title") or first_heading(body) or path.stem)
    status_default = "experimental"
    if layer == "deprecated":
        status_default = "deprecated"
    elif layer == "rejected":
        status_default = "rejected"
    source_url = str(frontmatter.get("source_url") or "")
    deprecated_reason = str(frontmatter.get("deprecated_reason") or frontmatter.get("deprecation_reason") or "")
    rejected_reason = str(frontmatter.get("rejected_reason") or frontmatter.get("rejection_reason") or "")
    quarantined_reason = str(frontmatter.get("quarantined_reason") or frontmatter.get("quarantine_reason") or "")
    source_hash = str(frontmatter.get("source_hash") or "")
    if not source_hash and source_url.strip():
        source_hash = sha256_text(source_url.strip().lower())
    content_hash = str(frontmatter.get("content_hash") or sha256_text(normalized_hash_text(body)))
    return {
        "path": to_relative_posix(path),
        "title": title,
        "category": str(frontmatter.get("category") or category),
        "layer": layer,
        "type": str(frontmatter.get("type") or ("raw" if layer == "raw" else "note")),
        "status": str(frontmatter.get("status") or status_default),
        "confidence": str(frontmatter.get("confidence") or "medium"),
        "source_type": str(frontmatter.get("source_type") or "unknown"),
        "source_url": source_url,
        "created_at": str(frontmatter.get("created_at") or ""),
        "last_reviewed": str(frontmatter.get("last_reviewed") or ""),
        "reviewed_by": str(frontmatter.get("reviewed_by") or ""),
        "reviewed_at": str(frontmatter.get("reviewed_at") or ""),
        "valid_for": metadata_string(frontmatter.get("valid_for") or []),
        "not_valid_for": metadata_string(frontmatter.get("not_valid_for") or []),
        "project_scope": str(frontmatter.get("project_scope") or ""),
        "supersedes": metadata_string(frontmatter.get("supersedes") or []),
        "superseded_by": str(frontmatter.get("superseded_by") or ""),
        "risk_level": str(frontmatter.get("risk_level") or "medium"),
        "verification_method": str(frontmatter.get("verification_method") or ""),
        "review_required": metadata_string(frontmatter.get("review_required") if "review_required" in frontmatter else layer not in FORMAL_LAYERS),
        "promoted_from": str(frontmatter.get("promoted_from") or ""),
        "topic_id": str(frontmatter.get("topic_id") or ""),
        "canonical_id": str(frontmatter.get("canonical_id") or ""),
        "source_hash": source_hash,
        "content_hash": content_hash,
        "deprecation_reason": deprecated_reason,
        "rejection_reason": rejected_reason,
        "quarantine_reason": quarantined_reason,
        "deprecated_reason": deprecated_reason,
        "rejected_reason": rejected_reason,
        "quarantined_reason": quarantined_reason,
        "review_note": str(frontmatter.get("review_note") or ""),
        "review_cycle_days": str(frontmatter.get("review_cycle_days") or ""),
    }


def connect_db(must_exist: bool = False) -> sqlite3.Connection:
    if must_exist and not DB_PATH.exists():
        die("index.sqlite does not exist. Run: python scripts/kb.py index")
    KB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def check_fts5(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.fts5_check USING fts5(content)")
        conn.execute("DROP TABLE temp.fts5_check")
    except sqlite3.Error as exc:
        die(f"SQLite FTS5 is not available: {exc}")


def ensure_schema(conn: sqlite3.Connection) -> None:
    check_fts5(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
          id INTEGER PRIMARY KEY,
          path TEXT UNIQUE NOT NULL,
          title TEXT,
          category TEXT NOT NULL,
          layer TEXT NOT NULL,
          type TEXT,
          status TEXT,
          confidence TEXT,
          source_type TEXT,
          source_url TEXT,
          created_at TEXT,
          last_reviewed TEXT,
          reviewed_by TEXT,
          reviewed_at TEXT,
          valid_for TEXT,
          not_valid_for TEXT,
          project_scope TEXT,
          supersedes TEXT,
          superseded_by TEXT,
          risk_level TEXT,
          verification_method TEXT,
          review_required TEXT,
          promoted_from TEXT,
          topic_id TEXT,
          canonical_id TEXT,
          source_hash TEXT,
          content_hash TEXT,
          deprecation_reason TEXT,
          rejection_reason TEXT,
          quarantine_reason TEXT,
          deprecated_reason TEXT,
          rejected_reason TEXT,
          quarantined_reason TEXT,
          review_note TEXT,
          review_cycle_days TEXT,
          mtime REAL NOT NULL,
          size INTEGER NOT NULL,
          sha256 TEXT NOT NULL,
          indexed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chunks (
          id INTEGER PRIMARY KEY,
          document_id INTEGER NOT NULL,
          chunk_index INTEGER NOT NULL,
          heading TEXT,
          content TEXT NOT NULL,
          token_estimate INTEGER,
          FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
          document_id UNINDEXED,
          chunk_id UNINDEXED,
          title,
          heading,
          content
        );

        CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
        CREATE INDEX IF NOT EXISTS idx_documents_layer ON documents(layer);
        CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
        CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(type);
        CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
        CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
        """
    )
    ensure_document_columns(conn)


def ensure_document_columns(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
    columns = {
        "reviewed_by": "TEXT",
        "valid_for": "TEXT",
        "not_valid_for": "TEXT",
        "project_scope": "TEXT",
        "supersedes": "TEXT",
        "risk_level": "TEXT",
        "verification_method": "TEXT",
        "review_required": "TEXT",
        "topic_id": "TEXT",
        "canonical_id": "TEXT",
        "source_hash": "TEXT",
        "content_hash": "TEXT",
        "deprecation_reason": "TEXT",
        "rejection_reason": "TEXT",
        "quarantine_reason": "TEXT",
        "deprecated_reason": "TEXT",
        "rejected_reason": "TEXT",
        "quarantined_reason": "TEXT",
        "review_note": "TEXT",
        "review_cycle_days": "TEXT",
    }
    for name, column_type in columns.items():
        if name not in existing:
            try:
                conn.execute(f"ALTER TABLE documents ADD COLUMN {name} {column_type}")
                existing.add(name)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
                existing = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_documents_topic_id ON documents(topic_id);
        CREATE INDEX IF NOT EXISTS idx_documents_canonical_id ON documents(canonical_id);
        CREATE INDEX IF NOT EXISTS idx_documents_source_hash ON documents(source_hash);
        CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
        """
    )


def delete_document_by_id(conn: sqlite3.Connection, document_id: int) -> None:
    conn.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


def index_one_file(conn: sqlite3.Connection, path: Path, stat: os.stat_result, digest: str) -> str:
    rel_path = to_relative_posix(path)
    text = read_single_markdown(path)
    frontmatter, body, _ = parse_frontmatter(text)
    meta = normalize_document_meta(path, frontmatter, body)
    chunks = chunk_markdown(body, meta["title"])
    indexed_at = now_iso()

    existing = conn.execute("SELECT id FROM documents WHERE path = ?", (rel_path,)).fetchone()
    action = "indexed"
    if existing:
        delete_document_by_id(conn, int(existing["id"]))
        action = "updated"

    cur = conn.execute(
        """
        INSERT INTO documents (
          path, title, category, layer, type, status, confidence, source_type,
          source_url, created_at, last_reviewed, reviewed_by, reviewed_at,
          valid_for, not_valid_for, project_scope, supersedes, superseded_by,
          risk_level, verification_method, review_required, promoted_from,
          topic_id, canonical_id, source_hash, content_hash,
          deprecation_reason, rejection_reason, quarantine_reason,
          deprecated_reason, rejected_reason, quarantined_reason, review_note,
          review_cycle_days, mtime, size, sha256, indexed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rel_path,
            meta["title"],
            meta["category"],
            meta["layer"],
            meta["type"],
            meta["status"],
            meta["confidence"],
            meta["source_type"],
            meta["source_url"],
            meta["created_at"],
            meta["last_reviewed"],
            meta["reviewed_by"],
            meta["reviewed_at"],
            meta["valid_for"],
            meta["not_valid_for"],
            meta["project_scope"],
            meta["supersedes"],
            meta["superseded_by"],
            meta["risk_level"],
            meta["verification_method"],
            meta["review_required"],
            meta["promoted_from"],
            meta["topic_id"],
            meta["canonical_id"],
            meta["source_hash"],
            meta["content_hash"],
            meta["deprecation_reason"],
            meta["rejection_reason"],
            meta["quarantine_reason"],
            meta["deprecated_reason"],
            meta["rejected_reason"],
            meta["quarantined_reason"],
            meta["review_note"],
            meta["review_cycle_days"],
            stat.st_mtime,
            stat.st_size,
            digest,
            indexed_at,
        ),
    )
    document_id = int(cur.lastrowid)

    for chunk in chunks:
        chunk_cur = conn.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, heading, content, token_estimate)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                document_id,
                chunk["chunk_index"],
                chunk["heading"],
                chunk["content"],
                chunk["token_estimate"],
            ),
        )
        chunk_id = int(chunk_cur.lastrowid)
        conn.execute(
            """
            INSERT INTO chunks_fts (document_id, chunk_id, title, heading, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, chunk_id, meta["title"], chunk["heading"], chunk["content"]),
        )
    return action


def iter_markdown_files() -> Iterable[Path]:
    if not KNOWLEDGE_DIR.exists():
        return []
    return (
        path
        for path in KNOWLEDGE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in SEARCHABLE_EXTENSIONS
    )


def perform_index(force_hash: bool = False) -> Dict[str, Any]:
    start = time.perf_counter()
    ensure_directories()
    conn = connect_db()
    ensure_schema(conn)

    indexed_rows = conn.execute("SELECT id, path, mtime, size, sha256 FROM documents").fetchall()
    indexed_by_path = {row["path"]: row for row in indexed_rows}
    current_paths = set()
    counts = {"indexed": 0, "updated": 0, "deleted": 0, "skipped": 0, "hashed": 0}

    with conn:
        for path in iter_markdown_files():
            rel_path = to_relative_posix(path)
            current_paths.add(rel_path)
            stat = path.stat()
            existing = indexed_by_path.get(rel_path)
            if (
                existing
                and float(existing["mtime"]) == float(stat.st_mtime)
                and int(existing["size"]) == int(stat.st_size)
                and not force_hash
            ):
                counts["skipped"] += 1
                continue
            digest = sha256_file(path)
            counts["hashed"] += 1
            action = index_one_file(conn, path, stat, digest)
            counts[action] += 1

        for rel_path, row in indexed_by_path.items():
            if rel_path not in current_paths:
                delete_document_by_id(conn, int(row["id"]))
                counts["deleted"] += 1

    counts["elapsed_ms"] = elapsed_ms(start)
    return counts


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
    start = time.perf_counter()
    KB_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in ["", "-wal", "-shm"]:
        path = Path(str(DB_PATH) + suffix)
        if path.exists():
            path.unlink()
    result = perform_index()
    result["reindexed"] = True
    result["elapsed_ms"] = elapsed_ms(start)
    print_json(result)


def build_fts_query(query: str) -> str:
    tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
    if not tokens:
        die("Query contains no searchable tokens")
    return " ".join(f'"{token}"' for token in tokens)


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


def metadata_weight(row: sqlite3.Row, query_tokens: Sequence[str]) -> float:
    layer_weight = {
        "rules": 5.0,
        "checklists": 4.5,
        "snippets": 4.0,
        "distilled": 2.0,
        "raw": 0.3,
        "deprecated": -4.0,
        "rejected": -8.0,
        "quarantine": -10.0,
    }
    status_weight = {"active": 2.0, "experimental": 0.8, "deprecated": -3.0, "rejected": -6.0}
    source_weight = {
        "official": 2.0,
        "github": 1.5,
        "paper": 1.4,
        "blog": 0.5,
        "forum": 0.1,
        "video": 0.1,
        "internal_practice": 1.2,
        "unknown": 0.0,
    }
    confidence_weight = {"high": 1.5, "medium": 0.7, "low": -0.5}

    score = 0.0
    score += layer_weight.get((row["layer"] or "").lower(), 0.0)
    score += status_weight.get((row["status"] or "").lower(), 0.0)
    score += source_weight.get((row["source_type"] or "").lower(), 0.0)
    score += confidence_weight.get((row["confidence"] or "").lower(), 0.0)

    title = (row["title"] or "").lower()
    heading = (row["heading"] or "").lower()
    content = (row["content"] or "").lower()
    for token in query_tokens:
        token_l = token.lower()
        if token_l in title:
            score += 3.0
        if token_l in heading:
            score += 1.5
        if token_l in content:
            score += 0.2

    reviewed = parse_date(str(row["last_reviewed"] or row["reviewed_at"] or ""))
    if reviewed:
        age_days = max(0, (datetime.now() - reviewed.replace(tzinfo=None)).days)
        if age_days <= 30:
            score += 1.0
        elif age_days <= 90:
            score += 0.6
        elif age_days <= 180:
            score += 0.2
    return score


def snippet_for(content: str, query_tokens: Sequence[str], max_chars: int = MAX_SNIPPET_CHARS) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    if len(normalized) <= max_chars:
        return normalized
    lower = normalized.lower()
    hit_index = -1
    for token in query_tokens:
        idx = lower.find(token.lower())
        if idx != -1 and (hit_index == -1 or idx < hit_index):
            hit_index = idx
    if hit_index == -1:
        return normalized[: max_chars - 1].rstrip() + "…"
    start = max(0, hit_index - max_chars // 3)
    end = min(len(normalized), start + max_chars)
    snippet = normalized[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(normalized):
        snippet += "…"
    return snippet


def validate_top_k(top_k: int, force: bool) -> int:
    if top_k <= 0:
        die("--top-k must be positive")
    if top_k > MAX_TOP_K and not force:
        die(f"--top-k max is {MAX_TOP_K}. Use --force to exceed it explicitly.")
    return top_k


def allowed_layers_for_search(args: argparse.Namespace, research: bool = False) -> List[str]:
    if research:
        if args.layer:
            return [args.layer]
        return sorted(EXPLORATORY_LAYERS)

    if args.layer:
        if args.layer == "raw" and not args.include_raw:
            die("search excludes raw by default. Use --include-raw explicitly, or use research.")
        if args.layer == "distilled" and not args.include_distilled:
            die("search excludes distilled by default. Use --include-distilled explicitly, or use research.")
        if args.layer == "deprecated" and not args.include_deprecated:
            die("search excludes deprecated by default. Use --include-deprecated explicitly.")
        if args.layer in {"rejected", "quarantine"}:
            die("search does not return rejected/quarantine content. Use list/open/audit for governance review.")
        return [args.layer]

    layers = set(DEFAULT_SEARCH_LAYERS)
    if args.include_distilled:
        layers.add("distilled")
    if args.include_raw:
        layers.add("raw")
    if args.include_deprecated:
        layers.add("deprecated")
    return sorted(layers)


def row_matches_filters(row: Dict[str, Any], args: argparse.Namespace, allowed_layers: Sequence[str]) -> bool:
    if args.category and row.get("category") != args.category:
        return False
    if row.get("layer") not in allowed_layers:
        return False
    if args.type and row.get("type") != args.type:
        return False
    if args.status and row.get("status") != args.status:
        return False
    if args.confidence and row.get("confidence") != args.confidence:
        return False
    if args.source_type and row.get("source_type") != args.source_type:
        return False
    if row.get("status") in {"deprecated", "rejected"} and row.get("layer") not in allowed_layers:
        return False
    return True


def run_slow_scan(args: argparse.Namespace) -> Dict[str, Any]:
    start = time.perf_counter()
    top_k = validate_top_k(args.top_k, args.force)
    query_tokens = re.findall(r"[\w]+", args.query, flags=re.UNICODE)
    if not query_tokens:
        die("Query contains no searchable tokens")

    allowed_layers = allowed_layers_for_search(args, research=bool(getattr(args, "research", False)))

    def execute() -> List[Tuple[float, Dict[str, Any]]]:
        matches: List[Tuple[float, Dict[str, Any]]] = []
        for path in iter_markdown_files():
            text = read_single_markdown(path)
            frontmatter, body, _ = parse_frontmatter(text)
            meta = normalize_document_meta(path, frontmatter, body)
            if not row_matches_filters(meta, args, allowed_layers):
                continue
            chunks = chunk_markdown(body, meta["title"])
            for chunk in chunks:
                haystack = f"{meta['title']} {chunk['heading']} {chunk['content']}".lower()
                if not all(token.lower() in haystack for token in query_tokens):
                    continue
                row = {
                    **meta,
                    "heading": chunk["heading"],
                    "content": chunk["content"],
                    "reviewed_at": meta.get("reviewed_at", ""),
                }
                score = metadata_weight(row, query_tokens)
                matches.append((score, row))
        matches.sort(key=lambda item: item[0], reverse=True)
        return matches

    ranked = execute()

    elapsed = elapsed_ms(start)
    results = []
    for score, row in ranked[:top_k]:
        results.append(
            {
                "path": row["path"],
                "title": row["title"],
                "category": row["category"],
                "layer": row["layer"],
                "type": row["type"],
                "status": row["status"],
                "confidence": row["confidence"],
                "source_type": row["source_type"],
                "score": round(score, 4),
                "heading": row["heading"],
                "snippet": snippet_for(row["content"], query_tokens),
                "elapsed_ms": elapsed,
            }
        )
    return {
        "query": args.query,
        "top_k": top_k,
        "mode": "slow_scan_explicit",
        "warning": "Explicit --slow-scan reads Markdown files and is intended only as an emergency fallback.",
        "allowed_layers": allowed_layers,
        "elapsed_ms": elapsed,
        "results": results,
    }


def run_search(args: argparse.Namespace) -> Dict[str, Any]:
    start = time.perf_counter()
    if args.slow_scan:
        return run_slow_scan(args)
    top_k = validate_top_k(args.top_k, args.force)
    conn = connect_db(must_exist=True)
    ensure_schema(conn)

    fts_query = build_fts_query(args.query)
    query_tokens = re.findall(r"[\w]+", args.query, flags=re.UNICODE)
    allowed_layers = allowed_layers_for_search(args, research=bool(getattr(args, "research", False)))

    def execute() -> List[sqlite3.Row]:
        where = ["chunks_fts MATCH ?"]
        params: List[Any] = [fts_query]

        if args.category:
            where.append("d.category = ?")
            params.append(args.category)
        where.append("d.layer IN (" + ",".join("?" for _ in allowed_layers) + ")")
        params.extend(allowed_layers)
        if args.type:
            where.append("d.type = ?")
            params.append(args.type)
        if args.status:
            where.append("d.status = ?")
            params.append(args.status)
        if args.confidence:
            where.append("d.confidence = ?")
            params.append(args.confidence)
        if args.source_type:
            where.append("d.source_type = ?")
            params.append(args.source_type)

        sql = f"""
            SELECT
              d.id AS document_id,
              d.path,
              d.title,
              d.category,
              d.layer,
              d.type,
              d.status,
              d.confidence,
              d.source_type,
              d.source_url,
              d.last_reviewed,
              d.reviewed_at,
              c.heading,
              c.content,
              bm25(chunks_fts, 8.0, 4.0, 1.0) AS bm25_score
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.chunk_id
            JOIN documents d ON d.id = chunks_fts.document_id
            WHERE {" AND ".join(where)}
            ORDER BY bm25(chunks_fts, 8.0, 4.0, 1.0)
            LIMIT ?
        """
        params.append(max(top_k * 8, 50))
        return list(conn.execute(sql, params))

    rows = execute()

    ranked = []
    for row in rows:
        bm25_score = float(row["bm25_score"] or 0.0)
        base = 1.0 / (1.0 + abs(bm25_score))
        score = base + metadata_weight(row, query_tokens)
        ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)

    elapsed = elapsed_ms(start)
    results = []
    for score, row in ranked[:top_k]:
        results.append(
            {
                "path": row["path"],
                "title": row["title"],
                "category": row["category"],
                "layer": row["layer"],
                "type": row["type"],
                "status": row["status"],
                "confidence": row["confidence"],
                "source_type": row["source_type"],
                "score": round(score, 4),
                "heading": row["heading"],
                "snippet": snippet_for(row["content"], query_tokens),
                "elapsed_ms": elapsed,
            }
        )
    return {
        "query": args.query,
        "top_k": top_k,
        "allowed_layers": allowed_layers,
        "elapsed_ms": elapsed,
        "results": results,
    }


def command_search(args: argparse.Namespace) -> None:
    print_json(run_search(args))


def command_open(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    path: Optional[Path] = None
    metadata: Dict[str, Any] = {}

    if args.id is not None:
        conn = connect_db(must_exist=True)
        row = conn.execute("SELECT id, path, title, category, layer FROM documents WHERE id = ?", (args.id,)).fetchone()
        if not row:
            die(f"No document with id={args.id}")
        path = ROOT / row["path"]
        metadata = dict(row)
    elif args.path:
        path = resolve_user_path(args.path)
        metadata = {"path": to_relative_posix(path) if path.exists() else args.path}
    else:
        die("open requires --path or --id")

    if not path.exists():
        die(f"File not found: {path}")
    content = read_single_markdown(path)
    print("--- kb-open-meta ---")
    print_json({**metadata, "elapsed_ms": elapsed_ms(start)})
    print("--- kb-open-content ---")
    print(content)


def command_list(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    where: List[str] = []
    params: List[Any] = []
    if args.category:
        where.append("category = ?")
        params.append(args.category)
    if args.layer:
        where.append("layer = ?")
        params.append(args.layer)
    sql = """
        SELECT id, path, title, category, layer, type, status, confidence, source_type,
               created_at, last_reviewed, reviewed_at, indexed_at
        FROM documents
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY category, layer, title LIMIT ?"
    params.append(args.limit)
    rows = [dict(row) for row in conn.execute(sql, params)]
    print_json({"elapsed_ms": elapsed_ms(start), "count": len(rows), "results": rows})


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


def query_documents(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT id, path, title, category, layer, type, status, confidence,
                   source_type, source_url, created_at, last_reviewed, reviewed_by,
                   reviewed_at, valid_for, not_valid_for, project_scope, supersedes,
                   superseded_by, risk_level, verification_method, review_required,
                   promoted_from, topic_id, canonical_id, source_hash, content_hash,
                   deprecation_reason, rejection_reason, quarantine_reason,
                   deprecated_reason, rejected_reason, quarantined_reason,
                   review_note, review_cycle_days, sha256, indexed_at
            FROM documents
            ORDER BY category, layer, title
            """
        )
    )


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


def priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 9)


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


def command_learning_queue(_: argparse.Namespace) -> None:
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
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"learning-queue-{today}.md"
    report_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print_json({"report": to_relative_posix(report_path), "task_count": task_count, "elapsed_ms": elapsed_ms(start)})


def command_distill_plan(args: argparse.Namespace) -> None:
    print_json(lifecycle.distill_plan(args.path))


def command_digest(_: argparse.Namespace) -> None:
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
    report_path = REPORTS_DIR / f"category-digest-{today}.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print_json({"report": to_relative_posix(report_path), "categories": rows, "elapsed_ms": elapsed_ms(start)})


def command_stats(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)

    def grouped(field: str) -> Dict[str, int]:
        return {
            str(row[field] or "unknown"): int(row["count"])
            for row in conn.execute(f"SELECT {field}, COUNT(*) AS count FROM documents GROUP BY {field}")
        }

    result = {
        "documents": int(conn.execute("SELECT COUNT(*) AS count FROM documents").fetchone()["count"]),
        "chunks": int(conn.execute("SELECT COUNT(*) AS count FROM chunks").fetchone()["count"]),
        "by_category": grouped("category"),
        "by_layer": grouped("layer"),
        "by_status": grouped("status"),
        "index_size_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
        "last_indexed_at": conn.execute("SELECT MAX(indexed_at) AS value FROM documents").fetchone()["value"],
        "elapsed_ms": elapsed_ms(start),
    }
    print_json(result)


def frontmatter_missing_warnings() -> List[Dict[str, Any]]:
    required = REQUIRED_SCHEMA_FIELDS
    warnings: List[Dict[str, Any]] = []
    for path in iter_markdown_files():
        text = read_single_markdown(path)
        frontmatter, _, has_frontmatter = parse_frontmatter(text)
        rel = to_relative_posix(path)
        if not has_frontmatter:
            warnings.append({"path": rel, "issue": "missing_frontmatter"})
            continue
        missing = [key for key in required if key not in frontmatter]
        if missing:
            warnings.append({"path": rel, "issue": "missing_frontmatter_keys", "keys": missing})
    return warnings


def command_doctor(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    checks: Dict[str, Any] = {
        "index_exists": DB_PATH.exists(),
        "fts5_available": False,
        "knowledge_file_count": 0,
        "indexed_document_count": 0,
        "missing_files": [],
        "orphan_chunks": 0,
        "stale_index": [],
        "frontmatter_warnings": [],
        "deprecated_without_superseded_by": [],
        "raw_misplaced_in_formal_layers": [],
    }

    memory_conn = sqlite3.connect(":memory:")
    try:
        check_fts5(memory_conn)
        checks["fts5_available"] = True
    except KBError:
        checks["fts5_available"] = False
    finally:
        memory_conn.close()

    files = list(iter_markdown_files())
    checks["knowledge_file_count"] = len(files)
    checks["frontmatter_warnings"] = frontmatter_missing_warnings()

    if DB_PATH.exists():
        conn = connect_db(must_exist=True)
        ensure_schema(conn)
        docs = conn.execute("SELECT id, path, mtime, size, sha256 FROM documents").fetchall()
        checks["indexed_document_count"] = len(docs)
        for row in docs:
            path = ROOT / row["path"]
            if not path.exists():
                checks["missing_files"].append(row["path"])
                continue
            stat = path.stat()
            digest = sha256_file(path)
            if (
                float(row["mtime"]) != float(stat.st_mtime)
                or int(row["size"]) != int(stat.st_size)
                or str(row["sha256"]) != digest
            ):
                checks["stale_index"].append(row["path"])
        orphan = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM chunks c
            LEFT JOIN documents d ON d.id = c.document_id
            WHERE d.id IS NULL
            """
        ).fetchone()
        checks["orphan_chunks"] = int(orphan["count"])
        deprecated = conn.execute(
            """
            SELECT path, title FROM documents
            WHERE (layer = 'deprecated' OR status = 'deprecated')
              AND COALESCE(type, '') = 'rule'
              AND COALESCE(superseded_by, '') = ''
              AND COALESCE(deprecation_reason, '') = ''
              AND COALESCE(deprecated_reason, '') = ''
            """
        ).fetchall()
        checks["deprecated_without_superseded_by"] = [dict(row) for row in deprecated]
        raw_misplaced = conn.execute(
            """
            SELECT path, title, layer, type, status FROM documents
            WHERE layer IN ('rules', 'checklists', 'snippets')
              AND (COALESCE(type, '') = 'raw' OR COALESCE(review_required, '') = 'true')
            """
        ).fetchall()
        checks["raw_misplaced_in_formal_layers"] = [dict(row) for row in raw_misplaced]

    checks["elapsed_ms"] = elapsed_ms(start)
    print_json(checks)


def command_vacuum(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    conn.execute("VACUUM")
    print_json({"status": "ok", "elapsed_ms": elapsed_ms(start)})


def command_secret_scan(args: argparse.Namespace) -> None:
    result = run_secret_scan(args.limit)
    print_json(result)
    if result["high_risk_count"]:
        raise SystemExit(1)


def benchmark_queries() -> List[str]:
    return ["react", "api", "database index", "security", "agent workflow"]


def command_benchmark(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    results = []
    for query in args.query or benchmark_queries():
        search_args = argparse.Namespace(
            query=query,
            category=None,
            layer=None,
            type=None,
            status=None,
            confidence=None,
            source_type=None,
            top_k=args.top_k,
            include_distilled=False,
            include_raw=False,
            include_deprecated=False,
            slow_scan=False,
            force=False,
            research=False,
        )
        item = run_search(search_args)
        results.append(
            {
                "query": query,
                "result_count": len(item["results"]),
                "elapsed_ms": item["elapsed_ms"],
            }
        )
    print_json({"elapsed_ms": elapsed_ms(start), "results": results})


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


def command_weekly_report(_: argparse.Namespace) -> None:
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
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{year}-{week:02d}-weekly-report.md"
    report_path.write_text(report, encoding="utf-8", newline="\n")
    print_json(
        {
            "report": to_relative_posix(report_path),
            "new_raw": len(new_raw),
            "new_distilled": len(new_distilled),
            "promoted": len(promoted),
            "pending_review": len(pending),
            "stale_or_missing_review": len(stale),
            "elapsed_ms": elapsed_ms(start),
        }
    )


def json_block(data: Any) -> str:
    return "```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```"


def command_monthly_maintenance(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    month = datetime.now().strftime("%Y-%m")
    index_result = perform_index(force_hash=args.force_hash)
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)

    lint_result = collect_lint_issues(iter_markdown_files(), args.limit)
    audit_result = collect_audit_summary(conn, rows, args.days, args.limit)
    dedupe_groups = build_dedupe_groups(rows, args.limit)
    conflicts = possible_conflicts(conn, rows, args.limit)
    stale_rows = [dict(row) for row in rows if row["status"] == "active" and is_stale_row(row, args.days)]
    secret_result = run_secret_scan(args.limit)

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

{json_block({"days": args.days, "count": len(stale_rows), "results": stale_rows[: args.limit]})}

## Secret Scan

{json_block(secret_result)}
"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"monthly-maintenance-{month}.md"
    report_path.write_text(report, encoding="utf-8", newline="\n")

    result = {
        "report": to_relative_posix(report_path),
        "summary": summary,
        "elapsed_ms": elapsed_ms(start),
    }
    print_json(result)
    if secret_result["high_risk_count"]:
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
    except sqlite3.Error as exc:
        print(f"SQLite ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
