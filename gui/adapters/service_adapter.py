"""Read-only GUI-to-service adapter for first-stage PySide6 screens."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from knowledge_app.ai.conversation_persistence_service import ConversationPersistenceService, ConversationPersistenceServiceError
from knowledge_app.ai.memory_service import MemoryService, MemoryServiceError
from knowledge_app.services.backup_service import BackupService
from knowledge_app.services.category_service import CategoryService
from knowledge_app.services.document_service import DocumentService
from knowledge_app.services.review_queue_service import ReviewQueueService
from knowledge_app.services.search_service import SearchService
from knowledge_app.services.task_queue_service import TaskQueueService
from knowledge_app.services.workspace_creation_service import WorkspaceCreationService
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

    def __init__(self, workspace_path: Path | str | None = None, memory_service: MemoryService | None = None):
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else Path.cwd().resolve()
        self._memory_service = memory_service

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
            {"section_id": "ai_memory", "label": "AI 记忆", "phase": "v2.6.1_in_memory_mock", "read_only": True, "editable": False, "execute_available": False},
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

    def create_workspace_from_plan(self, plan: Dict[str, Any], confirmed: bool) -> Dict[str, Any]:
        service = "WorkspaceCreationService"
        try:
            result = WorkspaceCreationService().create_workspace_from_plan(plan, confirmed=confirmed)
        except Exception as exc:  # noqa: BLE001
            return envelope("workspace_creation_execute", "error", None, [service], errors=[ui_error(service, str(exc))])
        data = result.to_dict()
        state = "ready" if result.success else "error"
        warnings = [ui_warning(service, item) for item in result.warnings]
        errors = [ui_error(service, item) for item in result.errors]
        return envelope("workspace_creation_execute", state, data, [service], warnings=warnings, errors=errors, elapsed_ms=result.elapsed_ms)

    def send_assistant_message_mock(
        self,
        message: str,
        conversation_id: str = "mock-conversation",
        context: Optional[Dict[str, Any]] = None,
        ui_context: Optional[Dict[str, Any]] = None,
        intent: str = "auto",
    ) -> Dict[str, Any]:
        services = ["AssistantService", "CapabilityRegistry", "PermissionPolicy", "MockAIProvider"]
        try:
            from knowledge_app.ai.assistant_models import AssistantRequest
            from knowledge_app.ai.assistant_service import AssistantService

            merged_ui_context = {
                "current_workspace": str(self.workspace_path),
                "provider_mode": "mock",
                "allowed_scope": "formal_only",
                **dict(ui_context or {}),
            }
            result = AssistantService.from_registry_path(workspace_path=self.workspace_path).send(
                AssistantRequest(
                    message=message,
                    intent=intent,
                    conversation_id=conversation_id,
                    context=dict(context or {}),
                    ui_context=merged_ui_context,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return envelope("assistant_mock", "error", None, services, errors=[ui_error("AssistantService", str(exc))])
        return envelope("assistant_mock", "ready", result.to_dict(), services)

    def list_ai_conversations(self, limit: int = 25, offset: int = 0) -> Dict[str, Any]:
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        service = "ConversationPersistenceService"
        try:
            rows = ConversationPersistenceService().list_conversations(
                self.workspace_path,
                self._ai_workspace_id(),
                limit=limit,
                offset=offset,
            )
        except ConversationPersistenceServiceError as exc:
            return self._conversation_error("ai_conversation_history", service, str(exc), limit, offset)
        except Exception as exc:  # noqa: BLE001
            return envelope("ai_conversation_history", "error", None, [service], errors=[ui_error(service, str(exc))])
        conversations = [self._conversation_summary(row.to_dict()) for row in rows]
        data = {
            "conversations": conversations,
            "page": {"limit": limit, "offset": offset, "count": len(conversations), "has_more": len(conversations) == limit},
            "storage": {"bootstrapped": True, "not_formal_knowledge": True, "not_long_term_memory": True},
        }
        return envelope("ai_conversation_history", "ready" if conversations else "empty", data, [service])

    def get_ai_conversation(self, conversation_id: str) -> Dict[str, Any]:
        service = "ConversationPersistenceService"
        try:
            record = ConversationPersistenceService().get_conversation(self.workspace_path, conversation_id)
        except ConversationPersistenceServiceError as exc:
            return self._conversation_error("ai_conversation_detail", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return envelope("ai_conversation_detail", "error", None, [service], errors=[ui_error(service, str(exc))])
        data = self._conversation_detail(record.to_dict())
        return envelope("ai_conversation_detail", "ready", data, [service])

    def delete_ai_conversation(self, conversation_id: str) -> Dict[str, Any]:
        service = "ConversationPersistenceService"
        try:
            cleanup_complete = ConversationPersistenceService().delete_conversation(self.workspace_path, conversation_id)
        except ConversationPersistenceServiceError as exc:
            return self._conversation_error("ai_conversation_delete", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return envelope("ai_conversation_delete", "error", None, [service], errors=[ui_error(service, str(exc))])
        warnings = []
        if not cleanup_complete:
            warnings.append(ui_warning(service, "对话已从 active manifest 删除，trash cleanup pending", code="cleanup_pending"))
        return envelope(
            "ai_conversation_delete",
            "ready" if cleanup_complete else "partial",
            {"conversation_id": conversation_id, "deleted": True, "cleanup_pending": not cleanup_complete},
            [service],
            warnings=warnings,
        )

    def export_ai_conversation(self, conversation_id: str) -> Dict[str, Any]:
        service = "ConversationPersistenceService"
        try:
            payload = ConversationPersistenceService().export_conversation(self.workspace_path, conversation_id)
        except ConversationPersistenceServiceError as exc:
            return self._conversation_error("ai_conversation_export", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return envelope("ai_conversation_export", "error", None, [service], errors=[ui_error(service, str(exc))])
        return envelope(
            "ai_conversation_export",
            "ready",
            {
                "conversation_id": conversation_id,
                "export_payload": payload,
                "export_mode": "preview",
                "not_formal_knowledge": True,
                "writes_file": False,
            },
            [service],
        )

    def list_memory_candidates(self, status: str | None = None) -> Dict[str, Any]:
        service = "MemoryService"
        try:
            candidates = self._memory().list_candidates(self._ai_workspace_id(), status=status)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_candidates", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._memory_error("ai_memory_candidates", service, str(exc))
        rows = [self._memory_candidate_row(item.to_dict()) for item in candidates]
        data = {
            "workspace_id": self._ai_workspace_id(),
            "status_filter": status,
            "candidates": rows,
            "count": len(rows),
            "storage": self._memory_storage_state(),
        }
        return envelope("ai_memory_candidates", "ready" if rows else "empty", data, [service])

    def accept_memory_candidate(self, candidate_id: str, confirmed: bool) -> Dict[str, Any]:
        service = "MemoryService"
        try:
            memory = self._memory().accept_candidate(candidate_id, confirmed=confirmed)
            candidates = self._memory().list_candidates(self._ai_workspace_id())
            memories = self._memory().list_memories(self._ai_workspace_id(), include_deleted=True)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_accept_candidate", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._memory_error("ai_memory_accept_candidate", service, str(exc))
        data = {
            "accepted_candidate_id": candidate_id,
            "memory": self._saved_memory_row(memory.to_dict()),
            "candidates": [self._memory_candidate_row(item.to_dict()) for item in candidates],
            "memories": [self._saved_memory_row(item.to_dict()) for item in memories],
            "storage": self._memory_storage_state(),
        }
        return envelope("ai_memory_accept_candidate", "ready", data, [service])

    def reject_memory_candidate(self, candidate_id: str) -> Dict[str, Any]:
        service = "MemoryService"
        try:
            candidate = self._memory().reject_candidate(candidate_id)
            candidates = self._memory().list_candidates(self._ai_workspace_id())
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_reject_candidate", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._memory_error("ai_memory_reject_candidate", service, str(exc))
        data = {
            "candidate": self._memory_candidate_row(candidate.to_dict()),
            "candidates": [self._memory_candidate_row(item.to_dict()) for item in candidates],
            "storage": self._memory_storage_state(),
        }
        return envelope("ai_memory_reject_candidate", "ready", data, [service])

    def expire_memory_candidate(self, candidate_id: str) -> Dict[str, Any]:
        service = "MemoryService"
        try:
            candidate = self._memory().expire_candidate(candidate_id)
            candidates = self._memory().list_candidates(self._ai_workspace_id())
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_expire_candidate", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._memory_error("ai_memory_expire_candidate", service, str(exc))
        data = {
            "candidate": self._memory_candidate_row(candidate.to_dict()),
            "candidates": [self._memory_candidate_row(item.to_dict()) for item in candidates],
            "storage": self._memory_storage_state(),
        }
        return envelope("ai_memory_expire_candidate", "ready", data, [service])

    def list_saved_memories(self) -> Dict[str, Any]:
        service = "MemoryService"
        try:
            memories = self._memory().list_memories(self._ai_workspace_id(), include_disabled=True, include_deleted=True)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_saved", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._memory_error("ai_memory_saved", service, str(exc))
        rows = [self._saved_memory_row(item.to_dict()) for item in memories]
        data = {
            "workspace_id": self._ai_workspace_id(),
            "memories": rows,
            "count": len(rows),
            "storage": self._memory_storage_state(),
        }
        return envelope("ai_memory_saved", "ready" if rows else "empty", data, [service])

    def disable_memory(self, memory_id: str) -> Dict[str, Any]:
        service = "MemoryService"
        try:
            memory = self._memory().disable_memory(memory_id)
            memories = self._memory().list_memories(self._ai_workspace_id(), include_disabled=True, include_deleted=True)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_disable", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._memory_error("ai_memory_disable", service, str(exc))
        data = {
            "memory": self._saved_memory_row(memory.to_dict()),
            "memories": [self._saved_memory_row(item.to_dict()) for item in memories],
            "storage": self._memory_storage_state(),
        }
        return envelope("ai_memory_disable", "ready", data, [service])

    def delete_memory(self, memory_id: str) -> Dict[str, Any]:
        service = "MemoryService"
        try:
            memory = self._memory().delete_memory(memory_id)
            memories = self._memory().list_memories(self._ai_workspace_id(), include_disabled=True, include_deleted=True)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_delete", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._memory_error("ai_memory_delete", service, str(exc))
        data = {
            "memory": self._saved_memory_row(memory.to_dict()),
            "memories": [self._saved_memory_row(item.to_dict()) for item in memories],
            "storage": self._memory_storage_state(),
        }
        return envelope("ai_memory_delete", "ready", data, [service])

    def clear_memory(self) -> Dict[str, Any]:
        service = "MemoryService"
        try:
            deleted_count = self._memory().clear_memory(self._ai_workspace_id())
            memories = self._memory().list_memories(self._ai_workspace_id(), include_disabled=True, include_deleted=True)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_clear", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._memory_error("ai_memory_clear", service, str(exc))
        data = {
            "deleted_count": deleted_count,
            "memories": [self._saved_memory_row(item.to_dict()) for item in memories],
            "storage": self._memory_storage_state(),
        }
        return envelope("ai_memory_clear", "ready", data, [service])

    def preview_memory_backup(self) -> Dict[str, Any]:
        service = "MemoryService"
        try:
            preview = self._memory().backup_policy_preview(self._ai_workspace_id())
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_backup_preview", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._memory_error("ai_memory_backup_preview", service, str(exc))
        return envelope("ai_memory_backup_preview", "ready", preview, [service])

    def preview_memory_export(self) -> Dict[str, Any]:
        service = "MemoryService"
        try:
            preview = self._memory().export_memory_preview(self._ai_workspace_id(), include_disabled=True, include_deleted=True)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_export_preview", service, str(exc))
        except Exception as exc:  # noqa: BLE001
            return self._memory_error("ai_memory_export_preview", service, str(exc))
        return envelope("ai_memory_export_preview", "ready", preview, [service])

    def get_memory_privacy_status(self) -> Dict[str, Any]:
        service = "MemoryService"
        try:
            privacy = self._memory().retention_policy.privacy.validate().to_dict()
        except Exception as exc:  # noqa: BLE001
            return self._memory_error("ai_memory_privacy_status", service, str(exc))
        privacy_mode = bool(privacy.get("privacy_mode", False))
        candidate_allowed = bool(privacy.get("memory_candidate_creation_allowed", False)) and not privacy_mode
        cloud_allowed = bool(privacy.get("cloud_memory_send_allowed", False))
        data = {
            "workspace_id": self._ai_workspace_id(),
            "storage": self._memory_storage_state(),
            "privacy": privacy,
            "memory_candidate_creation_allowed": candidate_allowed,
            "memory_save_allowed": candidate_allowed and not cloud_allowed,
            "cloud_send_allowed": cloud_allowed,
            "not_formal_knowledge": True,
            "formal_search_records": False,
            "save_blocked_reason": "隐私模式已开启，禁止保存 AI 记忆。" if privacy_mode else "",
        }
        return envelope("ai_memory_privacy_status", "ready", data, [service])

    def capabilities(self) -> Dict[str, bool]:
        names = ["mutation_ui", "category_execute", "archive_execute", "delete_execute", "merge_execute", "template_apply_execute", "restore_execute", "rss", "vector_search"]
        return {name: False for name in names}

    def _memory(self) -> MemoryService:
        if self._memory_service is None:
            self._memory_service = MemoryService()
        return self._memory_service

    def _ai_workspace_id(self) -> str:
        text = self.workspace_path.name.strip().lower()
        safe = "".join(character if character.isalnum() else "_" for character in text).strip("_")
        return safe or "workspace"

    def _memory_storage_state(self) -> Dict[str, Any]:
        return {
            "mode": "in_memory",
            "mock_mode": True,
            "writes_file": False,
            "creates_workspace_ai": False,
            "not_formal_knowledge": True,
            "cloud_send_allowed": False,
            "auto_loaded": False,
        }

    @staticmethod
    def _memory_candidate_row(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "candidate_id": str(payload.get("candidate_id") or ""),
            "conversation_id": str(payload.get("conversation_id") or ""),
            "workspace_id": str(payload.get("workspace_id") or ""),
            "type": str(payload.get("type") or ""),
            "proposed_text": str(payload.get("proposed_text") or ""),
            "source_message_ids": [str(item) for item in payload.get("source_message_ids") or []],
            "sensitivity": str(payload.get("sensitivity") or ""),
            "requires_confirmation": bool(payload.get("requires_confirmation", True)),
            "status": str(payload.get("status") or ""),
            "metadata": dict(payload.get("metadata") or {}),
            "not_formal_knowledge": True,
            "cloud_send_allowed": False,
        }

    @staticmethod
    def _saved_memory_row(payload: Dict[str, Any]) -> Dict[str, Any]:
        metadata = dict(payload.get("metadata") or {})
        status = str(payload.get("status") or "")
        redacted = bool(metadata.get("text_redacted", False)) or (status == "deleted" and not str(payload.get("text") or ""))
        source = dict(payload.get("source") or {})
        return {
            "memory_id": str(payload.get("memory_id") or ""),
            "workspace_id": str(payload.get("workspace_id") or ""),
            "type": str(payload.get("type") or ""),
            "text": "内容已删除" if redacted else str(payload.get("text") or ""),
            "text_redacted": redacted,
            "created_at": str(payload.get("created_at") or ""),
            "updated_at": str(payload.get("updated_at") or ""),
            "source": source,
            "source_candidate_id": str(source.get("candidate_id") or ""),
            "source_message_ids": [str(item) for item in source.get("source_message_ids") or []],
            "sensitivity": str(payload.get("sensitivity") or ""),
            "status": status,
            "metadata": metadata,
            "tombstone_label": "已删除，仅保留删除记录" if status == "deleted" else "",
            "not_formal_knowledge": True,
            "cloud_send_allowed": False,
        }

    @staticmethod
    def _memory_error(view_id: str, service: str, message: str) -> Dict[str, Any]:
        return envelope(view_id, "error", None, [service], errors=[ui_error(service, message)])


    @staticmethod
    def _conversation_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
        metadata = dict(payload.get("metadata") or {})
        summary = payload.get("summary") or {}
        return {
            "conversation_id": str(payload.get("conversation_id") or ""),
            "workspace_id": str(payload.get("workspace_id") or ""),
            "title": str(payload.get("title") or "Conversation"),
            "updated_at": str(payload.get("updated_at") or ""),
            "created_at": str(payload.get("created_at") or ""),
            "provider_kind": str(payload.get("provider_kind") or ""),
            "message_count": int(metadata.get("message_count") or len(payload.get("messages") or [])),
            "citation_count": len(payload.get("citations") or []),
            "policy_decision_count": len(payload.get("policy_decisions") or []),
            "status": "saved",
            "summary_preview": str(summary.get("text") or "")[:160] if isinstance(summary, dict) else "",
            "not_formal_knowledge": True,
            "not_long_term_memory": True,
        }

    def _conversation_detail(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        summary = self._conversation_summary(payload)
        return {
            **summary,
            "messages": [self._conversation_message(item) for item in payload.get("messages") or []],
            "citations": [dict(item) for item in payload.get("citations") or []],
            "policy_decisions": [self._policy_decision(item) for item in payload.get("policy_decisions") or []],
            "tasks": [self._task_reference(item) for item in payload.get("tasks") or []],
        }

    @staticmethod
    def _conversation_message(payload: Dict[str, Any]) -> Dict[str, Any]:
        content = dict(payload.get("content") or {})
        text = content.get("text") or content.get("body") or content.get("message") or ""
        if not text:
            text = " ".join(str(value) for value in content.values() if isinstance(value, (str, int, float)))
        return {
            "message_id": str(payload.get("message_id") or ""),
            "role": str(payload.get("role") or ""),
            "type": str(payload.get("type") or ""),
            "created_at": str(payload.get("created_at") or ""),
            "content_text": str(text),
            "citations": [str(item) for item in payload.get("citations") or []],
            "policy_decision_id": payload.get("policy_decision_id"),
            "task_id": payload.get("task_id"),
        }

    @staticmethod
    def _policy_decision(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "policy_decision_id": str(payload.get("policy_decision_id") or ""),
            "created_at": str(payload.get("created_at") or ""),
            "capability_id": str(payload.get("capability_id") or ""),
            "level": str(payload.get("level") or ""),
            "decision": str(payload.get("decision") or ""),
            "reason": str(payload.get("reason") or ""),
            "provider_kind": str(payload.get("provider_kind") or ""),
        }

    @staticmethod
    def _task_reference(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "task_id": str(payload.get("task_id") or ""),
            "capability_id": str(payload.get("capability_id") or ""),
            "status_at_last_render": str(payload.get("status_at_last_render") or ""),
            "progress_percent_at_last_render": int(payload.get("progress_percent_at_last_render") or 0),
            "message_id": payload.get("message_id"),
        }

    @staticmethod
    def _conversation_error(view_id: str, service: str, message: str, limit: int = 25, offset: int = 0) -> Dict[str, Any]:
        if "not bootstrapped" in message or "manifest.json is required" in message:
            return envelope(
                view_id,
                "not_bootstrapped",
                {
                    "message": "尚未启用 AI 对话记录存储",
                    "detail": "当前工作区没有已 bootstrap 的 workspace/ai 存储；这里不会自动启用或创建。",
                    "conversations": [],
                    "page": {"limit": limit, "offset": offset, "count": 0, "has_more": False},
                    "storage": {"bootstrapped": False, "auto_bootstrap_started": False},
                },
                [service],
                warnings=[ui_warning(service, message, code="ai_storage_not_bootstrapped")],
            )
        return envelope(view_id, "error", None, [service], errors=[ui_error(service, message)])

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
