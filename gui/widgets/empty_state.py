"""Empty state widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EmptyState(QWidget):
    def __init__(self, title: str, message: str = ""):
        super().__init__()
        self.setObjectName("softPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("emptyTitle")
        self.message_label = QLabel(message)
        self.message_label.setObjectName("mutedText")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)

    def set_state(self, title: str, message: str = "") -> None:
        self.title_label.setText(title)
        self.message_label.setText(message)
