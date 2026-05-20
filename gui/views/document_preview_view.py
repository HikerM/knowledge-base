"""Read-only Markdown document preview."""

from __future__ import annotations

import json
from typing import Any, Dict

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from gui.widgets.formatters import bool_label, confidence_label, layer_label, source_type_label, status_label


class DocumentPreviewView(QWidget):
    def __init__(self):
        super().__init__()
        self.header = QLabel("文档预览")
        self.path = QLabel("")
        self.badges = QLabel("")
        self.warning = QLabel("")
        self.content_state = QLabel("未打开文档。")
        self.metadata = QTextEdit()
        self.metadata.setReadOnly(True)
        self.metadata.setMaximumHeight(130)
        self.metadata.setLineWrapMode(QTextEdit.WidgetWidth)
        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setLineWrapMode(QTextEdit.WidgetWidth)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.header)
        layout.addWidget(self.path)
        layout.addWidget(self.badges)
        layout.addWidget(self.warning)
        layout.addWidget(self.content_state)
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
        self.content_state.setText("未打开文档。")
        self.metadata.setPlainText("")
        self.body.setPlainText("选择一条结果并打开后，仅加载该单篇文档。")

    def render_document(self, model: Dict[str, Any]) -> None:
        if model.get("state") == "error":
            message = "; ".join(item.get("message", "") for item in model.get("errors", []))
            self.header.setText("文档打开失败")
            self.path.setText("")
            self.badges.setText("")
            self.warning.setText(message)
            self.content_state.setText("请回到列表重新选择文档。")
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
                    f"来源：{source_type_label(data.get('source_type'))}",
                    f"需审核：{bool_label(data.get('review_required'))}",
                ]
            )
        )
        self.warning.setText(str(data.get("trust_warning") or ""))
        self.metadata.setPlainText(json.dumps(data.get("frontmatter") or {}, ensure_ascii=False, indent=2))
        body = str(data.get("body") or "")
        self.content_state.setText(f"只读预览；正文 {len(body)} 字符。长文可滚动查看。")
        self.body.setPlainText(body or "该文档没有正文内容。")
        self.body.moveCursor(QTextCursor.Start)
