"""SQLite indexer core for the Markdown knowledge base."""

from __future__ import annotations

import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence

from . import paths as core_paths
from .config import load_categories
from .frontmatter import metadata_string, parse_frontmatter
from .markdown import (
    SEARCHABLE_EXTENSIONS,
    chunk_markdown,
    first_heading,
    markdown_text_from_bytes,
    normalized_hash_text,
    read_single_markdown,
    sha256_bytes,
    sha256_text,
)
from .paths import FORMAL_LAYERS, infer_category_layer, to_relative_posix


class IndexerError(Exception):
    """Controlled indexer error."""


DEFAULT_INDEX_BATCH_SIZE = 1000
DEFAULT_INDEX_READ_BATCH_SIZE = 100
DEFAULT_INDEX_READ_WORKERS = min(8, max(1, os.cpu_count() or 1))


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


class IndexProfile:
    """Optional, low-overhead index timing collector.

    The CLI does not enable this by default, keeping existing JSON output stable.
    Tests and diagnostics can pass an instance to perform_index().
    """

    STAGES = [
        "file_discovery",
        "metadata_frontmatter_parse",
        "sha256_hash",
        "markdown_read",
        "chunking",
        "document_write",
        "chunk_insert",
        "fts_insert",
        "commit",
        "schema",
        "load_existing_index",
        "file_stat",
        "path_normalize",
        "stale_cleanup",
    ]

    def __init__(self) -> None:
        self.timings: Dict[str, float] = {stage: 0.0 for stage in self.STAGES}
        self.counts: Dict[str, int] = {}

    @contextmanager
    def time(self, stage: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.timings[stage] = self.timings.get(stage, 0.0) + (time.perf_counter() - start)

    def add_count(self, name: str, value: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + value

    def add_time(self, stage: str, seconds: float) -> None:
        self.timings[stage] = self.timings.get(stage, 0.0) + seconds

    def to_dict(self, total_index_ms: Optional[int] = None) -> Dict[str, Any]:
        result = {f"{stage}_ms": int(round(self.timings.get(stage, 0.0) * 1000)) for stage in self.STAGES}
        if total_index_ms is not None:
            result["total_index_ms"] = total_index_ms
        if self.counts:
            result["counts"] = dict(sorted(self.counts.items()))
        return result


@contextmanager
def profile_time(profile: Optional[IndexProfile], stage: str) -> Iterator[None]:
    if profile is None:
        yield
    else:
        with profile.time(stage):
            yield


def infer_category_layer_from_relative(
    rel_path: str,
    categories: Mapping[str, Mapping[str, str]],
) -> tuple[str, str]:
    parts = rel_path.split("/")
    if len(parts) < 4 or parts[0] != "knowledge":
        return "unknown", "unknown"

    category_dir = "/".join(parts[:2])
    layer = parts[2]
    for category, meta in categories.items():
        if Path(meta["path"]).as_posix() == category_dir:
            return category, layer
    return "unknown", layer


def normalize_document_meta(
    path: Path,
    frontmatter: Dict[str, Any],
    body: str,
    categories: Optional[Mapping[str, Mapping[str, str]]] = None,
    profile: Optional[IndexProfile] = None,
    rel_path: Optional[str] = None,
) -> Dict[str, Any]:
    with profile_time(profile, "metadata_frontmatter_parse"):
        if rel_path is not None and categories is not None:
            category, layer = infer_category_layer_from_relative(rel_path, categories)
        else:
            category, layer = infer_category_layer(path, categories)
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
        with profile_time(profile, "sha256_hash"):
            source_hash = sha256_text(source_url.strip().lower())
    content_hash = str(frontmatter.get("content_hash") or "")
    if not content_hash:
        with profile_time(profile, "sha256_hash"):
            content_hash = sha256_text(normalized_hash_text(body))
    if rel_path is None:
        with profile_time(profile, "path_normalize"):
            rel_path = to_relative_posix(path)
    with profile_time(profile, "metadata_frontmatter_parse"):
        return {
            "path": rel_path,
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
            "review_required": metadata_string(
                frontmatter.get("review_required") if "review_required" in frontmatter else layer not in FORMAL_LAYERS
            ),
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
    if must_exist and not core_paths.DB_PATH.exists():
        raise IndexerError("index.sqlite does not exist. Run: python scripts/kb.py index")
    core_paths.KB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(core_paths.DB_PATH)
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
        raise IndexerError(f"SQLite FTS5 is not available: {exc}") from exc


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


def read_markdown_for_index(path: Path, profile: Optional[IndexProfile] = None) -> tuple[str, str]:
    with profile_time(profile, "markdown_read"):
        raw = path.read_bytes()
        text = markdown_text_from_bytes(raw)
    with profile_time(profile, "sha256_hash"):
        digest = sha256_bytes(raw)
    return text, digest


def read_markdown_for_index_unprofiled(path: Path) -> tuple[str, str, float]:
    raw = path.read_bytes()
    text = markdown_text_from_bytes(raw)
    hash_start = time.perf_counter()
    digest = sha256_bytes(raw)
    hash_elapsed = time.perf_counter() - hash_start
    return text, digest, hash_elapsed


def index_one_file(
    conn: sqlite3.Connection,
    path: Path,
    stat: os.stat_result,
    digest: str,
    text: Optional[str] = None,
    categories: Optional[Mapping[str, Mapping[str, str]]] = None,
    profile: Optional[IndexProfile] = None,
    rel_path: Optional[str] = None,
) -> str:
    if rel_path is None:
        with profile_time(profile, "path_normalize"):
            rel_path = to_relative_posix(path)
    if text is None:
        with profile_time(profile, "markdown_read"):
            text = read_single_markdown(path)
    with profile_time(profile, "metadata_frontmatter_parse"):
        frontmatter, body, _ = parse_frontmatter(text)
    meta = normalize_document_meta(path, frontmatter, body, categories=categories, profile=profile, rel_path=rel_path)
    with profile_time(profile, "chunking"):
        chunks = chunk_markdown(body, meta["title"])
    indexed_at = now_iso()

    with profile_time(profile, "document_write"):
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

    fts_rows = []
    for chunk in chunks:
        with profile_time(profile, "chunk_insert"):
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
        fts_rows.append((document_id, chunk_id, meta["title"], chunk["heading"], chunk["content"]))
    if fts_rows:
        with profile_time(profile, "fts_insert"):
            conn.executemany(
                """
                INSERT INTO chunks_fts (document_id, chunk_id, title, heading, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                fts_rows,
            )
    return action


def commit_if_needed(conn: sqlite3.Connection, profile: Optional[IndexProfile] = None) -> None:
    if not conn.in_transaction:
        return
    with profile_time(profile, "commit"):
        conn.commit()


def rollback_if_needed(conn: sqlite3.Connection) -> None:
    if conn.in_transaction:
        conn.rollback()


ChangedFile = tuple[Path, str, os.stat_result]


def iter_read_index_sources(
    items: Sequence[ChangedFile],
    profile: Optional[IndexProfile],
    executor: Optional[ThreadPoolExecutor],
) -> Iterable[tuple[Path, str, os.stat_result, str, str]]:
    if not items:
        return []
    if executor is None or len(items) <= 1:
        return (
            (
                path,
                rel_path,
                stat,
                *read_markdown_for_index(path, profile),
            )
            for path, rel_path, stat in items
        )

    paths = [item[0] for item in items]
    start = time.perf_counter()
    results = list(executor.map(read_markdown_for_index_unprofiled, paths))
    if profile is not None:
        profile.add_time("markdown_read", time.perf_counter() - start)
        for _, _, hash_elapsed in results:
            profile.add_time("sha256_hash", hash_elapsed)
    return (
        (path, rel_path, stat, text, digest)
        for (path, rel_path, stat), (text, digest, _) in zip(items, results)
    )


def iter_markdown_files() -> Iterable[Path]:
    if not core_paths.KNOWLEDGE_DIR.exists():
        return []
    return (
        path
        for path in core_paths.KNOWLEDGE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in SEARCHABLE_EXTENSIONS
    )


def cleanup_stale_documents(
    conn: sqlite3.Connection,
    indexed_by_path: Dict[str, sqlite3.Row],
    current_paths: Sequence[str] | set[str],
) -> int:
    deleted = 0
    for rel_path, row in indexed_by_path.items():
        if rel_path not in current_paths:
            delete_document_by_id(conn, int(row["id"]))
            deleted += 1
    return deleted


def perform_index(
    force_hash: bool = False,
    profile: Optional[IndexProfile] = None,
    batch_size: int = DEFAULT_INDEX_BATCH_SIZE,
    read_batch_size: int = DEFAULT_INDEX_READ_BATCH_SIZE,
    read_workers: int = DEFAULT_INDEX_READ_WORKERS,
) -> Dict[str, Any]:
    start = time.perf_counter()
    batch_size = max(1, batch_size)
    read_batch_size = max(1, read_batch_size)
    read_workers = max(1, read_workers)
    core_paths.ensure_directories()
    conn = connect_db()
    with profile_time(profile, "schema"):
        ensure_schema(conn)

    with profile_time(profile, "load_existing_index"):
        indexed_rows = conn.execute("SELECT id, path, mtime, size, sha256 FROM documents").fetchall()
    indexed_by_path = {row["path"]: row for row in indexed_rows}
    current_paths: set[str] = set()
    counts = {"indexed": 0, "updated": 0, "deleted": 0, "skipped": 0, "hashed": 0}
    categories = load_categories()
    processed_in_batch = 0
    files: Iterable[Path]
    if profile is not None:
        with profile_time(profile, "file_discovery"):
            discovered_files = list(iter_markdown_files())
        profile.add_count("discovered_files", len(discovered_files))
        files = discovered_files
    else:
        files = iter_markdown_files()

    changed_batch: List[ChangedFile] = []

    def flush_changed_batch(executor: Optional[ThreadPoolExecutor]) -> None:
        nonlocal changed_batch
        if not changed_batch:
            return
        for path, rel_path, stat, text, digest in iter_read_index_sources(changed_batch, profile, executor):
            action = index_one_file(
                conn,
                path,
                stat,
                digest,
                text=text,
                categories=categories,
                profile=profile,
                rel_path=rel_path,
            )
            counts[action] += 1
        changed_batch = []

    try:
        executor: Optional[ThreadPoolExecutor] = None
        if read_workers > 1:
            executor = ThreadPoolExecutor(max_workers=read_workers)
        try:
            for path in files:
                with profile_time(profile, "path_normalize"):
                    rel_path = to_relative_posix(path)
                current_paths.add(rel_path)
                with profile_time(profile, "file_stat"):
                    stat = path.stat()
                existing = indexed_by_path.get(rel_path)
                if (
                    existing
                    and float(existing["mtime"]) == float(stat.st_mtime)
                    and int(existing["size"]) == int(stat.st_size)
                    and not force_hash
                ):
                    counts["skipped"] += 1
                    processed_in_batch += 1
                    if processed_in_batch >= batch_size:
                        flush_changed_batch(executor)
                        commit_if_needed(conn, profile)
                        processed_in_batch = 0
                    continue
                changed_batch.append((path, rel_path, stat))
                counts["hashed"] += 1
                processed_in_batch += 1
                if len(changed_batch) >= read_batch_size:
                    flush_changed_batch(executor)
                if processed_in_batch >= batch_size:
                    flush_changed_batch(executor)
                    commit_if_needed(conn, profile)
                    processed_in_batch = 0
            flush_changed_batch(executor)
        finally:
            if executor is not None:
                executor.shutdown(wait=True)

        with profile_time(profile, "stale_cleanup"):
            counts["deleted"] += cleanup_stale_documents(conn, indexed_by_path, current_paths)
        commit_if_needed(conn, profile)
    except Exception:
        rollback_if_needed(conn)
        raise

    counts["elapsed_ms"] = elapsed_ms(start)
    if profile is not None:
        counts["profile"] = profile.to_dict(total_index_ms=counts["elapsed_ms"])
    return counts


def perform_reindex() -> Dict[str, Any]:
    start = time.perf_counter()
    core_paths.KB_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in ["", "-wal", "-shm"]:
        path = Path(str(core_paths.DB_PATH) + suffix)
        if path.exists():
            path.unlink()
    result = perform_index()
    result["reindexed"] = True
    result["elapsed_ms"] = elapsed_ms(start)
    return result


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


def list_documents(
    conn: sqlite3.Connection,
    category: Optional[str] = None,
    layer: Optional[str] = None,
    limit: int = 100,
) -> List[sqlite3.Row]:
    where: List[str] = []
    params: List[Any] = []
    if category:
        where.append("category = ?")
        params.append(category)
    if layer:
        where.append("layer = ?")
        params.append(layer)
    sql = """
        SELECT id, path, title, category, layer, type, status, confidence, source_type,
               created_at, last_reviewed, reviewed_at, indexed_at
        FROM documents
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY category, layer, title LIMIT ?"
    params.append(limit)
    return list(conn.execute(sql, params))


def stats() -> Dict[str, Any]:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)

    def grouped(field: str) -> Dict[str, int]:
        return {
            str(row[field] or "unknown"): int(row["count"])
            for row in conn.execute(f"SELECT {field}, COUNT(*) AS count FROM documents GROUP BY {field}")
        }

    return {
        "documents": int(conn.execute("SELECT COUNT(*) AS count FROM documents").fetchone()["count"]),
        "chunks": int(conn.execute("SELECT COUNT(*) AS count FROM chunks").fetchone()["count"]),
        "by_category": grouped("category"),
        "by_layer": grouped("layer"),
        "by_status": grouped("status"),
        "index_size_bytes": core_paths.DB_PATH.stat().st_size if core_paths.DB_PATH.exists() else 0,
        "last_indexed_at": conn.execute("SELECT MAX(indexed_at) AS value FROM documents").fetchone()["value"],
        "elapsed_ms": elapsed_ms(start),
    }


def vacuum() -> Dict[str, Any]:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    conn.execute("VACUUM")
    return {"status": "ok", "elapsed_ms": elapsed_ms(start)}
