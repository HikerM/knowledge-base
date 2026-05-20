"""Workspace status ViewModel."""

from __future__ import annotations

from typing import Any, Dict


class WorkspaceViewModel:
    def __init__(self, adapter: Any):
        self.adapter = adapter
        self.status: Dict[str, Any] | None = None

    def load_status(self) -> Dict[str, Any]:
        self.status = self.adapter.load_workspace_status()
        return self.status

    @property
    def data(self) -> Dict[str, Any]:
        return dict((self.status or {}).get("data") or {})
