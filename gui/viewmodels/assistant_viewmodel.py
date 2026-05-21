"""Floating assistant ViewModel.

The ViewModel only talks to the GUI adapter. It does not call providers,
services, filesystem APIs, SQLite, or CLI commands directly.
"""

from __future__ import annotations

from typing import Any, Dict, List


INITIAL_MESSAGE = {
    "message_id": "assistant-initial-system",
    "role": "system",
    "author": "系统",
    "content": "你好，我是 AI 助手。当前为模拟模式，不会访问网络或修改资料。",
    "alignment": "center",
    "cards": [
        {
            "card_type": "system_notice",
            "title": "模拟模式",
            "body": "MockAIProvider 只返回固定卡片，不接 OpenAI、本地模型或 ModelScope。",
            "items": ["不会访问网络", "不会读取 Markdown / SQLite", "不会执行 mutation"],
            "citations": [],
            "actions": [],
            "metadata": {"mock_only": True},
        }
    ],
}


class AssistantViewModel:
    """Conversation state for the floating assistant skeleton."""

    def __init__(self, adapter: Any | None):
        self.adapter = adapter
        self.conversation_id = "gui-mock-conversation"
        self.messages: List[Dict[str, Any]] = [dict(INITIAL_MESSAGE)]
        self.last_response: Dict[str, Any] | None = None

    def set_adapter(self, adapter: Any | None) -> None:
        self.adapter = adapter

    def snapshot(self) -> Dict[str, Any]:
        return {
            "state": "ready",
            "conversation_id": self.conversation_id,
            "messages": list(self.messages),
            "provider_mode": "mock",
            "mutation_actions_available": False,
            "network_accessed": False,
        }

    def send_message(self, text: str) -> Dict[str, Any]:
        message = text.strip()
        if not message:
            return self.snapshot()
        self.messages.append(self._user_message(message, len(self.messages)))
        if self.adapter is None or not hasattr(self.adapter, "send_assistant_message_mock"):
            self.messages.append(self._assistant_error("当前没有可用工作区 adapter；AI 助手只保留本地模拟提示。"))
            return self.snapshot()
        response = self.adapter.send_assistant_message_mock(message=message, conversation_id=self.conversation_id)
        self.last_response = response
        if response.get("state") != "ready":
            error_text = "; ".join(item.get("message", "") for item in response.get("errors", [])) or "AssistantService unavailable"
            self.messages.append(self._assistant_error(error_text))
            return self.snapshot()
        data = response.get("data") or {}
        for item in data.get("messages", []):
            self.messages.append(dict(item))
        return self.snapshot()

    @staticmethod
    def _user_message(text: str, index: int) -> Dict[str, Any]:
        return {
            "message_id": f"user-{index}",
            "role": "user",
            "author": "我",
            "content": text,
            "alignment": "right",
            "cards": [],
        }

    @staticmethod
    def _assistant_error(text: str) -> Dict[str, Any]:
        return {
            "message_id": "assistant-error",
            "role": "assistant",
            "author": "AI 助手",
            "content": "当前无法处理这条消息。",
            "alignment": "left",
            "cards": [
                {
                    "card_type": "risk_notice",
                    "title": "AssistantService 不可用",
                    "body": text,
                    "items": ["没有执行任何写操作。"],
                    "citations": [],
                    "actions": [],
                    "metadata": {"blocked": True},
                }
            ],
        }
