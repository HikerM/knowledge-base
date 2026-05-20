"""Reusable screen header."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.title = QLabel(title)
        self.title.setObjectName("sectionTitle")
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("sectionSubtitle")
        self.subtitle.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)

    def set_subtitle(self, subtitle: str) -> None:
        self.subtitle.setText(subtitle)

