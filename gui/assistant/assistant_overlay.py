"""Bottom-right floating assistant overlay."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QVBoxLayout, QWidget

from gui.assistant.assistant_launcher import AssistantLauncher
from gui.assistant.assistant_panel import AssistantPanel
from gui.viewmodels.conversation_history_viewmodel import ConversationHistoryViewModel


class AssistantOverlay(QWidget):
    """Small anchored overlay that contains the launcher and optional panel."""

    def __init__(self, assistant_vm: Any, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("assistantOverlay")
        self.assistant_vm = assistant_vm
        self.history_vm = ConversationHistoryViewModel(getattr(assistant_vm, "adapter", None))
        self.panel = AssistantPanel()
        self.launcher = AssistantLauncher()
        self.panel.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.panel)
        layout.addWidget(self.launcher, 0, Qt.AlignmentFlag.AlignRight)

        self.launcher.clicked.connect(self.toggle_panel)
        self.panel.close_requested.connect(self.close_panel)
        self.panel.message_submitted.connect(self.send_message)
        self.panel.quick_action_requested.connect(self.run_quick_action)
        self.panel.history_requested.connect(self.open_history)
        self.panel.history_back_requested.connect(self.show_chat)
        self.panel.history_previous_page_requested.connect(self.previous_history_page)
        self.panel.history_next_page_requested.connect(self.next_history_page)
        self.panel.history_open_requested.connect(self.open_history_conversation)
        self.panel.history_delete_requested.connect(self.delete_history_conversation)
        self.panel.history_export_requested.connect(self.export_history_conversation)
        self._sync_size()
        self.panel.render(self.assistant_vm.snapshot())

    def toggle_panel(self) -> None:
        if self.panel.isVisible():
            self.close_panel()
        else:
            self.open_panel()

    def open_panel(self) -> None:
        self.panel.show()
        self.launcher.setToolTip("关闭 AI 助手")
        self._sync_size()
        self.reposition()
        self.raise_()
        self.panel.focus_composer()

    def close_panel(self) -> None:
        self.panel.hide()
        self.launcher.setToolTip("打开 AI 助手（模拟模式）")
        self._sync_size()
        self.reposition()
        self.raise_()
        self.launcher.setFocus()

    def send_message(self, text: str) -> None:
        model = self.assistant_vm.send_message(text)
        self.panel.render(model)
        self._sync_size()
        self.reposition()
        self.raise_()

    def run_quick_action(self, action_id: str, composer_text: str) -> None:
        model = self.assistant_vm.run_quick_action(action_id, composer_text)
        self.panel.render(model)
        self._sync_size()
        self.reposition()
        self.raise_()

    def set_adapter(self, adapter: Any | None) -> None:
        self.assistant_vm.set_adapter(adapter)
        self.history_vm.set_adapter(adapter)

    def open_history(self) -> None:
        model = self.history_vm.load_page()
        self.panel.render_history(model)
        self._sync_size()
        self.reposition()
        self.raise_()

    def show_chat(self) -> None:
        self.panel.render(self.assistant_vm.snapshot())
        self._sync_size()
        self.reposition()
        self.raise_()

    def previous_history_page(self) -> None:
        self.panel.render_history(self.history_vm.previous_page())
        self._sync_size()
        self.reposition()
        self.raise_()

    def next_history_page(self) -> None:
        self.panel.render_history(self.history_vm.next_page())
        self._sync_size()
        self.reposition()
        self.raise_()

    def open_history_conversation(self, conversation_id: str) -> None:
        self.panel.render_history(self.history_vm.open_conversation(conversation_id))
        self._sync_size()
        self.reposition()
        self.raise_()

    def delete_history_conversation(self, conversation_id: str) -> None:
        answer = QMessageBox.question(
            self.panel,
            "删除对话",
            "确定删除这个 AI 对话记录？这不会删除其他资料或索引数据。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.panel.render_history(self.history_vm.delete_conversation(conversation_id, confirmed=False))
            self._sync_size()
            self.reposition()
            self.raise_()
            return
        self.panel.render_history(self.history_vm.delete_conversation(conversation_id, confirmed=True))
        self._sync_size()
        self.reposition()
        self.raise_()

    def export_history_conversation(self, conversation_id: str) -> None:
        self.panel.render_history(self.history_vm.export_conversation(conversation_id))
        self._sync_size()
        self.reposition()
        self.raise_()

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        margin = 20
        statusbar_offset = 52
        x = max(12, parent.width() - self.width() - margin)
        y = max(12, parent.height() - self.height() - statusbar_offset)
        self.move(x, y)

    def _sync_size(self) -> None:
        if self.panel.isVisible():
            self.setFixedSize(420, 624)
        else:
            self.setFixedSize(56, 56)
