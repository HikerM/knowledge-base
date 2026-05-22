"""Minimal service-layer conversation persistence for workspace AI storage.

Layout:

workspace/ai/conversations/
  manifest.json
  conv_<uuid>/
    conversation.json
    messages.jsonl

The top-level workspace/ai/manifest.json must already exist and validate. This
service never bootstraps storage, never reads or writes memory, and never uses
SQLite or formal search.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List, Optional
import uuid

from knowledge_app.ai.conversation_models import (
    ALLOWED_PROVIDER_KINDS,
    CONVERSATION_SCHEMA_VERSION,
    CitationRecord,
    ConversationModelValidationError,
    ConversationRecord,
    MessageRecord,
    PolicyDecisionRecord,
    TaskReference,
)
from knowledge_app.ai.persistence_io import AIPersistenceIOError, ensure_directory, read_json, write_json_atomic
from knowledge_app.ai.persistence_models import (
    AI_PERSISTENCE_SCHEMA_VERSION,
    AIPersistenceModelValidationError,
    AIExportPlan,
    AIStorageLayout,
    AIStorageManifest,
)


CONVERSATION_PERSISTENCE_WRITER_VERSION = "2.5.3-conversation-persistence"
CONVERSATIONS_MANIFEST_SCHEMA_VERSION = "ai-conversations-manifest-v1"
CONVERSATION_LAYOUT_VERSION = "conversation-directory-v1"

_SENSITIVE_POLICY_METADATA_KEYS = {
    "api_key",
    "authorization",
    "body",
    "content",
    "context_body",
    "context_preview_body",
    "message",
    "password",
    "prompt",
    "raw_body",
    "raw_context",
    "request_body",
    "response",
    "secret",
    "sensitive_body",
    "text",
    "token",
}


class ConversationPersistenceServiceError(RuntimeError):
    """Controlled conversation persistence failure."""


class ConversationPersistenceService:
    """Persist conversation metadata and message JSONL in workspace AI storage."""

    def create_conversation(
        self,
        workspace_root: Path | str,
        workspace_id: str,
        title: str | None = None,
        provider_kind: str = "mock",
    ) -> ConversationRecord:
        _require_text(workspace_id, "workspace_id")
        _require_provider_kind(provider_kind)
        layout = self._load_layout(workspace_root)
        _require_workspace_match(layout, workspace_id)
        conversations_root = _conversations_root(layout)
        manifest = _read_conversations_manifest(conversations_root, layout.manifest.workspace_id, required=False)

        conversation_id = _new_id("conv")
        conversation_dir = _safe_conversation_dir(conversations_root, conversation_id)
        metadata_path = conversation_dir / "conversation.json"
        messages_path = conversation_dir / "messages.jsonl"
        now = _now_iso()
        record = ConversationRecord(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            created_at=now,
            updated_at=now,
            title=_clean_title(title),
            messages=[],
            citations=[],
            tasks=[],
            policy_decisions=[],
            provider_kind=provider_kind,
            summary=None,
            metadata={
                "schema_version": CONVERSATION_SCHEMA_VERSION,
                "storage": "jsonl",
                "layout": CONVERSATION_LAYOUT_VERSION,
                "not_formal_knowledge": True,
                "not_long_term_memory": True,
                "writer_version": CONVERSATION_PERSISTENCE_WRITER_VERSION,
                "message_count": 0,
            },
        ).validate()

        created_dir = False
        try:
            ensure_directory(conversation_dir)
            created_dir = True
            _write_messages_jsonl_atomic(messages_path, [])
            write_json_atomic(metadata_path, _metadata_payload(record))
            updated_manifest = _upsert_manifest_entry(manifest, _manifest_entry(record))
            _write_conversations_manifest(conversations_root, updated_manifest)
            _assert_conversation_consistency(conversations_root, conversation_id, updated_manifest)
            return _clone_conversation(record)
        except (
            AIPersistenceIOError,
            AIPersistenceModelValidationError,
            ConversationModelValidationError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            if created_dir:
                _remove_tree_quietly(conversation_dir)
            raise ConversationPersistenceServiceError(f"create conversation failed: {exc}") from exc

    def append_message(
        self,
        workspace_root: Path | str,
        conversation_id: str,
        message: MessageRecord | Dict[str, Any],
    ) -> ConversationRecord:
        layout = self._load_layout(workspace_root)
        conversations_root = _conversations_root(layout)
        conversation_dir = _safe_existing_conversation_dir(conversations_root, conversation_id)
        metadata_path = conversation_dir / "conversation.json"
        messages_path = conversation_dir / "messages.jsonl"

        try:
            metadata_record = _read_conversation_metadata(metadata_path)
            messages = _read_messages_jsonl(messages_path)
            manifest = _read_conversations_manifest(conversations_root, layout.manifest.workspace_id, required=False)
            _assert_conversation_consistency(conversations_root, conversation_id, manifest)
            payload = dict(message.to_dict() if isinstance(message, MessageRecord) else message)
            message_record = _coerce_message_record(payload, metadata_record.provider_kind)
            citation_records = _coerce_citation_records(payload.get("citation_records", []))
            task_references = _coerce_task_references(payload.get("task_references", []))
            policy_decisions = _coerce_policy_decisions(payload.get("policy_decision_records", []))

            now = _now_iso()
            metadata = dict(metadata_record.metadata)
            metadata["message_count"] = len(messages) + 1
            metadata["writer_version"] = CONVERSATION_PERSISTENCE_WRITER_VERSION
            updated = replace(
                metadata_record,
                updated_at=now,
                citations=_merge_by_id(metadata_record.citations, citation_records, "citation_id"),
                tasks=_merge_by_id(metadata_record.tasks, task_references, "task_id"),
                policy_decisions=_merge_by_id(
                    metadata_record.policy_decisions,
                    policy_decisions,
                    "policy_decision_id",
                ),
                metadata=metadata,
            ).validate()

            updated_messages = [*messages, message_record]
            updated_metadata_payload = _metadata_payload(updated)
            updated_manifest = _upsert_manifest_entry(manifest, _manifest_entry(updated))

            _serialize_messages_jsonl(updated_messages)
            json.dumps(updated_metadata_payload, ensure_ascii=False, indent=2, sort_keys=True)
            _validate_conversations_manifest(updated_manifest, layout.manifest.workspace_id)

            backups = _capture_file_backups([messages_path, metadata_path, conversations_root / "manifest.json"])
            try:
                _write_messages_jsonl_atomic(messages_path, updated_messages)
                write_json_atomic(metadata_path, updated_metadata_payload)
                _write_conversations_manifest(conversations_root, updated_manifest)
                _assert_conversation_consistency(conversations_root, conversation_id, updated_manifest)
            except (
                AIPersistenceIOError,
                AIPersistenceModelValidationError,
                ConversationModelValidationError,
                ConversationPersistenceServiceError,
                OSError,
                TypeError,
                ValueError,
            ) as write_exc:
                _restore_file_backups(backups)
                _assert_conversation_consistency(conversations_root, conversation_id, manifest)
                raise ConversationPersistenceServiceError(f"append message rolled back after write failure: {write_exc}") from write_exc
            return _clone_conversation(
                replace(
                    _read_conversation_metadata(metadata_path),
                    messages=_read_messages_jsonl(messages_path),
                ).validate()
            )
        except (
            AIPersistenceIOError,
            AIPersistenceModelValidationError,
            ConversationModelValidationError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ConversationPersistenceServiceError(f"append message failed: {exc}") from exc

    def get_conversation(self, workspace_root: Path | str, conversation_id: str) -> ConversationRecord:
        layout = self._load_layout(workspace_root)
        conversations_root = _conversations_root(layout)
        conversation_dir = _safe_existing_conversation_dir(conversations_root, conversation_id)
        try:
            metadata_record = _read_conversation_metadata(conversation_dir / "conversation.json")
            messages = _read_messages_jsonl(conversation_dir / "messages.jsonl")
            manifest = _read_conversations_manifest(conversations_root, layout.manifest.workspace_id, required=False)
            _assert_conversation_consistency(conversations_root, conversation_id, manifest)
            return _clone_conversation(replace(metadata_record, messages=messages).validate())
        except (
            AIPersistenceIOError,
            ConversationModelValidationError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ConversationPersistenceServiceError(f"get conversation failed: {exc}") from exc

    def list_conversations(
        self,
        workspace_root: Path | str,
        workspace_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ConversationRecord]:
        _require_text(workspace_id, "workspace_id")
        _require_positive_int(limit, "limit")
        _require_non_negative_int(offset, "offset")
        layout = self._load_layout(workspace_root)
        _require_workspace_match(layout, workspace_id)
        conversations_root = _conversations_root(layout)
        try:
            manifest = _read_conversations_manifest(conversations_root, workspace_id, required=False)
            _assert_conversations_manifest_consistency(conversations_root, manifest)
            entries = [entry for entry in manifest["conversations"] if entry["workspace_id"] == workspace_id]
            entries.sort(key=lambda item: (item["updated_at"], item["created_at"], item["conversation_id"]), reverse=True)
            page = entries[offset : offset + limit]
            records = []
            for entry in page:
                conversation_dir = _safe_existing_conversation_dir(conversations_root, entry["conversation_id"])
                _assert_conversation_consistency(conversations_root, entry["conversation_id"], manifest)
                records.append(_clone_conversation(_read_conversation_metadata(conversation_dir / "conversation.json")))
            return records
        except (
            AIPersistenceIOError,
            AIPersistenceModelValidationError,
            ConversationModelValidationError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ConversationPersistenceServiceError(f"list conversations failed: {exc}") from exc

    def delete_conversation(self, workspace_root: Path | str, conversation_id: str) -> bool:
        layout = self._load_layout(workspace_root)
        conversations_root = _conversations_root(layout)
        conversation_dir = _safe_existing_conversation_dir(conversations_root, conversation_id)
        trash_dir = conversations_root / f".trash_{conversation_id}_{uuid.uuid4().hex}"
        _assert_under(trash_dir, conversations_root, "delete trash path")
        manifest = _read_conversations_manifest(conversations_root, layout.manifest.workspace_id, required=False)
        _assert_conversation_consistency(conversations_root, conversation_id, manifest)
        updated_manifest = _remove_manifest_entry(manifest, conversation_id)
        try:
            conversation_dir.rename(trash_dir)
            _write_conversations_manifest(conversations_root, updated_manifest)
        except (
            AIPersistenceIOError,
            AIPersistenceModelValidationError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            if trash_dir.exists() and not conversation_dir.exists():
                try:
                    trash_dir.rename(conversation_dir)
                except OSError as rollback_exc:
                    raise ConversationPersistenceServiceError(
                        f"delete conversation failed and rollback failed; repair required: {rollback_exc}"
                    ) from exc
            _assert_conversation_consistency(conversations_root, conversation_id, manifest)
            raise ConversationPersistenceServiceError(f"delete conversation failed: {exc}") from exc

        try:
            shutil.rmtree(trash_dir)
            _assert_deleted_conversation_consistency(conversations_root, conversation_id, updated_manifest)
            return True
        except OSError as cleanup_exc:
            cleanup_manifest = _add_cleanup_pending_entry(
                _read_conversations_manifest(conversations_root, layout.manifest.workspace_id, required=False),
                conversation_id,
                trash_dir.name,
                str(cleanup_exc),
            )
            _write_conversations_manifest(conversations_root, cleanup_manifest)
            _assert_deleted_conversation_consistency(conversations_root, conversation_id, cleanup_manifest)
            return False
        except (
            AIPersistenceIOError,
            AIPersistenceModelValidationError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ConversationPersistenceServiceError(f"delete conversation cleanup state failed: {exc}") from exc

    def export_conversation(self, workspace_root: Path | str, conversation_id: str) -> Dict[str, Any]:
        layout = self._load_layout(workspace_root)
        conversation = self.get_conversation(workspace_root, conversation_id)
        export_plan = AIExportPlan(
            schema_version=AI_PERSISTENCE_SCHEMA_VERSION,
            export_id=_new_id("export"),
            workspace_id=conversation.workspace_id,
            export_scope="one_conversation",
            source_ids=[conversation.conversation_id],
            include_task_logs=False,
            not_formal_knowledge=True,
        ).validate()
        return {
            "schema_version": AI_PERSISTENCE_SCHEMA_VERSION,
            "export_plan": export_plan.to_dict(),
            "conversation": conversation.to_dict(),
            "layout": {
                "storage_root": "ai/conversations/",
                "conversation_directory": f"ai/conversations/{conversation.conversation_id}/",
                "metadata_file": "conversation.json",
                "messages_file": "messages.jsonl",
            },
            "includes": {
                "metadata": True,
                "messages": True,
                "citations": True,
                "policy_decisions": True,
                "task_references": True,
                "task_logs": False,
                "memory": False,
                "formal_search_records": False,
            },
            "not_formal_knowledge": True,
            "warning": "AI conversation exports are not formal knowledge and must not enter formal search.",
            "workspace_manifest_schema": layout.manifest.schema_version,
        }

    def _load_layout(self, workspace_root: Path | str) -> AIStorageLayout:
        workspace = _resolve_workspace(workspace_root)
        ai_root = workspace / "ai"
        manifest_path = ai_root / "manifest.json"
        if not manifest_path.exists():
            raise ConversationPersistenceServiceError("AI storage is not bootstrapped; workspace/ai/manifest.json is required")
        if not manifest_path.is_file():
            raise ConversationPersistenceServiceError("workspace/ai/manifest.json is not a file")
        try:
            manifest = AIStorageManifest.from_dict(read_json(manifest_path))
            manifest.validate(str(workspace))
            conversations_path = _resolve_manifest_directory(workspace, manifest.directories["conversations"])
            memory_path = _resolve_manifest_directory(workspace, manifest.directories["memory"])
            drafts_path = _resolve_manifest_directory(workspace, manifest.directories["drafts"])
            indexes_path = _resolve_manifest_directory(workspace, manifest.directories["indexes"])
            layout = AIStorageLayout(
                schema_version=AI_PERSISTENCE_SCHEMA_VERSION,
                workspace_id=manifest.workspace_id,
                workspace_root=str(workspace),
                storage_root=str(ai_root),
                conversations_path=str(conversations_path),
                memory_path=str(memory_path),
                drafts_path=str(drafts_path),
                indexes_path=str(indexes_path),
                manifest=manifest,
                install_root=None,
                source_records_are_truth=True,
                indexes_derived_only=True,
                indexes_rebuildable=True,
                storage_growth_limit_mb=1024,
            ).validate()
            if not conversations_path.exists() or not conversations_path.is_dir():
                raise ConversationPersistenceServiceError("workspace/ai/conversations is missing or not a directory")
            _assert_under(conversations_path, ai_root.resolve(), "conversations path")
            return layout
        except (
            AIPersistenceIOError,
            AIPersistenceModelValidationError,
            ConversationPersistenceServiceError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            if isinstance(exc, ConversationPersistenceServiceError):
                raise
            raise ConversationPersistenceServiceError(f"AI storage manifest is corrupt or invalid: {exc}") from exc


def _read_conversation_metadata(path: Path) -> ConversationRecord:
    payload = read_json(path)
    if payload.get("messages") != []:
        raise ConversationPersistenceServiceError("conversation.json must not embed messages; messages.jsonl is the source")
    return ConversationRecord.from_dict(payload)


def _metadata_payload(record: ConversationRecord) -> Dict[str, Any]:
    payload = record.to_dict()
    payload["messages"] = []
    payload["metadata"] = dict(payload["metadata"])
    payload["metadata"]["not_formal_knowledge"] = True
    payload["metadata"]["not_long_term_memory"] = True
    payload["metadata"]["layout"] = CONVERSATION_LAYOUT_VERSION
    return payload


def _read_messages_jsonl(path: Path) -> List[MessageRecord]:
    if not path.exists():
        raise ConversationPersistenceServiceError(f"messages file does not exist: {path}")
    if not path.is_file():
        raise ConversationPersistenceServiceError(f"messages path is not a file: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AIPersistenceIOError(f"could not read JSONL: {path}: {exc}") from exc
    if text and not text.endswith("\n"):
        raise ConversationPersistenceServiceError("messages.jsonl has a partial final line")
    records: List[MessageRecord] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise ConversationPersistenceServiceError(f"messages.jsonl contains blank line at {line_number}")
        try:
            payload = json.loads(line)
            records.append(MessageRecord.from_dict(payload))
        except (json.JSONDecodeError, ConversationModelValidationError) as exc:
            raise ConversationPersistenceServiceError(f"messages.jsonl corrupt at line {line_number}: {exc}") from exc
    return records


def _serialize_messages_jsonl(messages: List[MessageRecord]) -> str:
    lines = []
    for message in messages:
        lines.append(json.dumps(message.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return "".join(f"{line}\n" for line in lines)


def _write_messages_jsonl_atomic(path: Path, messages: List[MessageRecord]) -> Path:
    parent = path.parent
    if not parent.exists() or not parent.is_dir():
        raise AIPersistenceIOError(f"target parent directory does not exist: {parent}")
    serialized = _serialize_messages_jsonl(messages)
    temp_path: Path | None = None
    try:
        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(parent),
            text=True,
        )
        temp_path = Path(temp_name)
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            _fsync_file(handle)
        os.replace(str(temp_path), str(path))
        _fsync_directory(parent)
        return path.resolve()
    except (OSError, TypeError, ValueError, ConversationModelValidationError) as exc:
        if temp_path is not None:
            _remove_file_quietly(temp_path)
        raise AIPersistenceIOError(f"could not write JSONL atomically: {path}: {exc}") from exc


def _read_conversations_manifest(conversations_root: Path, workspace_id: str, required: bool) -> Dict[str, Any]:
    path = conversations_root / "manifest.json"
    if not path.exists():
        if required:
            raise ConversationPersistenceServiceError("workspace/ai/conversations/manifest.json is required")
        return _empty_conversations_manifest(workspace_id)
    payload = read_json(path)
    return _validate_conversations_manifest(payload, workspace_id)


def _write_conversations_manifest(conversations_root: Path, payload: Dict[str, Any]) -> None:
    workspace_id = str(payload.get("workspace_id") or "")
    validated = _validate_conversations_manifest(payload, workspace_id)
    write_json_atomic(conversations_root / "manifest.json", validated)


def _empty_conversations_manifest(workspace_id: str) -> Dict[str, Any]:
    return {
        "schema_version": CONVERSATIONS_MANIFEST_SCHEMA_VERSION,
        "workspace_id": workspace_id,
        "layout": CONVERSATION_LAYOUT_VERSION,
        "not_formal_knowledge": True,
        "not_long_term_memory": True,
        "writer_version": CONVERSATION_PERSISTENCE_WRITER_VERSION,
        "conversations": [],
        "cleanup_pending": [],
    }


def _validate_conversations_manifest(payload: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ConversationPersistenceServiceError("conversations manifest must be a dictionary")
    if payload.get("schema_version") != CONVERSATIONS_MANIFEST_SCHEMA_VERSION:
        raise ConversationPersistenceServiceError("unsupported conversations manifest schema_version")
    if payload.get("workspace_id") != workspace_id:
        raise ConversationPersistenceServiceError("conversations manifest workspace_id mismatch")
    if payload.get("layout") != CONVERSATION_LAYOUT_VERSION:
        raise ConversationPersistenceServiceError("unsupported conversations manifest layout")
    if type(payload.get("not_formal_knowledge")) is not bool or payload["not_formal_knowledge"] is not True:
        raise ConversationPersistenceServiceError("conversations manifest must set not_formal_knowledge=true")
    if type(payload.get("not_long_term_memory")) is not bool or payload["not_long_term_memory"] is not True:
        raise ConversationPersistenceServiceError("conversations manifest must set not_long_term_memory=true")
    conversations = payload.get("conversations")
    if not isinstance(conversations, list):
        raise ConversationPersistenceServiceError("conversations manifest conversations must be a list")
    cleanup_pending = payload.get("cleanup_pending", [])
    if not isinstance(cleanup_pending, list):
        raise ConversationPersistenceServiceError("conversations manifest cleanup_pending must be a list")
    seen: set[str] = set()
    validated_entries = []
    for index, entry in enumerate(conversations):
        if not isinstance(entry, dict):
            raise ConversationPersistenceServiceError(f"conversations manifest entry {index} must be a dictionary")
        conversation_id = str(entry.get("conversation_id") or "")
        _validate_conversation_id(conversation_id)
        if conversation_id in seen:
            raise ConversationPersistenceServiceError(f"duplicate conversation entry: {conversation_id}")
        seen.add(conversation_id)
        if entry.get("workspace_id") != workspace_id:
            raise ConversationPersistenceServiceError(f"conversation entry workspace mismatch: {conversation_id}")
        provider_kind = str(entry.get("provider_kind") or "")
        _require_provider_kind(provider_kind)
        validated_entries.append(
            {
                "conversation_id": conversation_id,
                "workspace_id": workspace_id,
                "title": _clean_title(str(entry.get("title") or "")),
                "created_at": _require_text_value(entry.get("created_at"), "created_at"),
                "updated_at": _require_text_value(entry.get("updated_at"), "updated_at"),
                "provider_kind": provider_kind,
                "message_count": _require_non_negative_int_value(entry.get("message_count"), "message_count"),
                "not_formal_knowledge": _require_true_bool(entry.get("not_formal_knowledge"), "not_formal_knowledge"),
            }
        )
    validated_cleanup = []
    for index, entry in enumerate(cleanup_pending):
        if not isinstance(entry, dict):
            raise ConversationPersistenceServiceError(f"cleanup_pending entry {index} must be a dictionary")
        conversation_id = str(entry.get("conversation_id") or "")
        _validate_conversation_id(conversation_id)
        trash_dir = _require_text_value(entry.get("trash_dir"), "cleanup_pending.trash_dir")
        if "/" in trash_dir or "\\" in trash_dir or not trash_dir.startswith(f".trash_{conversation_id}_"):
            raise ConversationPersistenceServiceError("cleanup_pending trash_dir must be a local trash directory name")
        validated_cleanup.append(
            {
                "conversation_id": conversation_id,
                "trash_dir": trash_dir,
                "created_at": _require_text_value(entry.get("created_at"), "cleanup_pending.created_at"),
                "error": _require_text_value(entry.get("error"), "cleanup_pending.error"),
            }
        )
    return {
        "schema_version": CONVERSATIONS_MANIFEST_SCHEMA_VERSION,
        "workspace_id": workspace_id,
        "layout": CONVERSATION_LAYOUT_VERSION,
        "not_formal_knowledge": True,
        "not_long_term_memory": True,
        "writer_version": str(payload.get("writer_version") or CONVERSATION_PERSISTENCE_WRITER_VERSION),
        "conversations": validated_entries,
        "cleanup_pending": validated_cleanup,
    }


def _manifest_entry(record: ConversationRecord) -> Dict[str, Any]:
    message_count = record.metadata.get("message_count")
    if type(message_count) is not int:
        message_count = len(record.messages)
    return {
        "conversation_id": record.conversation_id,
        "workspace_id": record.workspace_id,
        "title": record.title,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "provider_kind": record.provider_kind,
        "message_count": message_count,
        "not_formal_knowledge": True,
    }


def _upsert_manifest_entry(manifest: Dict[str, Any], entry: Dict[str, Any]) -> Dict[str, Any]:
    entries = [item for item in manifest["conversations"] if item["conversation_id"] != entry["conversation_id"]]
    entries.append(entry)
    updated = dict(manifest)
    updated["writer_version"] = CONVERSATION_PERSISTENCE_WRITER_VERSION
    updated["conversations"] = entries
    return updated


def _remove_manifest_entry(manifest: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
    _validate_conversation_id(conversation_id)
    updated = dict(manifest)
    updated["writer_version"] = CONVERSATION_PERSISTENCE_WRITER_VERSION
    updated["conversations"] = [
        item for item in manifest["conversations"] if item["conversation_id"] != conversation_id
    ]
    return updated


def _add_cleanup_pending_entry(
    manifest: Dict[str, Any],
    conversation_id: str,
    trash_dir_name: str,
    error: str,
) -> Dict[str, Any]:
    _validate_conversation_id(conversation_id)
    updated = dict(manifest)
    pending = [
        item
        for item in manifest.get("cleanup_pending", [])
        if item.get("conversation_id") != conversation_id or item.get("trash_dir") != trash_dir_name
    ]
    pending.append(
        {
            "conversation_id": conversation_id,
            "trash_dir": trash_dir_name,
            "created_at": _now_iso(),
            "error": error or "trash cleanup failed",
        }
    )
    updated["cleanup_pending"] = pending
    updated["writer_version"] = CONVERSATION_PERSISTENCE_WRITER_VERSION
    return _validate_conversations_manifest(updated, str(updated.get("workspace_id") or ""))


def _manifest_entry_for(manifest: Dict[str, Any], conversation_id: str) -> Optional[Dict[str, Any]]:
    for entry in manifest["conversations"]:
        if entry["conversation_id"] == conversation_id:
            return entry
    return None


def _assert_conversation_consistency(
    conversations_root: Path,
    conversation_id: str,
    manifest: Optional[Dict[str, Any]],
) -> None:
    conversation_dir = _safe_existing_conversation_dir(conversations_root, conversation_id)
    metadata_record = _read_conversation_metadata(conversation_dir / "conversation.json")
    messages = _read_messages_jsonl(conversation_dir / "messages.jsonl")
    if metadata_record.conversation_id != conversation_id:
        raise ConversationPersistenceServiceError("conversation metadata id does not match directory")
    message_count = metadata_record.metadata.get("message_count")
    if type(message_count) is not int:
        raise ConversationPersistenceServiceError("conversation metadata message_count must be an integer")
    if message_count != len(messages):
        raise ConversationPersistenceServiceError("conversation metadata message_count does not match messages.jsonl")
    if manifest is None:
        return
    entry = _manifest_entry_for(manifest, conversation_id)
    if entry is None:
        raise ConversationPersistenceServiceError("conversations manifest is missing conversation entry")
    if entry["workspace_id"] != metadata_record.workspace_id:
        raise ConversationPersistenceServiceError("manifest workspace_id does not match conversation metadata")
    if entry["title"] != metadata_record.title:
        raise ConversationPersistenceServiceError("manifest title does not match conversation metadata")
    if entry["updated_at"] != metadata_record.updated_at:
        raise ConversationPersistenceServiceError("manifest updated_at does not match conversation metadata")
    if entry["provider_kind"] != metadata_record.provider_kind:
        raise ConversationPersistenceServiceError("manifest provider_kind does not match conversation metadata")
    if entry["message_count"] != message_count:
        raise ConversationPersistenceServiceError("manifest message_count does not match conversation metadata")


def _assert_deleted_conversation_consistency(
    conversations_root: Path,
    conversation_id: str,
    manifest: Dict[str, Any],
) -> None:
    _validate_conversation_id(conversation_id)
    active_path = _safe_conversation_dir(conversations_root, conversation_id)
    if active_path.exists():
        raise ConversationPersistenceServiceError("deleted conversation still has an active directory")
    if _manifest_entry_for(manifest, conversation_id) is not None:
        raise ConversationPersistenceServiceError("deleted conversation is still listed in manifest")


def _assert_conversations_manifest_consistency(conversations_root: Path, manifest: Dict[str, Any]) -> None:
    manifest_ids = {entry["conversation_id"] for entry in manifest["conversations"]}
    missing_dirs = _detect_manifest_missing_conversation_dir(conversations_root, manifest)
    if missing_dirs:
        raise ConversationPersistenceServiceError(f"manifest references missing conversation dirs: {', '.join(missing_dirs)}")
    orphan_dirs = _detect_orphan_conversation_dirs(conversations_root, manifest)
    if orphan_dirs:
        raise ConversationPersistenceServiceError(f"orphan conversation dirs detected: {', '.join(orphan_dirs)}")
    for conversation_id in sorted(manifest_ids):
        _assert_conversation_consistency(conversations_root, conversation_id, manifest)


def _detect_orphan_conversation_dirs(conversations_root: Path, manifest: Dict[str, Any]) -> List[str]:
    manifest_ids = {entry["conversation_id"] for entry in manifest["conversations"]}
    orphan_dirs = []
    for child in conversations_root.iterdir():
        if child.is_dir() and child.name.startswith("conv_") and child.name not in manifest_ids:
            orphan_dirs.append(child.name)
    return sorted(orphan_dirs)


def _detect_manifest_missing_conversation_dir(conversations_root: Path, manifest: Dict[str, Any]) -> List[str]:
    missing = []
    for entry in manifest["conversations"]:
        if not _safe_conversation_dir(conversations_root, entry["conversation_id"]).is_dir():
            missing.append(entry["conversation_id"])
    return sorted(missing)


def _coerce_message_record(payload: Dict[str, Any], default_provider_kind: str) -> MessageRecord:
    metadata = dict(payload.get("metadata") or {})
    provider_kind = metadata.get("provider_kind", default_provider_kind)
    _require_provider_kind(provider_kind)
    metadata["provider_kind"] = provider_kind
    metadata["schema_version"] = str(metadata.get("schema_version") or CONVERSATION_SCHEMA_VERSION)
    metadata["not_formal_knowledge"] = True
    payload["metadata"] = metadata
    return MessageRecord.from_dict(payload)


def _coerce_citation_records(values: Any) -> List[CitationRecord]:
    return [CitationRecord.from_dict(item) for item in _require_list(values, "citation_records")]


def _coerce_task_references(values: Any) -> List[TaskReference]:
    return [TaskReference.from_dict(item) for item in _require_list(values, "task_references")]


def _coerce_policy_decisions(values: Any) -> List[PolicyDecisionRecord]:
    decisions = [PolicyDecisionRecord.from_dict(item) for item in _require_list(values, "policy_decision_records")]
    for decision in decisions:
        _reject_sensitive_policy_metadata(decision.metadata)
    return decisions


def _reject_sensitive_policy_metadata(payload: Dict[str, Any]) -> None:
    for key, value in payload.items():
        normalized = str(key).lower()
        if normalized in _SENSITIVE_POLICY_METADATA_KEYS:
            raise ConversationPersistenceServiceError("policy decision metadata must not copy sensitive body fields")
        if isinstance(value, dict):
            _reject_sensitive_policy_metadata(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _reject_sensitive_policy_metadata(item)


def _merge_by_id(existing: List[Any], incoming: List[Any], key: str) -> List[Any]:
    if not incoming:
        return list(existing)
    merged: Dict[str, Any] = {str(getattr(item, key)): item for item in existing}
    for item in incoming:
        merged[str(getattr(item, key))] = item
    return list(merged.values())


def _conversations_root(layout: AIStorageLayout) -> Path:
    return Path(layout.conversations_path).resolve()


def _safe_conversation_dir(conversations_root: Path, conversation_id: str) -> Path:
    _validate_conversation_id(conversation_id)
    target = (conversations_root / conversation_id).resolve()
    _assert_under(target, conversations_root, "conversation path")
    return target


def _safe_existing_conversation_dir(conversations_root: Path, conversation_id: str) -> Path:
    target = _safe_conversation_dir(conversations_root, conversation_id)
    if not target.exists():
        raise ConversationPersistenceServiceError(f"conversation not found: {conversation_id}")
    if not target.is_dir():
        raise ConversationPersistenceServiceError(f"conversation path is not a directory: {conversation_id}")
    return target


def _resolve_workspace(workspace_root: Path | str) -> Path:
    workspace = Path(workspace_root).expanduser().resolve()
    if not workspace.exists():
        raise ConversationPersistenceServiceError(f"workspace_root does not exist: {workspace}")
    if not workspace.is_dir():
        raise ConversationPersistenceServiceError(f"workspace_root is not a directory: {workspace}")
    return workspace


def _resolve_manifest_directory(workspace: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute():
        raise ConversationPersistenceServiceError("manifest directory paths must be workspace-relative")
    target = (workspace / relative_path).resolve()
    _assert_under(target, workspace.resolve() / "ai", "manifest directory")
    return target


def _assert_under(child: Path, parent: Path, field_name: str) -> None:
    child_resolved = child.resolve()
    parent_resolved = parent.resolve()
    try:
        child_resolved.relative_to(parent_resolved)
    except ValueError as exc:
        raise ConversationPersistenceServiceError(f"{field_name} must stay under {parent_resolved}") from exc


def _validate_conversation_id(conversation_id: str) -> None:
    _require_text(conversation_id, "conversation_id")
    if not conversation_id.startswith("conv_"):
        raise ConversationPersistenceServiceError("conversation_id must start with conv_")
    suffix = conversation_id.removeprefix("conv_")
    if len(suffix) != 32 or any(character not in "0123456789abcdef" for character in suffix):
        raise ConversationPersistenceServiceError("conversation_id must be a generated conv_<uuid> id")


def _require_workspace_match(layout: AIStorageLayout, workspace_id: str) -> None:
    if layout.manifest.workspace_id != workspace_id:
        raise ConversationPersistenceServiceError("workspace_id does not match AI storage manifest")


def _require_provider_kind(provider_kind: Any) -> None:
    if not isinstance(provider_kind, str) or provider_kind not in ALLOWED_PROVIDER_KINDS:
        raise ConversationPersistenceServiceError(
            f"provider_kind must be one of: {', '.join(sorted(ALLOWED_PROVIDER_KINDS))}"
        )


def _require_text(value: Any, field_name: str) -> None:
    if value is None or not str(value).strip():
        raise ConversationPersistenceServiceError(f"{field_name} is required")


def _require_text_value(value: Any, field_name: str) -> str:
    _require_text(value, field_name)
    return str(value)


def _require_true_bool(value: Any, field_name: str) -> bool:
    if type(value) is not bool or value is not True:
        raise ConversationPersistenceServiceError(f"{field_name} must be true")
    return True


def _require_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise ConversationModelValidationError(f"{field_name} must be a list")
    return value


def _require_positive_int(value: Any, field_name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ConversationPersistenceServiceError(f"{field_name} must be a positive integer")


def _require_non_negative_int(value: Any, field_name: str) -> None:
    if type(value) is not int or value < 0:
        raise ConversationPersistenceServiceError(f"{field_name} must be a non-negative integer")


def _require_non_negative_int_value(value: Any, field_name: str) -> int:
    _require_non_negative_int(value, field_name)
    return value


def _clean_title(title: str | None) -> str:
    if title is None:
        return "Conversation"
    text = str(title).strip()
    return text or "Conversation"


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _clone_conversation(record: ConversationRecord) -> ConversationRecord:
    return ConversationRecord.from_dict(record.to_dict())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _fsync_file(handle: Any) -> None:
    try:
        os.fsync(handle.fileno())
    except OSError:
        pass


def _fsync_directory(directory: Path) -> None:
    try:
        descriptor = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _capture_file_backups(paths: List[Path]) -> Dict[Path, Optional[bytes]]:
    backups: Dict[Path, Optional[bytes]] = {}
    for path in paths:
        try:
            backups[path] = path.read_bytes() if path.exists() else None
        except OSError as exc:
            raise ConversationPersistenceServiceError(f"could not capture persistence backup: {path}: {exc}") from exc
    return backups


def _restore_file_backups(backups: Dict[Path, Optional[bytes]]) -> None:
    errors = []
    for path, data in backups.items():
        try:
            _restore_file_bytes(path, data)
        except OSError as exc:
            errors.append(f"{path}: {exc}")
    if errors:
        joined = "; ".join(errors)
        raise ConversationPersistenceServiceError(f"rollback failed; repair required: {joined}")


def _restore_file_bytes(path: Path, data: Optional[bytes]) -> None:
    if data is None:
        if path.exists():
            path.unlink()
        return
    parent = path.parent
    if not parent.exists() or not parent.is_dir():
        raise OSError(f"restore parent directory does not exist: {parent}")
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.restore.",
        suffix=".tmp",
        dir=str(parent),
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            _fsync_file(handle)
        os.replace(str(temp_path), str(path))
        _fsync_directory(parent)
    except OSError:
        _remove_file_quietly(temp_path)
        raise


def _remove_file_quietly(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def _remove_tree_quietly(path: Path) -> None:
    try:
        if path.exists():
            shutil.rmtree(path)
    except OSError:
        pass
