"""Read-only dashboard page."""

from __future__ import annotations

from typing import Any, Dict

from pathlib import Path

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QListWidget, QVBoxLayout, QWidget

from gui.styles.tokens import SPACING
from gui.widgets.card import Card
from gui.widgets.controls import secondary_button
from gui.widgets.formatters import status_label
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_chip import StatusChip, tone_for_status


def _short_path(path: str, max_chars: int = 58) -> str:
    if len(path) <= max_chars:
        return path
    return f"...{path[-max_chars + 3:]}"


class DashboardView(QWidget):
    def __init__(self, dashboard_vm: Any):
        super().__init__()
        self.dashboard_vm = dashboard_vm
        self.cards: dict[str, Card] = {}
        self.recent_tasks = QListWidget()
        self.actions = QListWidget()
        self.state = QLabel("首页摘要尚未加载，点击刷新查看最近任务和推荐操作。")
        self.state.setObjectName("mutedText")
        self.state.setWordWrap(True)
        self.refresh_button = secondary_button("刷新首页摘要")
        self.index_chip = StatusChip("索引：未知")

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING.page, SPACING.page, SPACING.page, SPACING.page)
        root.setSpacing(SPACING.gap)
        root.addWidget(SectionHeader("首页", "只读状态总览。启动时只读取工作区状态。"))
        root.addWidget(self.state)
        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addStretch(1)
        root.addLayout(button_row)

        grid = QGridLayout()
        grid.setSpacing(12)
        for index, key in enumerate(["workspace", "index", "documents", "backup", "tasks"]):
            grid.addWidget(self._card(key), index // 3, index % 3)
        root.addLayout(grid)

        recent_title = QLabel("最近任务")
        recent_title.setObjectName("cardValue")
        root.addWidget(recent_title)
        root.addWidget(self.recent_tasks, 1)
        action_title = QLabel("推荐操作")
        action_title.setObjectName("cardValue")
        root.addWidget(action_title)
        root.addWidget(self.actions)
        self.refresh_button.clicked.connect(self.load)
        self._render_initial_placeholders()

    def load(self) -> None:
        self.state.setText("正在加载首页摘要...")
        self.render_summary(self.dashboard_vm.load_summary())

    def focus_primary(self) -> None:
        self.refresh_button.setFocus()

    def render_startup_status(self, model: Dict[str, Any]) -> None:
        data = model.get("data") or {}
        if model.get("state") == "error":
            self.state.setText(self._error_text(model))
            return
        self.state.setText("首页摘要尚未加载，点击刷新查看最近任务和推荐操作。")
        workspace_path = str(data.get("workspace_path") or "")
        self._set_card("workspace", "工作区", Path(workspace_path).name or "未选择", _short_path(workspace_path))
        self.cards["workspace"].setToolTip(workspace_path)
        self._set_card("index", "索引状态", status_label(data.get("index_status")), "启动只读取索引元数据")
        self._set_card("documents", "文档数量", f"{data.get('document_count', 0)} 篇", f"分块 {data.get('chunk_count', 0)} 个")
        self._set_card("backup", "备份状态", "尚未加载", "刷新首页摘要后读取")
        self._set_card("tasks", "任务状态", "尚未加载", "刷新首页摘要后读取")
        self.recent_tasks.clear()
        self.recent_tasks.addItem("点击刷新首页摘要后读取最近任务。")
        self.actions.clear()
        self.actions.addItem("点击刷新首页摘要后显示推荐操作。")

    def render_summary(self, model: Dict[str, Any]) -> None:
        data = model.get("data") or {}
        if model.get("state") == "error":
            self.state.setText(self._error_text(model))
            return
        self.state.setText("只读摘要已加载；不会自动触发索引。")
        workspace = data.get("workspace") or {}
        index = data.get("index") or {}
        backup = data.get("backup_summary") or {}
        task_summary = data.get("task_summary") or {}
        workspace_path = str(workspace.get("path") or "")
        self._set_card("workspace", "工作区", Path(workspace_path).name or "未选择", _short_path(workspace_path))
        self.cards["workspace"].setToolTip(workspace_path)
        self._set_card("index", "索引状态", status_label(index.get("status")), "不会自动重建索引")
        self._set_card("documents", "文档数量", f"{index.get('document_count', 0)} 篇", f"分块 {index.get('chunk_count', 0)} 个")
        snapshot = backup.get("latest_snapshot_at") or "不可用"
        self._set_card("backup", "备份状态", status_label(backup.get("status")), f"快照：{snapshot}")
        self._set_card("tasks", "任务状态", f"运行 {task_summary.get('running', 0)}", f"失败 {task_summary.get('failed', 0)}")
        self._render_recent_tasks(task_summary.get("recent") or [])
        self._render_actions(data.get("recommended_actions") or [])

    def _render_recent_tasks(self, rows: list[Dict[str, Any]]) -> None:
        self.recent_tasks.clear()
        if not rows:
            self.recent_tasks.addItem("没有最近任务记录。")
            return
        for task in rows[:5]:
            self.recent_tasks.addItem(f"{status_label(task.get('status'))} | {task.get('title', '')} | {task.get('progress_percent', 0)}%")

    def _render_actions(self, rows: list[Dict[str, Any]]) -> None:
        self.actions.clear()
        for action in rows[:3]:
            suffix = "" if action.get("enabled") else "（暂不可用）"
            self.actions.addItem(f"{action.get('label', '')}{suffix}")
        if not rows:
            self.actions.addItem("暂无推荐操作。")

    def _card(self, key: str) -> Card:
        card = Card("状态", "加载中", "")
        if key == "index":
            card.add_body_widget(self.index_chip)
        self.cards[key] = card
        return card

    def _set_card(self, key: str, title: str, value: str, caption: str) -> None:
        self.cards[key].set_content(title, value, caption)
        if key == "index":
            self.index_chip.set_chip(f"索引：{value}", tone_for_status(value))

    def _render_initial_placeholders(self) -> None:
        for card in self.cards.values():
            card.set_content("状态", "尚未加载", "")
        self.recent_tasks.addItem("摘要尚未加载。")
        self.actions.addItem("摘要尚未加载。")

    @staticmethod
    def _error_text(model: Dict[str, Any]) -> str:
        errors = "; ".join(item.get("message", "") for item in model.get("errors", []))
        return f"首页摘要加载失败：{errors or '服务不可用'}"
