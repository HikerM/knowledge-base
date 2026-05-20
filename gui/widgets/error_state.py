"""Error state widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ErrorState(QWidget):
    def __init__(self, title: str = "Service error", message: str = ""):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        title_label = QLabel(title)
        title_label.setObjectName("errorTitle")
        body = QLabel(message)
        body.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(body)
        self.setStyleSheet("#errorTitle { color: #B91C1C; font-weight: 600; } QLabel { color: #5B6678; }")
