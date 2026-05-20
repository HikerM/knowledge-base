"""Read-only task summary page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget


class TaskSummaryView(QWidget):
    def __init__(self, task_vm: Any):
        super().__init__()
        self.task_vm = task_vm
        self.summary = QLabel("TaskQueueService 只读任务摘要。")
        self.load_button = QPushButton("加载最近任务")
        self.cancel_button = QPushButton("Cancel disabled")
        self.retry_button = QPushButton("Retry disabled")
        self.cleanup_button = QPushButton("Cleanup disabled")
        for button in [self.cancel_button, self.retry_button, self.cleanup_button]:
            button.setEnabled(False)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["task_id", "type", "status", "progress", "elapsed_ms"])
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(QLabel("任务中心"))
        root.addWidget(self.summary)
        root.addWidget(self.load_button)
        root.addWidget(self.cancel_button)
        root.addWidget(self.retry_button)
        root.addWidget(self.cleanup_button)
        root.addWidget(self.table, 1)
        root.addWidget(QLabel("只读日志摘要"))
        root.addWidget(self.detail, 1)
        self.load_button.clicked.connect(self.load_tasks)
        self.table.itemSelectionChanged.connect(self.open_selected_task)

    def load_tasks(self) -> None:
        self.render_tasks(self.task_vm.load_recent_tasks())

    def render_tasks(self, model: Dict[str, Any]) -> None:
        rows = (model.get("data") or {}).get("tasks", [])
        self.summary.setText(f"{model.get('state')} | {len(rows)} task(s)")
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [row.get("task_id", ""), row.get("task_type", ""), row.get("status", ""), row.get("progress_percent", 0), row.get("elapsed_ms", 0)]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, row)
                self.table.setItem(row_index, col, item)

    def open_selected_task(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].data(Qt.UserRole) or {}
        task_id = row.get("task_id")
        if not task_id:
            return
        model = self.task_vm.load_task_detail(task_id)
        data = model.get("data") or {}
        logs = data.get("log_entries") or []
        lines = [f"{entry.get('timestamp', '')} {entry.get('message', '')}" for entry in logs]
        self.detail.setPlainText("\n".join(lines) if lines else "没有可用日志。")
