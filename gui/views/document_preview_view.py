"""Read-only Markdown document preview."""

from __future__ import annotations

import json
from typing import Any, Dict

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from gui.widgets.formatters import bool_label, confidence_label, layer_label, status_label


class DocumentPreviewView(QWidget):
    def __init__(self):
        super().__init__()
        self.header = QLabel("文档预览")
        self.path = QLabel("")
        self.badges = QLabel("")
        self.warning = QLabel("")
        self.metadata = QTextEdit()
        self.metadata.setReadOnly(True)
        self.metadata.setMaximumHeight(130)
        self.body = QTextEdit()
        self.body.setReadOnly(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.header)
        layout.addWidget(self.path)
        layout.addWidget(self.badges)
        layout.addWidget(self.warning)
        layout.addWidget(QLabel("元数据（开发者信息）"))
        layout.addWidget(self.metadata)
        layout.addWidget(QLabel("文档内容"))
        layout.addWidget(self.body, 1)
        self.render_empty()
        self.setStyleSheet("QTextEdit { border: 1px solid #D8DEE8; border-radius: 8px; padding: 8px; } QLabel { color: #1F2937; }")

    def render_empty(self) -> None:
        self.header.setText("文档预览")
        self.path.setText("")
        self.badges.setText("只读打开模式")
        self.warning.setText("")
        self.metadata.setPlainText("")
        self.body.setPlainText("未打开文档。")

    def render_document(self, model: Dict[str, Any]) -> None:
        if model.get("state") == "error":
            message = "; ".join(item.get("message", "") for item in model.get("errors", []))
            self.header.setText("文档打开失败")
            self.path.setText("")
            self.badges.setText("")
            self.warning.setText(message)
            self.metadata.setPlainText("")
            self.body.setPlainText("")
            return
        data = model.get("data") or {}
        self.header.setText(str(data.get("title") or data.get("path") or "文档预览"))
        self.path.setText(f"路径：{data.get('path', '')}")
        self.badges.setText(
            " | ".join(
                [
                    f"层级：{layer_label(data.get('layer'))}",
                    f"状态：{status_label(data.get('status'))}",
                    f"可信度：{confidence_label(data.get('confidence'))}",
                    f"来源：{data.get('source_type') or '未知'}",
                    f"需审核：{bool_label(data.get('review_required'))}",
                ]
            )
        )
        self.warning.setText(str(data.get("trust_warning") or ""))
        self.metadata.setPlainText(json.dumps(data.get("frontmatter") or {}, ensure_ascii=False, indent=2))
        self.body.setPlainText(str(data.get("body") or ""))
