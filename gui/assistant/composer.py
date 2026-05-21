"""Message composer for the mock assistant."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QWidget

from gui.widgets.controls import primary_button


class AssistantComposer(QWidget):
    submitted = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("assistantComposer")
        self.input = QLineEdit()
        self.input.setObjectName("assistantComposerInput")
        self.input.setPlaceholderText("问我的资料，或输入想整理的内容…")
        self.send_button = primary_button("发送")
        self.send_button.setObjectName("assistantSendButton")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.input, 1)
        layout.addWidget(self.send_button)

        self.input.returnPressed.connect(self._submit)
        self.send_button.clicked.connect(self._submit)

    def focus_input(self) -> None:
        self.input.setFocus()

    def current_text(self) -> str:
        return self.input.text().strip()

    def _submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.submitted.emit(text)
