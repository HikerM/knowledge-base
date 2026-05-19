"""Plan-only template mutation service."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

from knowledge_core.config import DEFAULT_CATEGORIES, DEFAULT_CONFIG_FILES

from knowledge_app.models.operation_result import OperationResult
from knowledge_app.models.plan_result import PlanResult
from knowledge_app.services.mutation_plan_helpers import (
    elapsed_ms,
    load_categories_for_workspace,
    load_sources_for_workspace,
    relative_to_workspace,
    resolve_workspace_path,
)


DEVELOPER_TEMPLATE_ID = "developer"
DEVELOPER_TEMPLATE_FILES = [
    "templates/knowledge-card.md",
    "templates/raw-note.md",
    "templates/rule.md",
    "templates/snippet.md",
    "templates/checklist.md",
    "templates/codex-task.md",
    "templates/weekly-report.md",
]


class TemplatePlanService:
    """Build dry-run template plans without writing workspace config."""

    def __init__(self, workspace_path: Path | str | None = None):
        self.workspace_path = resolve_workspace_path(workspace_path)

    def list_templates(self) -> OperationResult:
        start = time.perf_counter()
        payload = {
            "count": 1,
            "results": [
                {
                    "template_id": DEVELOPER_TEMPLATE_ID,
                    "display_name": "Developer Knowledge Base",
                    "version": "1.0.0",
                    "description": "Engineering rules, snippets, checklists, research notes, and Agent context.",
                    "config_files": sorted(DEFAULT_CONFIG_FILES.keys()),
                    "template_files": list(DEVELOPER_TEMPLATE_FILES),
                    "categories": sorted(DEFAULT_CATEGORIES.keys()),
                }
            ],
            "elapsed_ms": elapsed_ms(start),
        }
        return OperationResult(success=True, data=payload, elapsed_ms=payload["elapsed_ms"])

    def apply_template_plan(self, template_id: str, workspace_path: Path | str | None = None) -> PlanResult:
        start = time.perf_counter()
        target_workspace = resolve_workspace_path(workspace_path) if workspace_path else self.workspace_path
        blockers: List[str] = []
        if template_id != DEVELOPER_TEMPLATE_ID:
            blockers.append(f"unknown template_id: {template_id}")

        affected_configs = self._affected_configs(target_workspace) if not blockers else []
        affected_files = self._affected_template_files(target_workspace) if not blockers else []
        affected_categories = self._affected_categories(target_workspace) if not blockers else []
        affected_sources = self._affected_sources(target_workspace) if not blockers else []
        conflicts = [item for item in affected_configs if item.get("conflict")]
        warnings = [
            "template apply is plan-only; existing workspace config is preserved",
        ]
        if conflicts:
            warnings.append(f"{len(conflicts)} existing config file(s) differ from the built-in template and require manual merge")

        return PlanResult(
            plan_type="template_apply",
            summary="Plan applying a template to a workspace; no config, template, source, or category files are written.",
            target={
                "template_id": template_id,
                "workspace_path": str(target_workspace),
            },
            affected_files=affected_files,
            affected_configs=affected_configs,
            affected_categories=affected_categories,
            affected_sources=affected_sources,
            risks=[
                "template defaults must not overwrite user-owned workspace configuration",
                "template sources must still enter raw -> distilled -> review -> formal before project use",
            ],
            blockers=blockers,
            warnings=warnings,
            requires_snapshot=True,
            requires_confirmation=True,
            reversible=True,
            rollback_plan=[
                "No rollback is needed for this plan-only command because no files are modified.",
                "For a future execute phase, restore config/ and templates/ from the pre-apply snapshot.",
            ],
            validation_commands=[
                "python scripts/kb.py workspace-status",
                "python scripts/kb.py category-summary",
                "python scripts/kb.py audit",
                "python scripts/kb.py secret-scan",
            ],
            actions=[
                {
                    "action": "plan_apply_template_without_overwrite",
                    "status": "blocked" if blockers else "planned_not_executed",
                    "template_id": template_id,
                },
                {
                    "action": "plan_manual_merge_for_conflicting_config",
                    "status": "planned_not_executed",
                    "conflict_count": len(conflicts),
                },
            ],
            elapsed_ms=elapsed_ms(start),
        )

    def _affected_configs(self, workspace_path: Path) -> List[Dict[str, Any]]:
        affected: List[Dict[str, Any]] = []
        for rel_path, template_content in sorted(DEFAULT_CONFIG_FILES.items()):
            path = workspace_path / rel_path
            exists = path.exists()
            conflict = False
            if exists:
                try:
                    conflict = path.read_text(encoding="utf-8") != template_content
                except OSError:
                    conflict = True
            affected.append(
                {
                    "path": rel_path,
                    "operation": "preserve_existing" if exists else "would_add",
                    "exists": exists,
                    "conflict": conflict,
                    "would_overwrite": False,
                }
            )
        return affected

    def _affected_template_files(self, workspace_path: Path) -> List[Dict[str, Any]]:
        return [
            {
                "path": rel_path,
                "operation": "preserve_existing" if (workspace_path / rel_path).exists() else "would_add",
                "exists": (workspace_path / rel_path).exists(),
                "would_overwrite": False,
            }
            for rel_path in DEVELOPER_TEMPLATE_FILES
        ]

    def _affected_categories(self, workspace_path: Path) -> List[Dict[str, Any]]:
        current = load_categories_for_workspace(workspace_path)
        results: List[Dict[str, Any]] = []
        for category_id, template_meta in sorted(DEFAULT_CATEGORIES.items()):
            existing = current.get(category_id)
            conflict = bool(existing and existing.get("path") and existing.get("path") != template_meta.get("path"))
            results.append(
                {
                    "category_id": category_id,
                    "operation": "preserve_existing" if existing else "would_add",
                    "exists": bool(existing),
                    "conflict": conflict,
                    "template_path": str(template_meta.get("path") or ""),
                    "current_path": str((existing or {}).get("path") or ""),
                }
            )
        return results

    def _affected_sources(self, workspace_path: Path) -> List[Dict[str, Any]]:
        current_sources = load_sources_for_workspace(workspace_path)
        source_names = {str(source.get("name") or "") for source in current_sources}
        template_source = {
            "name": "OpenAI Codex Docs",
            "category": "ai_agent",
            "type": "official_docs",
            "url": "https://developers.openai.com/codex",
        }
        exists = template_source["name"] in source_names
        return [
            {
                **template_source,
                "operation": "preserve_existing" if exists else "would_add",
                "exists": exists,
                "would_overwrite": False,
                "workspace_path": relative_to_workspace(workspace_path / "config" / "sources.yaml", workspace_path),
            }
        ]
