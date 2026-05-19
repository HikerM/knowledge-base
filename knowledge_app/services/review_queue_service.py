"""Review queue metadata service for SQLite-hot read paths."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from knowledge_core import paths as core_paths

from knowledge_app.models.operation_result import OperationResult


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


class ReviewQueueService:
    """Page review candidates from SQLite documents metadata only."""

    def __init__(self, workspace_path: Path | None = None):
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else core_paths.ROOT.resolve()
        self.index_path = self.workspace_path / ".kb" / "index.sqlite"

    def list_review_queue(self, limit: int = 50, offset: int = 0, category_id: Optional[str] = None) -> OperationResult:
        start = time.perf_counter()
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        if not self.index_path.exists():
            payload = self._empty_payload(limit, offset, elapsed_ms(start), ["index.sqlite missing"])
            return OperationResult(success=True, data=payload, warnings=payload["warnings"], elapsed_ms=payload["elapsed_ms"])

        try:
            with self._connect_readonly() as conn:
                total = self._count(conn, category_id)
                rows = [self._row_to_item(row) for row in self._rows(conn, limit, offset, category_id)]
        except sqlite3.DatabaseError as exc:
            return OperationResult(success=False, errors=[f"sqlite read failed: {exc}"], elapsed_ms=elapsed_ms(start))
        except OSError as exc:
            return OperationResult(success=False, errors=[f"index metadata read failed: {exc}"], elapsed_ms=elapsed_ms(start))

        payload = {
            "count": len(rows),
            "total": total,
            "limit": limit,
            "offset": offset,
            "category_id": category_id or "",
            "results": rows,
            "warnings": [],
            "errors": [],
            "elapsed_ms": elapsed_ms(start),
        }
        return OperationResult(success=True, data=payload, elapsed_ms=payload["elapsed_ms"])

    def _connect_readonly(self) -> sqlite3.Connection:
        uri = f"{self.index_path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    @staticmethod
    def _base_where(category_id: Optional[str]) -> tuple[str, List[Any]]:
        where = [
            "layer IN ('raw', 'distilled')",
            "(LOWER(COALESCE(review_required, '')) IN ('true', '1', 'yes', 'y') OR status IN ('experimental', 'unreviewed'))",
        ]
        params: List[Any] = []
        if category_id:
            where.append("category = ?")
            params.append(category_id)
        return " AND ".join(where), params

    def _count(self, conn: sqlite3.Connection, category_id: Optional[str]) -> int:
        where, params = self._base_where(category_id)
        row = conn.execute(f"SELECT COUNT(*) AS count FROM documents WHERE {where}", params).fetchone()
        return int(row["count"] if row else 0)

    def _rows(self, conn: sqlite3.Connection, limit: int, offset: int, category_id: Optional[str]) -> List[sqlite3.Row]:
        where, params = self._base_where(category_id)
        params.extend([limit, offset])
        return list(
            conn.execute(
                f"""
                SELECT
                  id, path, title, category, layer, type, status,
                  risk_level AS risk, confidence, source_type, source_url,
                  review_required, created_at, indexed_at
                FROM documents
                WHERE {where}
                ORDER BY indexed_at DESC, category, layer, title
                LIMIT ? OFFSET ?
                """,
                params,
            )
        )

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "path": row["path"],
            "title": row["title"],
            "category": row["category"],
            "layer": row["layer"],
            "type": row["type"],
            "status": row["status"],
            "risk": row["risk"],
            "confidence": row["confidence"],
            "source_type": row["source_type"],
            "source_url": row["source_url"],
            "review_required": row["review_required"],
            "created_at": row["created_at"],
            "indexed_at": row["indexed_at"],
        }

    @staticmethod
    def _empty_payload(limit: int, offset: int, elapsed: int, warnings: List[str]) -> Dict[str, Any]:
        return {
            "count": 0,
            "total": 0,
            "limit": limit,
            "offset": offset,
            "category_id": "",
            "results": [],
            "warnings": warnings,
            "errors": [],
            "elapsed_ms": elapsed,
        }
