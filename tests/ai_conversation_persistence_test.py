#!/usr/bin/env python3
"""Minimal AI conversation persistence service tests."""

from __future__ import annotations

import inspect
import json
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

import knowledge_app.ai.conversation_persistence_service as persistence_module  # noqa: E402
from knowledge_app.ai.conversation_persistence_service import (  # noqa: E402
    ConversationPersistenceService,
    ConversationPersistenceServiceError,
)
from knowledge_app.ai.persistence_service import AIStorageBootstrapService  # noqa: E402
from knowledge_app.services.search_service import SearchService  # noqa: E402
from knowledge_app.services.workspace_status_service import WorkspaceStatusService  # noqa: E402


def expect_service_error(callable_) -> None:
    try:
        callable_()
    except ConversationPersistenceServiceError:
        return
    raise AssertionError("expected ConversationPersistenceServiceError")


def bootstrap_workspace(workspace: Path) -> str:
    manifest = AIStorageBootstrapService().bootstrap_storage(workspace, confirmed=True)
    return manifest.workspace_id


def valid_message(message_id: str = "msg_1") -> dict:
    return {
        "message_id": message_id,
        "role": "user",
        "type": "user_text",
        "created_at": "2026-05-22T10:00:00+08:00",
        "content": {"text": "Use explicit service-layer conversation persistence."},
        "citations": [],
        "policy_decision_id": None,
        "task_id": None,
        "metadata": {"not_formal_knowledge": True},
    }


def message_with_refs() -> dict:
    message = valid_message("msg_with_refs")
    message.update(
        {
            "role": "assistant",
            "type": "assistant_text",
            "content": {"text": "The answer used formal citations but remains non-formal AI data."},
            "citations": ["citation_1"],
            "policy_decision_id": "policy_1",
            "task_id": "task_1",
            "citation_records": [
                {
                    "citation_id": "citation_1",
                    "document_id": "12",
                    "title": "AI persistence boundary",
                    "layer": "rules",
                    "status": "active",
                    "source_type": "internal_practice",
                    "confidence": "high",
                    "review_required": False,
                    "chunk_id": "chunk_12_01",
                    "warning": None,
                }
            ],
            "task_references": [
                {
                    "task_id": "task_1",
                    "capability_id": "workspace_status",
                    "status_at_last_render": "succeeded",
                    "progress_percent_at_last_render": 100,
                    "message_id": "msg_with_refs",
                    "metadata": {"snapshot_only": True},
                }
            ],
            "policy_decision_records": [
                {
                    "policy_decision_id": "policy_1",
                    "created_at": "2026-05-22T10:00:01+08:00",
                    "capability_id": "ask_my_knowledge",
                    "level": "L0",
                    "decision": "allow",
                    "reason": "read-only formal search metadata was allowed",
                    "provider_kind": "mock",
                    "context_preview_id": None,
                    "confirmation_id": None,
                    "metadata": {"cloud_send_allowed": False, "mutation_allowed": False},
                }
            ],
        }
    )
    return message


def conversation_dir(workspace: Path, conversation_id: str) -> Path:
    return workspace / "ai" / "conversations" / conversation_id


def conversations_manifest_path(workspace: Path) -> Path:
    return workspace / "ai" / "conversations" / "manifest.json"


def read_conversations_manifest(workspace: Path) -> dict:
    return json.loads(conversations_manifest_path(workspace).read_text(encoding="utf-8"))


def assert_bootstrap_required() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        service = ConversationPersistenceService()
        expect_service_error(lambda: service.create_conversation(workspace, "workspace"))
        expect_service_error(lambda: service.list_conversations(workspace, "workspace"))
        if (workspace / "ai").exists():
            raise AssertionError("conversation persistence must not bootstrap workspace/ai")


def assert_create_conversation_writes_expected_files() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id, title="Persistence layout")
        root = conversation_dir(workspace, conversation.conversation_id)
        expected = {
            "ai/conversations/manifest.json",
            f"ai/conversations/{conversation.conversation_id}",
            f"ai/conversations/{conversation.conversation_id}/conversation.json",
            f"ai/conversations/{conversation.conversation_id}/messages.jsonl",
        }
        actual = {path.relative_to(workspace).as_posix() for path in (workspace / "ai" / "conversations").rglob("*")}
        missing = expected - actual
        if missing:
            raise AssertionError(f"conversation persistence missing expected files: {missing}")
        metadata = json.loads((root / "conversation.json").read_text(encoding="utf-8"))
        if metadata["messages"] != []:
            raise AssertionError("conversation.json must store metadata only")
        if (root / "messages.jsonl").read_text(encoding="utf-8") != "":
            raise AssertionError("new conversation messages.jsonl should be empty")


def assert_append_message_persists() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id)
        updated = service.append_message(workspace, conversation.conversation_id, valid_message())
        if len(updated.messages) != 1:
            raise AssertionError("append_message did not return persisted message")
        messages_path = conversation_dir(workspace, conversation.conversation_id) / "messages.jsonl"
        lines = messages_path.read_text(encoding="utf-8").splitlines()
        if len(lines) != 1:
            raise AssertionError(f"expected one JSONL message line, got {len(lines)}")
        if json.loads(lines[0])["message_id"] != "msg_1":
            raise AssertionError("persisted JSONL message changed message_id")
        metadata = json.loads((conversation_dir(workspace, conversation.conversation_id) / "conversation.json").read_text(encoding="utf-8"))
        if metadata["metadata"]["message_count"] != 1:
            raise AssertionError("conversation metadata did not update message_count")


def assert_get_conversation_round_trip() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id, title="Round trip")
        service.append_message(workspace, conversation.conversation_id, message_with_refs())
        restored = service.get_conversation(workspace, conversation.conversation_id)
        if restored.title != "Round trip":
            raise AssertionError("conversation title did not round-trip")
        if [message.message_id for message in restored.messages] != ["msg_with_refs"]:
            raise AssertionError("messages did not round-trip")
        if [citation.citation_id for citation in restored.citations] != ["citation_1"]:
            raise AssertionError("citation records did not round-trip")
        if [decision.policy_decision_id for decision in restored.policy_decisions] != ["policy_1"]:
            raise AssertionError("policy decisions did not round-trip")


def assert_list_conversations_pagination() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversations = [
            service.create_conversation(workspace, workspace_id, title=f"Conversation {index}")
            for index in range(3)
        ]
        first_page = service.list_conversations(workspace, workspace_id, limit=2, offset=0)
        second_page = service.list_conversations(workspace, workspace_id, limit=2, offset=2)
        if len(first_page) != 2 or len(second_page) != 1:
            raise AssertionError("list_conversations pagination returned wrong page sizes")
        listed_ids = {item.conversation_id for item in first_page + second_page}
        expected_ids = {item.conversation_id for item in conversations}
        if listed_ids != expected_ids:
            raise AssertionError("list_conversations pagination lost or duplicated conversations")
        if any(item.messages for item in first_page + second_page):
            raise AssertionError("list_conversations must not load message JSONL bodies")


def assert_delete_conversation_removes_only_conversation() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        memory_sentinel = workspace / "ai" / "memory" / "manual_sentinel.txt"
        memory_sentinel.write_text("existing memory-side file", encoding="utf-8")
        service = ConversationPersistenceService()
        first = service.create_conversation(workspace, workspace_id, title="Delete me")
        second = service.create_conversation(workspace, workspace_id, title="Keep me")
        service.delete_conversation(workspace, first.conversation_id)
        if conversation_dir(workspace, first.conversation_id).exists():
            raise AssertionError("delete_conversation left target conversation directory behind")
        if not conversation_dir(workspace, second.conversation_id).exists():
            raise AssertionError("delete_conversation removed another conversation")
        if not memory_sentinel.exists():
            raise AssertionError("delete_conversation touched memory/")
        listed = service.list_conversations(workspace, workspace_id)
        if [item.conversation_id for item in listed] != [second.conversation_id]:
            raise AssertionError("delete_conversation did not update conversations manifest")


def assert_export_includes_citations_and_policy_decisions() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id)
        service.append_message(workspace, conversation.conversation_id, message_with_refs())
        exported = service.export_conversation(workspace, conversation.conversation_id)
        if exported["not_formal_knowledge"] is not True:
            raise AssertionError("conversation export must be marked non-formal")
        if exported["includes"]["citations"] is not True:
            raise AssertionError("conversation export must include citation metadata")
        if exported["includes"]["policy_decisions"] is not True:
            raise AssertionError("conversation export must include policy decisions")
        conversation_payload = exported["conversation"]
        if conversation_payload["citations"][0]["citation_id"] != "citation_1":
            raise AssertionError("export omitted citation records")
        if conversation_payload["policy_decisions"][0]["policy_decision_id"] != "policy_1":
            raise AssertionError("export omitted policy decision records")


def assert_corrupt_manifest_blocked() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        (workspace / "ai" / "manifest.json").write_text("{not json", encoding="utf-8")
        service = ConversationPersistenceService()
        expect_service_error(lambda: service.create_conversation(workspace, workspace_id))


def assert_corrupt_message_jsonl_blocked() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id)
        service.append_message(workspace, conversation.conversation_id, valid_message())
        messages_path = conversation_dir(workspace, conversation.conversation_id) / "messages.jsonl"
        messages_path.write_text('{"message_id": "partial"', encoding="utf-8")
        expect_service_error(lambda: service.get_conversation(workspace, conversation.conversation_id))


def assert_append_metadata_write_failure_rolls_back() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id)
        service.append_message(workspace, conversation.conversation_id, valid_message("msg_1"))
        before_messages = (conversation_dir(workspace, conversation.conversation_id) / "messages.jsonl").read_text(
            encoding="utf-8"
        )
        original_write = persistence_module.write_json_atomic

        def fail_metadata(path, data):
            if Path(path).name == "conversation.json":
                raise persistence_module.AIPersistenceIOError("forced metadata write failure")
            return original_write(path, data)

        persistence_module.write_json_atomic = fail_metadata
        try:
            expect_service_error(
                lambda: service.append_message(workspace, conversation.conversation_id, valid_message("msg_2"))
            )
        finally:
            persistence_module.write_json_atomic = original_write

        after_messages = (conversation_dir(workspace, conversation.conversation_id) / "messages.jsonl").read_text(
            encoding="utf-8"
        )
        if after_messages != before_messages:
            raise AssertionError("metadata write failure left messages.jsonl permanently ahead")
        restored = service.get_conversation(workspace, conversation.conversation_id)
        if [message.message_id for message in restored.messages] != ["msg_1"]:
            raise AssertionError("metadata write rollback did not restore original message set")
        listed = service.list_conversations(workspace, workspace_id)
        if listed[0].metadata["message_count"] != 1:
            raise AssertionError("metadata write rollback left stale list metadata")


def assert_append_manifest_write_failure_rolls_back() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id)
        service.append_message(workspace, conversation.conversation_id, valid_message("msg_1"))
        before_manifest = read_conversations_manifest(workspace)
        original_write = persistence_module.write_json_atomic

        def fail_conversations_manifest(path, data):
            target = Path(path)
            if target.name == "manifest.json" and target.parent.name == "conversations":
                raise persistence_module.AIPersistenceIOError("forced manifest write failure")
            return original_write(path, data)

        persistence_module.write_json_atomic = fail_conversations_manifest
        try:
            expect_service_error(
                lambda: service.append_message(workspace, conversation.conversation_id, valid_message("msg_2"))
            )
        finally:
            persistence_module.write_json_atomic = original_write

        restored = service.get_conversation(workspace, conversation.conversation_id)
        if [message.message_id for message in restored.messages] != ["msg_1"]:
            raise AssertionError("manifest write rollback did not restore original messages")
        after_manifest = read_conversations_manifest(workspace)
        if after_manifest != before_manifest:
            raise AssertionError("manifest write rollback changed manifest")


def assert_stale_metadata_detected_without_silent_return() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id)
        service.append_message(workspace, conversation.conversation_id, valid_message("msg_1"))
        metadata_path = conversation_dir(workspace, conversation.conversation_id) / "conversation.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["metadata"]["message_count"] = 0
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        expect_service_error(lambda: service.get_conversation(workspace, conversation.conversation_id))
        expect_service_error(lambda: service.list_conversations(workspace, workspace_id))


def assert_delete_manifest_write_failure_rolls_back_active_dir() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id)
        original_write = persistence_module.write_json_atomic

        def fail_conversations_manifest(path, data):
            target = Path(path)
            if target.name == "manifest.json" and target.parent.name == "conversations":
                raise persistence_module.AIPersistenceIOError("forced delete manifest write failure")
            return original_write(path, data)

        persistence_module.write_json_atomic = fail_conversations_manifest
        try:
            expect_service_error(lambda: service.delete_conversation(workspace, conversation.conversation_id))
        finally:
            persistence_module.write_json_atomic = original_write

        if not conversation_dir(workspace, conversation.conversation_id).exists():
            raise AssertionError("delete manifest failure did not restore active conversation dir")
        restored = service.get_conversation(workspace, conversation.conversation_id)
        if restored.conversation_id != conversation.conversation_id:
            raise AssertionError("delete rollback restored wrong conversation")
        listed = service.list_conversations(workspace, workspace_id)
        if [item.conversation_id for item in listed] != [conversation.conversation_id]:
            raise AssertionError("delete rollback left manifest inconsistent")


def assert_delete_trash_cleanup_failure_records_pending_cleanup() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        memory_sentinel = workspace / "ai" / "memory" / "manual_sentinel.txt"
        memory_sentinel.write_text("existing memory-side file", encoding="utf-8")
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id)
        original_rmtree = persistence_module.shutil.rmtree

        def fail_rmtree(path):
            raise OSError("forced trash cleanup failure")

        persistence_module.shutil.rmtree = fail_rmtree
        try:
            result = service.delete_conversation(workspace, conversation.conversation_id)
        finally:
            persistence_module.shutil.rmtree = original_rmtree

        if result is not False:
            raise AssertionError("trash cleanup failure should return cleanup-pending false")
        if conversation_dir(workspace, conversation.conversation_id).exists():
            raise AssertionError("trash cleanup failure left active conversation dir")
        expect_service_error(lambda: service.get_conversation(workspace, conversation.conversation_id))
        listed = service.list_conversations(workspace, workspace_id)
        if listed:
            raise AssertionError("trash cleanup failure left deleted conversation in active list")
        manifest = read_conversations_manifest(workspace)
        if not manifest["cleanup_pending"]:
            raise AssertionError("trash cleanup failure did not record cleanup_pending")
        if not memory_sentinel.exists():
            raise AssertionError("trash cleanup failure touched memory/")


def assert_delete_success_manifest_list_get_consistent() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id)
        if service.delete_conversation(workspace, conversation.conversation_id) is not True:
            raise AssertionError("delete_conversation should return true on full cleanup success")
        manifest = read_conversations_manifest(workspace)
        if manifest["conversations"]:
            raise AssertionError("delete success left conversation in manifest")
        expect_service_error(lambda: service.get_conversation(workspace, conversation.conversation_id))
        if service.list_conversations(workspace, workspace_id):
            raise AssertionError("delete success left conversation in list")


def assert_consistency_check_detects_orphan_and_missing_dirs() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        first = service.create_conversation(workspace, workspace_id, title="First")
        orphan = service.create_conversation(workspace, workspace_id, title="Orphan")
        manifest = read_conversations_manifest(workspace)
        manifest["conversations"] = [
            entry for entry in manifest["conversations"] if entry["conversation_id"] != orphan.conversation_id
        ]
        conversations_manifest_path(workspace).write_text(json.dumps(manifest), encoding="utf-8")
        expect_service_error(lambda: service.list_conversations(workspace, workspace_id))

        fixed_manifest = read_conversations_manifest(workspace)
        fixed_manifest["conversations"].append(
            {
                "conversation_id": orphan.conversation_id,
                "workspace_id": workspace_id,
                "title": "Orphan",
                "created_at": orphan.created_at,
                "updated_at": orphan.updated_at,
                "provider_kind": "mock",
                "message_count": 0,
                "not_formal_knowledge": True,
            }
        )
        conversations_manifest_path(workspace).write_text(json.dumps(fixed_manifest), encoding="utf-8")
        persistence_module.shutil.rmtree(conversation_dir(workspace, first.conversation_id))
        expect_service_error(lambda: service.list_conversations(workspace, workspace_id))


def assert_no_memory_knowledge_kb_or_sqlite_writes() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id)
        service.append_message(workspace, conversation.conversation_id, valid_message())
        service.get_conversation(workspace, conversation.conversation_id)
        service.export_conversation(workspace, conversation.conversation_id)
        if list((workspace / "ai" / "memory").iterdir()):
            raise AssertionError("conversation persistence created memory files")
        if (workspace / "knowledge").exists():
            raise AssertionError("conversation persistence wrote knowledge/")
        if (workspace / ".kb").exists():
            raise AssertionError("conversation persistence wrote .kb/")
        if list(workspace.rglob("*.sqlite")):
            raise AssertionError("conversation persistence created SQLite files")


def assert_no_startup_scan_or_auto_bootstrap() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        result = WorkspaceStatusService(workspace).get_status()
        if result.data is None:
            raise AssertionError("workspace status returned no data")
        if (workspace / "ai").exists():
            raise AssertionError("startup status must not bootstrap AI storage")
        service = ConversationPersistenceService()
        expect_service_error(lambda: service.list_conversations(workspace, "workspace"))
        if (workspace / "ai").exists():
            raise AssertionError("list_conversations must not bootstrap AI storage")


def assert_no_formal_search_contamination() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id)
        service.append_message(workspace, conversation.conversation_id, valid_message())
        search_result = SearchService(workspace).search("conversation", top_k=10)
        if search_result.success and search_result.data is not None and search_result.data.results:
            raise AssertionError("AI conversation data must not enter formal search results")


def assert_absolute_manifest_directory_blocked() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-conv-") as temp:
        workspace = Path(temp) / "workspace"
        workspace.mkdir()
        outside = Path(temp) / "outside"
        outside.mkdir()
        workspace_id = bootstrap_workspace(workspace)
        manifest_path = workspace / "ai" / "manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["directories"]["conversations"] = str(outside)
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        service = ConversationPersistenceService()
        expect_service_error(lambda: service.create_conversation(workspace, workspace_id))


def assert_source_has_no_forbidden_dependencies() -> None:
    source = inspect.getsource(persistence_module)
    forbidden = ["sqlite3", "knowledge_core", "SearchService", "WorkspaceStatusService", "OpenAI", "ModelScope"]
    for token in forbidden:
        if token in source:
            raise AssertionError(f"conversation persistence service uses forbidden dependency: {token}")


def main() -> int:
    assert_bootstrap_required()
    assert_create_conversation_writes_expected_files()
    assert_append_message_persists()
    assert_get_conversation_round_trip()
    assert_list_conversations_pagination()
    assert_delete_conversation_removes_only_conversation()
    assert_export_includes_citations_and_policy_decisions()
    assert_corrupt_manifest_blocked()
    assert_corrupt_message_jsonl_blocked()
    assert_append_metadata_write_failure_rolls_back()
    assert_append_manifest_write_failure_rolls_back()
    assert_stale_metadata_detected_without_silent_return()
    assert_delete_manifest_write_failure_rolls_back_active_dir()
    assert_delete_trash_cleanup_failure_records_pending_cleanup()
    assert_delete_success_manifest_list_get_consistent()
    assert_consistency_check_detects_orphan_and_missing_dirs()
    assert_no_memory_knowledge_kb_or_sqlite_writes()
    assert_no_startup_scan_or_auto_bootstrap()
    assert_no_formal_search_contamination()
    assert_absolute_manifest_directory_blocked()
    assert_source_has_no_forbidden_dependencies()

    print("AI conversation persistence tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
