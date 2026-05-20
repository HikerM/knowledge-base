"""Read-only settings entry page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class SettingsEntryView(QWidget):
    def __init__(self, workspace_vm: Any):
        super().__init__()
        self.workspace_vm = workspace_vm
        self.workspace = QLabel("workspace: unknown")
        self.notice = QLabel("Phase 1 只读入口：不提供 editable forms、save/apply 或 mutation execute。")
        self.sections = QTableWidget(0, 5)
        self.sections.setHorizontalHeaderLabels(["section", "phase", "read_only", "editable", "execute"])
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(QLabel("设置"))
        root.addWidget(self.workspace)
        root.addWidget(self.notice)
        root.addWidget(self.sections, 1)

    def render_settings(self, model: Dict[str, Any] | None = None) -> None:
        data = (model or self.workspace_vm.status or {}).get("data") or {}
        self.workspace.setText(f"workspace: {data.get('workspace_path', '')}")
        rows = [
            {"label": "分类设置", "phase": "future", "read_only": True, "editable": False, "execute_available": False},
            {"label": "模板管理", "phase": "future", "read_only": True, "editable": False, "execute_available": False},
            {"label": "来源管理", "phase": "future", "read_only": True, "editable": False, "execute_available": False},
            {"label": "App / Workspace 设置", "phase": "phase_1_read_only", "read_only": True, "editable": False, "execute_available": False},
        ]
        self.sections.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [row["label"], row["phase"], row["read_only"], row["editable"], row["execute_available"]]
            for col, value in enumerate(values):
                self.sections.setItem(row_index, col, QTableWidgetItem(str(value)))
