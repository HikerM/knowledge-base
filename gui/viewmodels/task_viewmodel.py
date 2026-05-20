"""Read-only task summary ViewModel."""

from __future__ import annotations

from typing import Any, Dict


class TaskViewModel:
    def __init__(self, adapter: Any):
        self.adapter = adapter
        self.summary: Dict[str, Any] | None = None
        self.detail: Dict[str, Any] | None = None

    def load_recent_tasks(self, limit: int = 25, offset: int = 0) -> Dict[str, Any]:
        self.summary = self.adapter.load_recent_tasks(limit=limit, offset=offset)
        return self.summary

    def load_task_detail(self, task_id: str, tail: int = 80) -> Dict[str, Any]:
        self.detail = self.adapter.load_task_detail(task_id=task_id, tail=tail)
        return self.detail
