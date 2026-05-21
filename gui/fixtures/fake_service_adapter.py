"""Stable read-only fake adapter for GUI tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


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


class FakeServiceAdapter:
    """Fixture adapter that exposes only first-stage read-only capabilities."""

    def __init__(self):
        self.calls: list[tuple[str, Dict[str, Any]]] = []

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
