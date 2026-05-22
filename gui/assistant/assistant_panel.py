"""Floating assistant chat panel."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout

from gui.assistant.composer import AssistantComposer
from gui.assistant.conversation_view import ConversationView
from gui.assistant.conversation_history_view import ConversationHistoryView
from gui.styles.tokens import SPACING
from gui.widgets.controls import ghost_button
from gui.widgets.status_chip import StatusChip


class AssistantPanel(QFrame):
    close_requested = Signal()
    message_submitted = Signal(str)
    quick_action_requested = Signal(str, str)
    history_requested = Signal()
    history_back_requested = Signal()
    history_previous_page_requested = Signal()
    history_next_page_requested = Signal()
    history_open_requested = Signal(str)
    history_delete_requested = Signal(str)
    history_export_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("assistantPanel")
        self.setFixedSize(420, 560)
        self.title = QLabel("AI 助手")
        self.title.setObjectName("assistantPanelTitle")
        self.mode_badge = StatusChip("模拟模式", "info")
        self.close_button = ghost_button("关闭")
        self.close_button.setObjectName("assistantCloseButton")
        self.history_button = ghost_button("对话历史")
        self.history_button.setObjectName("assistantHistoryButton")
        self.conversation = ConversationView()
        self.history_view = ConversationHistoryView()
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("assistantContentStack")
        self.content_stack.addWidget(self.conversation)
        self.content_stack.addWidget(self.history_view)
        self.composer = AssistantComposer()
        self.ask_button = ghost_button("问我的资料")
        self.ask_button.setObjectName("assistantAskButton")
        self.summary_button = ghost_button("总结当前文档")
        self.summary_button.setObjectName("assistantSummarizeButton")
        self.organize_button = ghost_button("整理建议")
        self.organize_button.setObjectName("assistantOrganizeButton")
        self.checklist_button = ghost_button("生成清单")
        self.checklist_button.setObjectName("assistantChecklistButton")

        header = QHBoxLayout()
        header.setContentsMargins(12, 12, 12, 8)
        header.setSpacing(8)
        header.addWidget(self.title)
        header.addWidget(self.mode_badge)
        header.addStretch(1)
        header.addWidget(self.history_button)
        header.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addWidget(self.content_stack, 1)
        layout.addLayout(self._quick_action_row())
        layout.addWidget(self.composer)

        self.close_button.clicked.connect(self.close_requested.emit)
        self.history_button.clicked.connect(self.history_requested.emit)
        self.composer.submitted.connect(self.message_submitted.emit)
        self.ask_button.clicked.connect(lambda: self.quick_action_requested.emit("ask_my_knowledge", self.composer.current_text()))
        self.summary_button.clicked.connect(lambda: self.quick_action_requested.emit("summarize_current_document", self.composer.current_text()))
        self.organize_button.clicked.connect(lambda: self.quick_action_requested.emit("organize_suggestion", self.composer.current_text()))
        self.checklist_button.clicked.connect(lambda: self.quick_action_requested.emit("generate_checklist", self.composer.current_text()))
        self.history_view.load_requested.connect(self.history_requested.emit)
        self.history_view.back_requested.connect(self.history_back_requested.emit)
        self.history_view.previous_page_requested.connect(self.history_previous_page_requested.emit)
        self.history_view.next_page_requested.connect(self.history_next_page_requested.emit)
        self.history_view.open_requested.connect(self.history_open_requested.emit)
        self.history_view.delete_requested.connect(self.history_delete_requested.emit)
        self.history_view.export_requested.connect(self.history_export_requested.emit)

    def render(self, model: Dict[str, Any]) -> None:
        self.content_stack.setCurrentWidget(self.conversation)
        self.composer.show()
        self.conversation.render(model.get("messages") or [])

    def render_history(self, model: Dict[str, Any]) -> None:
        self.content_stack.setCurrentWidget(self.history_view)
        self.composer.hide()
        self.history_view.render(model)

    def focus_composer(self) -> None:
        if self.content_stack.currentWidget() is self.conversation:
            self.composer.focus_input()

    def _quick_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(12, 8, 12, 4)
        row.setSpacing(SPACING.compact)
        for button in [self.ask_button, self.summary_button, self.organize_button, self.checklist_button]:
            row.addWidget(button)
        row.addStretch(1)
        return row
