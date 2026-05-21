"""Read-only GUI-to-service adapter for first-stage PySide6 screens."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from knowledge_app.services.backup_service import BackupService
from knowledge_app.services.category_service import CategoryService
from knowledge_app.services.document_service import DocumentService
from knowledge_app.services.review_queue_service import ReviewQueueService
from knowledge_app.services.search_service import SearchService
from knowledge_app.services.task_queue_service import TaskQueueService
from knowledge_app.services.workspace_creation_plan_service import WorkspaceCreationPlanService
from knowledge_app.services.workspace_status_service import WorkspaceStatusService

from gui.adapters.viewmodel_helpers import (
    FORMAL_LAYERS,
    as_dict,
    category_row,
    document_payload,
    empty_search,
    envelope,
    formal_filters,
    formal_totals,
    route_action,
    search_row,
    task_row,
    ui_error,
    ui_warning,
)


class ServiceAdapter:
    """Thin adapter over read-only service-layer calls used by the GUI."""

    def __init__(self, workspace_path: Path | str | None = None):
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else Path.cwd().resolve()

    def load_workspace_status(self) -> Dict[str, Any]:
        service = "WorkspaceStatusService"
        try:
            result = WorkspaceStatusService(self.workspace_path).get_status()
        except Exception as exc:  # noqa: BLE001
            return envelope("workspace_status", "error", None, [service], errors=[ui_error(service, str(exc))])
        if not result.success or result.data is None:
            errors = result.errors or ["workspace status unavailable"]
            return envelope("workspace_status", "error", None, [service], errors=[ui_error(service, item) for item in errors], elapsed_ms=result.elapsed_ms)
        data = {
            **as_dict(result.data),
            "startup_guards": {
                "markdown_scan_performed": False,
                "markdown_body_read": False,
                "hash_performed": False,
                "auto_index_started": False,
            },
        }
        warnings = [ui_warning(service, item) for item in result.warnings]
        return envelope("workspace_status", "ready", data, [service], warnings=warnings, elapsed_ms=result.elapsed_ms)

    def load_home_summary(self) -> Dict[str, Any]:
        status = self.load_workspace_status()
        if status.get("state") == "error":
            return envelope("home", "error", None, status.get("source_services", []), errors=status.get("errors", []))

        status_data = status.get("data") or {}
        task_model = self.load_recent_tasks(limit=5, offset=0)
        review_summary, review_state = self._review_summary()
        backup_summary, backup_state = self._backup_summary()
        tasks = (task_model.get("data") or {}).get("tasks", [])
        index_status = str(status_data.get("index_status") or "missing")
        data = {
            "workspace": {"path": status_data.get("workspace_path", ""), "health": self._workspace_health(index_status)},
            "index": {
                "status": index_status,
                "document_count": int(status_data.get("document_count") or 0),
                "chunk_count": int(status_data.get("chunk_count") or 0),
                "last_indexed_at": status_data.get("last_indexed_at") or "",
            },
            "review_summary": review_summary,
            "backup_summary": backup_summary,
            "task_summary": {
                "running": sum(1 for item in tasks if item.get("status") == "running"),
                "pending": sum(1 for item in tasks if item.get("status") == "pending"),
                "failed": sum(1 for item in tasks if item.get("status") == "failed"),
                "recent": tasks[:5],
            },
            "recommended_actions": self._recommended_actions(index_status),
        }
        services = ["WorkspaceStatusService", "TaskQueueService", "ReviewQueueService", "BackupService"]
        warnings = list(status.get("warnings", [])) + list(task_model.get("warnings", [])) + review_state["warnings"] + backup_state["warnings"]
        errors = list(task_model.get("errors", [])) + review_state["errors"] + backup_state["errors"]
        state = "partial" if errors else "ready"
        return envelope("home", state, data, services, warnings=warnings, errors=errors, elapsed_ms=status.get("elapsed_ms", 0))

    def search(self, query: str, limit: int = 25, offset: int = 0, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query = query.strip()
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        if not query:
            return envelope("search", "empty", empty_search(query, limit, offset, "idle"), ["SearchService"])
        index_status = self._index_status()
        if index_status in {"missing", "failed"}:
            warning = ui_warning("WorkspaceStatusService", "索引不可用，搜索结果为空", code="index_unavailable")
            return envelope("search", "empty", empty_search(query, limit, offset, index_status), ["WorkspaceStatusService", "SearchService"], warnings=[warning])
        try:
            result = SearchService(self.workspace_path).search(query, filters=formal_filters(filters), top_k=min(limit + offset, 50))
        except Exception as exc:  # noqa: BLE001
            return envelope("search", "error", empty_search(query, limit, offset, index_status), ["SearchService"], errors=[ui_error("SearchService", str(exc))])
        if not result.success or result.data is None:
            errors = result.errors or ["search service unavailable"]
            return envelope("search", "error", empty_search(query, limit, offset, index_status), ["SearchService"], errors=[ui_error("SearchService", item) for item in errors], elapsed_ms=result.elapsed_ms)
        rows = [search_row(item) for item in as_dict(result.data).get("results", [])]
        page_rows = rows[offset : offset + limit]
        data = {
            "query": query,
            "filters": {"layers": FORMAL_LAYERS, "status": ["active"]},
            "page": {"limit": limit, "offset": offset, "count": len(page_rows), "has_more": len(rows) > offset + limit},
            "results": page_rows,
            "index_status": index_status,
        }
        return envelope("search", "ready" if page_rows else "empty", data, ["SearchService"], elapsed_ms=result.elapsed_ms)

    def load_library_summary(self, limit: int = 50, offset: int = 0, layer: str | None = None, category_id: str | None = None) -> Dict[str, Any]:
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        service = "CategoryService"
        try:
            category_result = CategoryService(self.workspace_path).list_categories()
            document_result = CategoryService(self.workspace_path).list_formal_documents(category_id=category_id, layer=layer, limit=limit, offset=offset)
        except Exception as exc:  # noqa: BLE001
            return envelope("library", "error", None, [service], errors=[ui_error(service, str(exc))])
        if not category_result.success or not category_result.data:
            errors = category_result.errors or ["category metadata unavailable"]
            return envelope("library", "error", None, [service], errors=[ui_error(service, item) for item in errors], elapsed_ms=category_result.elapsed_ms)
        categories = [category_row(item) for item in category_result.data.get("results", [])]
        document_data = as_dict(document_result.data)
        documents = [search_row(item) for item in document_data.get("results", [])] if document_result.success else []
        data = {
            "categories": categories,
            "formal_layer_totals": formal_totals(categories),
            "active_category_id": category_id,
            "active_view": layer if layer in FORMAL_LAYERS else "all_formal",
            "documents": documents,
            "page": {
                "limit": limit,
                "offset": offset,
                "count": len(documents),
                "total": int(document_data.get("total") or len(documents)),
                "has_more": bool(document_data.get("has_more", False)),
            },
        }
        warnings = [ui_warning(service, item) for item in category_result.warnings + document_result.warnings]
        errors = [ui_error(service, item) for item in document_result.errors]
        state = "partial" if errors else ("ready" if categories or documents else "empty")
        return envelope("library", state, data, [service], warnings=warnings, errors=errors, elapsed_ms=max(category_result.elapsed_ms, document_result.elapsed_ms))

    def open_document(self, document_id: int | str | None = None, path: str | None = None) -> Dict[str, Any]:
        service = "DocumentService"
        try:
            numeric_id = int(document_id) if document_id not in (None, "") and str(document_id).isdigit() else None
            resolved_path = path or (str(document_id) if numeric_id is None and document_id not in (None, "") else None)
            result = DocumentService(self.workspace_path).open_document(document_id=numeric_id, path=resolved_path)
        except Exception as exc:  # noqa: BLE001
            return envelope("document_preview", "error", None, [service], errors=[ui_error(service, str(exc))])
        if not result.success or not result.data:
            errors = result.errors or ["document open failed"]
            return envelope("document_preview", "error", None, [service], errors=[ui_error(service, item) for item in errors], elapsed_ms=result.elapsed_ms)
        return envelope("document_preview", "ready", document_payload(result.data), [service], elapsed_ms=result.elapsed_ms)

    def load_recent_tasks(self, limit: int = 25, offset: int = 0) -> Dict[str, Any]:
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        try:
            records = TaskQueueService(self.workspace_path).list_tasks(limit=limit, offset=offset)
        except Exception as exc:  # noqa: BLE001
            return envelope("task_summary", "error", None, ["TaskQueueService"], errors=[ui_error("TaskQueueService", str(exc))])
        rows = [task_row(record) for record in records]
        controls = {"create_task_available": False, "run_task_available": False, "cancel_task_available": False, "retry_task_available": False, "cleanup_execute_available": False}
        data = {"tasks": rows, "page": {"limit": limit, "offset": offset, "count": len(rows), "has_more": len(rows) == limit}, "phase_1_controls": controls}
        return envelope("task_summary", "ready" if rows else "empty", data, ["TaskQueueService"])

    def load_task_detail(self, task_id: str, tail: int = 80) -> Dict[str, Any]:
        service = TaskQueueService(self.workspace_path)
        try:
            record = service.get_task(task_id)
            progress = [item.to_dict() for item in service.get_task_progress(task_id, limit=100, offset=0)]
            logs = service.get_task_log(task_id, tail=tail)
        except Exception as exc:  # noqa: BLE001
            return envelope("task_detail", "error", None, ["TaskQueueService"], errors=[ui_error("TaskQueueService", str(exc))])
        return envelope("task_detail", "ready", {"task": task_row(record), "progress_events": progress, "log_entries": logs}, ["TaskQueueService"])

    def load_settings_entry(self) -> Dict[str, Any]:
        status = self.load_workspace_status()
        data = status.get("data") or {}
        sections = [
            {"section_id": "workspace_status", "label": "工作区状态", "phase": "phase_1_read_only", "read_only": True, "editable": False, "execute_available": False},
            {"section_id": "category_settings", "label": "分类设置", "phase": "future", "read_only": True, "editable": False, "execute_available": False},
            {"section_id": "template_manager", "label": "模板管理", "phase": "future", "read_only": True, "editable": False, "execute_available": False},
            {"section_id": "source_manager", "label": "来源管理", "phase": "future", "read_only": True, "editable": False, "execute_available": False},
        ]
        payload = {
            "workspace_path": data.get("workspace_path", ""),
            "index_status": data.get("index_status", "unknown"),
            "document_count": int(data.get("document_count") or 0),
            "chunk_count": int(data.get("chunk_count") or 0),
            "service_status": "available" if status.get("state") != "error" else "unavailable",
            "mutation_actions_available": False,
            "sections": sections,
        }
        return envelope("settings_entry", "ready", payload, ["WorkspaceStatusService"], warnings=status.get("warnings", []), errors=status.get("errors", []), elapsed_ms=status.get("elapsed_ms", 0))

    def list_workspace_templates(self) -> Dict[str, Any]:
        service = "WorkspaceCreationPlanService"
        try:
            result = WorkspaceCreationPlanService().list_workspace_templates()
        except Exception as exc:  # noqa: BLE001
            return envelope("workspace_creation_templates", "error", None, [service], errors=[ui_error(service, str(exc))])
        if not result.success or not result.data:
            errors = result.errors or ["workspace templates unavailable"]
            return envelope("workspace_creation_templates", "error", None, [service], errors=[ui_error(service, item) for item in errors], elapsed_ms=result.elapsed_ms)
        return envelope("workspace_creation_templates", "ready", result.data, [service], warnings=[ui_warning(service, item) for item in result.warnings], elapsed_ms=result.elapsed_ms)

    def create_workspace_plan(self, request: Dict[str, Any]) -> Dict[str, Any]:
        service = "WorkspaceCreationPlanService"
        try:
            plan = WorkspaceCreationPlanService().create_workspace_plan(request)
        except Exception as exc:  # noqa: BLE001
            return envelope("workspace_creation_plan", "error", None, [service], errors=[ui_error(service, str(exc))])
        data = plan.to_dict()
        state = "blocked" if data.get("blocked") else "ready"
        warnings = [ui_warning(service, item) for item in data.get("warnings", [])]
        return envelope("workspace_creation_plan", state, data, [service], warnings=warnings, elapsed_ms=plan.elapsed_ms)

    def capabilities(self) -> Dict[str, bool]:
        names = ["mutation_ui", "category_execute", "archive_execute", "delete_execute", "merge_execute", "template_apply_execute", "restore_execute", "rss", "vector_search"]
        return {name: False for name in names}

    def _index_status(self) -> str:
        model = self.load_workspace_status()
        return str((model.get("data") or {}).get("index_status") or "failed")

    def _review_summary(self) -> tuple[Dict[str, int], Dict[str, list[Dict[str, Any]]]]:
        try:
            result = ReviewQueueService(self.workspace_path).list_review_queue(limit=1, offset=0)
        except Exception as exc:  # noqa: BLE001
            return {"pending_count": 0, "raw_count": 0, "distilled_count": 0}, {"warnings": [], "errors": [ui_error("ReviewQueueService", str(exc))]}
        if not result.success or not result.data:
            return {"pending_count": 0, "raw_count": 0, "distilled_count": 0}, {"warnings": [], "errors": [ui_error("ReviewQueueService", item) for item in result.errors]}
        total = int(result.data.get("total") or 0)
        warnings = [ui_warning("ReviewQueueService", item) for item in result.warnings]
        return {"pending_count": total, "raw_count": 0, "distilled_count": 0}, {"warnings": warnings, "errors": []}

    def _backup_summary(self) -> tuple[Dict[str, Any], Dict[str, list[Dict[str, Any]]]]:
        try:
            result = BackupService(self.workspace_path).list_backups()
        except Exception as exc:  # noqa: BLE001
            return self._backup_unavailable(), {"warnings": [], "errors": [ui_error("BackupService", str(exc))]}
        if not result.success or not result.data:
            return self._backup_unavailable(), {"warnings": [], "errors": [ui_error("BackupService", item) for item in result.errors]}
        rows = list(result.data.get("results") or [])
        rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        latest_backup = next((item for item in rows if not str(item.get("reason") or "").startswith("snapshot-")), None)
        latest_snapshot = next((item for item in rows if str(item.get("reason") or "").startswith("snapshot-")), None)
        status = "missing" if not rows else ("failed" if any(item.get("error") for item in rows[:3]) else "recent")
        warnings = [ui_warning("BackupService", item) for item in result.warnings]
        return {"status": status, "latest_backup_at": (latest_backup or {}).get("created_at"), "latest_snapshot_at": (latest_snapshot or {}).get("created_at")}, {"warnings": warnings, "errors": []}

    @staticmethod
    def _backup_unavailable() -> Dict[str, Any]:
        return {"status": "unknown", "latest_backup_at": None, "latest_snapshot_at": None}

    @staticmethod
    def _workspace_health(index_status: str) -> str:
        if index_status == "ready":
            return "ready"
        if index_status in {"missing", "stale", "partial"}:
            return "warning"
        return "blocked"

    @staticmethod
    def _recommended_actions(index_status: str) -> list[Dict[str, Any]]:
        if index_status == "missing":
            return [
                route_action("index_missing", "索引缺失，等待后续维护入口重建", "disabled_future", "index", False, "第一阶段不自动触发索引"),
                route_action("open_tasks", "查看任务中心", "route", "tasks", True),
                route_action("open_settings", "查看只读设置", "route", "settings", True),
            ]
        return [
            route_action("open_search", "搜索正式知识", "route", "search", True),
            route_action("open_library", "浏览知识库", "route", "library", True),
            route_action("open_tasks", "查看任务中心", "route", "tasks", True),
        ]
