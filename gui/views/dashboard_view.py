"""Read-only dashboard page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from gui.widgets.badges import StatusBadge, tone_for_status


class DashboardView(QWidget):
    def __init__(self, task_vm: Any | None = None):
        super().__init__()
        self.task_vm = task_vm
        self.cards: dict[str, QLabel] = {}
        self.recent_tasks = QListWidget()
        self.recent_tasks.addItem("最近任务不会在启动时自动加载；进入任务中心后读取只读摘要。")
        self.load_tasks_button = QPushButton("加载最近任务")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)
        title = QLabel("首页")
        title.setObjectName("screenTitle")
        root.addWidget(title)
        grid = QGridLayout()
        for index, key in enumerate(["workspace", "index", "documents", "chunks"]):
            grid.addWidget(self._card(key), index // 2, index % 2)
        root.addLayout(grid)
        root.addWidget(QLabel("最近任务"))
        root.addWidget(self.load_tasks_button)
        root.addWidget(self.recent_tasks, 1)
        self.load_tasks_button.clicked.connect(self.load_recent_tasks)
        self.setStyleSheet("#screenTitle { font-size: 24px; font-weight: 600; color: #1F2937; } QLabel { color: #1F2937; }")

    def render_status(self, model: Dict[str, Any]) -> None:
        data = model.get("data") or {}
        state = model.get("state", "error")
        if state == "error":
            errors = "; ".join(item.get("message", "") for item in model.get("errors", []))
            self.cards["workspace"].setText(f"workspace\n{errors or 'service unavailable'}")
            return
        self.cards["workspace"].setText(f"workspace\n{data.get('workspace_path', '')}")
        index_status = str(data.get("index_status") or "missing")
        self.cards["index"].setText(f"index status\n{index_status}")
        self.cards["documents"].setText(f"documents\n{data.get('document_count', 0)}")
        self.cards["chunks"].setText(f"chunks\n{data.get('chunk_count', 0)}")

    def render_tasks(self, model: Dict[str, Any]) -> None:
        self.recent_tasks.clear()
        rows = (model.get("data") or {}).get("tasks", [])
        if not rows:
            self.recent_tasks.addItem("没有最近任务记录。")
            return
        for task in rows[:5]:
            self.recent_tasks.addItem(f"{task.get('status')} | {task.get('title')} | {task.get('progress_percent')}%")

    def load_recent_tasks(self) -> None:
        if self.task_vm is None:
            return
        self.render_tasks(self.task_vm.load_recent_tasks(limit=5, offset=0))

    def _card(self, key: str) -> QFrame:
        card = QFrame()
        card.setObjectName("summaryCard")
        layout = QVBoxLayout(card)
        label = QLabel(f"{key}\nloading")
        label.setWordWrap(True)
        if key == "index":
            layout.addWidget(StatusBadge("read-only", tone_for_status("info")))
        layout.addWidget(label)
        self.cards[key] = label
        card.setStyleSheet("#summaryCard { background: #FFFFFF; border: 1px solid #D8DEE8; border-radius: 8px; padding: 12px; }")
        return card
