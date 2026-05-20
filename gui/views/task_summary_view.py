"""Read-only task summary page."""

from __future__ import annotations

import json
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QLabel, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget

from gui.widgets.formatters import elapsed_label, status_label


class TaskSummaryView(QWidget):
    def __init__(self, task_vm: Any):
        super().__init__()
        self.task_vm = task_vm
        self.summary = QLabel("正在读取任务摘要。")
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["任务", "类型", "状态", "进度", "耗时", "错误摘要"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(QLabel("任务中心"))
        root.addWidget(self.summary)
        root.addWidget(self.table, 1)
        root.addWidget(QLabel("只读日志摘要"))
        root.addWidget(self.detail, 1)
        self.table.itemSelectionChanged.connect(self.open_selected_task)

    def load_tasks(self) -> None:
        self.render_tasks(self.task_vm.load_recent_tasks(limit=25, offset=0))

    def render_tasks(self, model: Dict[str, Any]) -> None:
        rows = (model.get("data") or {}).get("tasks", [])
        if model.get("errors"):
            self.summary.setText(self._error_text(model))
        elif not rows:
            self.summary.setText("没有任务记录。")
        else:
            self.summary.setText(f"最近任务 {len(rows)} 条；操作按钮在 Phase 1 隐藏。")
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("title", ""),
                row.get("task_type", ""),
                status_label(row.get("status")),
                f"{row.get('progress_percent', 0)}%",
                elapsed_label(row.get("elapsed_ms")),
                (row.get("error") or {}).get("message", ""),
            ]
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
        if model.get("state") == "error":
            self.detail.setPlainText(self._error_text(model))
            return
        data = model.get("data") or {}
        task = data.get("task") or {}
        logs = data.get("log_entries") or []
        events = data.get("progress_events") or []
        lines = [
            f"任务：{task.get('title', '')}",
            f"状态：{status_label(task.get('status'))}，进度：{task.get('progress_percent', 0)}%",
            f"错误：{json.dumps(task.get('error') or {}, ensure_ascii=False)}",
            "",
            "进度事件：",
        ]
        lines.extend(f"{item.get('sequence', '')}. {item.get('message', '')}" for item in events[:20])
        lines.append("")
        lines.append("日志：")
        lines.extend(f"{entry.get('timestamp', '')} {entry.get('message', '')}" for entry in logs[:80])
        self.detail.setPlainText("\n".join(lines) if logs or events else "没有可用日志。")

    @staticmethod
    def _error_text(model: Dict[str, Any]) -> str:
        errors = "; ".join(item.get("message", "") for item in model.get("errors", []))
        return f"任务数据读取失败：{errors or '服务不可用'}"
