"""Bottom status bar."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout

from gui.widgets.formatters import status_label


class StatusBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("statusbar")
        self.workspace = QLabel("工作区：未知")
        self.index = QLabel("索引：未知")
        self.tasks = QLabel("任务：只读")
        self.backup = QLabel("备份：只读")
        self.notice = QLabel("")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(18)
        layout.addWidget(self.workspace)
        layout.addWidget(self.index)
        layout.addWidget(self.tasks)
        layout.addWidget(self.backup)
        layout.addWidget(self.notice)
        layout.addStretch(1)
        for label in [self.workspace, self.index, self.tasks, self.backup, self.notice]:
            label.setObjectName("mutedText")

    def update_workspace(self, model: Dict[str, Any]) -> None:
        data = model.get("data") or {}
        path = str(data.get("workspace_path") or "unknown")
        self.workspace.setText(f"工作区：{Path(path).name or path}")
        self.index.setText(f"索引：{status_label(data.get('index_status', 'unknown'))} | 文档：{data.get('document_count', 0)} | 分块：{data.get('chunk_count', 0)}")

    def show_notice(self, message: str) -> None:
        self.notice.setText(message)
