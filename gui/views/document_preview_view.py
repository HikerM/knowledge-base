"""Read-only document preview."""

from __future__ import annotations

import json
from typing import Any, Dict

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTextEdit, QVBoxLayout, QWidget

from gui.styles.tokens import SPACING
from gui.widgets.formatters import bool_label, confidence_label, layer_label, source_type_label, status_label
from gui.widgets.status_chip import StatusChip, tone_for_status


def _short_path(path: str, max_chars: int = 72) -> str:
    if len(path) <= max_chars:
        return path
    return f"...{path[-max_chars + 3:]}"


class DocumentPreviewView(QWidget):
    def __init__(self):
        super().__init__()
        self.header = QLabel("文档预览")
        self.header.setObjectName("sectionTitle")
        self.path = QLabel("")
        self.path.setObjectName("pathLabel")
        self.path.setWordWrap(True)
        self.readonly_chip = StatusChip("只读打开", "info")
        self.layer_chip = StatusChip("层级：未知", "muted")
        self.status_chip = StatusChip("状态：未知", "muted")
        self.source_chip = StatusChip("来源：未知", "muted")
        self.confidence_chip = StatusChip("可信度：未知", "muted")
        self.review_chip = StatusChip("审核：未知", "muted")
        self.warning = QLabel("")
        self.warning.setObjectName("mutedText")
        self.warning.setWordWrap(True)
        self.content_state = QLabel("未打开文档。")
        self.content_state.setObjectName("mutedText")
        self.metadata = QTextEdit()
        self.metadata.setObjectName("metadataPanel")
        self.metadata.setReadOnly(True)
        self.metadata.setMaximumHeight(130)
        self.metadata.setLineWrapMode(QTextEdit.WidgetWidth)
        self.body = QTextEdit()
        self.body.setObjectName("documentBody")
        self.body.setReadOnly(True)
        self.body.setLineWrapMode(QTextEdit.WidgetWidth)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.compact)
        layout.addWidget(self.header)
        layout.addWidget(self.path)
        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)
        for chip in [self.readonly_chip, self.layer_chip, self.status_chip]:
            chips.addWidget(chip)
        chips.addStretch(1)
        layout.addLayout(chips)
        trust_chips = QHBoxLayout()
        trust_chips.setContentsMargins(0, 0, 0, 0)
        trust_chips.setSpacing(6)
        for chip in [self.confidence_chip, self.source_chip, self.review_chip]:
            trust_chips.addWidget(chip)
        trust_chips.addStretch(1)
        layout.addLayout(trust_chips)
        layout.addWidget(self.warning)
        layout.addWidget(self.content_state)
        meta_label = QLabel("元数据")
        meta_label.setObjectName("cardTitle")
        layout.addWidget(meta_label)
        layout.addWidget(self.metadata)
        body_label = QLabel("文档内容")
        body_label.setObjectName("cardTitle")
        layout.addWidget(body_label)
        layout.addWidget(self.body, 1)
        self.render_empty()

    def render_empty(self) -> None:
        self.header.setText("文档预览")
        self.path.setText("")
        self.readonly_chip.set_chip("只读打开", "info")
        self.layer_chip.set_chip("层级：未知", "muted")
        self.status_chip.set_chip("状态：未知", "muted")
        self.source_chip.set_chip("来源：未知", "muted")
        self.confidence_chip.set_chip("可信度：未知", "muted")
        self.review_chip.set_chip("审核：未知", "muted")
        self.warning.setText("")
        self.content_state.setText("未打开文档。")
        self.metadata.setPlainText("")
        self.body.setPlainText("选择一条结果并打开后，仅加载该单篇文档。")

    def render_document(self, model: Dict[str, Any]) -> None:
        if model.get("state") == "error":
            message = "; ".join(item.get("message", "") for item in model.get("errors", []))
            self.header.setText("文档打开失败")
            self.path.setText("")
            self.readonly_chip.set_chip("只读打开", "info")
            self.layer_chip.set_chip("层级：未知", "muted")
            self.status_chip.set_chip("状态：错误", "danger")
            self.source_chip.set_chip("来源：未知", "muted")
            self.confidence_chip.set_chip("可信度：未知", "muted")
            self.review_chip.set_chip("审核：未知", "muted")
            self.warning.setText(message)
            self.content_state.setText("请回到列表重新选择文档。")
            self.metadata.setPlainText("")
            self.body.setPlainText("")
            return
        data = model.get("data") or {}
        self.header.setText(str(data.get("title") or data.get("path") or "文档预览"))
        path = str(data.get("path") or "")
        self.path.setText(f"路径：{_short_path(path)}")
        self.path.setToolTip(path)
        self.readonly_chip.set_chip("只读打开", "info")
        self.layer_chip.set_chip(f"层级：{layer_label(data.get('layer'))}", "info")
        self.status_chip.set_chip(f"状态：{status_label(data.get('status'))}", tone_for_status(data.get("status")))
        self.confidence_chip.set_chip(f"可信度：{confidence_label(data.get('confidence'))}", "muted")
        self.source_chip.set_chip(f"来源：{source_type_label(data.get('source_type'))}", "muted")
        self.review_chip.set_chip(f"需审核：{bool_label(data.get('review_required'))}", "muted")
        self.warning.setText(str(data.get("trust_warning") or ""))
        self.metadata.setPlainText(json.dumps(data.get("frontmatter") or {}, ensure_ascii=False, indent=2))
        body = str(data.get("body") or "")
        self.content_state.setText(f"只读预览；正文 {len(body)} 字符。长文可滚动查看。")
        self.body.setPlainText(body or "该文档没有正文内容。")
        self.body.moveCursor(QTextCursor.Start)
