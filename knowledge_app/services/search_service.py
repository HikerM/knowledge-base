"""Search service for SQLite-hot GUI/CLI read paths."""

from __future__ import annotations

import argparse
from typing import Any, Dict, Optional

from knowledge_core.search import DEFAULT_TOP_K, SearchError, run_search

from knowledge_app.models.operation_result import OperationResult
from knowledge_app.models.search_result import SearchResult


class SearchService:
    """Thin service wrapper around the existing SQLite FTS search behavior."""

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = DEFAULT_TOP_K,
        include_options: Optional[Dict[str, Any]] = None,
        explain_score: bool = False,
    ) -> OperationResult:
        filters = dict(filters or {})
        include_options = dict(include_options or {})
        args = argparse.Namespace(
            query=query,
            category=filters.get("category") or filters.get("category_id"),
            layer=filters.get("layer"),
            type=filters.get("type"),
            status=filters.get("status"),
            confidence=filters.get("confidence"),
            source_type=filters.get("source_type"),
            top_k=top_k,
            include_distilled=bool(include_options.get("include_distilled", False)),
            include_raw=bool(include_options.get("include_raw", False)),
            include_deprecated=bool(include_options.get("include_deprecated", False)),
            slow_scan=False,
            force=bool(include_options.get("force", False)),
            explain_score=explain_score,
            research=bool(include_options.get("research", False)),
        )
        try:
            payload = run_search(args, read_only=True)
            result = SearchResult.from_payload(payload)
            return OperationResult(success=True, data=result, elapsed_ms=result.elapsed_ms)
        except SearchError as exc:
            return OperationResult(success=False, errors=[str(exc)])
        except Exception as exc:
            return OperationResult(success=False, errors=[f"search service failed: {exc}"])
