"""Read-only SQLite index metadata service.

This module is intentionally separate from the indexer. Startup/status callers
must not create schemas, scan Markdown, hash files, or trigger indexing.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple


class IndexMetadataService:
    """Read index statistics from an existing SQLite database only."""

    REQUIRED_TABLES = {"documents", "chunks", "chunks_fts"}

    def __init__(self, index_path: Path):
        self.index_path = Path(index_path)

    def read_metadata(self) -> Tuple[str, Dict[str, object], List[str], List[str]]:
        """Return (status, metadata, warnings, errors) without writing files."""

        if not self.index_path.exists():
            return (
                "missing",
                self._empty_metadata(),
                [],
                [],
            )

        warnings: List[str] = []
        errors: List[str] = []
        metadata = self._empty_metadata()

        try:
            metadata["index_size_bytes"] = self.index_path.stat().st_size
            with self._connect_readonly() as conn:
                existing_tables = self._table_names(conn)
                missing_tables = sorted(self.REQUIRED_TABLES - existing_tables)
                if "documents" not in existing_tables:
                    errors.append("required table missing: documents")
                    return "failed", metadata, warnings, errors
                if missing_tables:
                    warnings.append(f"required index tables missing: {', '.join(missing_tables)}")

                metadata["document_count"] = self._count(conn, "documents")
                metadata["category_counts"] = self._grouped(conn, "category")
                metadata["layer_counts"] = self._grouped(conn, "layer")
                metadata["status_counts"] = self._grouped(conn, "status")
                metadata["last_indexed_at"] = self._max_value(conn, "indexed_at")

                if "chunks" in existing_tables:
                    metadata["chunk_count"] = self._count(conn, "chunks")
                else:
                    metadata["chunk_count"] = 0

                if missing_tables:
                    return "partial", metadata, warnings, errors
                if int(metadata["document_count"]) > 0 and int(metadata["chunk_count"]) == 0:
                    warnings.append("documents table has rows but chunks table is empty")
                    return "partial", metadata, warnings, errors
                return "ready", metadata, warnings, errors
        except sqlite3.DatabaseError as exc:
            errors.append(f"sqlite read failed: {exc}")
            return "failed", metadata, warnings, errors
        except OSError as exc:
            errors.append(f"index metadata read failed: {exc}")
            return "failed", metadata, warnings, errors

    def _connect_readonly(self) -> sqlite3.Connection:
        uri = f"{self.index_path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    @staticmethod
    def _empty_metadata() -> Dict[str, object]:
        return {
            "document_count": 0,
            "chunk_count": 0,
            "category_counts": {},
            "layer_counts": {},
            "status_counts": {},
            "index_size_bytes": 0,
            "last_indexed_at": "",
        }

    @staticmethod
    def _table_names(conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type IN ('table', 'view')
            """
        ).fetchall()
        return {str(row["name"]) for row in rows}

    @staticmethod
    def _count(conn: sqlite3.Connection, table: str) -> int:
        row = conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
        return int(row["count"] if row else 0)

    @staticmethod
    def _grouped(conn: sqlite3.Connection, field: str) -> Dict[str, int]:
        rows = conn.execute(
            f"""
            SELECT {field} AS value, COUNT(*) AS count
            FROM documents
            GROUP BY {field}
            """
        ).fetchall()
        return {str(row["value"] or "unknown"): int(row["count"]) for row in rows}

    @staticmethod
    def _max_value(conn: sqlite3.Connection, field: str) -> str:
        row = conn.execute(f"SELECT MAX({field}) AS value FROM documents").fetchone()
        return str(row["value"] or "") if row else ""
