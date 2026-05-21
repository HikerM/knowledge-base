#!/usr/bin/env python3
"""AI retention static model tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.retention_models import (  # noqa: E402
    BackupInclusionPolicy,
    PrivacyModePolicy,
    RetentionModelValidationError,
    RetentionPolicy,
)


def expect_retention_error(model_factory) -> None:
    try:
        model_factory()
    except RetentionModelValidationError:
        return
    raise AssertionError("expected RetentionModelValidationError")


def assert_retention_policy_round_trip() -> None:
    policy = RetentionPolicy.from_dict(
        {
            "policy_id": "default_local",
            "conversation_retention_days": 90,
            "memory_candidate_expiry_days": 14,
            "rejected_candidate_suppression_days": 120,
            "long_term_memory_retention": "until_user_deletion",
            "conversation_retention_configurable": True,
            "memory_candidate_expiry_configurable": True,
            "backup": {
                "include_ai_conversations": False,
                "include_ai_memory": False,
                "include_ai_drafts": False,
            },
            "privacy": {
                "cloud_memory_send_allowed": False,
                "cloud_conversation_send_allowed": False,
                "context_preview_required_for_cloud": True,
            },
            "metadata": {"schema_version": "0.1"},
        }
    )
    serialized = policy.to_dict()
    restored = RetentionPolicy.from_dict(serialized)
    if restored.to_dict() != serialized:
        raise AssertionError("RetentionPolicy round-trip changed payload")
    if restored.conversation_retention_days != 90:
        raise AssertionError("conversation retention must be configurable")
    if restored.memory_candidate_expiry_days != 14:
        raise AssertionError("memory candidate expiry must be configurable")
    if restored.long_term_memory_retention != "until_user_deletion":
        raise AssertionError("long-term memory must be kept until user deletion")


def assert_defaults_exclude_ai_data_from_backup() -> None:
    backup = BackupInclusionPolicy()
    payload = backup.to_dict()
    if payload["include_ai_conversations"] is not False:
        raise AssertionError("default backup must exclude AI conversations")
    if payload["include_ai_memory"] is not False:
        raise AssertionError("default backup must exclude AI memory")
    if payload["include_ai_drafts"] is not False:
        raise AssertionError("default backup must exclude AI drafts")

    policy_payload = RetentionPolicy().to_dict()
    if policy_payload["backup"]["include_ai_conversations"] is not False:
        raise AssertionError("RetentionPolicy default backup must exclude AI conversations")
    if policy_payload["backup"]["include_ai_memory"] is not False:
        raise AssertionError("RetentionPolicy default backup must exclude AI memory")
    if policy_payload["backup"]["include_ai_drafts"] is not False:
        raise AssertionError("RetentionPolicy default backup must exclude AI drafts")


def assert_cloud_memory_send_default_false() -> None:
    privacy = PrivacyModePolicy()
    payload = privacy.to_dict()
    if payload["cloud_memory_send_allowed"] is not False:
        raise AssertionError("cloud memory send must default to false")
    if payload["cloud_conversation_send_allowed"] is not False:
        raise AssertionError("cloud conversation send must default to false")
    if payload["context_preview_required_for_cloud"] is not True:
        raise AssertionError("cloud context must require preview by default")


def assert_invalid_retention_values_rejected() -> None:
    expect_retention_error(lambda: RetentionPolicy(conversation_retention_days=0).validate())
    expect_retention_error(lambda: RetentionPolicy(memory_candidate_expiry_days=0).validate())
    expect_retention_error(lambda: RetentionPolicy(long_term_memory_retention="auto_expire").validate())
    expect_retention_error(
        lambda: PrivacyModePolicy(cloud_memory_send_allowed=True, context_preview_required_for_cloud=False).validate()
    )


def assert_models_do_not_create_workspace_ai_files() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir()
        before = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
        RetentionPolicy(policy_id=str(workspace)).to_dict()
        BackupInclusionPolicy().to_dict()
        PrivacyModePolicy().to_dict()
        after = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
        if before != after:
            raise AssertionError(f"retention models created files: before={before}, after={after}")
        if (workspace / "ai").exists():
            raise AssertionError("retention models must not create workspace/ai")


def main() -> int:
    assert_retention_policy_round_trip()
    assert_defaults_exclude_ai_data_from_backup()
    assert_cloud_memory_send_default_false()
    assert_invalid_retention_values_rejected()
    assert_models_do_not_create_workspace_ai_files()

    print("AI retention model tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
