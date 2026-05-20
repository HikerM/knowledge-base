"""Empty state widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EmptyState(QWidget):
    def __init__(self, title: str, message: str = ""):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        title_label = QLabel(title)
        title_label.setObjectName("emptyTitle")
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(message_label)
        self.setStyleSheet("#emptyTitle { font-weight: 600; font-size: 16px; } QLabel { color: #5B6678; }")
