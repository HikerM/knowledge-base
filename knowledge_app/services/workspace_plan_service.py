"""Plan-only workspace mutation service."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List

from knowledge_core.config import DEFAULT_CONFIG_FILES

from knowledge_app.models.plan_result import PlanResult
from knowledge_app.services.mutation_plan_helpers import (
    elapsed_ms,
    read_document_counts,
    relative_to_workspace,
    resolve_workspace_path,
)


WORKSPACE_CORE_PATHS = [
    "knowledge",
    "config",
    "templates",
    "reports",
    "docs",
    "README.md",
    "AGENTS.md",
    "workspace.yaml",
]


class WorkspacePlanService:
    """Build dry-run workspace lifecycle plans without mutating the workspace."""

    def __init__(self, workspace_path: Path | str | None = None):
        self.workspace_path = resolve_workspace_path(workspace_path)

    def workspace_upgrade_plan(self) -> PlanResult:
        start = time.perf_counter()
        workspace_yaml = self.workspace_path / "workspace.yaml"
        warnings: List[str] = []
        if not workspace_yaml.exists():
            warnings.append("workspace.yaml missing; v1.5.0 only plans a future metadata bootstrap/upgrade path")

        return PlanResult(
            plan_type="workspace_upgrade",
            summary="Plan a future workspace metadata/schema upgrade; no files or SQLite schema are modified.",
            target={
                "workspace_path": str(self.workspace_path),
                "workspace_yaml": relative_to_workspace(workspace_yaml, self.workspace_path),
                "current_schema_version": "unknown" if not workspace_yaml.exists() else "declared_in_workspace_yaml",
                "target_schema_version": "future",
            },
            affected_files=[
                {
                    "scope": "workspace_metadata",
                    "count": 1 if workspace_yaml.exists() else 0,
                    "count_known": True,
                    "count_source": "path_exists",
                    "paths_sample": [relative_to_workspace(workspace_yaml, self.workspace_path)] if workspace_yaml.exists() else [],
                }
            ],
            affected_configs=[
                {
                    "path": rel_path,
                    "operation": "would_validate_for_future_upgrade",
                    "exists": (self.workspace_path / rel_path).exists(),
                    "would_overwrite": False,
                }
                for rel_path in sorted(DEFAULT_CONFIG_FILES.keys())
            ],
            affected_categories=[],
            affected_sources=[],
            risks=[
                "future upgrade execution may require config migration and explicit reindex",
                "SQLite remains derived index data and must not be treated as the migration source of truth",
            ],
            blockers=[],
            warnings=warnings,
            requires_snapshot=True,
            requires_confirmation=True,
            reversible=True,
            rollback_plan=[
                "No rollback is needed for this plan-only command because no files are modified.",
                "For a future execute phase, restore workspace metadata and config from the pre-upgrade snapshot.",
            ],
            validation_commands=[
                "python scripts/kb.py workspace-status",
                "python scripts/kb.py audit",
                "python scripts/kb.py secret-scan",
            ],
            actions=[
                {
                    "action": "plan_workspace_upgrade",
                    "status": "planned_not_executed",
                    "requires_future_execute_phase": True,
                }
            ],
            elapsed_ms=elapsed_ms(start),
        )

    def workspace_archive_plan(self) -> PlanResult:
        start = time.perf_counter()
        counts, warnings = read_document_counts(self.workspace_path)
        return PlanResult(
            plan_type="workspace_archive",
            summary="Plan archiving the current workspace; no files are moved and workspace metadata is not changed.",
            target={
                "workspace_path": str(self.workspace_path),
                "archive_semantics": "mark or move workspace only in a future execute phase",
            },
            affected_files=[self._workspace_file_entry(counts)],
            affected_configs=[
                {
                    "path": "workspace.yaml",
                    "operation": "would_mark_workspace_archived",
                    "exists": (self.workspace_path / "workspace.yaml").exists(),
                    "would_overwrite": False,
                }
            ],
            affected_categories=[],
            affected_sources=[],
            risks=[
                "archived workspace must remain restorable and explicitly searchable",
                "archive is not delete and must not hide quarantine risk semantics",
            ],
            blockers=[],
            warnings=warnings,
            requires_snapshot=True,
            requires_confirmation=True,
            reversible=True,
            rollback_plan=[
                "Restore workspace archive status from the pre-archive snapshot.",
                "If a future execute phase moves directories, restore the original workspace path from snapshot/backup.",
            ],
            validation_commands=[
                "python scripts/kb.py workspace-status",
                "python scripts/kb.py audit",
            ],
            actions=[
                {
                    "action": "plan_archive_workspace",
                    "status": "planned_not_executed",
                    "workspace_path": str(self.workspace_path),
                }
            ],
            elapsed_ms=elapsed_ms(start),
        )

    def workspace_delete_plan(self) -> PlanResult:
        start = time.perf_counter()
        counts, warnings = read_document_counts(self.workspace_path)
        evidence = self._non_empty_evidence()
        blockers: List[str] = []
        if evidence:
            blockers.append(f"workspace is not empty: {', '.join(evidence)}")
        elif counts["known"] and counts["document_count"] > 0:
            blockers.append(f"workspace index contains {counts['document_count']} document(s)")
        elif not counts["known"]:
            blockers.append("cannot verify workspace is empty without index metadata or an explicit scan")

        return PlanResult(
            plan_type="workspace_delete",
            summary="Plan deleting an empty workspace only; blocked for non-empty workspaces.",
            target={
                "workspace_path": str(self.workspace_path),
                "empty_required": True,
            },
            affected_files=[self._workspace_file_entry(counts)],
            affected_configs=[
                {
                    "path": rel_path,
                    "operation": "would_delete_if_unblocked",
                    "exists": (self.workspace_path / rel_path).exists(),
                    "would_overwrite": False,
                }
                for rel_path in WORKSPACE_CORE_PATHS
            ],
            affected_categories=[],
            affected_sources=[],
            risks=[
                "workspace delete is destructive; .kb/index.sqlite cannot restore Markdown, config, templates, or reports",
                "Git is optional and must not be the required recovery mechanism",
            ],
            blockers=blockers,
            warnings=warnings,
            requires_snapshot=True,
            requires_confirmation=True,
            reversible=False,
            rollback_plan=[
                "Restore the workspace directory from the pre-delete local snapshot or backup.",
                "Run explicit reindex after restore because SQLite is a derived index.",
            ],
            validation_commands=[
                "python scripts/kb.py workspace-status",
                "python scripts/kb.py audit",
                "python scripts/kb.py secret-scan",
            ],
            actions=[
                {
                    "action": "plan_delete_empty_workspace",
                    "status": "blocked" if blockers else "planned_not_executed",
                    "workspace_path": str(self.workspace_path),
                }
            ],
            elapsed_ms=elapsed_ms(start),
        )

    @staticmethod
    def _workspace_file_entry(counts: Dict[str, object]) -> Dict[str, object]:
        return {
            "scope": "workspace",
            "count": int(counts["document_count"]),
            "count_known": bool(counts["known"]),
            "count_source": str(counts["count_source"]),
            "layer_counts": dict(counts["layer_counts"]),
            "status_counts": dict(counts["status_counts"]),
            "paths_sample": list(counts["paths_sample"]),
        }

    def _non_empty_evidence(self) -> List[str]:
        evidence: List[str] = []
        for rel_path in WORKSPACE_CORE_PATHS:
            path = self.workspace_path / rel_path
            if not path.exists():
                continue
            if path.is_file():
                evidence.append(rel_path)
                continue
            try:
                if any(path.iterdir()):
                    evidence.append(rel_path)
            except OSError:
                evidence.append(rel_path)
        return evidence
