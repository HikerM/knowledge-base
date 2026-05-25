"""Stable read-only fake adapter for GUI tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from knowledge_app.ai.memory_service import MemoryService, MemoryServiceError
from knowledge_app.ai.retention_models import PrivacyModePolicy, RetentionPolicy
from knowledge_app.models.operation_result import OperationResult
from knowledge_app.models.search_result import SearchResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _envelope(view_id: str, state: str, data: Dict[str, Any] | None, services: list[str]) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "view_id": view_id,
        "state": state,
        "data": data,
        "warnings": [],
        "errors": [],
        "source_services": services,
        "elapsed_ms": 0,
        "generated_at": _now(),
    }


def _error_envelope(view_id: str, service: str, message: str, code: str = "fixture_error") -> Dict[str, Any]:
    payload = _envelope(view_id, "error", None, [service])
    payload["errors"] = [{"service": service, "message": message, "code": code}]
    return payload


class FakeServiceAdapter:
    """Fixture adapter that exposes only first-stage read-only capabilities."""

    def __init__(
        self,
        ai_storage_bootstrapped: bool = True,
        include_corrupt_conversation: bool = False,
        memory_privacy_mode: bool = False,
    ):
        self.calls: list[tuple[str, Dict[str, Any]]] = []
        self.ai_storage_bootstrapped = ai_storage_bootstrapped
        self.ai_conversations = self._ai_conversation_rows()
        if include_corrupt_conversation:
            self.ai_conversations.append(self._ai_corrupt_conversation_row())
        self.memory_workspace_id = "personal_knowledge_base"
        self.memory_service = MemoryService()
        self._seed_memory_fixtures()
        if memory_privacy_mode:
            self.memory_service.retention_policy = RetentionPolicy(privacy=PrivacyModePolicy(privacy_mode=True)).validate()

    def load_workspace_status(self) -> Dict[str, Any]:
        self.calls.append(("load_workspace_status", {}))
        return _envelope(
            "workspace_status",
            "ready",
            {
                "workspace_path": "D:/AI/personal-knowledge-base",
                "index_path": "D:/AI/personal-knowledge-base/.kb/index.sqlite",
                "index_exists": True,
                "index_status": "ready",
                "document_count": 12,
                "chunk_count": 36,
                "category_counts": {"frontend": 4, "ai_agent": 8},
                "layer_counts": {"rules": 7, "checklists": 3, "snippets": 2},
                "status_counts": {"active": 12},
                "last_indexed_at": "2026-05-20T00:00:00Z",
                "startup_guards": {
                    "markdown_scan_performed": False,
                    "markdown_body_read": False,
                    "hash_performed": False,
                    "auto_index_started": False,
                },
            },
            ["WorkspaceStatusService"],
        )

    def load_home_summary(self) -> Dict[str, Any]:
        self.calls.append(("load_home_summary", {}))
        return _envelope(
            "home",
            "ready",
            {
                "workspace": {"path": "D:/AI/personal-knowledge-base", "health": "ready"},
                "index": {"status": "ready", "document_count": 12, "chunk_count": 36, "last_indexed_at": "2026-05-20T00:00:00Z"},
                "review_summary": {"pending_count": 2, "raw_count": 1, "distilled_count": 1},
                "backup_summary": {"status": "recent", "latest_backup_at": "2026-05-20T00:00:00Z", "latest_snapshot_at": None},
                "task_summary": {"running": 1, "pending": 0, "failed": 1, "recent": self._task_rows()},
                "recommended_actions": [
                    {"action_id": "open_search", "label": "搜索正式知识", "kind": "route", "target": "search", "execute": False, "enabled": True},
                    {"action_id": "open_library", "label": "浏览知识库", "kind": "route", "target": "library", "execute": False, "enabled": True},
                    {"action_id": "open_tasks", "label": "查看任务中心", "kind": "route", "target": "tasks", "execute": False, "enabled": True},
                ],
            },
            ["WorkspaceStatusService", "TaskQueueService"],
        )

    def search(self, query: str, limit: int = 25, offset: int = 0, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.calls.append(("search", {"query": query, "limit": limit, "offset": offset, "filters": dict(filters or {})}))
        rows = [] if not query.strip() else [self._search_row("rules"), self._search_row("checklists", 2)]
        return _envelope(
            "search",
            "ready" if rows else "empty",
            {
                "query": query,
                "filters": {"layers": ["rules", "checklists", "snippets"], "status": ["active"]},
                "page": {"limit": limit, "offset": offset, "count": len(rows), "has_more": False},
                "results": rows,
                "index_status": "ready",
            },
            ["SearchService"],
        )

    def load_library_summary(self, limit: int = 50, offset: int = 0, layer: str | None = None, category_id: str | None = None) -> Dict[str, Any]:
        self.calls.append(("load_library_summary", {"limit": limit, "offset": offset, "layer": layer, "category_id": category_id}))
        categories = [
            {
                "category_id": "frontend",
                "display_name": "前端",
                "path": "knowledge/01-frontend",
                "description": "前端正式知识",
                "document_count": 5,
                "layer_counts": {"rules": 3, "checklists": 1, "snippets": 1},
                "status_counts": {"active": 5},
                "review_required_count": 0,
                "edit_available": False,
            }
        ]
        layers = ["rules", "checklists", "snippets"] * 20
        documents = [self._search_row(layer_name, index) for index, layer_name in enumerate(layers, start=1)]
        if layer:
            documents = [item for item in documents if item["layer"] == layer]
        total = len(documents)
        documents = documents[offset : offset + limit]
        return _envelope(
            "library",
            "ready",
            {
                "categories": categories,
                "formal_layer_totals": {"rules": 3, "checklists": 1, "snippets": 1},
                "active_category_id": None,
                "active_view": layer or "all_formal",
                "documents": documents,
                "page": {"limit": limit, "offset": offset, "count": len(documents), "total": total, "has_more": offset + limit < total},
            },
            ["CategoryService"],
        )

    def open_document(self, document_id: int | str | None = None, path: str | None = None) -> Dict[str, Any]:
        self.calls.append(("open_document", {"document_id": document_id, "path": path}))
        target = path or str(document_id or "knowledge/01-frontend/rules/fake-rule.md")
        return _envelope(
            "document_preview",
            "ready",
            {
                "document_id": str(document_id or target),
                "path": target,
                "title": "示例正式规则",
                "category_id": "frontend",
                "layer": "rules",
                "status": "active",
                "confidence": "high",
                "source_type": "internal_practice",
                "source_url": "https://example.com/gui-fixture",
                "review_required": False,
                "last_reviewed": "2026-05-20",
                "frontmatter": {"title": "示例正式规则"},
                "body": "# 示例正式规则\n\n只读预览正文。",
                "open_mode": "read_only",
                "trust_warning": None,
                "mutation_actions_available": False,
            },
            ["DocumentService"],
        )

    def load_recent_tasks(self, limit: int = 25, offset: int = 0) -> Dict[str, Any]:
        self.calls.append(("load_recent_tasks", {"limit": limit, "offset": offset}))
        rows = self._task_rows()[:limit]
        return _envelope(
            "task_summary",
            "ready",
            {
                "tasks": rows,
                "page": {"limit": limit, "offset": offset, "count": len(rows), "has_more": False},
                "phase_1_controls": {
                    "create_task_available": False,
                    "run_task_available": False,
                    "cancel_task_available": False,
                    "retry_task_available": False,
                    "cleanup_execute_available": False,
                },
            },
            ["TaskQueueService"],
        )

    def load_task_detail(self, task_id: str, tail: int = 80) -> Dict[str, Any]:
        self.calls.append(("load_task_detail", {"task_id": task_id, "tail": tail}))
        task = self._task_rows()[0]
        task["task_id"] = task_id
        return _envelope(
            "task_detail",
            "ready",
            {
                "task": task,
                "progress_events": [{"schema_version": 1, "sequence": 1, "timestamp": "2026-05-20T00:00:00Z", "progress_percent": 40, "message": "运行中", "current_step": "示例", "detail": {}}],
                "log_entries": [{"timestamp": "2026-05-20T00:00:00Z", "message": "示例日志", "detail": {}}],
            },
            ["TaskQueueService"],
        )

    def load_settings_entry(self) -> Dict[str, Any]:
        self.calls.append(("load_settings_entry", {}))
        return _envelope(
            "settings_entry",
            "ready",
            {
                "workspace_path": "D:/AI/personal-knowledge-base",
                "index_status": "ready",
                "mutation_actions_available": False,
                "sections": [
                    {"section_id": "ai_memory", "label": "AI 记忆", "phase": "v2.6.1_in_memory_mock", "read_only": True, "editable": False, "execute_available": False},
                    {"section_id": "category_settings", "label": "分类设置", "phase": "future", "read_only": True, "editable": False, "execute_available": False},
                    {"section_id": "template_manager", "label": "模板管理", "phase": "future", "read_only": True, "editable": False, "execute_available": False},
                ],
            },
            ["WorkspaceStatusService"],
        )

    def list_workspace_templates(self) -> Dict[str, Any]:
        self.calls.append(("list_workspace_templates", {}))
        templates = [
            {"template_id": "personal", "display_name": "个人资料", "description": "私人笔记和长期收藏", "intended_use": ["私人笔记"], "not_intended_for": ["自动导入资料"], "default_dirs": ["knowledge", "config", "templates", "reports"], "default_files": ["workspace.yaml"], "default_configs": ["config/categories.yaml"]},
            {"template_id": "learning", "display_name": "学习", "description": "课程、读书和主题学习", "intended_use": ["课程笔记"], "not_intended_for": ["未经审核直接正式化"], "default_dirs": ["knowledge", "config", "templates", "reports"], "default_files": ["workspace.yaml"], "default_configs": ["config/categories.yaml"]},
            {"template_id": "work", "display_name": "工作", "description": "项目经验和流程记录", "intended_use": ["项目经验"], "not_intended_for": ["客户隐私"], "default_dirs": ["knowledge", "config", "templates", "reports"], "default_files": ["workspace.yaml"], "default_configs": ["config/categories.yaml"]},
            {"template_id": "developer", "display_name": "开发者", "description": "工程规则和代码片段", "intended_use": ["工程规则"], "not_intended_for": ["把 raw 当正式规则"], "default_dirs": ["knowledge", "config", "templates", "reports"], "default_files": ["workspace.yaml"], "default_configs": ["config/categories.yaml"]},
            {"template_id": "custom", "display_name": "自定义", "description": "最小结构", "intended_use": ["自定义分类"], "not_intended_for": ["迁移旧 workspace"], "default_dirs": ["knowledge", "config", "templates", "reports"], "default_files": ["workspace.yaml"], "default_configs": ["config/categories.yaml"]},
        ]
        return _envelope("workspace_creation_templates", "ready", {"templates": templates, "count": len(templates), "elapsed_ms": 0}, ["WorkspaceCreationPlanService"])

    def create_workspace_plan(self, request: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append(("create_workspace_plan", dict(request)))
        target_path = str(request.get("target_path") or "")
        workspace_name = str(request.get("workspace_name") or "").strip()
        template_id = str(request.get("template_id") or "")
        blockers = []
        if not workspace_name:
            blockers.append("workspace_name must not be empty")
        if template_id not in {"personal", "learning", "work", "developer", "custom"}:
            blockers.append(f"unknown template_id: {template_id}")
        if "non-empty" in target_path:
            blockers.append("target_path exists and is not empty; non-empty initialization is blocked in this version")
        plan = {
            "schema_version": "1.0",
            "plan_id": "fixture-workspace-create-plan",
            "workspace_name": workspace_name,
            "target_path": target_path,
            "template_id": template_id,
            "would_create_dirs": [target_path, "knowledge", "config", "templates", "reports", "backups"],
            "would_create_files": ["workspace.yaml"],
            "would_write_configs": ["config/categories.yaml"],
            "blockers": blockers,
            "warnings": ["target_path does not exist; confirmed create would create it"] if target_path else [],
            "requires_confirmation": True,
            "dry_run": True,
            "would_modify": False,
            "blocked": bool(blockers),
            "reversible": True,
            "validation_commands": [f"python scripts/kb.py workspace-status --workspace \"{target_path}\""],
            "estimated_result": {
                "index_status": "missing",
                "auto_index_started": False,
                "created_formal_knowledge": False,
                "imported_existing_files": False,
                "created_runtime_index": False,
                "create_execute_available": True,
            },
            "elapsed_ms": 0,
        }
        return _envelope("workspace_creation_plan", "blocked" if blockers else "ready", plan, ["WorkspaceCreationPlanService"])

    def create_workspace_from_plan(self, plan: Dict[str, Any], confirmed: bool) -> Dict[str, Any]:
        self.calls.append(("create_workspace_from_plan", {"plan_id": plan.get("plan_id"), "confirmed": confirmed}))
        target_path = str(plan.get("target_path") or "")
        errors = []
        if not confirmed:
            errors.append("workspace creation requires confirmed=true")
        if plan.get("blocked"):
            errors.append("blocked workspace creation plans cannot be executed")
        if "execute-error" in target_path:
            errors.append("fixture execution failure")
        success = not errors
        result = {
            "schema_version": "1.0",
            "success": success,
            "plan_id": str(plan.get("plan_id") or ""),
            "workspace_path": target_path,
            "created_dirs": [target_path, "knowledge", "config", "templates", "reports"] if success else [],
            "created_files": ["workspace.yaml", "config/categories.yaml"] if success else [],
            "skipped_existing": [],
            "warnings": [],
            "errors": errors,
            "elapsed_ms": 0,
            "next_steps": ["打开 workspace status，确认 index_status=missing"] if success else [],
        }
        return _envelope("workspace_creation_execute", "ready" if success else "error", result, ["WorkspaceCreationService"])

    def send_assistant_message_mock(
        self,
        message: str,
        conversation_id: str = "mock-conversation",
        context: Optional[Dict[str, Any]] = None,
        ui_context: Optional[Dict[str, Any]] = None,
        intent: str = "auto",
    ) -> Dict[str, Any]:
        self.calls.append(
            (
                "send_assistant_message_mock",
                {"message": message, "conversation_id": conversation_id, "context": dict(context or {}), "ui_context": dict(ui_context or {}), "intent": intent},
            )
        )
        from knowledge_app.ai.assistant_models import AssistantRequest
        from knowledge_app.ai.assistant_service import AssistantService

        result = AssistantService(
            registry=AssistantService.from_registry_path().registry,
            search_service_factory=lambda workspace: _FakeAssistantSearchService(),
            document_service_factory=lambda workspace: _FakeAssistantDocumentService(),
        ).send(
            AssistantRequest(
                message=message,
                intent=intent,
                conversation_id=conversation_id,
                context=dict(context or {}),
                ui_context={
                    "current_workspace": "D:/AI/personal-knowledge-base",
                    "current_screen": "test",
                    "provider_mode": "mock",
                    "allowed_scope": "formal_only",
                    **dict(ui_context or {}),
                },
            )
        )
        return _envelope(
            "assistant_mock",
            "ready",
            result.to_dict(),
            ["AssistantService", "CapabilityRegistry", "PermissionPolicy", "MockAIProvider"],
        )

    def list_ai_conversations(self, limit: int = 25, offset: int = 0) -> Dict[str, Any]:
        self.calls.append(("list_ai_conversations", {"limit": limit, "offset": offset}))
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        if not self.ai_storage_bootstrapped:
            return _envelope(
                "ai_conversation_history",
                "not_bootstrapped",
                {
                    "message": "尚未启用 AI 对话记录存储",
                    "detail": "fixture AI storage missing; no bootstrap started",
                    "conversations": [],
                    "page": {"limit": limit, "offset": offset, "count": 0, "has_more": False},
                    "storage": {"bootstrapped": False, "auto_bootstrap_started": False},
                },
                ["ConversationPersistenceService"],
            )
        rows = self.ai_conversations[offset : offset + limit]
        return _envelope(
            "ai_conversation_history",
            "ready" if rows else "empty",
            {
                "conversations": [self._ai_summary(row) for row in rows],
                "page": {"limit": limit, "offset": offset, "count": len(rows), "has_more": offset + limit < len(self.ai_conversations)},
                "storage": {"bootstrapped": True, "not_formal_knowledge": True, "not_long_term_memory": True},
            },
            ["ConversationPersistenceService"],
        )

    def get_ai_conversation(self, conversation_id: str) -> Dict[str, Any]:
        self.calls.append(("get_ai_conversation", {"conversation_id": conversation_id}))
        if not self.ai_storage_bootstrapped:
            return self._ai_not_bootstrapped("ai_conversation_detail")
        row = self._find_ai_conversation(conversation_id)
        if row is None:
            return _error_envelope("ai_conversation_detail", "ConversationPersistenceService", "读取对话失败：conversation not found", "conversation_missing")
        if row.get("corrupt_fixture"):
            return _error_envelope(
                "ai_conversation_detail",
                "ConversationPersistenceService",
                "读取对话失败：conversation fixture is corrupt；未自动修复、未自动删除、未自动 bootstrap。",
                "conversation_corrupt",
            )
        return _envelope("ai_conversation_detail", "ready", dict(row), ["ConversationPersistenceService"])

    def delete_ai_conversation(self, conversation_id: str) -> Dict[str, Any]:
        self.calls.append(("delete_ai_conversation", {"conversation_id": conversation_id}))
        if not self.ai_storage_bootstrapped:
            return self._ai_not_bootstrapped("ai_conversation_delete")
        self.ai_conversations = [row for row in self.ai_conversations if row["conversation_id"] != conversation_id]
        return _envelope(
            "ai_conversation_delete",
            "ready",
            {"conversation_id": conversation_id, "deleted": True, "cleanup_pending": False},
            ["ConversationPersistenceService"],
        )

    def export_ai_conversation(self, conversation_id: str) -> Dict[str, Any]:
        self.calls.append(("export_ai_conversation", {"conversation_id": conversation_id}))
        if not self.ai_storage_bootstrapped:
            return self._ai_not_bootstrapped("ai_conversation_export")
        row = self._find_ai_conversation(conversation_id) or {}
        if row.get("corrupt_fixture"):
            return _error_envelope(
                "ai_conversation_export",
                "ConversationPersistenceService",
                "对话导出失败：conversation fixture is corrupt；不会写文件。",
                "conversation_corrupt",
            )
        return _envelope(
            "ai_conversation_export",
            "ready",
            {
                "conversation_id": conversation_id,
                "export_mode": "preview",
                "writes_file": False,
                "not_formal_knowledge": True,
                "export_payload": {
                    "schema_version": "0.1",
                    "conversation": dict(row),
                    "not_formal_knowledge": True,
                    "includes": {"memory": False, "formal_search_records": False, "task_logs": False},
                },
            },
            ["ConversationPersistenceService"],
        )

    def list_memory_candidates(self, status: str | None = None) -> Dict[str, Any]:
        self.calls.append(("list_memory_candidates", {"status": status}))
        try:
            candidates = self.memory_service.list_candidates(self.memory_workspace_id, status=status)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_candidates", str(exc))
        rows = [self._memory_candidate_row(item.to_dict()) for item in candidates]
        return _envelope(
            "ai_memory_candidates",
            "ready" if rows else "empty",
            {"workspace_id": self.memory_workspace_id, "status_filter": status, "candidates": rows, "count": len(rows), "storage": self._memory_storage_state()},
            ["MemoryService"],
        )

    def accept_memory_candidate(self, candidate_id: str, confirmed: bool) -> Dict[str, Any]:
        self.calls.append(("accept_memory_candidate", {"candidate_id": candidate_id, "confirmed": confirmed}))
        try:
            memory = self.memory_service.accept_candidate(candidate_id, confirmed=confirmed)
            candidates = self.memory_service.list_candidates(self.memory_workspace_id)
            memories = self.memory_service.list_memories(self.memory_workspace_id, include_disabled=True, include_deleted=True)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_accept_candidate", str(exc))
        return _envelope(
            "ai_memory_accept_candidate",
            "ready",
            {
                "accepted_candidate_id": candidate_id,
                "memory": self._saved_memory_row(memory.to_dict()),
                "candidates": [self._memory_candidate_row(item.to_dict()) for item in candidates],
                "memories": [self._saved_memory_row(item.to_dict()) for item in memories],
                "storage": self._memory_storage_state(),
            },
            ["MemoryService"],
        )

    def reject_memory_candidate(self, candidate_id: str) -> Dict[str, Any]:
        self.calls.append(("reject_memory_candidate", {"candidate_id": candidate_id}))
        try:
            candidate = self.memory_service.reject_candidate(candidate_id)
            candidates = self.memory_service.list_candidates(self.memory_workspace_id)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_reject_candidate", str(exc))
        return _envelope(
            "ai_memory_reject_candidate",
            "ready",
            {"candidate": self._memory_candidate_row(candidate.to_dict()), "candidates": [self._memory_candidate_row(item.to_dict()) for item in candidates], "storage": self._memory_storage_state()},
            ["MemoryService"],
        )

    def expire_memory_candidate(self, candidate_id: str) -> Dict[str, Any]:
        self.calls.append(("expire_memory_candidate", {"candidate_id": candidate_id}))
        try:
            candidate = self.memory_service.expire_candidate(candidate_id)
            candidates = self.memory_service.list_candidates(self.memory_workspace_id)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_expire_candidate", str(exc))
        return _envelope(
            "ai_memory_expire_candidate",
            "ready",
            {"candidate": self._memory_candidate_row(candidate.to_dict()), "candidates": [self._memory_candidate_row(item.to_dict()) for item in candidates], "storage": self._memory_storage_state()},
            ["MemoryService"],
        )

    def list_saved_memories(self, status: str | None = None) -> Dict[str, Any]:
        self.calls.append(("list_saved_memories", {"status": status}))
        memories = self.memory_service.list_memories(self.memory_workspace_id, include_disabled=True, include_deleted=True)
        rows = [self._saved_memory_row(item.to_dict()) for item in memories]
        if status:
            rows = [row for row in rows if row["status"] == status]
        return _envelope(
            "ai_memory_saved",
            "ready" if rows else "empty",
            {"workspace_id": self.memory_workspace_id, "status_filter": status, "memories": rows, "count": len(rows), "storage": self._memory_storage_state()},
            ["MemoryService"],
        )

    def disable_memory(self, memory_id: str) -> Dict[str, Any]:
        self.calls.append(("disable_memory", {"memory_id": memory_id}))
        try:
            memory = self.memory_service.disable_memory(memory_id)
            memories = self.memory_service.list_memories(self.memory_workspace_id, include_disabled=True, include_deleted=True)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_disable", str(exc))
        return _envelope(
            "ai_memory_disable",
            "ready",
            {"memory": self._saved_memory_row(memory.to_dict()), "memories": [self._saved_memory_row(item.to_dict()) for item in memories], "storage": self._memory_storage_state()},
            ["MemoryService"],
        )

    def delete_memory(self, memory_id: str) -> Dict[str, Any]:
        self.calls.append(("delete_memory", {"memory_id": memory_id}))
        try:
            memory = self.memory_service.delete_memory(memory_id)
            memories = self.memory_service.list_memories(self.memory_workspace_id, include_disabled=True, include_deleted=True)
        except MemoryServiceError as exc:
            return self._memory_error("ai_memory_delete", str(exc))
        return _envelope(
            "ai_memory_delete",
            "ready",
            {"memory": self._saved_memory_row(memory.to_dict()), "memories": [self._saved_memory_row(item.to_dict()) for item in memories], "storage": self._memory_storage_state()},
            ["MemoryService"],
        )

    def clear_memory(self) -> Dict[str, Any]:
        self.calls.append(("clear_memory", {}))
        deleted_count = self.memory_service.clear_memory(self.memory_workspace_id)
        memories = self.memory_service.list_memories(self.memory_workspace_id, include_disabled=True, include_deleted=True)
        return _envelope(
            "ai_memory_clear",
            "ready",
            {"deleted_count": deleted_count, "memories": [self._saved_memory_row(item.to_dict()) for item in memories], "storage": self._memory_storage_state()},
            ["MemoryService"],
        )

    def preview_memory_backup(self) -> Dict[str, Any]:
        self.calls.append(("preview_memory_backup", {}))
        return _envelope("ai_memory_backup_preview", "ready", self.memory_service.backup_policy_preview(self.memory_workspace_id), ["MemoryService"])

    def preview_memory_export(self) -> Dict[str, Any]:
        self.calls.append(("preview_memory_export", {}))
        return _envelope(
            "ai_memory_export_preview",
            "ready",
            self.memory_service.export_memory_preview(self.memory_workspace_id, include_disabled=True, include_deleted=True),
            ["MemoryService"],
        )

    def get_memory_privacy_status(self) -> Dict[str, Any]:
        self.calls.append(("get_memory_privacy_status", {}))
        privacy = self.memory_service.retention_policy.privacy.validate().to_dict()
        privacy_mode = bool(privacy.get("privacy_mode", False))
        candidate_allowed = bool(privacy.get("memory_candidate_creation_allowed", False)) and not privacy_mode
        cloud_allowed = bool(privacy.get("cloud_memory_send_allowed", False))
        return _envelope(
            "ai_memory_privacy_status",
            "ready",
            {
                "workspace_id": self.memory_workspace_id,
                "storage": self._memory_storage_state(),
                "privacy": privacy,
                "memory_candidate_creation_allowed": candidate_allowed,
                "memory_save_allowed": candidate_allowed and not cloud_allowed,
                "cloud_send_allowed": cloud_allowed,
                "not_formal_knowledge": True,
                "formal_search_records": False,
                "save_blocked_reason": "隐私模式已开启，禁止保存 AI 记忆。" if privacy_mode else "",
            },
            ["MemoryService"],
        )

    def capabilities(self) -> Dict[str, bool]:
        self.calls.append(("capabilities", {}))
        return {
            "mutation_ui": False,
            "category_execute": False,
            "archive_execute": False,
            "delete_execute": False,
            "merge_execute": False,
            "template_apply_execute": False,
            "restore_execute": False,
            "rss": False,
            "vector_search": False,
        }

    def _seed_memory_fixtures(self) -> None:
        self.memory_service.create_candidate(
            conversation_id="conv_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            workspace_id=self.memory_workspace_id,
            proposed_text="用户偏好简洁的验证摘要。",
            type="preference",
            source_message_ids=["msg_user_1"],
        )
        self.memory_service.create_candidate(
            conversation_id="conv_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            workspace_id=self.memory_workspace_id,
            proposed_text="高敏感信息不应保存。",
            type="preference",
            source_message_ids=["msg_blocked_1"],
            sensitivity="blocked",
        )
        rejected = self.memory_service.create_candidate(
            conversation_id="conv_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            workspace_id=self.memory_workspace_id,
            proposed_text="用户偏好过时的输出格式。",
            type="format",
            source_message_ids=["msg_rejected_1"],
        )
        self.memory_service.reject_candidate(rejected.candidate_id)
        expired = self.memory_service.create_candidate(
            conversation_id="conv_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            workspace_id=self.memory_workspace_id,
            proposed_text="临时任务偏好。",
            type="workflow",
            source_message_ids=["msg_expired_1"],
        )
        self.memory_service.expire_candidate(expired.candidate_id)
        self.memory_service.accept_candidate(
            self.memory_service.create_candidate(
                conversation_id="conv_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                workspace_id=self.memory_workspace_id,
                proposed_text="用户偏好中文摘要。",
                type="preference",
                source_message_ids=["msg_saved_1"],
            ).candidate_id,
            confirmed=True,
        )
        disabled = self.memory_service.accept_candidate(
            self.memory_service.create_candidate(
                conversation_id="conv_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                workspace_id=self.memory_workspace_id,
                proposed_text="用户偏好保留命令输出。",
                type="workflow",
                source_message_ids=["msg_saved_2"],
            ).candidate_id,
            confirmed=True,
        )
        self.memory_service.disable_memory(disabled.memory_id)
        deleted = self.memory_service.accept_candidate(
            self.memory_service.create_candidate(
                conversation_id="conv_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                workspace_id=self.memory_workspace_id,
                proposed_text="用户偏好已删除示例。",
                type="format",
                source_message_ids=["msg_saved_3"],
            ).candidate_id,
            confirmed=True,
        )
        self.memory_service.delete_memory(deleted.memory_id)

    @staticmethod
    def _memory_storage_state() -> Dict[str, Any]:
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
    def _memory_error(view_id: str, message: str) -> Dict[str, Any]:
        payload = _envelope(view_id, "error", None, ["MemoryService"])
        payload["errors"] = [{"service": "MemoryService", "message": message, "code": "memory_service_error"}]
        return payload

    def _find_ai_conversation(self, conversation_id: str) -> Dict[str, Any] | None:
        for row in self.ai_conversations:
            if row["conversation_id"] == conversation_id:
                return row
        return None

    @staticmethod
    def _ai_not_bootstrapped(view_id: str) -> Dict[str, Any]:
        return _envelope(
            view_id,
            "not_bootstrapped",
            {
                "message": "尚未启用 AI 对话记录存储",
                "detail": "fixture AI storage missing; no bootstrap started",
                "conversations": [],
                "page": {"limit": 25, "offset": 0, "count": 0, "has_more": False},
                "storage": {"bootstrapped": False, "auto_bootstrap_started": False},
            },
            ["ConversationPersistenceService"],
        )

    @staticmethod
    def _ai_summary(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            key: row[key]
            for key in [
                "conversation_id",
                "workspace_id",
                "title",
                "updated_at",
                "created_at",
                "provider_kind",
                "message_count",
                "citation_count",
                "policy_decision_count",
                "status",
                "summary_preview",
                "not_formal_knowledge",
                "not_long_term_memory",
            ]
        }

    @staticmethod
    def _ai_conversation_rows() -> list[Dict[str, Any]]:
        return [
            {
                "conversation_id": "conv_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "workspace_id": "personal_knowledge_base",
                "title": "Ask My Knowledge",
                "created_at": "2026-05-22T08:00:00Z",
                "updated_at": "2026-05-22T08:05:00Z",
                "provider_kind": "mock",
                "message_count": 2,
                "citation_count": 1,
                "policy_decision_count": 1,
                "status": "saved",
                "summary_preview": "搜索正式知识并返回引用。",
                "not_formal_knowledge": True,
                "not_long_term_memory": True,
                "messages": [
                    {
                        "message_id": "msg_user_1",
                        "role": "user",
                        "type": "user_text",
                        "created_at": "2026-05-22T08:00:00Z",
                        "content_text": "搜索 service layer",
                        "citations": [],
                    },
                    {
                        "message_id": "msg_assistant_1",
                        "role": "assistant",
                        "type": "assistant_text",
                        "created_at": "2026-05-22T08:05:00Z",
                        "content_text": "GUI 必须通过 ViewModel 和 ServiceAdapter 访问 service layer。",
                        "citations": ["cit_1"],
                        "policy_decision_id": "policy_1",
                        "task_id": "task_snapshot_1",
                    },
                ],
                "citations": [
                    {
                        "citation_id": "cit_1",
                        "document_id": "101",
                        "title": "AGENTS.md Project Guidance Rule",
                        "layer": "rules",
                        "status": "active",
                        "source_type": "official",
                        "confidence": "medium",
                        "review_required": False,
                    }
                ],
                "policy_decisions": [
                    {
                        "policy_decision_id": "policy_1",
                        "created_at": "2026-05-22T08:05:00Z",
                        "capability_id": "ask_my_knowledge",
                        "level": "L1",
                        "decision": "allow",
                        "reason": "formal search only",
                        "provider_kind": "mock",
                    }
                ],
                "tasks": [
                    {
                        "task_id": "task_snapshot_1",
                        "capability_id": "ask_my_knowledge",
                        "status_at_last_render": "succeeded",
                        "progress_percent_at_last_render": 100,
                        "message_id": "msg_assistant_1",
                    }
                ],
            },
            {
                "conversation_id": "conv_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "workspace_id": "personal_knowledge_base",
                "title": "Document summary",
                "created_at": "2026-05-21T08:00:00Z",
                "updated_at": "2026-05-21T08:03:00Z",
                "provider_kind": "mock",
                "message_count": 1,
                "citation_count": 0,
                "policy_decision_count": 0,
                "status": "saved",
                "summary_preview": "",
                "not_formal_knowledge": True,
                "not_long_term_memory": True,
                "messages": [
                    {
                        "message_id": "msg_assistant_2",
                        "role": "assistant",
                        "type": "system_notice",
                        "created_at": "2026-05-21T08:03:00Z",
                        "content_text": "请先打开一篇文档。",
                        "citations": [],
                    }
                ],
                "citations": [],
                "policy_decisions": [],
                "tasks": [],
            },
        ]

    @staticmethod
    def _ai_corrupt_conversation_row() -> Dict[str, Any]:
        return {
            "conversation_id": "conv_corruptcccccccccccccccccccccccc",
            "workspace_id": "personal_knowledge_base",
            "title": "Corrupt conversation fixture",
            "created_at": "2026-05-20T08:00:00Z",
            "updated_at": "2026-05-20T08:01:00Z",
            "provider_kind": "mock",
            "message_count": 0,
            "citation_count": 0,
            "policy_decision_count": 0,
            "status": "corrupt",
            "summary_preview": "用于验证 GUI controlled error 状态；不得自动修复或删除。",
            "not_formal_knowledge": True,
            "not_long_term_memory": True,
            "corrupt_fixture": True,
            "messages": [],
            "citations": [],
            "policy_decisions": [],
            "tasks": [],
        }

    @staticmethod
    def _search_row(layer: str, index: int = 1) -> Dict[str, Any]:
        path = f"knowledge/01-frontend/{layer}/fixture-{layer}-{index}.md"
        return {
            "document_id": path,
            "path": path,
            "title": f"示例 {layer} {index}",
            "category_id": "frontend",
            "layer": layer,
            "status": "active",
            "confidence": "high",
            "source_type": "internal_practice",
            "review_required": False,
            "snippet": "示例正式搜索结果。",
            "updated_at": "2026-05-20T00:00:00Z",
            "open_document_action": {"action_id": "open_document", "label": "打开文档", "kind": "open_document", "target": path, "execute": False, "enabled": True},
        }

    @staticmethod
    def _task_rows() -> list[Dict[str, Any]]:
        return [
            {
                "task_id": "fixture-task-running",
                "task_type": "index",
                "status": "running",
                "title": "示例索引任务",
                "progress_percent": 40,
                "progress_message": "正在索引",
                "cancel_requested": False,
                "error": {},
                "log_available": True,
                "result_summary": {},
                "elapsed_ms": 1200,
                "created_at": "2026-05-20T00:00:00Z",
                "started_at": "2026-05-20T00:00:01Z",
                "finished_at": "",
                "retry_of": None,
                "retry_root": None,
            }
        ]


class _FakeAssistantSearchService:
    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 5, include_options: Optional[Dict[str, Any]] = None, explain_score: bool = False) -> OperationResult:
        if "index-missing" in query:
            return OperationResult(success=False, errors=["index.sqlite missing; cannot search"])
        rows = [] if "no-results" in query else [
            {
                "id": 101,
                "path": "knowledge/09-ai-agent/rules/agentsmd-project-guidance-rule.md",
                "title": "AGENTS.md Project Guidance Rule",
                "category": "ai_agent",
                "layer": "rules",
                "status": "active",
                "confidence": "medium",
                "source_type": "official",
                "review_required": False,
                "snippet": "启动时不得自动 index；AI 和 GUI 必须遵守 service boundary。",
            }
        ]
        return OperationResult(
            success=True,
            data=SearchResult(query=query, top_k=top_k, allowed_layers=["rules", "checklists", "snippets"], elapsed_ms=0, results=rows),
        )


class _FakeAssistantDocumentService:
    def open_document(self, document_id: Optional[int] = None, path: Optional[str] = None) -> OperationResult:
        return OperationResult(
            success=True,
            data={
                "path": path or "knowledge/09-ai-agent/rules/agentsmd-project-guidance-rule.md",
                "metadata": {
                    "id": document_id or 101,
                    "title": "AGENTS.md Project Guidance Rule",
                    "category": "ai_agent",
                    "layer": "rules",
                    "status": "active",
                    "confidence": "medium",
                    "source_type": "official",
                },
                "frontmatter": {
                    "title": "AGENTS.md Project Guidance Rule",
                    "category": "ai_agent",
                    "layer": "rules",
                    "status": "active",
                    "confidence": "medium",
                    "source_type": "official",
                    "review_required": False,
                },
                "body": "GUI 和 AI 助手必须通过 ViewModel、Adapter 和 service layer 工作。启动时不得自动 index。",
            },
        )
