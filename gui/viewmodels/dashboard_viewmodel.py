"""Dashboard summary ViewModel."""

from __future__ import annotations

from typing import Any, Dict


class DashboardViewModel:
    def __init__(self, adapter: Any):
        self.adapter = adapter
        self.summary: Dict[str, Any] | None = None

    def load_summary(self) -> Dict[str, Any]:
        self.summary = self.adapter.load_home_summary()
        return self.summary
