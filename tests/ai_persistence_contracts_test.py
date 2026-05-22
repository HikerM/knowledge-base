#!/usr/bin/env python3
"""AI persistence contract validator tests."""

from __future__ import annotations

import re
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.persistence_contracts import (  # noqa: E402
    AIPersistenceContractValidationError,
    validate_backup_inclusion,
    validate_migration_requires_plan_snapshot_approval,
    validate_no_formal_search_injection,
    validate_no_startup_scan_contract,
    validate_privacy_mode_no_write,
    validate_storage_layout,
)
from knowledge_app.ai.persistence_models import (  # noqa: E402
    AIBackupInclusion,
    AIMigrationPlan,
    AIPersistencePlan,
    AIRollbackPlan,
    AIStorageLayout,
    AIStorageManifest,
)


def valid_manifest() -> AIStorageManifest:
    return AIStorageManifest(
        schema_version="ai-storage-manifest-v1",
        workspace_id="workspace_01",
    )


def valid_layout() -> AIStorageLayout:
    workspace = "D:/workspaces/pkb"
    return AIStorageLayout(
        schema_version="0.1",
        workspace_id="workspace_01",
        workspace_root=workspace,
        storage_root=f"{workspace}/ai",
        conversations_path=f"{workspace}/ai/conversations",
        memory_path=f"{workspace}/ai/memory",
        drafts_path=f"{workspace}/ai/drafts",
        indexes_path=f"{workspace}/ai/indexes",
        manifest=valid_manifest(),
        install_root="D:/Program Files/PersonalKnowledgeBase",
    )


def valid_persistence_plan() -> AIPersistencePlan:
    return AIPersistencePlan(
        schema_version="0.1",
        plan_id="plan_01",
        workspace_id="workspace_01",
        layout=valid_layout(),
        scan_all=False,
        startup_scan_conversations=False,
        startup_scan_memory=False,
        list_conversations_paginated=True,
        list_memories_paginated=True,
        storage_growth_limit_mb=1024,
    )


def valid_rollback_plan() -> AIRollbackPlan:
    return AIRollbackPlan(
        schema_version="0.1",
        rollback_id="rollback_01",
        workspace_id="workspace_01",
        restore_paths=["ai/conversations/"],
        remove_paths=["ai/.migration/mig_01/"],
        validation_commands=["python tests/ai_persistence_contracts_test.py"],
    )


def valid_migration_plan() -> AIMigrationPlan:
    return AIMigrationPlan(
        schema_version="0.1",
        migration_id="mig_01",
        workspace_id="workspace_01",
        source_schema_versions={"conversation": "conversation-record-v1"},
        target_schema_versions={"conversation": "conversation-record-v2"},
        rollback_plan=valid_rollback_plan(),
        actions=["mark derived indexes stale"],
        impacted_paths=["ai/conversations/"],
        estimated_record_counts={"conversation": 10},
        requires_snapshot=True,
        requires_approval=True,
        silent_migration=False,
        rebuild_derived_index=False,
        validation_commands=["python tests/ai_persistence_models_test.py"],
    )


def expect_contract_error(model_factory) -> None:
    try:
        model_factory()
    except AIPersistenceContractValidationError:
        return
    raise AssertionError("expected AIPersistenceContractValidationError")


def assert_valid_layout_passes() -> None:
    layout = validate_storage_layout(valid_layout())
    if layout.indexes_rebuildable is not True:
        raise AssertionError("derived indexes must be rebuildable")
    if layout.manifest.source_of_truth["indexes"] != "derived":
        raise AssertionError("manifest indexes must be derived")


def assert_backup_flags_default_false() -> None:
    policy = validate_backup_inclusion(AIBackupInclusion())
    payload = policy.to_dict()
    if payload["include_ai_conversations"] is not False:
        raise AssertionError("backup conversations default must be false")
    if payload["include_ai_memory"] is not False:
        raise AssertionError("backup memory default must be false")
    if payload["include_ai_drafts"] is not False:
        raise AssertionError("backup drafts default must be false")

    expect_contract_error(
        lambda: validate_backup_inclusion(AIBackupInclusion(include_ai_conversations=True))
    )


def assert_privacy_mode_no_write() -> None:
    plan = valid_persistence_plan()
    privacy_plan = AIPersistencePlan(
        schema_version=plan.schema_version,
        plan_id=plan.plan_id,
        workspace_id=plan.workspace_id,
        layout=plan.layout,
        privacy_mode=True,
        would_write_persistent_data=False,
    )
    validate_privacy_mode_no_write(privacy_plan)

    expect_contract_error(
        lambda: validate_privacy_mode_no_write(
            AIPersistencePlan(
                schema_version=plan.schema_version,
                plan_id=plan.plan_id,
                workspace_id=plan.workspace_id,
                layout=plan.layout,
                privacy_mode=True,
                would_write_persistent_data=True,
            )
        )
    )


def assert_migration_without_snapshot_rejected() -> None:
    plan = valid_migration_plan()
    expect_contract_error(
        lambda: validate_migration_requires_plan_snapshot_approval(
            AIMigrationPlan(
                schema_version=plan.schema_version,
                migration_id=plan.migration_id,
                workspace_id=plan.workspace_id,
                source_schema_versions=plan.source_schema_versions,
                target_schema_versions=plan.target_schema_versions,
                rollback_plan=plan.rollback_plan,
                requires_snapshot=False,
                requires_approval=True,
                silent_migration=False,
            )
        )
    )


def assert_migration_without_approval_rejected() -> None:
    plan = valid_migration_plan()
    expect_contract_error(
        lambda: validate_migration_requires_plan_snapshot_approval(
            AIMigrationPlan(
                schema_version=plan.schema_version,
                migration_id=plan.migration_id,
                workspace_id=plan.workspace_id,
                source_schema_versions=plan.source_schema_versions,
                target_schema_versions=plan.target_schema_versions,
                rollback_plan=plan.rollback_plan,
                requires_snapshot=True,
                requires_approval=False,
                silent_migration=False,
            )
        )
    )


def assert_migration_without_rollback_rejected() -> None:
    plan = valid_migration_plan()
    expect_contract_error(
        lambda: validate_migration_requires_plan_snapshot_approval(
            AIMigrationPlan(
                schema_version=plan.schema_version,
                migration_id=plan.migration_id,
                workspace_id=plan.workspace_id,
                source_schema_versions=plan.source_schema_versions,
                target_schema_versions=plan.target_schema_versions,
                rollback_plan=None,  # type: ignore[arg-type]
            )
        )
    )


def assert_silent_migration_rejected() -> None:
    plan = valid_migration_plan()
    expect_contract_error(
        lambda: validate_migration_requires_plan_snapshot_approval(
            AIMigrationPlan(
                schema_version=plan.schema_version,
                migration_id=plan.migration_id,
                workspace_id=plan.workspace_id,
                source_schema_versions=plan.source_schema_versions,
                target_schema_versions=plan.target_schema_versions,
                rollback_plan=plan.rollback_plan,
                silent_migration=True,
            )
        )
    )


def assert_valid_migration_passes() -> None:
    plan = validate_migration_requires_plan_snapshot_approval(valid_migration_plan())
    if type(plan.rebuild_derived_index) is not bool:
        raise AssertionError("rebuild_derived_index must be explicitly boolean")


def assert_startup_scan_contract_rejects_scan_all() -> None:
    plan = valid_persistence_plan()
    expect_contract_error(
        lambda: validate_no_startup_scan_contract(
            AIPersistencePlan(
                schema_version=plan.schema_version,
                plan_id=plan.plan_id,
                workspace_id=plan.workspace_id,
                layout=plan.layout,
                scan_all=True,
            )
        )
    )


def assert_startup_scan_contract_rejects_ai_storage_scan() -> None:
    plan = valid_persistence_plan()
    expect_contract_error(
        lambda: validate_no_startup_scan_contract(
            AIPersistencePlan(
                schema_version=plan.schema_version,
                plan_id=plan.plan_id,
                workspace_id=plan.workspace_id,
                layout=plan.layout,
                startup_scan_conversations=True,
            )
        )
    )
    expect_contract_error(
        lambda: validate_no_startup_scan_contract(
            AIPersistencePlan(
                schema_version=plan.schema_version,
                plan_id=plan.plan_id,
                workspace_id=plan.workspace_id,
                layout=plan.layout,
                startup_scan_memory=True,
            )
        )
    )


def assert_list_without_pagination_rejected() -> None:
    plan = valid_persistence_plan()
    expect_contract_error(
        lambda: validate_no_startup_scan_contract(
            AIPersistencePlan(
                schema_version=plan.schema_version,
                plan_id=plan.plan_id,
                workspace_id=plan.workspace_id,
                layout=plan.layout,
                list_conversations_paginated=False,
            )
        )
    )
    expect_contract_error(
        lambda: validate_no_startup_scan_contract(
            AIPersistencePlan(
                schema_version=plan.schema_version,
                plan_id=plan.plan_id,
                workspace_id=plan.workspace_id,
                layout=plan.layout,
                list_memories_paginated=False,
            )
        )
    )


def assert_no_formal_search_injection() -> None:
    validate_no_formal_search_injection(valid_persistence_plan())
    plan = valid_persistence_plan()
    expect_contract_error(
        lambda: validate_no_formal_search_injection(
            AIPersistencePlan(
                schema_version=plan.schema_version,
                plan_id=plan.plan_id,
                workspace_id=plan.workspace_id,
                layout=plan.layout,
                inject_into_formal_search=True,
            )
        )
    )


def assert_no_forbidden_imports_in_persistence_modules() -> None:
    forbidden = {"sqlite3", "subprocess", "knowledge_core"}
    for relative_path in [
        "knowledge_app/ai/persistence_models.py",
        "knowledge_app/ai/persistence_contracts.py",
    ]:
        source = (SOURCE_ROOT / relative_path).read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if not re.match(r"^(import|from)\s+", stripped):
                continue
            for name in forbidden:
                if re.search(rf"\b{name}\b", stripped):
                    raise AssertionError(f"{relative_path} imports forbidden dependency {name}: {stripped}")


def main() -> int:
    assert_valid_layout_passes()
    assert_backup_flags_default_false()
    assert_privacy_mode_no_write()
    assert_migration_without_snapshot_rejected()
    assert_migration_without_approval_rejected()
    assert_migration_without_rollback_rejected()
    assert_silent_migration_rejected()
    assert_valid_migration_passes()
    assert_startup_scan_contract_rejects_scan_all()
    assert_startup_scan_contract_rejects_ai_storage_scan()
    assert_list_without_pagination_rejected()
    assert_no_formal_search_injection()
    assert_no_forbidden_imports_in_persistence_modules()

    print("AI persistence contract tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
