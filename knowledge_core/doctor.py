"""Doctor command core."""

from __future__ import annotations

import sqlite3
import time
from typing import Any, Dict, List

from . import paths as core_paths
from .frontmatter import REQUIRED_SCHEMA_FIELDS, parse_frontmatter
from .indexer import IndexerError, check_fts5, connect_db, ensure_schema, iter_markdown_files
from .markdown import read_single_markdown, sha256_file
from .paths import to_relative_posix


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


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


def run_doctor() -> Dict[str, Any]:
    start = time.perf_counter()
    checks: Dict[str, Any] = {
        "index_exists": core_paths.DB_PATH.exists(),
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
    except IndexerError:
        checks["fts5_available"] = False
    finally:
        memory_conn.close()

    files = list(iter_markdown_files())
    checks["knowledge_file_count"] = len(files)
    checks["frontmatter_warnings"] = frontmatter_missing_warnings()

    if core_paths.DB_PATH.exists():
        conn = connect_db(must_exist=True)
        ensure_schema(conn)
        docs = conn.execute("SELECT id, path, mtime, size, sha256 FROM documents").fetchall()
        checks["indexed_document_count"] = len(docs)
        for row in docs:
            path = core_paths.ROOT / row["path"]
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
    return checks
