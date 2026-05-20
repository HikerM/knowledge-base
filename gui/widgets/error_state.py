"""Error state widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ErrorState(QWidget):
    def __init__(self, title: str = "服务错误", message: str = ""):
        super().__init__()
        self.setObjectName("softPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("errorTitle")
        self.body = QLabel(message)
        self.body.setObjectName("mutedText")
        self.body.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.body)

    def set_state(self, title: str, message: str = "") -> None:
        self.title_label.setText(title)
        self.body.setText(message)
