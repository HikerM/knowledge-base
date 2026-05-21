#!/usr/bin/env python3
"""AI memory static model tests."""

from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.memory_models import (  # noqa: E402
    MemoryCandidate,
    MemoryModelValidationError,
    SavedMemory,
)


def valid_candidate_payload() -> dict:
    return {
        "candidate_id": "memcand_01",
        "conversation_id": "conv_01",
        "workspace_id": "workspace_01",
        "type": "preference",
        "proposed_text": "User prefers concise validation results.",
        "source_message_ids": ["msg_1", "msg_2"],
        "sensitivity": "low",
        "requires_confirmation": True,
        "status": "pending",
        "metadata": {
            "schema_version": "0.1",
            "created_at": "2026-05-21T10:05:00+08:00",
            "expires_at": "2026-06-20T10:05:00+08:00",
            "rejection_fingerprint": "hash-of-normalized-proposal",
            "blocked_reason": None,
        },
    }


def valid_saved_memory_payload() -> dict:
    return {
        "memory_id": "mem_01",
        "workspace_id": "workspace_01",
        "type": "preference",
        "text": "User prefers concise validation results.",
        "created_at": "2026-05-21T10:06:00+08:00",
        "updated_at": "2026-05-21T10:06:00+08:00",
        "source": {
            "candidate_id": "memcand_01",
            "conversation_id": "conv_01",
            "source_message_ids": ["msg_1"],
        },
        "sensitivity": "low",
        "status": "active",
        "metadata": {
            "schema_version": "0.1",
            "confirmed_by": "user",
            "confirmation_id": "confirm_01",
            "retention_policy_id": "until_user_deletes",
            "cloud_send_allowed": False,
            "not_formal_knowledge": True,
        },
    }


def expect_memory_error(model_factory) -> None:
    try:
        model_factory()
    except MemoryModelValidationError:
        return
    raise AssertionError("expected MemoryModelValidationError")


def assert_valid_memory_candidate_round_trip() -> None:
    candidate = MemoryCandidate.from_dict(valid_candidate_payload())
    serialized = candidate.to_dict()
    restored = MemoryCandidate.from_dict(serialized)
    if restored.to_dict() != serialized:
        raise AssertionError("MemoryCandidate round-trip changed payload")


def assert_requires_confirmation_must_be_true() -> None:
    payload = valid_candidate_payload()
    payload["requires_confirmation"] = False
    expect_memory_error(lambda: MemoryCandidate.from_dict(payload))


def assert_blocked_candidate_cannot_be_accepted() -> None:
    payload = valid_candidate_payload()
    payload["sensitivity"] = "blocked"
    payload["status"] = "accepted"
    expect_memory_error(lambda: MemoryCandidate.from_dict(payload))


def assert_invalid_memory_type_rejected() -> None:
    payload = valid_candidate_payload()
    payload["type"] = "secret"
    expect_memory_error(lambda: MemoryCandidate.from_dict(payload))

    payload = valid_saved_memory_payload()
    payload["type"] = "secret"
    expect_memory_error(lambda: SavedMemory.from_dict(payload))


def assert_saved_memory_requires_confirmation_metadata() -> None:
    payload = valid_saved_memory_payload()
    payload["metadata"] = dict(payload["metadata"])
    del payload["metadata"]["confirmed_by"]
    expect_memory_error(lambda: SavedMemory.from_dict(payload))

    payload = valid_saved_memory_payload()
    payload["metadata"]["confirmed_by"] = "assistant"
    expect_memory_error(lambda: SavedMemory.from_dict(payload))


def assert_saved_memory_not_formal_knowledge() -> None:
    payload = valid_saved_memory_payload()
    payload["metadata"]["formal_knowledge"] = True
    expect_memory_error(lambda: SavedMemory.from_dict(payload))

    payload = valid_saved_memory_payload()
    payload["metadata"]["not_formal_knowledge"] = False
    expect_memory_error(lambda: SavedMemory.from_dict(payload))

    payload = valid_saved_memory_payload()
    payload["metadata"]["layer"] = "rules"
    expect_memory_error(lambda: SavedMemory.from_dict(payload))


def assert_valid_saved_memory_round_trip() -> None:
    saved = SavedMemory.from_dict(valid_saved_memory_payload())
    serialized = saved.to_dict()
    restored = SavedMemory.from_dict(serialized)
    if restored.to_dict() != serialized:
        raise AssertionError("SavedMemory round-trip changed payload")
    if serialized["metadata"]["not_formal_knowledge"] is not True:
        raise AssertionError("SavedMemory must mark not_formal_knowledge=true")


def assert_models_do_not_create_workspace_ai_files() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir()
        before = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))

        candidate_payload = copy.deepcopy(valid_candidate_payload())
        candidate_payload["workspace_id"] = str(workspace)
        MemoryCandidate.from_dict(candidate_payload).to_dict()

        saved_payload = copy.deepcopy(valid_saved_memory_payload())
        saved_payload["workspace_id"] = str(workspace)
        SavedMemory.from_dict(saved_payload).to_dict()

        after = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
        if before != after:
            raise AssertionError(f"memory models created files: before={before}, after={after}")
        if (workspace / "ai").exists():
            raise AssertionError("memory models must not create workspace/ai")


def main() -> int:
    assert_valid_memory_candidate_round_trip()
    assert_requires_confirmation_must_be_true()
    assert_blocked_candidate_cannot_be_accepted()
    assert_invalid_memory_type_rejected()
    assert_saved_memory_requires_confirmation_metadata()
    assert_saved_memory_not_formal_knowledge()
    assert_valid_saved_memory_round_trip()
    assert_models_do_not_create_workspace_ai_files()

    print("AI memory model tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
