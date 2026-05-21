"""Scrollable conversation view for the mock assistant."""

from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from gui.assistant.cards import create_card_widget
from gui.assistant.message_bubble import MessageBubble
from gui.styles.tokens import SPACING


class ConversationView(QScrollArea):
    """Render message bubbles and assistant cards with left/right alignment."""

    def __init__(self):
        super().__init__()
        self.setObjectName("assistantConversationView")
        self.setWidgetResizable(True)
        self.container = QWidget()
        self.container.setObjectName("assistantConversationContainer")
        self.message_layout = QVBoxLayout(self.container)
        self.message_layout.setContentsMargins(12, 12, 12, 12)
        self.message_layout.setSpacing(SPACING.compact)
        self.message_layout.addStretch(1)
        self.setWidget(self.container)

    def render(self, messages: List[Dict[str, Any]]) -> None:
        self._clear()
        for message in messages:
            self._add_message(message)
        self.message_layout.addStretch(1)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _add_message(self, message: Dict[str, Any]) -> None:
        role = str(message.get("role") or "assistant")
        alignment = str(message.get("alignment") or ("right" if role == "user" else "left"))
        column = QVBoxLayout()
        column.setSpacing(6)
        column.setContentsMargins(0, 0, 0, 0)
        content = str(message.get("content") or "")
        if content:
            column.addWidget(MessageBubble(str(message.get("author") or ""), content, role, alignment))
        for card in message.get("cards") or []:
            column.addWidget(create_card_widget(card))
        group = QWidget()
        group.setObjectName("assistantMessageGroup")
        group.setProperty("messageRole", role)
        group.setProperty("alignment", alignment)
        group.setLayout(column)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if alignment == "right":
            row.addStretch(1)
            row.addWidget(group)
        elif alignment == "center":
            row.addStretch(1)
            row.addWidget(group, 0, Qt.AlignmentFlag.AlignHCenter)
            row.addStretch(1)
        else:
            row.addWidget(group)
            row.addStretch(1)
        self.message_layout.addLayout(row)

    def _clear(self) -> None:
        while self.message_layout.count():
            item = self.message_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            layout = item.layout()
            if layout is not None:
                self._clear_layout(layout)

    def _clear_layout(self, layout: QHBoxLayout | QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            child = item.layout()
            if child is not None:
                self._clear_layout(child)

    def _scroll_to_bottom(self) -> None:
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
