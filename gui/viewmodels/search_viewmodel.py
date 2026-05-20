"""Formal search ViewModel."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _empty_search(query: str) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "view_id": "search",
        "state": "empty",
        "data": {
            "query": query,
            "filters": {"layers": ["rules", "checklists", "snippets"], "status": ["active"]},
            "page": {"limit": 25, "offset": 0, "count": 0, "has_more": False},
            "results": [],
            "index_status": "idle",
        },
        "warnings": [],
        "errors": [],
        "source_services": [],
        "elapsed_ms": 0,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


class SearchViewModel:
    def __init__(self, adapter: Any):
        self.adapter = adapter
        self.results: Dict[str, Any] | None = None

    def search(self, query: str, limit: int = 25, offset: int = 0, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not query.strip():
            self.results = _empty_search(query)
            return self.results
        self.results = self.adapter.search(query=query, limit=limit, offset=offset, filters=filters)
        return self.results

    def open_result(self, document_id: int | str | None = None, path: str | None = None) -> Dict[str, Any]:
        return self.adapter.open_document(document_id=document_id, path=path)
