"""Reusable styled input, select, and button controls."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton

from gui.styles.tokens import CONTROLS


class SearchInput(QLineEdit):
    def __init__(self, placeholder: str = ""):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.setMinimumHeight(CONTROLS.large_height)
        self.setProperty("controlKind", "search")


class Select(QComboBox):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(CONTROLS.height)
        self.setProperty("controlKind", "select")


class Button(QPushButton):
    def __init__(self, text: str, role: str = "secondary"):
        super().__init__(text)
        self.set_role(role)
        self.setMinimumHeight(CONTROLS.height)

    def set_role(self, role: str) -> None:
        self.setProperty("buttonRole", role)
        self.style().unpolish(self)
        self.style().polish(self)


def primary_button(text: str) -> Button:
    return Button(text, "primary")


def secondary_button(text: str) -> Button:
    return Button(text, "secondary")


def ghost_button(text: str) -> Button:
    return Button(text, "ghost")


def danger_button(text: str) -> Button:
    return Button(text, "danger")

