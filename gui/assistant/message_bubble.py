"""Message bubbles for the mock assistant conversation."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from gui.styles.tokens import SPACING


class MessageBubble(QFrame):
    """Role-aware bubble with author and content labels."""

    def __init__(self, author: str, content: str, role: str, alignment: str):
        super().__init__()
        object_name = "userMessageBubble" if role == "user" else ("systemMessageBubble" if role == "system" else "assistantMessageBubble")
        self.setObjectName(object_name)
        self.setProperty("messageRole", role)
        self.setProperty("alignment", alignment)
        self.setMaximumWidth(320)

        self.author_label = QLabel(author)
        self.author_label.setObjectName("messageAuthor")
        self.author_label.setProperty("messageRole", role)
        self.content_label = QLabel(content)
        self.content_label.setObjectName("messageContent")
        self.content_label.setWordWrap(True)
        self.content_label.setTextInteractionFlags(self.content_label.textInteractionFlags())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.compact, SPACING.compact, SPACING.compact, SPACING.compact)
        layout.setSpacing(4)
        layout.addWidget(self.author_label)
        layout.addWidget(self.content_label)
