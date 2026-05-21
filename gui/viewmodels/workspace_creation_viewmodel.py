"""Workspace creation plan ViewModel."""

from __future__ import annotations

from typing import Any, Dict


class WorkspaceCreationViewModel:
    """Thin ViewModel for the plan-only workspace creation wizard."""

    def __init__(self, adapter: Any):
        self.adapter = adapter
        self.templates: Dict[str, Any] | None = None
        self.plan: Dict[str, Any] | None = None

    def list_templates(self) -> Dict[str, Any]:
        self.templates = self.adapter.list_workspace_templates()
        return self.templates

    def create_plan(self, target_path: str, workspace_name: str, template_id: str) -> Dict[str, Any]:
        self.plan = self.adapter.create_workspace_plan(
            {
                "target_path": target_path,
                "workspace_name": workspace_name,
                "template_id": template_id,
                "create_backups_directory": True,
            }
        )
        return self.plan

    @property
    def template_rows(self) -> list[Dict[str, Any]]:
        return list(((self.templates or {}).get("data") or {}).get("templates") or [])

    @property
    def plan_data(self) -> Dict[str, Any]:
        return dict((self.plan or {}).get("data") or {})
