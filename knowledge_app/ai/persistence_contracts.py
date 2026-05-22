"""Pure AI persistence contract validators.

The functions in this module validate static model fields only. They do not
read paths, write files, spawn processes, import SQLite, or call core services.
"""

from __future__ import annotations

from knowledge_app.ai.persistence_models import (
    AIBackupInclusion,
    AIMigrationPlan,
    AIPersistenceModelValidationError,
    AIPersistencePlan,
    AIStorageLayout,
    AIStorageManifest,
)


class AIPersistenceContractValidationError(ValueError):
    """Raised when a static persistence contract is violated."""


def validate_storage_manifest(
    manifest: AIStorageManifest,
    workspace_root: str | None = None,
    install_root: str | None = None,
) -> AIStorageManifest:
    """Validate manifest directory boundaries and derived-index markers."""

    try:
        manifest.validate(workspace_root=workspace_root, install_root=install_root)
    except AIPersistenceModelValidationError as exc:
        raise AIPersistenceContractValidationError(str(exc)) from exc
    if manifest.source_of_truth.get("indexes") != "derived":
        raise AIPersistenceContractValidationError("indexes must be marked as derived")
    if manifest.derived_indexes.get("derived_only") is not True:
        raise AIPersistenceContractValidationError("manifest indexes must be derived only")
    if manifest.derived_indexes.get("rebuildable") is not True:
        raise AIPersistenceContractValidationError("manifest indexes must be rebuildable")
    if manifest.indexes_derived_only is not True:
        raise AIPersistenceContractValidationError("indexes must be derived only")
    if manifest.indexes_rebuildable is not True:
        raise AIPersistenceContractValidationError("derived indexes must be rebuildable")
    return manifest


def validate_storage_layout(layout: AIStorageLayout) -> AIStorageLayout:
    """Validate workspace-scoped storage layout and derived-index boundaries."""

    try:
        layout.validate()
    except AIPersistenceModelValidationError as exc:
        raise AIPersistenceContractValidationError(str(exc)) from exc
    validate_storage_manifest(layout.manifest, layout.workspace_root, layout.install_root)
    if layout.manifest.source_of_truth.get("indexes") != "derived":
        raise AIPersistenceContractValidationError("indexes must be marked as derived")
    if layout.indexes_derived_only is not True:
        raise AIPersistenceContractValidationError("indexes must be derived only")
    if layout.indexes_rebuildable is not True:
        raise AIPersistenceContractValidationError("derived indexes must be rebuildable")
    if layout.storage_growth_limit_mb <= 0:
        raise AIPersistenceContractValidationError("storage growth limit is required")
    return layout


def validate_backup_inclusion(policy: AIBackupInclusion) -> AIBackupInclusion:
    """Validate explicit backup flags and privacy-warning acknowledgement."""

    try:
        policy.validate()
    except AIPersistenceModelValidationError as exc:
        raise AIPersistenceContractValidationError(str(exc)) from exc
    includes_ai_data = (
        policy.include_ai_conversations
        or policy.include_ai_memory
        or policy.include_ai_drafts
        or policy.include_ai_indexes
    )
    if includes_ai_data and not policy.ai_data_privacy_warning_acknowledged:
        raise AIPersistenceContractValidationError("including AI data requires privacy warning acknowledgement")
    return policy


def validate_no_startup_scan_contract(plan: AIPersistencePlan) -> AIPersistencePlan:
    """Validate startup and performance gates for AI storage."""

    try:
        plan.validate()
    except AIPersistenceModelValidationError as exc:
        raise AIPersistenceContractValidationError(str(exc)) from exc
    if plan.scan_all:
        raise AIPersistenceContractValidationError("startup contract must not scan all AI data")
    if plan.startup_scan_conversations:
        raise AIPersistenceContractValidationError("startup must not scan ai/conversations")
    if plan.startup_scan_memory:
        raise AIPersistenceContractValidationError("startup must not scan ai/memory")
    if plan.startup_scan_drafts:
        raise AIPersistenceContractValidationError("startup must not scan ai/drafts")
    if not plan.list_conversations_paginated:
        raise AIPersistenceContractValidationError("conversation listing must be paginated")
    if not plan.list_memories_paginated:
        raise AIPersistenceContractValidationError("memory listing must be paginated")
    if plan.conversation_page_size <= 0 or plan.memory_page_size <= 0:
        raise AIPersistenceContractValidationError("pagination page sizes must be positive")
    if plan.storage_growth_limit_mb <= 0:
        raise AIPersistenceContractValidationError("storage growth limit is required")
    return plan


def validate_no_formal_search_injection(plan: AIPersistencePlan) -> AIPersistencePlan:
    """Validate that AI persistence data cannot enter formal search results."""

    try:
        plan.validate()
    except AIPersistenceModelValidationError as exc:
        raise AIPersistenceContractValidationError(str(exc)) from exc
    if plan.inject_into_formal_search:
        raise AIPersistenceContractValidationError("AI persistence data must not enter formal search")
    return plan


def validate_privacy_mode_no_write(policy: AIPersistencePlan) -> AIPersistencePlan:
    """Validate that privacy mode expresses no persistent write."""

    try:
        policy.validate()
    except AIPersistenceModelValidationError as exc:
        raise AIPersistenceContractValidationError(str(exc)) from exc
    if policy.privacy_mode and policy.would_write_persistent_data:
        raise AIPersistenceContractValidationError("privacy mode must not write persistent AI data")
    return policy


def validate_migration_requires_plan_snapshot_approval(plan: AIMigrationPlan) -> AIMigrationPlan:
    """Validate static migration lifecycle gates."""

    try:
        plan.validate()
    except AIPersistenceModelValidationError as exc:
        raise AIPersistenceContractValidationError(str(exc)) from exc
    if plan.plan_first is not True:
        raise AIPersistenceContractValidationError("migration must be plan-first")
    if plan.dry_run is not True:
        raise AIPersistenceContractValidationError("migration plan must be dry-run")
    if plan.would_modify is not False:
        raise AIPersistenceContractValidationError("static migration plan must not modify")
    if plan.requires_snapshot is not True:
        raise AIPersistenceContractValidationError("migration requires snapshot")
    if plan.requires_approval is not True:
        raise AIPersistenceContractValidationError("migration requires approval")
    if plan.rollback_plan is None:
        raise AIPersistenceContractValidationError("migration requires rollback plan")
    if plan.silent_migration:
        raise AIPersistenceContractValidationError("silent migration is forbidden")
    if type(plan.rebuild_derived_index) is not bool:
        raise AIPersistenceContractValidationError("rebuild_derived_index must be explicitly boolean")
    return plan
