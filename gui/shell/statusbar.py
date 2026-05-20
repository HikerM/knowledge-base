"""Bottom status bar."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout


class StatusBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("statusbar")
        self.workspace = QLabel("workspace: unknown")
        self.index = QLabel("index: unknown")
        self.tasks = QLabel("tasks: read-only")
        self.backup = QLabel("backup: read-only")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(18)
        layout.addWidget(self.workspace)
        layout.addWidget(self.index)
        layout.addWidget(self.tasks)
        layout.addWidget(self.backup)
        layout.addStretch(1)
        self.setStyleSheet("#statusbar { background: #EEF1F5; border-top: 1px solid #D8DEE8; } QLabel { color: #5B6678; font-size: 12px; }")

    def update_workspace(self, model: Dict[str, Any]) -> None:
        data = model.get("data") or {}
        path = str(data.get("workspace_path") or "unknown")
        self.workspace.setText(f"workspace: {Path(path).name or path}")
        self.index.setText(f"index: {data.get('index_status', 'unknown')} | docs: {data.get('document_count', 0)} | chunks: {data.get('chunk_count', 0)}")
