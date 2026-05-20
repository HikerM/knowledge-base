"""Read-only GUI-to-service adapter for Phase 1 PySide6 screens."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from knowledge_app.services.category_service import CategoryService
from knowledge_app.services.document_service import DocumentService
from knowledge_app.services.search_service import SearchService
from knowledge_app.services.task_queue_service import TaskQueueService
from knowledge_app.services.workspace_status_service import WorkspaceStatusService

FORMAL_LAYERS = ["rules", "checklists", "snippets"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _env(
    view_id: str,
    state: str,
    data: Optional[Dict[str, Any]],
    services: Iterable[str],
    warnings: Optional[list[Dict[str, Any]]] = None,
    errors: Optional[list[Dict[str, Any]]] = None,
    elapsed_ms: int = 0,
) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "view_id": view_id,
        "state": state,
        "data": data,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
        "source_services": list(services),
        "elapsed_ms": int(elapsed_ms or 0),
        "generated_at": _now(),
    }


def _error(service: str, message: str, code: str = "service_error") -> Dict[str, Any]:
    return {"code": code, "message": message, "service": service, "recoverable": True}


def _warning(service: str, message: str) -> Dict[str, Any]:
    return {"code": "service_warning", "message": message, "service": service}


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    return dict(value.to_dict() if hasattr(value, "to_dict") else value)


class ServiceAdapter:
    """Thin adapter over read-only service-layer calls used by the GUI."""

    def __init__(self, workspace_path: Path | str | None = None):
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else None

    def load_workspace_status(self) -> Dict[str, Any]:
        service = "WorkspaceStatusService"
        try:
            result = WorkspaceStatusService(self.workspace_path).get_status()
        except Exception as exc:  # noqa: BLE001
            return _env("workspace_status", "error", None, [service], errors=[_error(service, str(exc))])
        if not result.success or result.data is None:
            return _env("workspace_status", "error", None, [service], errors=[_error(service, item) for item in result.errors], elapsed_ms=result.elapsed_ms)
        data = {
            **_as_dict(result.data),
            "startup_guards": {
                "markdown_scan_performed": False,
                "markdown_body_read": False,
                "hash_performed": False,
                "auto_index_started": False,
            },
        }
        return _env("workspace_status", "ready", data, [service], warnings=[_warning(service, item) for item in result.warnings], elapsed_ms=result.elapsed_ms)

    def search(self, query: str, limit: int = 25, offset: int = 0, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query = query.strip()
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        if not query:
            return _env("search", "empty", self._empty_search(query, limit, offset), ["SearchService"])
        try:
            result = SearchService().search(query, filters=self._formal_filters(filters), top_k=min(limit + offset, 50))
        except Exception as exc:  # noqa: BLE001
            return _env("search", "error", self._empty_search(query, limit, offset), ["SearchService"], errors=[_error("SearchService", str(exc))])
        if not result.success or result.data is None:
            return _env(
                "search",
                "error",
                self._empty_search(query, limit, offset),
                ["SearchService"],
                errors=[_error("SearchService", item) for item in result.errors],
                elapsed_ms=result.elapsed_ms,
            )
        rows = [self._search_row(item) for item in _as_dict(result.data).get("results", [])]
        page_rows = rows[offset : offset + limit]
        data = {
            "query": query,
            "filters": {"layers": FORMAL_LAYERS, "status": ["active"]},
            "page": {"limit": limit, "offset": offset, "count": len(page_rows), "has_more": len(rows) > offset + limit},
            "results": page_rows,
            "index_status": "service_backed",
        }
        return _env("search", "ready" if page_rows else "empty", data, ["SearchService"], elapsed_ms=result.elapsed_ms)

    def load_library_summary(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        try:
            result = CategoryService(self.workspace_path).list_categories()
        except Exception as exc:  # noqa: BLE001
            return _env("library", "error", None, ["CategoryService"], errors=[_error("CategoryService", str(exc))])
        if not result.success or not result.data:
            return _env("library", "error", None, ["CategoryService"], errors=[_error("CategoryService", item) for item in result.errors])
        rows = [self._category_row(item) for item in result.data.get("results", [])]
        page_rows = rows[offset : offset + limit]
        data = {
            "categories": page_rows,
            "formal_layer_totals": self._formal_totals(rows),
            "active_category_id": None,
            "active_view": "all_formal",
            "documents": [],
            "page": {"limit": limit, "offset": offset, "count": len(page_rows), "total": len(rows), "has_more": len(rows) > offset + limit},
        }
        return _env("library", "ready" if page_rows else "empty", data, ["CategoryService"], elapsed_ms=result.elapsed_ms)

    def open_document(self, document_id: int | str | None = None, path: str | None = None) -> Dict[str, Any]:
        service = "DocumentService"
        try:
            numeric_id = int(document_id) if document_id not in (None, "") and str(document_id).isdigit() else None
            result = DocumentService(self.workspace_path).open_document(document_id=numeric_id, path=path)
        except Exception as exc:  # noqa: BLE001
            return _env("document_preview", "error", None, [service], errors=[_error(service, str(exc))])
        if not result.success or not result.data:
            return _env("document_preview", "error", None, [service], errors=[_error(service, item) for item in result.errors], elapsed_ms=result.elapsed_ms)
        return _env("document_preview", "ready", self._document_payload(result.data), [service], elapsed_ms=result.elapsed_ms)

    def load_recent_tasks(self, limit: int = 25, offset: int = 0) -> Dict[str, Any]:
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        try:
            records = TaskQueueService(self.workspace_path).list_tasks(limit=limit, offset=offset)
        except Exception as exc:  # noqa: BLE001
            return _env("task_summary", "error", None, ["TaskQueueService"], errors=[_error("TaskQueueService", str(exc))])
        rows = [self._task_row(record) for record in records]
        controls = {"create_task_available": False, "run_task_available": False, "cancel_task_available": False, "retry_task_available": False, "cleanup_execute_available": False}
        data = {"tasks": rows, "page": {"limit": limit, "offset": offset, "count": len(rows), "has_more": len(rows) == limit}, "phase_1_controls": controls}
        return _env("task_summary", "ready" if rows else "empty", data, ["TaskQueueService"])

    def load_task_detail(self, task_id: str, tail: int = 80) -> Dict[str, Any]:
        service = TaskQueueService(self.workspace_path)
        try:
            record = service.get_task(task_id)
            progress = [item.to_dict() for item in service.get_task_progress(task_id, limit=100, offset=0)]
            logs = service.get_task_log(task_id, tail=tail)
        except Exception as exc:  # noqa: BLE001
            return _env("task_detail", "error", None, ["TaskQueueService"], errors=[_error("TaskQueueService", str(exc))])
        return _env("task_detail", "ready", {"task": self._task_row(record), "progress_events": progress, "log_entries": logs}, ["TaskQueueService"])

    def capabilities(self) -> Dict[str, bool]:
        names = ["mutation_ui", "category_execute", "archive_execute", "delete_execute", "merge_execute", "template_apply_execute", "restore_execute", "rss", "vector_search"]
        return {name: False for name in names}

    @staticmethod
    def _formal_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        filters = dict(filters or {})
        layer = filters.get("layer")
        filters["status"] = filters.get("status") or "active"
        if layer not in FORMAL_LAYERS:
            filters.pop("layer", None)
        return filters

    @staticmethod
    def _empty_search(query: str, limit: int, offset: int) -> Dict[str, Any]:
        return {
            "query": query,
            "filters": {"layers": FORMAL_LAYERS, "status": ["active"]},
            "page": {"limit": limit, "offset": offset, "count": 0, "has_more": False},
            "results": [],
            "index_status": "unknown",
        }

    @staticmethod
    def _search_row(item: Dict[str, Any]) -> Dict[str, Any]:
        path = str(item.get("path") or "")
        document_id = str(item.get("document_id") or item.get("id") or path)
        return {
            "document_id": document_id,
            "path": path,
            "title": str(item.get("title") or path or "Untitled"),
            "category_id": str(item.get("category_id") or item.get("category") or ""),
            "layer": str(item.get("layer") or ""),
            "status": str(item.get("status") or ""),
            "confidence": str(item.get("confidence") or ""),
            "source_type": str(item.get("source_type") or ""),
            "review_required": bool(item.get("review_required", False)),
            "snippet": str(item.get("snippet") or ""),
            "updated_at": str(item.get("updated_at") or item.get("indexed_at") or "") or None,
            "open_document_action": {"action_id": "open_document", "label": "Open", "kind": "open_document", "target": path, "execute": False, "enabled": bool(path)},
        }

    @staticmethod
    def _category_row(item: Dict[str, Any]) -> Dict[str, Any]:
        layer_counts = dict(item.get("layer_counts") or {})
        formal_counts = {layer: int(layer_counts.get(layer) or 0) for layer in FORMAL_LAYERS}
        return {
            "category_id": str(item.get("category_id") or ""),
            "display_name": str(item.get("display_name") or item.get("category_id") or ""),
            "path": str(item.get("path") or ""),
            "description": str(item.get("description") or ""),
            "document_count": sum(formal_counts.values()),
            "layer_counts": formal_counts,
            "status_counts": dict(item.get("status_counts") or {}),
            "review_required_count": int(item.get("review_required_count") or 0),
            "edit_available": False,
        }

    @staticmethod
    def _formal_totals(rows: list[Dict[str, Any]]) -> Dict[str, int]:
        return {layer: sum(int((row.get("layer_counts") or {}).get(layer) or 0) for row in rows) for layer in FORMAL_LAYERS}

    @staticmethod
    def _document_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        metadata = dict(payload.get("metadata") or {})
        frontmatter = dict(payload.get("frontmatter") or {})
        layer = str(frontmatter.get("layer") or metadata.get("layer") or ServiceAdapter._layer_from_path(payload.get("path", "")))
        status = str(frontmatter.get("status") or metadata.get("status") or "")
        review_required = bool(frontmatter.get("review_required") or metadata.get("review_required") in {"true", "1", True})
        trust_warning = "未经审核，不能作为正式项目规则" if layer in {"raw", "distilled"} or review_required or status in {"quarantine", "rejected"} else None
        return {
            "document_id": str(metadata.get("id") or payload.get("path") or ""),
            "path": str(payload.get("path") or ""),
            "title": str(frontmatter.get("title") or metadata.get("title") or payload.get("path") or "Untitled"),
            "category_id": str(frontmatter.get("category") or metadata.get("category") or ""),
            "layer": layer,
            "status": status,
            "confidence": str(frontmatter.get("confidence") or metadata.get("confidence") or ""),
            "source_type": str(frontmatter.get("source_type") or metadata.get("source_type") or ""),
            "source_url": frontmatter.get("source_url") or metadata.get("source_url"),
            "review_required": review_required,
            "last_reviewed": frontmatter.get("last_reviewed") or metadata.get("last_reviewed"),
            "frontmatter": frontmatter,
            "body": str(payload.get("body") or ""),
            "open_mode": "read_only",
            "trust_warning": trust_warning,
            "mutation_actions_available": False,
        }

    @staticmethod
    def _task_row(record: Any) -> Dict[str, Any]:
        payload = record.to_dict() if hasattr(record, "to_dict") else dict(record)
        meta = dict(payload.get("metadata") or {})
        return {
            "task_id": str(payload.get("task_id") or ""),
            "task_type": str(payload.get("task_type") or ""),
            "status": str(payload.get("status") or ""),
            "title": str(payload.get("title") or payload.get("task_type") or ""),
            "progress_percent": int(payload.get("progress_percent") or 0),
            "progress_message": str(payload.get("progress_message") or ""),
            "cancel_requested": bool(payload.get("cancel_requested", False)),
            "error": dict(payload.get("error") or {}),
            "log_available": bool(payload.get("log_path")),
            "result_summary": dict(payload.get("result_summary") or {}),
            "elapsed_ms": int(payload.get("elapsed_ms") or 0),
            "created_at": str(payload.get("created_at") or ""),
            "started_at": str(payload.get("started_at") or ""),
            "finished_at": str(payload.get("finished_at") or ""),
            "retry_of": meta.get("retry_of"),
            "retry_root": meta.get("retry_root"),
        }

    @staticmethod
    def _layer_from_path(path: str) -> str:
        parts = Path(path).parts
        for layer in ["raw", "distilled", "rules", "checklists", "snippets", "deprecated", "rejected", "quarantine"]:
            if layer in parts:
                return layer
        return ""
