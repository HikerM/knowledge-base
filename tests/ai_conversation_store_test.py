#!/usr/bin/env python3
"""In-memory ConversationStore harness tests."""

from __future__ import annotations

import inspect
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import knowledge_app.ai.conversation_store as conversation_store_module  # noqa: E402
from knowledge_app.ai.conversation_models import ConversationModelValidationError  # noqa: E402
from knowledge_app.ai.conversation_store import ConversationStore, ConversationStoreError  # noqa: E402
from knowledge_app.ai.memory_service import MemoryService  # noqa: E402


def valid_message_payload(message_id: str = "msg_1") -> dict:
    return {
        "message_id": message_id,
        "role": "user",
        "type": "user_text",
        "created_at": "2026-05-22T10:00:00+08:00",
        "content": {"text": "Use formal search only."},
        "citations": [],
        "policy_decision_id": None,
        "task_id": None,
        "metadata": {"not_formal_knowledge": True},
    }


def assert_create_append_list_delete_clear_conversation() -> None:
    store = ConversationStore()
    first = store.create_conversation("workspace_01", title="Service harness")
    second = store.create_conversation("workspace_01", title="Second")
    assert first.workspace_id == "workspace_01"
    assert first.provider_kind == "mock"
    assert first.metadata["storage"] == "in_memory"
    assert first.metadata["not_formal_knowledge"] is True

    updated = store.append_message(first.conversation_id, valid_message_payload())
    assert len(updated.messages) == 1
    assert updated.messages[0].message_id == "msg_1"

    listed = store.list_conversations("workspace_01", limit=10, offset=0)
    assert [item.conversation_id for item in listed] == [updated.conversation_id, second.conversation_id]

    assert store.delete_conversation(second.conversation_id) is True
    listed = store.list_conversations("workspace_01", limit=10, offset=0)
    assert [item.conversation_id for item in listed] == [updated.conversation_id]

    cleared = store.clear_conversations("workspace_01")
    assert cleared == 1
    assert store.list_conversations("workspace_01") == []


def assert_append_citation_and_task_metadata() -> None:
    store = ConversationStore()
    conversation = store.create_conversation("workspace_01")
    message = valid_message_payload("msg_with_refs")
    message["citations"] = ["citation_1"]
    message["task_id"] = "task_1"
    message["citation_records"] = [
        {
            "citation_id": "citation_1",
            "document_id": "12",
            "title": "Formal Rule",
            "layer": "rules",
            "status": "active",
            "source_type": "internal_practice",
            "confidence": "high",
            "review_required": False,
            "chunk_id": "chunk_1",
            "warning": None,
        }
    ]
    message["task_references"] = [
        {
            "task_id": "task_1",
            "capability_id": "workspace_status",
            "status_at_last_render": "running",
            "progress_percent_at_last_render": 50,
            "message_id": "msg_with_refs",
            "metadata": {"snapshot_only": True},
        }
    ]
    updated = store.append_message(conversation.conversation_id, message)
    assert updated.citations[0].title == "Formal Rule"
    assert updated.citations[0].layer == "rules"
    assert updated.tasks[0].task_id == "task_1"
    assert updated.tasks[0].status_at_last_render == "running"


def assert_summary_placeholder_is_not_memory() -> None:
    store = ConversationStore()
    conversation = store.create_conversation("workspace_01")
    updated = store.append_message(conversation.conversation_id, valid_message_payload())
    summary = store.summarize_conversation_placeholder(updated.conversation_id)
    assert summary.not_long_term_memory is True
    assert summary.source_message_ids == ["msg_1"]
    restored = store.get_conversation(updated.conversation_id)
    assert restored.summary is not None
    assert restored.summary.not_long_term_memory is True


def assert_delete_conversation_does_not_delete_memory() -> None:
    conversation_store = ConversationStore()
    memory_service = MemoryService()
    conversation = conversation_store.create_conversation("workspace_01")
    candidate = memory_service.create_candidate(
        conversation_id=conversation.conversation_id,
        workspace_id="workspace_01",
        proposed_text="User prefers concise results.",
        type="preference",
        source_message_ids=["msg_1"],
    )
    memory = memory_service.accept_candidate(candidate.candidate_id)
    conversation_store.delete_conversation(conversation.conversation_id)
    memories = memory_service.list_memories("workspace_01")
    assert [item.memory_id for item in memories] == [memory.memory_id]


def assert_append_invalid_message_rejected() -> None:
    store = ConversationStore()
    conversation = store.create_conversation("workspace_01")

    invalid_role = valid_message_payload()
    invalid_role["role"] = "developer"
    try:
        store.append_message(conversation.conversation_id, invalid_role)
    except ConversationModelValidationError:
        pass
    else:
        raise AssertionError("invalid message role should be rejected")

    invalid_content = valid_message_payload()
    invalid_content["content"] = "not-a-dict"
    try:
        store.append_message(conversation.conversation_id, invalid_content)
    except ConversationModelValidationError:
        pass
    else:
        raise AssertionError("invalid message content should be rejected")


def assert_no_files_or_workspace_ai_created() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir()
        before = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
        store = ConversationStore()
        conversation = store.create_conversation(str(workspace))
        store.append_message(conversation.conversation_id, valid_message_payload())
        store.summarize_conversation_placeholder(conversation.conversation_id)
        after = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
        assert before == after
        assert not (workspace / "ai").exists()


def assert_missing_conversation_rejected() -> None:
    store = ConversationStore()
    try:
        store.get_conversation("missing")
    except ConversationStoreError:
        return
    raise AssertionError("missing conversation should be rejected")


def assert_service_has_no_low_level_or_provider_dependency() -> None:
    source = inspect.getsource(conversation_store_module).lower()
    for token in ["sqlite3", "subprocess", "knowledge_core", "mockaiprovider", "aiprovider", "openai", "modelscope"]:
        assert token not in source
    assert "searchservice" not in source


def main() -> int:
    assert_create_append_list_delete_clear_conversation()
    assert_append_citation_and_task_metadata()
    assert_summary_placeholder_is_not_memory()
    assert_delete_conversation_does_not_delete_memory()
    assert_append_invalid_message_rejected()
    assert_no_files_or_workspace_ai_created()
    assert_missing_conversation_rejected()
    assert_service_has_no_low_level_or_provider_dependency()
    print("AI conversation store tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
