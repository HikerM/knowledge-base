"""Reusable card container widgets."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from gui.styles.tokens import SPACING


class Card(QFrame):
    """Small white card with title, value, optional caption, and child slot."""

    def __init__(self, title: str = "", value: str = "", caption: str = ""):
        super().__init__()
        self.setObjectName("card")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("cardValue")
        self.value_label.setWordWrap(True)
        self.caption_label = QLabel(caption)
        self.caption_label.setObjectName("cardCaption")
        self.caption_label.setWordWrap(True)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(SPACING.compact)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.card, SPACING.card, SPACING.card, SPACING.card)
        layout.setSpacing(SPACING.compact)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.caption_label)
        layout.addLayout(self.body)

    def set_content(self, title: str | None = None, value: str | None = None, caption: str | None = None) -> None:
        if title is not None:
            self.title_label.setText(title)
        if value is not None:
            self.value_label.setText(value)
        if caption is not None:
            self.caption_label.setText(caption)

    def add_body_widget(self, widget: QWidget) -> None:
        self.body.addWidget(widget)

