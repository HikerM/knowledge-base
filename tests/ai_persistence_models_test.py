#!/usr/bin/env python3
"""AI persistence static model tests."""

from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.persistence_models import (  # noqa: E402
    AIBackupInclusion,
    AIClearPlan,
    AIExportPlan,
    AIMigrationPlan,
    AIPersistenceModelValidationError,
    AIRollbackPlan,
    AIStorageLayout,
    AIStorageManifest,
)


def valid_manifest_payload() -> dict:
    return {
        "schema_version": "ai-storage-manifest-v1",
        "workspace_id": "workspace_01",
        "storage_layout_version": "ai-storage-layout-v1",
        "directories": {
            "conversations": "ai/conversations/",
            "memory": "ai/memory/",
            "drafts": "ai/drafts/",
            "indexes": "ai/indexes/",
        },
        "source_of_truth": {
            "conversations": "jsonl",
            "memory": "jsonl",
            "drafts": "jsonl",
            "indexes": "derived",
        },
        "privacy_mode_default": False,
        "schema_min_reader_version": "2.5.1-static-contract",
        "schema_writer_version": None,
        "indexes_derived_only": True,
        "indexes_rebuildable": True,
    }


def valid_layout_payload(workspace_root: str = "D:/workspaces/pkb") -> dict:
    workspace_root = workspace_root.replace("\\", "/").rstrip("/")
    return {
        "schema_version": "0.1",
        "workspace_id": "workspace_01",
        "workspace_root": workspace_root,
        "storage_root": f"{workspace_root}/ai",
        "conversations_path": f"{workspace_root}/ai/conversations",
        "memory_path": f"{workspace_root}/ai/memory",
        "drafts_path": f"{workspace_root}/ai/drafts",
        "indexes_path": f"{workspace_root}/ai/indexes",
        "manifest": valid_manifest_payload(),
        "install_root": "D:/Program Files/PersonalKnowledgeBase",
        "source_records_are_truth": True,
        "indexes_derived_only": True,
        "indexes_rebuildable": True,
        "storage_growth_limit_mb": 1024,
    }


def valid_rollback_payload() -> dict:
    return {
        "schema_version": "0.1",
        "rollback_id": "rollback_01",
        "workspace_id": "workspace_01",
        "ai_storage_only": True,
        "restore_paths": ["ai/conversations/"],
        "remove_paths": ["ai/.migration/mig_01/"],
        "conflicts": [],
        "privacy_impact": "rollback ai persistence files only",
        "backup_contains_ai_conversations": False,
        "backup_contains_ai_memory": False,
        "backup_contains_ai_drafts": False,
        "touches_knowledge": False,
        "touches_kb_index": False,
        "marks_derived_indexes_stale": True,
        "requires_approval": True,
        "validation_commands": ["python tests/ai_persistence_models_test.py"],
    }


def valid_migration_payload() -> dict:
    return {
        "schema_version": "0.1",
        "migration_id": "mig_01",
        "workspace_id": "workspace_01",
        "source_schema_versions": {"conversation": "conversation-record-v1"},
        "target_schema_versions": {"conversation": "conversation-record-v2"},
        "rollback_plan": valid_rollback_payload(),
        "dry_run": True,
        "would_modify": False,
        "blocked": False,
        "blockers": [],
        "actions": ["mark derived indexes stale"],
        "impacted_paths": ["ai/conversations/"],
        "estimated_record_counts": {"conversation": 10},
        "requires_snapshot": True,
        "requires_approval": True,
        "plan_first": True,
        "silent_migration": False,
        "rebuild_derived_index": False,
        "validation_commands": ["python tests/ai_persistence_contracts_test.py"],
        "privacy_warnings": [],
    }


def expect_model_error(model_factory) -> None:
    try:
        model_factory()
    except AIPersistenceModelValidationError:
        return
    raise AssertionError("expected AIPersistenceModelValidationError")


def assert_valid_layout_passes() -> None:
    layout = AIStorageLayout.from_dict(valid_layout_payload())
    serialized = layout.to_dict()
    restored = AIStorageLayout.from_dict(serialized)
    if restored.to_dict() != serialized:
        raise AssertionError("AIStorageLayout round-trip changed payload")
    if restored.storage_root.replace("\\", "/").endswith("/ai") is not True:
        raise AssertionError("storage root must be workspace ai directory")

    manifest = AIStorageManifest.from_dict(
        {
            "schema_version": "ai-storage-manifest-v1",
            "workspace_id": "workspace_01",
        }
    )
    if manifest.source_of_truth["indexes"] != "derived":
        raise AssertionError("minimal manifest must default indexes to derived")


def assert_manifest_directory_boundaries() -> None:
    AIStorageManifest.from_dict(valid_manifest_payload()).validate("D:/workspaces/pkb")

    payload = valid_manifest_payload()
    payload["directories"]["conversations"] = "knowledge/ai/conversations/"
    expect_model_error(lambda: AIStorageManifest.from_dict(payload))

    payload = valid_manifest_payload()
    payload["directories"]["memory"] = ".kb/ai/memory/"
    expect_model_error(lambda: AIStorageManifest.from_dict(payload))

    payload = valid_manifest_payload()
    payload["directories"]["drafts"] = "D:/Program Files/PersonalKnowledgeBase/ai/drafts/"
    expect_model_error(lambda: AIStorageManifest.from_dict(payload))

    payload = valid_manifest_payload()
    payload["directories"]["indexes"] = "../ai/indexes/"
    expect_model_error(lambda: AIStorageManifest.from_dict(payload))


def assert_schema_version_required() -> None:
    payload = valid_layout_payload()
    del payload["schema_version"]
    expect_model_error(lambda: AIStorageLayout.from_dict(payload))

    payload = valid_manifest_payload()
    del payload["schema_version"]
    expect_model_error(lambda: AIStorageManifest.from_dict(payload))


def assert_knowledge_storage_rejected() -> None:
    payload = valid_layout_payload()
    workspace = payload["workspace_root"]
    payload["storage_root"] = f"{workspace}/knowledge/ai"
    payload["conversations_path"] = f"{workspace}/knowledge/ai/conversations"
    payload["memory_path"] = f"{workspace}/knowledge/ai/memory"
    payload["drafts_path"] = f"{workspace}/knowledge/ai/drafts"
    payload["indexes_path"] = f"{workspace}/knowledge/ai/indexes"
    expect_model_error(lambda: AIStorageLayout.from_dict(payload))


def assert_kb_storage_rejected() -> None:
    payload = valid_layout_payload()
    workspace = payload["workspace_root"]
    payload["storage_root"] = f"{workspace}/.kb/ai"
    payload["conversations_path"] = f"{workspace}/.kb/ai/conversations"
    payload["memory_path"] = f"{workspace}/.kb/ai/memory"
    payload["drafts_path"] = f"{workspace}/.kb/ai/drafts"
    payload["indexes_path"] = f"{workspace}/.kb/ai/indexes"
    expect_model_error(lambda: AIStorageLayout.from_dict(payload))


def assert_install_dir_storage_rejected() -> None:
    workspace = "D:/Program Files/PersonalKnowledgeBase"
    payload = valid_layout_payload(workspace_root=workspace)
    payload["install_root"] = workspace
    expect_model_error(lambda: AIStorageLayout.from_dict(payload))


def assert_derived_indexes_marked_rebuildable() -> None:
    layout_payload = valid_layout_payload()
    layout = AIStorageLayout.from_dict(layout_payload)
    if layout.indexes_derived_only is not True:
        raise AssertionError("AI indexes must be derived only")
    if layout.indexes_rebuildable is not True:
        raise AssertionError("AI indexes must be rebuildable")
    if layout.manifest.source_of_truth["indexes"] != "derived":
        raise AssertionError("manifest must mark indexes as derived")
    if layout.manifest.derived_indexes["derived_only"] is not True:
        raise AssertionError("manifest derived_indexes must be derived only")
    if layout.manifest.derived_indexes["rebuildable"] is not True:
        raise AssertionError("manifest derived_indexes must be rebuildable")

    payload = copy.deepcopy(layout_payload)
    payload["indexes_rebuildable"] = False
    expect_model_error(lambda: AIStorageLayout.from_dict(payload))

    payload = copy.deepcopy(layout_payload)
    payload["manifest"]["derived_indexes"] = {"derived_only": True, "rebuildable": False}
    expect_model_error(lambda: AIStorageLayout.from_dict(payload))


def assert_backup_flags_default_false() -> None:
    policy = AIBackupInclusion()
    payload = policy.to_dict()
    for field_name in [
        "include_ai_conversations",
        "include_ai_memory",
        "include_ai_drafts",
        "include_ai_indexes",
    ]:
        if payload[field_name] is not False:
            raise AssertionError(f"{field_name} must default to false")


def assert_migration_round_trip() -> None:
    plan = AIMigrationPlan.from_dict(valid_migration_payload())
    serialized = plan.to_dict()
    restored = AIMigrationPlan.from_dict(serialized)
    if restored.to_dict() != serialized:
        raise AssertionError("AIMigrationPlan round-trip changed payload")
    if restored.rollback_plan is None:
        raise AssertionError("migration plan must keep rollback plan")


def assert_clear_conversations_does_not_clear_memory() -> None:
    plan = AIClearPlan(
        schema_version="0.1",
        clear_id="clear_01",
        workspace_id="workspace_01",
        clear_conversations=True,
    )
    payload = plan.to_dict()
    if payload["clear_conversations"] is not True:
        raise AssertionError("clear_conversations flag not preserved")
    if payload["clear_memory"] is not False:
        raise AssertionError("clear conversations must not clear memory by default")


def assert_clear_memory_does_not_delete_knowledge() -> None:
    plan = AIClearPlan(
        schema_version="0.1",
        clear_id="clear_02",
        workspace_id="workspace_01",
        clear_memory=True,
    )
    payload = plan.to_dict()
    if payload["clear_memory"] is not True:
        raise AssertionError("clear_memory flag not preserved")
    if payload["delete_knowledge"] is not False:
        raise AssertionError("clear memory must not delete knowledge")
    if payload["delete_workspace"] is not False:
        raise AssertionError("clear memory must not delete workspace")

    expect_model_error(
        lambda: AIClearPlan(
            schema_version="0.1",
            clear_id="clear_bad",
            workspace_id="workspace_01",
            clear_memory=True,
            delete_knowledge=True,
        ).validate()
    )


def assert_export_redacts_sensitive_by_default() -> None:
    plan = AIExportPlan(
        schema_version="0.1",
        export_id="export_01",
        workspace_id="workspace_01",
        export_scope="one_conversation",
        source_ids=["conv_01"],
    )
    payload = plan.to_dict()
    if payload["redact_sensitive"] is not True:
        raise AssertionError("export must redact sensitive data by default")
    if payload["redact_secrets"] is not True:
        raise AssertionError("export must redact secrets by default")


def assert_models_do_not_create_workspace_ai_files() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir()
        before = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
        layout_payload = valid_layout_payload(str(workspace))
        AIStorageLayout.from_dict(layout_payload).to_dict()
        AIBackupInclusion().to_dict()
        AIExportPlan(
            schema_version="0.1",
            export_id="export_01",
            workspace_id="workspace_01",
            export_scope="saved_memory",
        ).to_dict()
        AIClearPlan(schema_version="0.1", clear_id="clear_01", workspace_id="workspace_01").to_dict()
        AIMigrationPlan.from_dict(valid_migration_payload()).to_dict()
        after = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
        if before != after:
            raise AssertionError(f"persistence models created files: before={before}, after={after}")
        if (workspace / "ai").exists():
            raise AssertionError("persistence models must not create workspace/ai")


def main() -> int:
    assert_valid_layout_passes()
    assert_manifest_directory_boundaries()
    assert_schema_version_required()
    assert_knowledge_storage_rejected()
    assert_kb_storage_rejected()
    assert_install_dir_storage_rejected()
    assert_derived_indexes_marked_rebuildable()
    assert_backup_flags_default_false()
    assert_migration_round_trip()
    assert_clear_conversations_does_not_clear_memory()
    assert_clear_memory_does_not_delete_knowledge()
    assert_export_redacts_sensitive_by_default()
    assert_models_do_not_create_workspace_ai_files()

    print("AI persistence model tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
