"""Floating assistant launcher button."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton


class AssistantLauncher(QPushButton):
    """Bottom-right launcher for the mock assistant panel."""

    def __init__(self):
        super().__init__("AI")
        self.setObjectName("assistantLauncher")
        self.setAccessibleName("AI 助手")
        self.setToolTip("打开 AI 助手（模拟模式）")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(56, 56)
