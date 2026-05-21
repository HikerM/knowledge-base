"""Floating assistant chat panel."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from gui.assistant.composer import AssistantComposer
from gui.assistant.conversation_view import ConversationView
from gui.styles.tokens import SPACING
from gui.widgets.controls import ghost_button
from gui.widgets.status_chip import StatusChip


class AssistantPanel(QFrame):
    close_requested = Signal()
    message_submitted = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("assistantPanel")
        self.setFixedSize(420, 560)
        self.title = QLabel("AI 助手")
        self.title.setObjectName("assistantPanelTitle")
        self.mode_badge = StatusChip("模拟模式", "info")
        self.close_button = ghost_button("关闭")
        self.close_button.setObjectName("assistantCloseButton")
        self.conversation = ConversationView()
        self.composer = AssistantComposer()

        header = QHBoxLayout()
        header.setContentsMargins(12, 12, 12, 8)
        header.setSpacing(8)
        header.addWidget(self.title)
        header.addWidget(self.mode_badge)
        header.addStretch(1)
        header.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self.conversation, 1)
        layout.addWidget(self.composer)

        self.close_button.clicked.connect(self.close_requested.emit)
        self.composer.submitted.connect(self.message_submitted.emit)

    def render(self, model: Dict[str, Any]) -> None:
        self.conversation.render(model.get("messages") or [])

    def focus_composer(self) -> None:
        self.composer.focus_input()
