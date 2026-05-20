"""Read-only dashboard page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from gui.widgets.formatters import status_label


class DashboardView(QWidget):
    def __init__(self, dashboard_vm: Any):
        super().__init__()
        self.dashboard_vm = dashboard_vm
        self.cards: dict[str, QLabel] = {}
        self.recent_tasks = QListWidget()
        self.actions = QListWidget()
        self.state = QLabel("启动阶段只读取工作区状态；点击刷新后加载首页摘要。")
        self.state.setWordWrap(True)
        self.refresh_button = QPushButton("刷新首页摘要")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)
        title = QLabel("首页")
        title.setObjectName("screenTitle")
        root.addWidget(title)
        root.addWidget(self.state)
        root.addWidget(self.refresh_button)

        grid = QGridLayout()
        grid.setSpacing(12)
        for index, key in enumerate(["workspace", "index", "documents", "chunks", "backup", "tasks"]):
            grid.addWidget(self._card(key), index // 3, index % 3)
        root.addLayout(grid)

        root.addWidget(QLabel("最近任务"))
        root.addWidget(self.recent_tasks, 1)
        root.addWidget(QLabel("推荐操作"))
        root.addWidget(self.actions)
        self.refresh_button.clicked.connect(self.load)
        self._render_initial_placeholders()
        self.setStyleSheet("#screenTitle { font-size: 24px; font-weight: 600; color: #1F2937; } QLabel { color: #1F2937; } QListWidget { border: 1px solid #D8DEE8; border-radius: 8px; }")

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
        self.state.setText("启动状态已加载；首页摘要尚未加载。")
        self.cards["workspace"].setText(f"工作区路径\n{data.get('workspace_path', '')}")
        self.cards["index"].setText(f"索引状态\n{status_label(data.get('index_status'))}")
        self.cards["documents"].setText(f"文档数量\n{data.get('document_count', 0)}")
        self.cards["chunks"].setText(f"分块数量\n{data.get('chunk_count', 0)}")
        self.cards["backup"].setText("备份 / 快照\n摘要尚未加载")
        self.cards["tasks"].setText("任务摘要\n摘要尚未加载")
        self.recent_tasks.clear()
        self.recent_tasks.addItem("摘要尚未加载。点击刷新首页摘要后读取最近任务。")
        self.actions.clear()
        self.actions.addItem("摘要尚未加载。点击刷新首页摘要后显示推荐操作。")

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
        self.cards["workspace"].setText(f"工作区路径\n{workspace.get('path', '')}")
        self.cards["index"].setText(f"索引状态\n{status_label(index.get('status'))}")
        self.cards["documents"].setText(f"文档数量\n{index.get('document_count', 0)}")
        self.cards["chunks"].setText(f"分块数量\n{index.get('chunk_count', 0)}")
        snapshot = backup.get("latest_snapshot_at") or "不可用"
        self.cards["backup"].setText(f"备份 / 快照\n{status_label(backup.get('status'))}\n快照：{snapshot}")
        self.cards["tasks"].setText(f"任务摘要\n运行 {task_summary.get('running', 0)} / 失败 {task_summary.get('failed', 0)}")
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

    def _card(self, key: str) -> QFrame:
        card = QFrame()
        card.setObjectName("summaryCard")
        layout = QVBoxLayout(card)
        label = QLabel("加载中")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.cards[key] = label
        card.setStyleSheet("#summaryCard { background: #FFFFFF; border: 1px solid #D8DEE8; border-radius: 8px; padding: 12px; }")
        return card

    def _render_initial_placeholders(self) -> None:
        for label in self.cards.values():
            label.setText("摘要尚未加载")
        self.recent_tasks.addItem("摘要尚未加载。")
        self.actions.addItem("摘要尚未加载。")

    @staticmethod
    def _error_text(model: Dict[str, Any]) -> str:
        errors = "; ".join(item.get("message", "") for item in model.get("errors", []))
        return f"首页摘要加载失败：{errors or '服务不可用'}"
