"""Top bar with workspace, global search, and status indicators."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QPushButton, QHBoxLayout

from gui.widgets.formatters import status_label
from gui.widgets.status_chip import StatusChip, tone_for_status


def _compact_path(path: str, max_chars: int = 34) -> str:
    if len(path) <= max_chars:
        return path
    return f"...{path[-max_chars + 3:]}"


class TopBar(QFrame):
    search_submitted = Signal(str)
    settings_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("topbar")
        self.workspace_label = QLabel("工作区")
        self.workspace_label.setObjectName("mutedText")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索正式层规则、清单、片段")
        self.index_badge = StatusChip("索引：未知")
        self.task_badge = StatusChip("任务：只读", "info")
        self.backup_badge = StatusChip("备份：只读", "info")
        settings_button = QPushButton("设置")
        settings_button.setProperty("buttonRole", "ghost")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)
        layout.addWidget(self.workspace_label)
        layout.addWidget(self.search_input, 1)
        layout.addWidget(self.index_badge)
        layout.addWidget(self.task_badge)
        layout.addWidget(self.backup_badge)
        layout.addWidget(settings_button)

        self.search_input.returnPressed.connect(lambda: self.search_submitted.emit(self.search_input.text()))
        settings_button.clicked.connect(self.settings_requested.emit)

    def update_workspace(self, model: Dict[str, Any]) -> None:
        data = model.get("data") or {}
        workspace_path = str(data.get("workspace_path") or "未选择工作区")
        name = Path(workspace_path).name or workspace_path
        self.workspace_label.setText(f"工作区：{_compact_path(name)}")
        self.workspace_label.setToolTip(workspace_path)
        index_status = str(data.get("index_status") or "unknown")
        self.index_badge.set_chip(f"索引：{status_label(index_status)}", tone_for_status(index_status))
