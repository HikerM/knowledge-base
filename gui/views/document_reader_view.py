"""Main-area read-only document reader."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTextEdit, QVBoxLayout, QWidget

from gui.styles.tokens import SPACING
from gui.widgets.card import Card
from gui.widgets.controls import secondary_button
from gui.widgets.empty_state import EmptyState
from gui.widgets.formatters import bool_label, confidence_label, layer_label, source_type_label, status_label
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_chip import StatusChip, tone_for_status


def _short_path(path: str, max_chars: int = 96) -> str:
    return path if len(path) <= max_chars else f"...{path[-max_chars + 3:]}"


class DocumentReaderView(QWidget):
    return_requested = Signal()

    def __init__(self, return_label: str):
        super().__init__()
        self.return_button = secondary_button(return_label)
        self.header = SectionHeader("文档阅读", "请选择一篇文档进行阅读。")
        self.path = QLabel("")
        self.path.setObjectName("pathLabel")
        self.path.setWordWrap(True)
        self.readonly_chip = StatusChip("只读", "info")
        self.layer_chip = StatusChip("层级：未知", "muted")
        self.status_chip = StatusChip("状态：未知", "muted")
        self.source_chip = StatusChip("来源：未知", "muted")
        self.empty_state = EmptyState("请选择一篇文档进行阅读。", "从左侧列表选择文档，再点击在主区域打开。")
        self.meta_card = Card("元数据", "未打开", "")
        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setLineWrapMode(QTextEdit.WidgetWidth)
        self.body.hide()
        self.meta_card.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.gap)
        return_row = QHBoxLayout()
        return_row.addWidget(self.return_button)
        return_row.addStretch(1)
        layout.addLayout(return_row)
        layout.addWidget(self.header)
        layout.addWidget(self.path)
        for chip in [self.readonly_chip, self.layer_chip, self.status_chip, self.source_chip]:
            layout.addWidget(chip)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.meta_card)
        body_title = QLabel("文档内容")
        body_title.setObjectName("cardTitle")
        layout.addWidget(body_title)
        layout.addWidget(self.body, 1)
        self.return_button.clicked.connect(self.return_requested.emit)
        self.render_empty()

    def render_empty(self) -> None:
        self.header.title.setText("文档阅读")
        self.header.set_subtitle("请选择一篇文档进行阅读。")
        self.path.setText("")
        self.readonly_chip.set_chip("只读", "info")
        self.layer_chip.set_chip("层级：未知", "muted")
        self.status_chip.set_chip("状态：未知", "muted")
        self.source_chip.set_chip("来源：未知", "muted")
        self.empty_state.show()
        self.meta_card.hide()
        self.body.hide()
        self.body.setPlainText("")

    def render_document(self, model: Dict[str, Any]) -> None:
        if model.get("state") == "error":
            message = "; ".join(item.get("message", "") for item in model.get("errors", []))
            self.header.title.setText("文档打开失败")
            self.header.set_subtitle(message or "服务不可用")
            self.empty_state.set_state("文档打开失败", "请返回列表重新选择文档。")
            self.empty_state.show()
            self.meta_card.hide()
            self.body.hide()
            return
        data = model.get("data") or {}
        path = str(data.get("path") or "")
        title = str(data.get("title") or path or "未命名文档")
        body = str(data.get("body") or "")
        self.header.title.setText(title)
        self.header.set_subtitle("完整正文只在主阅读区显示，内容保持只读。")
        self.path.setText(f"路径：{_short_path(path)}")
        self.path.setToolTip(path)
        self.layer_chip.set_chip(f"层级：{layer_label(data.get('layer'))}", "info")
        self.status_chip.set_chip(f"状态：{status_label(data.get('status'))}", tone_for_status(data.get("status")))
        self.source_chip.set_chip(
            f"可信度 {confidence_label(data.get('confidence'))} · 来源 {source_type_label(data.get('source_type'))} · 需审核 {bool_label(data.get('review_required'))}",
            "muted",
        )
        self.meta_card.set_content("元数据", f"来源：{data.get('source_url') or '无'}", f"最近审核：{data.get('last_reviewed') or '未知'}")
        self.empty_state.hide()
        self.meta_card.show()
        self.body.show()
        self.body.setPlainText(body or "该文档没有内容。")
        self.body.moveCursor(QTextCursor.Start)
