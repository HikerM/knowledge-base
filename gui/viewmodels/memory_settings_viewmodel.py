"""ViewModel for explicit AI memory settings management.

The ViewModel only talks to the GUI adapter. It does not read files, query
SQLite, call providers, or import service-layer modules directly.
"""

from __future__ import annotations

from typing import Any, Dict, List


class MemorySettingsViewModel:
    """State holder for the in-memory AI memory settings screen."""

    def __init__(self, adapter: Any | None):
        self.adapter = adapter
        self.status_filter: str | None = None
        self.memory_status_filter: str | None = None
        self.candidates: List[Dict[str, Any]] = []
        self.memories: List[Dict[str, Any]] = []
        self.backup_preview: Dict[str, Any] = {}
        self.export_preview: Dict[str, Any] = {}
        self.privacy_status: Dict[str, Any] = {}
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.state = "idle"
        self.message = "点击加载按钮后才会读取内存中的 AI 记忆。"

    def set_adapter(self, adapter: Any | None) -> None:
        self.adapter = adapter
        self.reset()

    def reset(self) -> Dict[str, Any]:
        self.status_filter = None
        self.memory_status_filter = None
        self.candidates = []
        self.memories = []
        self.backup_preview = {}
        self.export_preview = {}
        self.privacy_status = {}
        self.errors = []
        self.warnings = []
        self.state = "idle"
        self.message = "点击加载按钮后才会读取内存中的 AI 记忆。"
        return self.snapshot()

    def snapshot(self) -> Dict[str, Any]:
        privacy = dict(self.privacy_status)
        save_allowed = bool(privacy.get("memory_save_allowed", True))
        blocked_reason = str(privacy.get("save_blocked_reason") or "")
        return {
            "state": self.state,
            "message": self.message,
            "status_filter": self.status_filter,
            "memory_status_filter": self.memory_status_filter,
            "candidates": list(self.candidates),
            "memories": list(self.memories),
            "backup_preview": dict(self.backup_preview),
            "export_preview": dict(self.export_preview),
            "privacy_status": privacy,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "mode": {
                "storage": "in_memory",
                "mock_mode": True,
                "writes_file": False,
                "cloud_send_allowed": False,
                "formal_search_records": False,
                "auto_loaded": False,
            },
            "safety_text": [
                "AI 记忆当前为内存模拟模式，关闭应用后不会保留。",
                "长期记忆必须由你确认后才会保存。",
                "AI 记忆不会作为正式知识，也不会进入搜索规则。",
                "当前不会发送到云端。",
                "删除为删除记录，不是正式知识删除。",
            ],
            "memory_save_allowed": save_allowed,
            "save_blocked_reason": blocked_reason,
        }

    def load_candidates(self, status: str | None = None) -> Dict[str, Any]:
        normalized_status = status or None
        response = self._call("list_memory_candidates", status=normalized_status)
        self._capture_response(response)
        self.status_filter = normalized_status
        if response.get("state") in {"ready", "empty"}:
            data = response.get("data") or {}
            self.candidates = self._apply_candidate_filter([dict(item) for item in data.get("candidates") or []])
            self.state = str(response.get("state") or "empty")
            self.message = "已加载 MemoryCandidate。" if self.candidates else "没有符合条件的 MemoryCandidate。"
        else:
            self.message = self._error_message("读取 MemoryCandidate 失败。")
        return self.snapshot()

    def accept_candidate(self, candidate_id: str, confirmed: bool = False) -> Dict[str, Any]:
        if confirmed is not True:
            self.message = "接受 MemoryCandidate 需要明确确认。"
            return self.snapshot()
        response = self._call("accept_memory_candidate", candidate_id=candidate_id, confirmed=True)
        self._capture_response(response)
        if response.get("state") == "ready":
            data = response.get("data") or {}
            self.candidates = self._apply_candidate_filter([dict(item) for item in data.get("candidates") or self.candidates])
            self.memories = self._apply_memory_filter([dict(item) for item in data.get("memories") or self.memories])
            self.state = "ready"
            self.message = "已保存到内存中的 SavedMemory；不会写入磁盘。"
        else:
            self.message = self._error_message("接受 MemoryCandidate 失败。")
        return self.snapshot()

    def reject_candidate(self, candidate_id: str) -> Dict[str, Any]:
        response = self._call("reject_memory_candidate", candidate_id=candidate_id)
        self._capture_response(response)
        if response.get("state") == "ready":
            data = response.get("data") or {}
            self.candidates = self._apply_candidate_filter([dict(item) for item in data.get("candidates") or self.candidates])
            self.state = "ready"
            self.message = "已拒绝 MemoryCandidate；不会保存长期记忆。"
        else:
            self.message = self._error_message("拒绝 MemoryCandidate 失败。")
        return self.snapshot()

    def expire_candidate(self, candidate_id: str, confirmed: bool = False) -> Dict[str, Any]:
        if confirmed is not True:
            self.message = "标记过期 MemoryCandidate 需要确认；过期不会保存长期记忆。"
            return self.snapshot()
        response = self._call("expire_memory_candidate", candidate_id=candidate_id)
        self._capture_response(response)
        if response.get("state") == "ready":
            data = response.get("data") or {}
            self.candidates = self._apply_candidate_filter([dict(item) for item in data.get("candidates") or self.candidates])
            self.state = "ready"
            self.message = "已将 MemoryCandidate 标记为 expired；不会保存 SavedMemory。"
        else:
            self.message = self._error_message("过期 MemoryCandidate 失败。")
        return self.snapshot()

    def load_memories(self, status: str | None = None) -> Dict[str, Any]:
        normalized_status = status or None
        response = self._call("list_saved_memories", status=normalized_status)
        self._capture_response(response)
        self.memory_status_filter = normalized_status
        if response.get("state") in {"ready", "empty"}:
            data = response.get("data") or {}
            self.memories = self._apply_memory_filter([dict(item) for item in data.get("memories") or []])
            self.state = str(response.get("state") or "empty")
            self.message = "已加载 SavedMemory。" if self.memories else "当前没有 SavedMemory。"
        else:
            self.message = self._error_message("读取 SavedMemory 失败。")
        return self.snapshot()

    def disable_memory(self, memory_id: str) -> Dict[str, Any]:
        response = self._call("disable_memory", memory_id=memory_id)
        self._capture_response(response)
        if response.get("state") == "ready":
            data = response.get("data") or {}
            self.memories = self._apply_memory_filter([dict(item) for item in data.get("memories") or self.memories])
            self.state = "ready"
            self.message = "已禁用 SavedMemory；仅影响内存模拟状态。"
        else:
            self.message = self._error_message("禁用 SavedMemory 失败。")
        return self.snapshot()

    def delete_memory(self, memory_id: str, confirmed: bool = False) -> Dict[str, Any]:
        if confirmed is not True:
            self.message = "删除 SavedMemory 需要确认；删除为删除记录，不是正式知识删除。"
            return self.snapshot()
        response = self._call("delete_memory", memory_id=memory_id)
        self._capture_response(response)
        if response.get("state") == "ready":
            data = response.get("data") or {}
            self.memories = self._apply_memory_filter([dict(item) for item in data.get("memories") or self.memories])
            self.state = "ready"
            self.message = "已生成删除记录；内容已删除，不影响正式知识。"
        else:
            self.message = self._error_message("删除 SavedMemory 失败。")
        return self.snapshot()

    def clear_memory(self, confirmed: bool = False) -> Dict[str, Any]:
        if confirmed is not True:
            self.message = "清空内存记忆需要确认；不会删除正式知识。"
            return self.snapshot()
        response = self._call("clear_memory")
        self._capture_response(response)
        if response.get("state") == "ready":
            data = response.get("data") or {}
            self.memories = self._apply_memory_filter([dict(item) for item in data.get("memories") or []])
            self.state = "ready"
            self.message = f"已清空当前工作区内存记忆：{int(data.get('deleted_count') or 0)} 条。"
        else:
            self.message = self._error_message("清空内存记忆失败。")
        return self.snapshot()

    def refresh_previews(self) -> Dict[str, Any]:
        backup = self._call("preview_memory_backup")
        export = self._call("preview_memory_export")
        privacy = self._call("get_memory_privacy_status")
        self.errors = []
        self.warnings = []
        for response in [backup, export, privacy]:
            self.errors.extend(dict(item) for item in response.get("errors") or [])
            self.warnings.extend(dict(item) for item in response.get("warnings") or [])
        if backup.get("state") == "ready":
            self.backup_preview = dict(backup.get("data") or {})
        if export.get("state") == "ready":
            self.export_preview = dict(export.get("data") or {})
        if privacy.get("state") == "ready":
            self.privacy_status = dict(privacy.get("data") or {})
        if self.errors:
            self.state = "error"
            self.message = self._error_message("刷新 AI 记忆预览失败。")
        else:
            self.state = "ready"
            self.message = "已刷新 backup/export/privacy 预览；不会写文件或发送云端。"
        return self.snapshot()

    def _call(self, method_name: str, **kwargs: Any) -> Dict[str, Any]:
        if self.adapter is None or not hasattr(self.adapter, method_name):
            return {
                "state": "error",
                "data": None,
                "warnings": [],
                "errors": [{"service": "ServiceAdapter", "message": "当前没有可用的 AI 记忆服务。"}],
            }
        return getattr(self.adapter, method_name)(**kwargs)

    def _capture_response(self, response: Dict[str, Any]) -> None:
        self.errors = [dict(item) for item in response.get("errors") or []]
        self.warnings = [dict(item) for item in response.get("warnings") or []]
        self.state = str(response.get("state") or "error")

    def _error_message(self, fallback: str) -> str:
        if self.errors:
            message = "; ".join(str(item.get("message") or "") for item in self.errors if item.get("message")) or fallback
            lower = message.lower()
            if "privacy mode" in lower:
                return "隐私模式已开启，禁止保存 AI 记忆。"
            if "blocked" in lower:
                return "blocked candidate 不可保存为长期记忆。"
            return message
        return fallback

    def _apply_candidate_filter(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.status_filter:
            return rows
        return [row for row in rows if str(row.get("status") or "") == self.status_filter]

    def _apply_memory_filter(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.memory_status_filter:
            return rows
        return [row for row in rows if str(row.get("status") or "") == self.memory_status_filter]
