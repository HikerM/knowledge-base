"""Plan-only category mutation service."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

from knowledge_app.models.plan_result import PlanResult
from knowledge_app.services.mutation_plan_helpers import (
    elapsed_ms,
    load_categories_for_workspace,
    read_document_counts,
    relative_to_workspace,
    resolve_workspace_path,
    source_references_for_category,
)


class CategoryPlanService:
    """Build dry-run category plans without modifying files."""

    def __init__(self, workspace_path: Path | str | None = None):
        self.workspace_path = resolve_workspace_path(workspace_path)
        self.categories_path = self.workspace_path / "config" / "categories.yaml"

    def update_display_name_plan(self, category_id: str, new_display_name: str) -> PlanResult:
        start = time.perf_counter()
        categories = load_categories_for_workspace(self.workspace_path)
        blockers: List[str] = []
        warnings: List[str] = []
        category = categories.get(category_id)
        if not category:
            blockers.append(f"unknown category_id: {category_id}")
            category = {}
        if not new_display_name.strip():
            blockers.append("new_display_name must not be empty")

        old_display_name = str(category.get("display_name") or category_id)
        if category and old_display_name == new_display_name:
            warnings.append("new_display_name is identical to the current display_name")

        return PlanResult(
            plan_type="category_update_display_name",
            summary="Plan to update category display_name only; no path rename, Markdown edit, or index rebuild is performed.",
            target={
                "category_id": category_id,
                "old_display_name": old_display_name,
                "new_display_name": new_display_name,
                "workspace_path": str(self.workspace_path),
            },
            affected_files=[
                {
                    "scope": "markdown",
                    "count": 0,
                    "count_source": "not_applicable",
                    "note": "display_name change does not edit Markdown files",
                }
            ],
            affected_configs=[
                {
                    "path": relative_to_workspace(self.categories_path, self.workspace_path),
                    "operation": "would_update_field",
                    "field": f"{category_id}.display_name",
                    "would_overwrite": False,
                }
            ],
            affected_categories=[
                {
                    "category_id": category_id,
                    "old_display_name": old_display_name,
                    "new_display_name": new_display_name,
                    "path": str(category.get("path") or ""),
                }
            ],
            affected_sources=[],
            risks=[
                "display_name is presentation-only; treating it as category_id would break references",
            ],
            blockers=blockers,
            warnings=warnings,
            requires_snapshot=False,
            requires_confirmation=True,
            reversible=True,
            rollback_plan=[
                f"Restore {category_id}.display_name to {old_display_name!r} in config/categories.yaml.",
            ],
            validation_commands=[
                "python scripts/kb.py category-summary",
                f"python scripts/kb.py category-summary --category {category_id}",
            ],
            actions=[
                {
                    "action": "plan_update_config_field",
                    "status": "planned_not_executed",
                    "path": "config/categories.yaml",
                    "field": f"{category_id}.display_name",
                    "from": old_display_name,
                    "to": new_display_name,
                },
                {
                    "action": "plan_no_markdown_changes",
                    "status": "planned_not_executed",
                    "reason": "display_name does not affect category_id, path, or frontmatter",
                },
            ],
            elapsed_ms=elapsed_ms(start),
        )

    def archive_category_plan(self, category_id: str) -> PlanResult:
        start = time.perf_counter()
        categories = load_categories_for_workspace(self.workspace_path)
        category = categories.get(category_id)
        blockers: List[str] = []
        if not category:
            blockers.append(f"unknown category_id: {category_id}")
            category = {}
        counts, warnings = read_document_counts(self.workspace_path, category_id)
        sources = source_references_for_category(self.workspace_path, category_id)

        return PlanResult(
            plan_type="category_archive",
            summary="Plan to archive a category; no files are moved and no config is written in this phase.",
            target=self._category_target(category_id, category),
            affected_files=[self._affected_file_entry(category_id, counts)],
            affected_configs=[
                {
                    "path": relative_to_workspace(self.categories_path, self.workspace_path),
                    "operation": "would_set_category_status_archived",
                    "field": f"{category_id}.status",
                    "would_overwrite": False,
                }
            ],
            affected_categories=[self._category_record(category_id, category, "would_archive")],
            affected_sources=sources,
            risks=[
                "archiving changes default visibility in future search/category views",
                "quarantine content must remain risk-isolated and must not be hidden by ordinary archive semantics",
            ],
            blockers=blockers,
            warnings=warnings,
            requires_snapshot=True,
            requires_confirmation=True,
            reversible=True,
            rollback_plan=[
                f"Restore {category_id}.status to active or its previous value in config/categories.yaml.",
                "Run explicit index/reindex after a future execute phase if archive status affects indexed metadata.",
            ],
            validation_commands=[
                f"python scripts/kb.py category-summary --category {category_id}",
                "python scripts/kb.py audit",
            ],
            actions=[
                {
                    "action": "plan_set_category_status",
                    "status": "planned_not_executed",
                    "category_id": category_id,
                    "to": "archived",
                },
                {
                    "action": "plan_preserve_source_chain",
                    "status": "planned_not_executed",
                    "fields": ["source_url", "source_file", "promoted_from", "supersedes", "superseded_by"],
                },
            ],
            elapsed_ms=elapsed_ms(start),
        )

    def merge_category_plan(self, source_category_id: str, target_category_id: str) -> PlanResult:
        start = time.perf_counter()
        categories = load_categories_for_workspace(self.workspace_path)
        source = categories.get(source_category_id)
        target = categories.get(target_category_id)
        blockers: List[str] = []
        if not source:
            blockers.append(f"unknown source_category_id: {source_category_id}")
            source = {}
        if not target:
            blockers.append(f"unknown target_category_id: {target_category_id}")
            target = {}
        if source_category_id == target_category_id:
            blockers.append("source_category_id and target_category_id must be different")

        counts, warnings = read_document_counts(self.workspace_path, source_category_id)
        sources = source_references_for_category(self.workspace_path, source_category_id)

        return PlanResult(
            plan_type="category_merge",
            summary="Plan to merge one category into another; no Markdown, config, or index changes are executed.",
            target={
                "source_category_id": source_category_id,
                "target_category_id": target_category_id,
                "workspace_path": str(self.workspace_path),
            },
            affected_files=[self._affected_file_entry(source_category_id, counts)],
            affected_configs=[
                {
                    "path": relative_to_workspace(self.categories_path, self.workspace_path),
                    "operation": "would_mark_source_category_merged",
                    "field": f"{source_category_id}.merged_into",
                    "would_overwrite": False,
                },
                {
                    "path": "config/sources.yaml",
                    "operation": "would_review_source_category_references",
                    "source_reference_count": len(sources),
                    "would_overwrite": False,
                },
            ],
            affected_categories=[
                self._category_record(source_category_id, source, "would_merge_from"),
                self._category_record(target_category_id, target, "would_merge_into"),
            ],
            affected_sources=sources,
            risks=[
                "source and target categories may contain overlapping topic_id or canonical knowledge",
                "future execute phase may require frontmatter category updates and index rebuild",
                "reports may retain historical references to the source category",
            ],
            blockers=blockers,
            warnings=warnings,
            requires_snapshot=True,
            requires_confirmation=True,
            reversible=True,
            rollback_plan=[
                f"Restore {source_category_id}.status and merged_into fields in config/categories.yaml.",
                "Restore any future Markdown moves or frontmatter edits from the pre-merge snapshot.",
                "Run explicit reindex after rollback if a future execute phase changed indexed metadata.",
            ],
            validation_commands=[
                f"python scripts/kb.py category-summary --category {source_category_id}",
                f"python scripts/kb.py category-summary --category {target_category_id}",
                "python scripts/kb.py conflicts",
                "python scripts/kb.py audit",
            ],
            actions=[
                {
                    "action": "plan_mark_category_merged",
                    "status": "planned_not_executed",
                    "source_category_id": source_category_id,
                    "target_category_id": target_category_id,
                },
                {
                    "action": "plan_review_frontmatter_category_changes",
                    "status": "planned_not_executed",
                    "affected_document_count": counts["document_count"] if counts["known"] else None,
                },
            ],
            elapsed_ms=elapsed_ms(start),
        )

    def delete_category_plan(self, category_id: str) -> PlanResult:
        start = time.perf_counter()
        categories = load_categories_for_workspace(self.workspace_path)
        category = categories.get(category_id)
        blockers: List[str] = []
        if not category:
            blockers.append(f"unknown category_id: {category_id}")
            category = {}

        counts, warnings = read_document_counts(self.workspace_path, category_id)
        sources = source_references_for_category(self.workspace_path, category_id)
        if not counts["known"]:
            blockers.append("cannot verify category is empty without index metadata or an explicit scan")
        elif counts["document_count"] > 0:
            blockers.append(f"category is not empty: {counts['document_count']} indexed document(s)")
        if sources:
            blockers.append(f"category has {len(sources)} configured source reference(s)")

        return PlanResult(
            plan_type="category_delete",
            summary="Plan advanced delete for an empty category; blocked unless the category is empty and unreferenced.",
            target=self._category_target(category_id, category),
            affected_files=[self._affected_file_entry(category_id, counts)],
            affected_configs=[
                {
                    "path": relative_to_workspace(self.categories_path, self.workspace_path),
                    "operation": "would_remove_category_entry_if_unblocked",
                    "field": category_id,
                    "would_overwrite": False,
                }
            ],
            affected_categories=[self._category_record(category_id, category, "would_delete_if_unblocked")],
            affected_sources=sources,
            risks=[
                "delete is destructive and should be replaced by disable, archive, or merge for historical knowledge",
                "SQLite index cannot restore deleted Markdown or config",
            ],
            blockers=blockers,
            warnings=warnings,
            requires_snapshot=True,
            requires_confirmation=True,
            reversible=False,
            rollback_plan=[
                "Restore config/categories.yaml from the pre-delete local snapshot.",
                "Restore any future deleted files from the pre-delete local snapshot.",
                "Run explicit reindex after rollback if a future execute phase changed files.",
            ],
            validation_commands=[
                "python scripts/kb.py category-summary",
                f"python scripts/kb.py category-summary --category {category_id}",
                "python scripts/kb.py audit",
            ],
            actions=[
                {
                    "action": "plan_delete_empty_category_config",
                    "status": "blocked" if blockers else "planned_not_executed",
                    "category_id": category_id,
                }
            ],
            elapsed_ms=elapsed_ms(start),
        )

    def _category_target(self, category_id: str, category: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "category_id": category_id,
            "display_name": str(category.get("display_name") or category_id),
            "path": str(category.get("path") or ""),
            "status": str(category.get("status") or "active"),
            "workspace_path": str(self.workspace_path),
        }

    def _category_record(self, category_id: str, category: Dict[str, Any], operation: str) -> Dict[str, Any]:
        return {
            "category_id": category_id,
            "display_name": str(category.get("display_name") or category_id),
            "path": str(category.get("path") or ""),
            "status": str(category.get("status") or "active"),
            "operation": operation,
        }

    @staticmethod
    def _affected_file_entry(category_id: str, counts: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "scope": "category",
            "category_id": category_id,
            "count": int(counts["document_count"]),
            "count_known": bool(counts["known"]),
            "count_source": str(counts["count_source"]),
            "layer_counts": dict(counts["layer_counts"]),
            "status_counts": dict(counts["status_counts"]),
            "paths_sample": list(counts["paths_sample"]),
        }
