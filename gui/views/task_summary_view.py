"""Read-only task summary page."""

from __future__ import annotations

import json
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget

from gui.styles.tokens import SPACING
from gui.widgets.empty_state import EmptyState
from gui.widgets.error_state import ErrorState
from gui.widgets.formatters import elapsed_label, status_label, task_type_label
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_chip import StatusChip, tone_for_status


class TaskSummaryView(QWidget):
    def __init__(self, task_vm: Any):
        super().__init__()
        self.task_vm = task_vm
        self.summary = QLabel("进入任务中心后读取最近任务；日志摘要需选择任务后显式查看。")
        self.summary.setObjectName("mutedText")
        self.summary.setWordWrap(True)
        self.empty_state = EmptyState("等待加载", "进入任务中心后读取最近任务。")
        self.error_state = ErrorState("任务读取失败", "")
        self.error_state.hide()
        self.refresh_button = QPushButton("刷新任务")
        self.refresh_button.setProperty("buttonRole", "primary")
        self.detail_button = QPushButton("查看日志摘要")
        self.detail_button.setEnabled(False)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["任务", "类型", "状态", "进度", "耗时", "错误摘要"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlainText("选择一条任务后点击“查看日志摘要”。")
        controls = QHBoxLayout()
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.detail_button)
        controls.addStretch(1)
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING.page, SPACING.page, SPACING.page, SPACING.page)
        root.setSpacing(SPACING.gap)
        root.addWidget(SectionHeader("任务中心", "只读查看最近任务；日志摘要需要手动打开。"))
        root.addWidget(self.summary)
        root.addLayout(controls)
        root.addWidget(self.empty_state)
        root.addWidget(self.error_state)
        root.addWidget(self.table, 1)
        detail_title = QLabel("只读日志摘要")
        detail_title.setObjectName("cardValue")
        root.addWidget(detail_title)
        root.addWidget(self.detail, 1)
        self.refresh_button.clicked.connect(self.load_tasks)
        self.detail_button.clicked.connect(self.open_selected_task)
        self.table.itemSelectionChanged.connect(self.update_selection_state)
        self.table.itemActivated.connect(lambda item: self.open_selected_task())
        self.setTabOrder(self.refresh_button, self.table)
        self.setTabOrder(self.table, self.detail_button)

    def load_tasks(self) -> None:
        self.render_tasks(self.task_vm.load_recent_tasks(limit=25, offset=0))

    def focus_primary(self) -> None:
        self.refresh_button.setFocus()

    def render_tasks(self, model: Dict[str, Any]) -> None:
        rows = (model.get("data") or {}).get("tasks", [])
        if model.get("errors"):
            self.summary.setText(self._error_text(model))
            self.error_state.set_state("任务读取失败", self._error_text(model))
            self.error_state.show()
            self.empty_state.hide()
        elif not rows:
            self.summary.setText("没有任务记录。")
            self.empty_state.set_state("没有任务记录", "当前工作区还没有可显示的任务摘要。")
            self.empty_state.show()
            self.error_state.hide()
        else:
            self.summary.setText(f"最近任务 {len(rows)} 条；操作按钮在第一阶段隐藏。")
            self.empty_state.hide()
            self.error_state.hide()
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("title", ""),
                task_type_label(row.get("task_type")),
                status_label(row.get("status")),
                f"{row.get('progress_percent', 0)}%",
                elapsed_label(row.get("elapsed_ms")),
                (row.get("error") or {}).get("message", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, row)
                self.table.setItem(row_index, col, item)
            self.table.setCellWidget(row_index, 2, StatusChip(status_label(row.get("status")), tone_for_status(row.get("status"))))
        self.update_selection_state()

    def update_selection_state(self) -> None:
        self.detail_button.setEnabled(bool(self.table.selectedItems()))

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
            f"结果摘要：{json.dumps(task.get('result_summary') or {}, ensure_ascii=False)}",
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
