"""Read-only Markdown document preview."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from gui.widgets.badges import StatusBadge, tone_for_status
from gui.widgets.empty_state import EmptyState
from gui.widgets.error_state import ErrorState


class DocumentPreviewView(QWidget):
    def __init__(self):
        super().__init__()
        self.header = QLabel("文档预览")
        self.badges = QLabel("")
        self.warning = QLabel("")
        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.empty = EmptyState("未选择文档", "搜索或知识库中点击一条记录后，只读打开单篇 Markdown。")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.header)
        layout.addWidget(self.badges)
        layout.addWidget(self.warning)
        layout.addWidget(self.body, 1)
        self.render_empty()
        self.setStyleSheet("QTextEdit { border: 1px solid #D8DEE8; border-radius: 8px; padding: 8px; } QLabel { color: #1F2937; }")

    def render_empty(self) -> None:
        self.header.setText("文档预览")
        self.badges.setText("open_mode: read_only")
        self.warning.setText("")
        self.body.setPlainText("未打开文档。")

    def render_document(self, model: Dict[str, Any]) -> None:
        if model.get("state") == "error":
            message = "; ".join(item.get("message", "") for item in model.get("errors", []))
            self.header.setText("文档打开失败")
            self.badges.setText("")
            self.warning.setText(message)
            self.body.setPlainText("")
            return
        data = model.get("data") or {}
        self.header.setText(str(data.get("title") or data.get("path") or "文档预览"))
        badge_text = " | ".join(
            [
                f"layer: {data.get('layer', '')}",
                f"status: {data.get('status', '')}",
                f"confidence: {data.get('confidence', '')}",
                f"source: {data.get('source_type', '')}",
            ]
        )
        self.badges.setText(badge_text)
        self.warning.setText(str(data.get("trust_warning") or ""))
        self.body.setPlainText(str(data.get("body") or ""))
