#!/usr/bin/env python3
"""AI conversation static model tests."""

from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.conversation_models import (  # noqa: E402
    ConversationModelValidationError,
    ConversationRecord,
)


def valid_conversation_payload() -> dict:
    return {
        "conversation_id": "conv_01",
        "workspace_id": "workspace_01",
        "created_at": "2026-05-21T10:00:00+08:00",
        "updated_at": "2026-05-21T10:15:00+08:00",
        "title": "Ask My Knowledge: service boundary",
        "messages": [
            {
                "message_id": "msg_1",
                "role": "user",
                "type": "user_text",
                "created_at": "2026-05-21T10:01:00+08:00",
                "content": {"text": "搜索 service boundary"},
                "citations": [],
                "policy_decision_id": None,
                "task_id": None,
                "metadata": {"not_formal_knowledge": True},
            },
            {
                "message_id": "msg_2",
                "role": "assistant",
                "type": "assistant_text",
                "created_at": "2026-05-21T10:02:00+08:00",
                "content": {"text": "SearchService is the formal search entry."},
                "citations": ["citation_1"],
                "policy_decision_id": "policy_1",
                "task_id": "task_1",
                "metadata": {"provider_kind": "mock", "not_formal_knowledge": True},
            },
        ],
        "citations": [
            {
                "citation_id": "citation_1",
                "document_id": "12",
                "title": "Service Boundary Rule",
                "layer": "rules",
                "status": "active",
                "source_type": "internal_practice",
                "confidence": "high",
                "review_required": False,
                "chunk_id": "chunk_12_01",
                "warning": None,
            }
        ],
        "tasks": [
            {
                "task_id": "task_1",
                "capability_id": "workspace_status",
                "status_at_last_render": "running",
                "progress_percent_at_last_render": 60,
                "message_id": "msg_2",
                "metadata": {"read_via_service": True},
            }
        ],
        "policy_decisions": [
            {
                "policy_decision_id": "policy_1",
                "created_at": "2026-05-21T10:02:00+08:00",
                "capability_id": "search_knowledge",
                "level": "L0",
                "decision": "allow",
                "reason": "formal search is read-only",
                "provider_kind": "mock",
                "context_preview_id": None,
                "confirmation_id": None,
                "metadata": {"cloud_send_allowed": False, "mutation_allowed": False},
            }
        ],
        "provider_kind": "mock",
        "summary": {
            "text": "Short non-authoritative conversation summary.",
            "created_at": "2026-05-21T10:15:00+08:00",
            "source_message_ids": ["msg_1", "msg_2"],
            "not_long_term_memory": True,
        },
        "metadata": {
            "schema_version": "0.1",
            "app_version": "2.4.1-static-models",
            "policy_version": "ai-memory-retention-0.1",
            "retention_policy_id": "default_local",
            "privacy_mode": False,
            "memory_disabled": False,
        },
    }


def expect_validation_error(payload: dict) -> None:
    try:
        ConversationRecord.from_dict(payload)
    except ConversationModelValidationError:
        return
    raise AssertionError("expected ConversationModelValidationError")


def assert_valid_conversation_round_trip() -> None:
    record = ConversationRecord.from_dict(valid_conversation_payload())
    serialized = record.to_dict()
    restored = ConversationRecord.from_dict(serialized)
    if restored.to_dict() != serialized:
        raise AssertionError("conversation round-trip changed payload")
    if restored.schema_version != "0.1":
        raise AssertionError("conversation schema_version was not preserved")


def assert_invalid_message_type_rejected() -> None:
    payload = valid_conversation_payload()
    payload["messages"][0]["type"] = "unsupported"
    expect_validation_error(payload)


def assert_invalid_role_rejected() -> None:
    payload = valid_conversation_payload()
    payload["messages"][0]["role"] = "developer"
    expect_validation_error(payload)


def assert_summary_not_long_term_memory_required() -> None:
    payload = valid_conversation_payload()
    del payload["summary"]["not_long_term_memory"]
    expect_validation_error(payload)

    payload = valid_conversation_payload()
    payload["summary"]["not_long_term_memory"] = False
    expect_validation_error(payload)


def assert_citation_fields_required() -> None:
    for field_name in ["title", "layer", "status", "source_type", "confidence"]:
        payload = valid_conversation_payload()
        del payload["citations"][0][field_name]
        expect_validation_error(payload)


def assert_task_reference_does_not_include_logs() -> None:
    record = ConversationRecord.from_dict(valid_conversation_payload())
    task_payload = record.to_dict()["tasks"][0]
    for key in ["log", "logs", "log_path", "task_log", "task_logs"]:
        if key in task_payload:
            raise AssertionError(f"task reference leaked log field: {key}")

    payload = valid_conversation_payload()
    payload["tasks"][0]["log_path"] = ".kb/tasks/task_1/task.log"
    expect_validation_error(payload)

    payload = valid_conversation_payload()
    payload["tasks"][0]["metadata"]["logs"] = ["secret task log"]
    expect_validation_error(payload)


def assert_provider_kind_rejected() -> None:
    payload = valid_conversation_payload()
    payload["provider_kind"] = "openai"
    expect_validation_error(payload)


def assert_models_do_not_create_workspace_ai_files() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir()
        before = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
        payload = copy.deepcopy(valid_conversation_payload())
        payload["workspace_id"] = str(workspace)
        ConversationRecord.from_dict(payload).to_dict()
        after = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
        if before != after:
            raise AssertionError(f"conversation models created files: before={before}, after={after}")
        if (workspace / "ai").exists():
            raise AssertionError("conversation models must not create workspace/ai")


def main() -> int:
    assert_valid_conversation_round_trip()
    assert_invalid_message_type_rejected()
    assert_invalid_role_rejected()
    assert_summary_not_long_term_memory_required()
    assert_citation_fields_required()
    assert_task_reference_does_not_include_logs()
    assert_provider_kind_rejected()
    assert_models_do_not_create_workspace_ai_files()

    print("AI conversation model tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
