"""Category metadata service backed by config and SQLite documents metadata."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from knowledge_core import paths as core_paths
from knowledge_core.config import load_categories
from knowledge_core.paths import LAYERS

from knowledge_app.models.operation_result import OperationResult


REPORTED_LAYERS = ["raw", "distilled", "rules", "checklists", "snippets", "deprecated"]
FORMAL_LAYERS = ["rules", "checklists", "snippets"]


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


class CategoryService:
    """Read category summaries without scanning knowledge/ or reading Markdown."""

    def __init__(self, workspace_path: Path | None = None):
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else core_paths.ROOT.resolve()
        self.index_path = self.workspace_path / ".kb" / "index.sqlite"

    def list_categories(self) -> OperationResult:
        start = time.perf_counter()
        categories = load_categories()
        warnings: List[str] = []
        errors: List[str] = []
        counts_by_category: Dict[str, Dict[str, Any]] = {}

        if self.index_path.exists():
            try:
                with self._connect_readonly() as conn:
                    counts_by_category = self._read_counts(conn)
            except sqlite3.DatabaseError as exc:
                errors.append(f"sqlite read failed: {exc}")
            except OSError as exc:
                errors.append(f"index metadata read failed: {exc}")
        else:
            warnings.append("index.sqlite missing; category counts default to zero")

        results = []
        for category_id, meta in sorted(categories.items()):
            layer_counts = self._zero_layer_counts()
            status_counts: Dict[str, int] = {}
            document_count = 0
            review_required_count = 0
            if category_id in counts_by_category:
                bucket = counts_by_category[category_id]
                layer_counts.update(bucket["layer_counts"])
                status_counts = dict(bucket["status_counts"])
                document_count = int(bucket["document_count"])
                review_required_count = int(bucket["review_required_count"])
            results.append(
                {
                    "category_id": category_id,
                    "display_name": str(meta.get("display_name") or category_id),
                    "path": str(meta.get("path") or ""),
                    "description": str(meta.get("description") or ""),
                    "document_count": document_count,
                    "layer_counts": layer_counts,
                    "status_counts": status_counts,
                    "review_required_count": review_required_count,
                }
            )

        payload = {
            "count": len(results),
            "results": results,
            "elapsed_ms": elapsed_ms(start),
            "warnings": warnings,
            "errors": errors,
        }
        return OperationResult(success=not errors, data=payload, warnings=warnings, errors=errors, elapsed_ms=payload["elapsed_ms"])

    def get_category_summary(self, category_id: str) -> OperationResult:
        start = time.perf_counter()
        listed = self.list_categories()
        if not listed.data:
            return listed
        for item in listed.data["results"]:
            if item["category_id"] == category_id:
                payload = dict(item)
                payload["elapsed_ms"] = elapsed_ms(start)
                return OperationResult(success=True, data=payload, warnings=listed.warnings, elapsed_ms=payload["elapsed_ms"])
        return OperationResult(success=False, errors=[f"unknown category_id: {category_id}"], elapsed_ms=elapsed_ms(start))

    def get_category_counts(self) -> OperationResult:
        listed = self.list_categories()
        if not listed.data:
            return listed
        payload = {
            "category_counts": {item["category_id"]: item["document_count"] for item in listed.data["results"]},
            "layer_counts": {item["category_id"]: item["layer_counts"] for item in listed.data["results"]},
            "elapsed_ms": listed.data["elapsed_ms"],
            "warnings": listed.data["warnings"],
            "errors": listed.data["errors"],
        }
        return OperationResult(success=listed.success, data=payload, warnings=listed.warnings, errors=listed.errors, elapsed_ms=listed.elapsed_ms)

    def list_formal_documents(
        self,
        category_id: Optional[str] = None,
        layer: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> OperationResult:
        """Page formal document metadata without reading Markdown bodies."""

        start = time.perf_counter()
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        if layer and layer not in FORMAL_LAYERS:
            return OperationResult(
                success=True,
                data=self._empty_documents_payload(limit, offset, elapsed_ms(start), [f"unsupported formal layer filter: {layer}"]),
                warnings=[f"unsupported formal layer filter: {layer}"],
                elapsed_ms=elapsed_ms(start),
            )
        if not self.index_path.exists():
            payload = self._empty_documents_payload(limit, offset, elapsed_ms(start), ["index.sqlite missing"])
            return OperationResult(success=True, data=payload, warnings=payload["warnings"], elapsed_ms=payload["elapsed_ms"])

        try:
            with self._connect_readonly() as conn:
                total = self._formal_document_count(conn, category_id, layer)
                rows = [self._formal_document_row(item) for item in self._formal_document_rows(conn, category_id, layer, limit, offset)]
        except sqlite3.DatabaseError as exc:
            return OperationResult(success=False, errors=[f"sqlite read failed: {exc}"], elapsed_ms=elapsed_ms(start))
        except OSError as exc:
            return OperationResult(success=False, errors=[f"index metadata read failed: {exc}"], elapsed_ms=elapsed_ms(start))

        payload = {
            "count": len(rows),
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(rows) < total,
            "category_id": category_id or "",
            "layer": layer or "",
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
    def _zero_layer_counts() -> Dict[str, int]:
        counts = {layer: 0 for layer in LAYERS}
        for layer in REPORTED_LAYERS:
            counts.setdefault(layer, 0)
        return counts

    def _read_counts(self, conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
        counts: Dict[str, Dict[str, Any]] = {}

        for row in conn.execute(
            """
            SELECT category, COUNT(*) AS count
            FROM documents
            GROUP BY category
            """
        ):
            category_id = str(row["category"] or "unknown")
            counts.setdefault(category_id, self._empty_bucket())
            counts[category_id]["document_count"] = int(row["count"])

        for row in conn.execute(
            """
            SELECT category, layer, COUNT(*) AS count
            FROM documents
            GROUP BY category, layer
            """
        ):
            category_id = str(row["category"] or "unknown")
            layer = str(row["layer"] or "unknown")
            counts.setdefault(category_id, self._empty_bucket())
            counts[category_id]["layer_counts"][layer] = int(row["count"])

        for row in conn.execute(
            """
            SELECT category, status, COUNT(*) AS count
            FROM documents
            GROUP BY category, status
            """
        ):
            category_id = str(row["category"] or "unknown")
            status = str(row["status"] or "unknown")
            counts.setdefault(category_id, self._empty_bucket())
            counts[category_id]["status_counts"][status] = int(row["count"])

        for row in conn.execute(
            """
            SELECT category, COUNT(*) AS count
            FROM documents
            WHERE LOWER(COALESCE(review_required, '')) IN ('true', '1', 'yes', 'y')
            GROUP BY category
            """
        ):
            category_id = str(row["category"] or "unknown")
            counts.setdefault(category_id, self._empty_bucket())
            counts[category_id]["review_required_count"] = int(row["count"])

        return counts

    def _formal_document_count(self, conn: sqlite3.Connection, category_id: Optional[str], layer: Optional[str]) -> int:
        where, params = self._formal_document_where(category_id, layer)
        row = conn.execute(f"SELECT COUNT(*) AS count FROM documents WHERE {where}", params).fetchone()
        return int(row["count"] if row else 0)

    def _formal_document_rows(
        self,
        conn: sqlite3.Connection,
        category_id: Optional[str],
        layer: Optional[str],
        limit: int,
        offset: int,
    ) -> List[sqlite3.Row]:
        where, params = self._formal_document_where(category_id, layer)
        params.extend([limit, offset])
        return list(
            conn.execute(
                f"""
                SELECT
                  id AS document_id, path, title, category AS category_id,
                  layer, status, confidence, source_type, review_required,
                  last_reviewed, indexed_at
                FROM documents
                WHERE {where}
                ORDER BY category, layer, title
                LIMIT ? OFFSET ?
                """,
                params,
            )
        )

    @staticmethod
    def _formal_document_where(category_id: Optional[str], layer: Optional[str]) -> tuple[str, List[Any]]:
        where = ["layer IN ('rules', 'checklists', 'snippets')"]
        params: List[Any] = []
        if category_id:
            where.append("category = ?")
            params.append(category_id)
        if layer:
            where.append("layer = ?")
            params.append(layer)
        return " AND ".join(where), params

    @staticmethod
    def _formal_document_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "document_id": row["document_id"],
            "path": row["path"],
            "title": row["title"],
            "category_id": row["category_id"],
            "layer": row["layer"],
            "status": row["status"],
            "confidence": row["confidence"],
            "source_type": row["source_type"],
            "review_required": row["review_required"],
            "snippet": "",
            "last_reviewed": row["last_reviewed"],
            "indexed_at": row["indexed_at"],
        }

    @staticmethod
    def _empty_documents_payload(limit: int, offset: int, elapsed: int, warnings: List[str]) -> Dict[str, Any]:
        return {
            "count": 0,
            "total": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False,
            "category_id": "",
            "layer": "",
            "results": [],
            "warnings": warnings,
            "errors": [],
            "elapsed_ms": elapsed,
        }

    def _empty_bucket(self) -> Dict[str, Any]:
        return {
            "document_count": 0,
            "layer_counts": self._zero_layer_counts(),
            "status_counts": {},
            "review_required_count": 0,
        }
