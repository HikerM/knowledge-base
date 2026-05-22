"""ViewModel for explicitly opened AI conversation history.

The ViewModel only talks to the GUI adapter. It does not read files, call
providers, query SQLite, or invoke services directly.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List


class ConversationHistoryViewModel:
    """State holder for paginated AI conversation history."""

    def __init__(self, adapter: Any | None, limit: int = 25):
        self.adapter = adapter
        self.limit = max(1, min(int(limit), 50))
        self.offset = 0
        self.conversations: List[Dict[str, Any]] = []
        self.selected_conversation: Dict[str, Any] | None = None
        self.export_preview: str = ""
        self.last_response: Dict[str, Any] | None = None
        self.state = "idle"
        self.message = "点击“对话历史”后才会加载已保存的对话。"
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []

    def set_adapter(self, adapter: Any | None) -> None:
        self.adapter = adapter
        self.reset()

    def reset(self) -> Dict[str, Any]:
        self.offset = 0
        self.conversations = []
        self.selected_conversation = None
        self.export_preview = ""
        self.state = "idle"
        self.message = "点击“对话历史”后才会加载已保存的对话。"
        self.errors = []
        self.warnings = []
        self.last_response = None
        return self.snapshot()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "message": self.message,
            "conversations": list(self.conversations),
            "selected_conversation": dict(self.selected_conversation or {}),
            "export_preview": self.export_preview,
            "page": self._page_model(),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "not_formal_knowledge": True,
            "not_long_term_memory": True,
            "auto_loaded": False,
        }

    def load_page(self, limit: int | None = None, offset: int | None = None) -> Dict[str, Any]:
        if limit is not None:
            self.limit = max(1, min(int(limit), 50))
        if offset is not None:
            self.offset = max(0, int(offset))
        response = self._call("list_ai_conversations", limit=self.limit, offset=self.offset)
        self.last_response = response
        self.errors = list(response.get("errors") or [])
        self.warnings = list(response.get("warnings") or [])
        self.state = str(response.get("state") or "error")
        data = response.get("data") or {}
        self.conversations = [dict(item) for item in data.get("conversations") or []]
        page = dict(data.get("page") or {})
        self.limit = int(page.get("limit") or self.limit)
        self.offset = int(page.get("offset") or self.offset)
        self.selected_conversation = None
        self.export_preview = ""
        if self.state == "not_bootstrapped":
            self.message = str(data.get("message") or "未启用 AI 对话记录存储。")
        elif self.state == "empty":
            self.message = "当前页没有对话历史。可返回上一页。" if self.offset > 0 else "暂无对话历史。"
        elif self.state == "ready":
            self.message = "已加载对话历史。"
        else:
            self.message = self._error_message("读取对话失败。")
        return self.snapshot()

    def next_page(self) -> Dict[str, Any]:
        if not self._has_more():
            return self.snapshot()
        return self.load_page(offset=self.offset + self.limit)

    def previous_page(self) -> Dict[str, Any]:
        return self.load_page(offset=max(0, self.offset - self.limit))

    def open_conversation(self, conversation_id: str) -> Dict[str, Any]:
        response = self._call("get_ai_conversation", conversation_id=conversation_id)
        self.last_response = response
        self.errors = list(response.get("errors") or [])
        self.warnings = list(response.get("warnings") or [])
        self.state = str(response.get("state") or "error")
        self.export_preview = ""
        if self.state == "ready":
            self.selected_conversation = dict(response.get("data") or {})
            self.message = "已打开对话。"
        elif self.state == "not_bootstrapped":
            data = response.get("data") or {}
            self.selected_conversation = None
            self.message = str(data.get("message") or "未启用 AI 对话记录存储。")
        else:
            self.selected_conversation = None
            self.message = self._error_message("读取对话失败。")
        return self.snapshot()

    def delete_conversation(self, conversation_id: str, confirmed: bool = False) -> Dict[str, Any]:
        if not confirmed:
            self.message = "删除对话需要确认。"
            return self.snapshot()
        response = self._call("delete_ai_conversation", conversation_id=conversation_id)
        self.last_response = response
        self.errors = list(response.get("errors") or [])
        self.warnings = list(response.get("warnings") or [])
        if response.get("state") in {"ready", "partial"}:
            self.selected_conversation = None
            self.export_preview = ""
            deleted_message = "对话已删除。" if response.get("state") == "ready" else "对话已删除，trash cleanup pending。"
            self.load_page(offset=self.offset)
            self.message = deleted_message
            return self.snapshot()
        self.state = str(response.get("state") or "error")
        self.message = self._error_message("对话删除失败。")
        return self.snapshot()

    def export_conversation(self, conversation_id: str) -> Dict[str, Any]:
        response = self._call("export_ai_conversation", conversation_id=conversation_id)
        self.last_response = response
        self.errors = list(response.get("errors") or [])
        self.warnings = list(response.get("warnings") or [])
        self.state = str(response.get("state") or "error")
        if self.state == "ready":
            payload = (response.get("data") or {}).get("export_payload") or {}
            self.export_preview = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            self.message = "导出预览已生成；对话记录不是正式知识，不会自动写入文件。"
        elif self.state == "not_bootstrapped":
            self.export_preview = ""
            self.message = "未启用 AI 对话记录存储。"
        else:
            self.export_preview = ""
            self.message = self._error_message("对话导出失败。")
        return self.snapshot()

    def _call(self, method_name: str, **kwargs: Any) -> Dict[str, Any]:
        if self.adapter is None or not hasattr(self.adapter, method_name):
            return {
                "state": "error",
                "data": None,
                "warnings": [],
                "errors": [{"service": "ServiceAdapter", "message": "当前没有可用的 AI 对话历史服务。"}],
            }
        return getattr(self.adapter, method_name)(**kwargs)

    def _has_more(self) -> bool:
        if self.last_response is None:
            return False
        data = self.last_response.get("data") or {}
        page = data.get("page") or {}
        return bool(page.get("has_more", False))

    def _page_model(self) -> Dict[str, Any]:
        current_page = self.offset // self.limit + 1 if self.limit else 1
        has_more = self._has_more()
        return {
            "limit": self.limit,
            "offset": self.offset,
            "count": len(self.conversations),
            "has_more": has_more,
            "current_page": current_page,
            "can_previous": self.offset > 0,
            "can_next": has_more,
            "label": f"第 {current_page} 页 | 本页 {len(self.conversations)} 条 | 每页最多 {self.limit} 条",
        }

    def _error_message(self, fallback: str) -> str:
        if self.errors:
            return "; ".join(str(item.get("message") or "") for item in self.errors if item.get("message")) or fallback
        return fallback
