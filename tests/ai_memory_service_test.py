#!/usr/bin/env python3
"""In-memory MemoryService harness tests."""

from __future__ import annotations

import inspect
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import knowledge_app.ai.memory_service as memory_service_module  # noqa: E402
from knowledge_app.ai.conversation_store import ConversationStore  # noqa: E402
from knowledge_app.ai.memory_models import MemoryStatus  # noqa: E402
from knowledge_app.ai.memory_service import MemoryService, MemoryServiceError  # noqa: E402
from knowledge_app.ai.retention_models import PrivacyModePolicy, RetentionPolicy  # noqa: E402


def create_candidate(service: MemoryService, workspace_id: str = "workspace_01"):
    return service.create_candidate(
        conversation_id="conv_01",
        workspace_id=workspace_id,
        proposed_text="User prefers concise validation summaries.",
        type="preference",
        source_message_ids=["msg_1", "msg_2"],
    )


def assert_create_and_list_memory_candidate() -> None:
    service = MemoryService()
    candidate = create_candidate(service)
    assert candidate.requires_confirmation is True
    assert candidate.status == MemoryStatus.PENDING.value
    assert candidate.metadata["storage"] == "in_memory"
    assert candidate.metadata["not_formal_knowledge"] is True
    candidates = service.list_candidates("workspace_01")
    assert [item.candidate_id for item in candidates] == [candidate.candidate_id]


def assert_accept_candidate_creates_in_memory_saved_memory() -> None:
    service = MemoryService()
    candidate = create_candidate(service)
    memory = service.accept_candidate(candidate.candidate_id, confirmed=True, confirmation_id="confirm_01")
    assert memory.status == MemoryStatus.ACTIVE.value
    assert memory.source.candidate_id == candidate.candidate_id
    assert memory.metadata["storage"] == "in_memory"
    assert memory.metadata["confirmed_by"] == "user"
    assert memory.metadata["confirmation_id"] == "confirm_01"
    assert memory.metadata["not_formal_knowledge"] is True
    assert memory.metadata["cloud_send_allowed"] is False
    assert memory.metadata["backup_default_included"] is False
    assert memory.metadata["export_writes_file"] is False
    assert memory.metadata["mutation_authority"] is False
    memories = service.list_memories("workspace_01")
    assert [item.memory_id for item in memories] == [memory.memory_id]
    accepted = service.list_candidates("workspace_01", status=MemoryStatus.ACCEPTED.value)
    assert [item.candidate_id for item in accepted] == [candidate.candidate_id]
    assert accepted[0].metadata["confirmation_id"] == "confirm_01"


def assert_accept_requires_user_confirmation() -> None:
    service = MemoryService()
    candidate = create_candidate(service)
    try:
        service.accept_candidate(candidate.candidate_id)
    except MemoryServiceError:
        pass
    else:
        raise AssertionError("accept_candidate must require explicit user confirmation")
    assert service.list_memories("workspace_01") == []
    assert service.list_candidates("workspace_01", status=MemoryStatus.PENDING.value)[0].candidate_id == candidate.candidate_id


def assert_reject_candidate_does_not_save_memory() -> None:
    service = MemoryService()
    candidate = create_candidate(service)
    rejected = service.reject_candidate(candidate.candidate_id)
    assert rejected.status == MemoryStatus.REJECTED.value
    assert service.list_memories("workspace_01") == []
    try:
        service.accept_candidate(candidate.candidate_id, confirmed=True)
    except MemoryServiceError:
        pass
    else:
        raise AssertionError("rejected candidate should not be accepted")


def assert_blocked_sensitivity_cannot_be_accepted() -> None:
    service = MemoryService()
    candidate = service.create_candidate(
        conversation_id="conv_01",
        workspace_id="workspace_01",
        proposed_text="Sensitive preference that must not be saved.",
        type="preference",
        source_message_ids=["msg_1"],
        sensitivity="blocked",
    )
    try:
        service.accept_candidate(candidate.candidate_id, confirmed=True)
    except MemoryServiceError:
        pass
    else:
        raise AssertionError("blocked sensitivity candidate should not be accepted")
    assert service.list_memories("workspace_01") == []


def assert_expire_candidate_does_not_save_memory() -> None:
    service = MemoryService()
    candidate = create_candidate(service)
    expired = service.expire_candidate(candidate.candidate_id)
    assert expired.status == MemoryStatus.EXPIRED.value
    assert expired.metadata["expired_at"]
    assert service.list_memories("workspace_01") == []


def assert_delete_disable_clear_memory() -> None:
    service = MemoryService()
    first = service.accept_candidate(create_candidate(service).candidate_id, confirmed=True)
    second = service.accept_candidate(create_candidate(service).candidate_id, confirmed=True)
    disabled = service.disable_memory(first.memory_id)
    assert disabled.status == MemoryStatus.DISABLED.value
    memories = service.list_memories("workspace_01")
    assert {item.memory_id for item in memories} == {first.memory_id, second.memory_id}
    deleted = service.delete_memory(second.memory_id)
    assert deleted.status == MemoryStatus.DELETED.value
    assert deleted.text == ""
    assert deleted.metadata["text_redacted"] is True
    assert [item.memory_id for item in service.list_memories("workspace_01")] == [first.memory_id]
    deleted_memories = service.list_memories("workspace_01", include_deleted=True)
    assert second.memory_id in {item.memory_id for item in deleted_memories}
    assert service.clear_memory("workspace_01") == 1
    assert service.list_memories("workspace_01") == []
    assert {item.status for item in service.list_memories("workspace_01", include_deleted=True)} == {MemoryStatus.DELETED.value}


def assert_delete_memory_does_not_affect_conversation() -> None:
    conversation_store = ConversationStore()
    memory_service = MemoryService()
    conversation = conversation_store.create_conversation("workspace_01")
    candidate = memory_service.create_candidate(
        conversation_id=conversation.conversation_id,
        workspace_id="workspace_01",
        proposed_text="User prefers source citations.",
        type="workflow",
        source_message_ids=["msg_1"],
    )
    memory = memory_service.accept_candidate(candidate.candidate_id, confirmed=True)
    memory_service.delete_memory(memory.memory_id)
    assert conversation_store.get_conversation(conversation.conversation_id).conversation_id == conversation.conversation_id


def assert_no_files_or_workspace_ai_created() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir) / "workspace"
        workspace.mkdir()
        before = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
        service = MemoryService()
        candidate = service.create_candidate(
            conversation_id="conv_01",
            workspace_id=str(workspace),
            proposed_text="User prefers concise output.",
            type="preference",
            source_message_ids=["msg_1"],
        )
        memory = service.accept_candidate(candidate.candidate_id, confirmed=True)
        service.disable_memory(memory.memory_id)
        service.backup_policy_preview(str(workspace))
        service.export_memory_preview(str(workspace), include_deleted=True)
        after = sorted(path.relative_to(workspace) for path in workspace.rglob("*"))
        assert before == after
        assert not (workspace / "ai").exists()


def assert_memory_does_not_become_formal_knowledge_or_authorize_mutation() -> None:
    service = MemoryService()
    memory = service.accept_candidate(create_candidate(service).candidate_id, confirmed=True)
    payload = memory.to_dict()
    metadata = payload["metadata"]
    assert metadata["not_formal_knowledge"] is True
    assert metadata["cloud_send_allowed"] is False
    assert metadata["mutation_authority"] is False
    assert "layer" not in metadata


def assert_retention_enforcement_expires_pending_candidates_only() -> None:
    start = datetime(2026, 5, 22, 0, 0, tzinfo=timezone.utc)
    service = MemoryService(RetentionPolicy(memory_candidate_expiry_days=1))
    pending = service.create_candidate(
        conversation_id="conv_01",
        workspace_id="workspace_01",
        proposed_text="User prefers short summaries.",
        type="preference",
        source_message_ids=["msg_1"],
        now=start,
    )
    saved_candidate = service.create_candidate(
        conversation_id="conv_01",
        workspace_id="workspace_01",
        proposed_text="User prefers test output.",
        type="workflow",
        source_message_ids=["msg_2"],
        now=start,
    )
    saved = service.accept_candidate(saved_candidate.candidate_id, confirmed=True, now=start)
    result = service.enforce_retention("workspace_01", now=start + timedelta(days=2))
    assert result["expired_candidate_ids"] == [pending.candidate_id]
    assert result["saved_memory_auto_expired"] == 0
    assert service.list_candidates("workspace_01", status=MemoryStatus.EXPIRED.value)[0].candidate_id == pending.candidate_id
    assert service.list_memories("workspace_01")[0].memory_id == saved.memory_id


def assert_privacy_mode_blocks_candidate_and_save() -> None:
    service = MemoryService(RetentionPolicy(privacy=PrivacyModePolicy(privacy_mode=True)))
    try:
        create_candidate(service)
    except MemoryServiceError:
        pass
    else:
        raise AssertionError("privacy mode must block memory candidate creation")
    assert service.list_candidates("workspace_01") == []
    assert service.list_memories("workspace_01") == []


def assert_backup_and_export_policy_mock_boundaries() -> None:
    service = MemoryService()
    memory = service.accept_candidate(create_candidate(service).candidate_id, confirmed=True)
    backup = service.backup_policy_preview("workspace_01")
    assert backup["writes_file"] is False
    assert backup["memory_default_included"] is False
    assert backup["default_backup"]["include_ai_memory"] is False
    assert backup["default_backup"]["include_ai_drafts"] is False
    assert backup["privacy_warning_required_for_ai_memory"] is True
    export = service.export_memory_preview("workspace_01")
    assert export["writes_file"] is False
    assert export["not_formal_knowledge"] is True
    assert export["cloud_send_allowed"] is False
    assert export["includes"]["formal_search_records"] is False
    assert export["includes"]["knowledge_markdown"] is False
    assert export["memories"][0]["memory_id"] == memory.memory_id


def assert_invalid_candidate_inputs_rejected() -> None:
    service = MemoryService()
    try:
        service.create_candidate(
            conversation_id="conv_01",
            workspace_id="workspace_01",
            proposed_text="Invalid source ids.",
            type="preference",
            source_message_ids="msg_1",
        )
    except Exception:
        pass
    else:
        raise AssertionError("invalid source_message_ids should be rejected")


def assert_service_has_no_low_level_or_provider_dependency() -> None:
    source = inspect.getsource(memory_service_module).lower()
    for token in ["sqlite3", "subprocess", "knowledge_core", "mockaiprovider", "aiprovider", "openai", "modelscope"]:
        assert token not in source
    assert "searchservice" not in source


def main() -> int:
    assert_create_and_list_memory_candidate()
    assert_accept_candidate_creates_in_memory_saved_memory()
    assert_accept_requires_user_confirmation()
    assert_reject_candidate_does_not_save_memory()
    assert_blocked_sensitivity_cannot_be_accepted()
    assert_expire_candidate_does_not_save_memory()
    assert_delete_disable_clear_memory()
    assert_delete_memory_does_not_affect_conversation()
    assert_no_files_or_workspace_ai_created()
    assert_memory_does_not_become_formal_knowledge_or_authorize_mutation()
    assert_retention_enforcement_expires_pending_candidates_only()
    assert_privacy_mode_blocks_candidate_and_save()
    assert_backup_and_export_policy_mock_boundaries()
    assert_invalid_candidate_inputs_rejected()
    assert_service_has_no_low_level_or_provider_dependency()
    print("AI memory service tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
