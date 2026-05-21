"""First-run workspace selection entry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QLabel, QVBoxLayout, QWidget

from gui.styles.tokens import SPACING
from gui.widgets.card import Card
from gui.widgets.controls import primary_button, secondary_button
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_chip import StatusChip


class WorkspaceGateView(QWidget):
    """Friendly first-run gate before a workspace is selected."""

    workspace_selected = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("workspaceGate")
        self.header = SectionHeader("请选择一个知识库文件夹", "不会自动扫描或修改你的文件。")
        self.message = QLabel("选择已有知识库后，应用只会读取工作区状态。未检测到搜索索引时，你可以稍后建立索引。")
        self.message.setObjectName("mutedText")
        self.message.setWordWrap(True)
        self.status_chip = StatusChip("未选择知识库", "warning")
        self.card = Card("首次使用", "选择已有知识库", "不会自动建立索引，也不会自动创建知识库。")
        self.select_button = primary_button("选择已有知识库")
        self.retry_button = secondary_button("重新检测")
        self.retry_button.setVisible(False)
        self.card.add_body_widget(self.status_chip)
        self.card.add_body_widget(self.select_button)
        self.card.add_body_widget(self.retry_button)
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING.page, SPACING.page, SPACING.page, SPACING.page)
        root.setSpacing(SPACING.gap)
        root.addWidget(self.header)
        root.addWidget(self.message)
        root.addWidget(self.card)
        root.addStretch(1)
        self.select_button.clicked.connect(self.choose_workspace)
        self.retry_button.clicked.connect(self._retry_last)
        self._last_path = ""

    def choose_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "请选择一个知识库文件夹")
        if path:
            self.submit_workspace(path)

    def submit_workspace(self, path: str | Path) -> None:
        self._last_path = str(path)
        self.workspace_selected.emit(str(path))

    def show_unselected(self) -> None:
        self.status_chip.set_chip("未选择知识库", "warning")
        self.card.set_content("首次使用", "选择已有知识库", "不会自动建立索引，也不会自动创建知识库。")
        self.retry_button.setVisible(False)

    def show_unavailable_last_workspace(self, path: str) -> None:
        self._last_path = path
        self.status_chip.set_chip("上次的知识库位置不可用", "warning")
        self.card.set_content("需要重新选择", "上次的知识库位置不可用", _short_path(path))
        self.retry_button.setVisible(False)

    def show_error(self, message: str, path: str = "") -> None:
        self._last_path = path
        self.status_chip.set_chip("文件夹不可用", "danger")
        self.card.set_content("请选择其他文件夹", message, _short_path(path))
        self.retry_button.setVisible(bool(path))

    def show_index_missing(self, path: str) -> None:
        self.status_chip.set_chip("未检测到搜索索引", "warning")
        self.card.set_content("已选择知识库", "未检测到搜索索引", f"{_short_path(path)} · 你可以稍后建立索引")
        self.retry_button.setVisible(False)

    def focus_primary(self) -> None:
        self.select_button.setFocus()

    def _retry_last(self) -> None:
        if self._last_path:
            self.submit_workspace(self._last_path)


def _short_path(path: str, max_chars: int = 72) -> str:
    if len(path) <= max_chars:
        return path
    return f"...{path[-max_chars + 3:]}"
