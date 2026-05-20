"""Read-only settings entry page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QAbstractItemView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from gui.widgets.formatters import bool_label, status_label


class SettingsEntryView(QWidget):
    def __init__(self, settings_vm: Any):
        super().__init__()
        self.settings_vm = settings_vm
        self.workspace = QLabel("工作区：未知")
        self.service = QLabel("服务状态：未知")
        self.notice = QLabel("第一阶段只读入口：不提供编辑表单、保存、应用或执行操作。")
        self.sections = QTableWidget(0, 5)
        self.sections.setHorizontalHeaderLabels(["区域", "阶段", "只读", "可编辑", "可执行"])
        self.sections.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sections.setSelectionBehavior(QAbstractItemView.SelectRows)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(QLabel("设置"))
        root.addWidget(self.workspace)
        root.addWidget(self.service)
        root.addWidget(self.notice)
        root.addWidget(self.sections, 1)

    def load_settings(self) -> None:
        self.render_settings(self.settings_vm.load_entry())

    def focus_primary(self) -> None:
        self.sections.setFocus()

    def render_settings(self, model: Dict[str, Any]) -> None:
        data = model.get("data") or {}
        self.workspace.setText(f"工作区：{data.get('workspace_path', '')}")
        self.service.setText(
            f"服务状态：{status_label(data.get('service_status'))}；索引：{status_label(data.get('index_status'))}；"
            f"文档 {data.get('document_count', 0)} / 分块 {data.get('chunk_count', 0)}"
        )
        rows = data.get("sections") or []
        self.sections.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [row.get("label", ""), self._phase_label(row.get("phase")), bool_label(row.get("read_only")), bool_label(row.get("editable")), bool_label(row.get("execute_available"))]
            for col, value in enumerate(values):
                self.sections.setItem(row_index, col, QTableWidgetItem(str(value)))

    @staticmethod
    def _phase_label(value: str) -> str:
        if value == "future":
            return "未来阶段"
        if value == "phase_1_read_only":
            return "第一阶段只读"
        return value or "未知"
