"""In-memory ConversationStore harness for service-layer behavior tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid

from knowledge_app.ai.conversation_models import (
    CONVERSATION_SCHEMA_VERSION,
    ALLOWED_PROVIDER_KINDS,
    CitationRecord,
    ConversationModelValidationError,
    ConversationRecord,
    ConversationSummary,
    MessageRecord,
    PolicyDecisionRecord,
    TaskReference,
)


class ConversationStoreError(ValueError):
    """Raised when the in-memory conversation harness cannot satisfy a request."""


class ConversationStore:
    """Process-local ConversationStore harness with no persistence behavior."""

    def __init__(self) -> None:
        self._conversations: Dict[str, ConversationRecord] = {}
        self._sequence = 0

    def create_conversation(
        self,
        workspace_id: str,
        title: str | None = None,
        provider_kind: str = "mock",
    ) -> ConversationRecord:
        _require_text(workspace_id, "workspace_id")
        if provider_kind not in ALLOWED_PROVIDER_KINDS:
            raise ConversationStoreError(f"provider_kind must be one of: {', '.join(sorted(ALLOWED_PROVIDER_KINDS))}")
        now = _now_iso()
        conversation = ConversationRecord(
            conversation_id=_new_id("conv"),
            workspace_id=workspace_id,
            created_at=now,
            updated_at=now,
            title=_clean_title(title),
            messages=[],
            citations=[],
            tasks=[],
            policy_decisions=[],
            provider_kind=provider_kind,
            metadata={
                "schema_version": CONVERSATION_SCHEMA_VERSION,
                "storage": "in_memory",
                "not_formal_knowledge": True,
                "not_long_term_memory": True,
                "sort_sequence": self._next_sequence(),
            },
        ).validate()
        self._conversations[conversation.conversation_id] = conversation
        return _clone_conversation(conversation)

    def append_message(self, conversation_id: str, message: MessageRecord | Dict[str, Any]) -> ConversationRecord:
        conversation = self._get_existing(conversation_id)
        payload = dict(message.to_dict() if isinstance(message, MessageRecord) else message)
        message_record = MessageRecord.from_dict(payload)
        citation_records = _coerce_citation_records(payload.get("citation_records", []))
        task_references = _coerce_task_references(payload.get("task_references", []))
        policy_decisions = _coerce_policy_decisions(payload.get("policy_decision_records", []))

        now = _now_iso()
        metadata = dict(conversation.metadata)
        metadata["sort_sequence"] = self._next_sequence()
        updated = replace(
            conversation,
            updated_at=now,
            messages=[*conversation.messages, message_record],
            citations=_merge_by_id(conversation.citations, citation_records, "citation_id"),
            tasks=_merge_by_id(conversation.tasks, task_references, "task_id"),
            policy_decisions=_merge_by_id(
                conversation.policy_decisions,
                policy_decisions,
                "policy_decision_id",
            ),
            metadata=metadata,
        ).validate()
        self._conversations[conversation_id] = updated
        return _clone_conversation(updated)

    def get_conversation(self, conversation_id: str) -> ConversationRecord:
        return _clone_conversation(self._get_existing(conversation_id))

    def list_conversations(self, workspace_id: str, limit: int = 50, offset: int = 0) -> List[ConversationRecord]:
        _require_text(workspace_id, "workspace_id")
        _require_non_negative_int(offset, "offset")
        _require_positive_int(limit, "limit")
        records = [record for record in self._conversations.values() if record.workspace_id == workspace_id]
        records.sort(key=lambda item: (_sort_sequence(item), item.updated_at, item.created_at), reverse=True)
        return [_clone_conversation(record) for record in records[offset : offset + limit]]

    def delete_conversation(self, conversation_id: str) -> bool:
        self._get_existing(conversation_id)
        del self._conversations[conversation_id]
        return True

    def clear_conversations(self, workspace_id: str) -> int:
        _require_text(workspace_id, "workspace_id")
        conversation_ids = [
            conversation_id
            for conversation_id, record in self._conversations.items()
            if record.workspace_id == workspace_id
        ]
        for conversation_id in conversation_ids:
            del self._conversations[conversation_id]
        return len(conversation_ids)

    def summarize_conversation_placeholder(self, conversation_id: str) -> ConversationSummary:
        conversation = self._get_existing(conversation_id)
        if not conversation.messages:
            raise ConversationStoreError("cannot summarize a conversation with no messages")
        now = _now_iso()
        metadata = dict(conversation.metadata)
        metadata["sort_sequence"] = self._next_sequence()
        source_message_ids = [message.message_id for message in conversation.messages]
        summary = ConversationSummary(
            text=f"Placeholder summary for {len(source_message_ids)} message(s); not long-term memory.",
            created_at=now,
            source_message_ids=source_message_ids,
            not_long_term_memory=True,
        ).validate()
        updated = replace(conversation, updated_at=now, summary=summary, metadata=metadata).validate()
        self._conversations[conversation_id] = updated
        return ConversationSummary.from_dict(summary.to_dict())

    def _get_existing(self, conversation_id: str) -> ConversationRecord:
        _require_text(conversation_id, "conversation_id")
        try:
            return self._conversations[conversation_id]
        except KeyError as exc:
            raise ConversationStoreError(f"conversation not found: {conversation_id}") from exc

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence


def _coerce_citation_records(values: Any) -> List[CitationRecord]:
    return [CitationRecord.from_dict(item) for item in _require_list(values, "citation_records")]


def _coerce_task_references(values: Any) -> List[TaskReference]:
    return [TaskReference.from_dict(item) for item in _require_list(values, "task_references")]


def _coerce_policy_decisions(values: Any) -> List[PolicyDecisionRecord]:
    return [PolicyDecisionRecord.from_dict(item) for item in _require_list(values, "policy_decision_records")]


def _merge_by_id(existing: List[Any], incoming: List[Any], key: str) -> List[Any]:
    if not incoming:
        return list(existing)
    merged: Dict[str, Any] = {str(getattr(item, key)): item for item in existing}
    for item in incoming:
        merged[str(getattr(item, key))] = item
    return list(merged.values())


def _clone_conversation(record: ConversationRecord) -> ConversationRecord:
    return ConversationRecord.from_dict(record.to_dict())


def _sort_sequence(record: ConversationRecord) -> int:
    value = record.metadata.get("sort_sequence")
    return value if type(value) is int else 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _clean_title(title: str | None) -> str:
    if title is None:
        return "Conversation"
    text = str(title).strip()
    return text or "Conversation"


def _require_text(value: Any, field_name: str) -> None:
    if value is None or not str(value).strip():
        raise ConversationStoreError(f"{field_name} is required")


def _require_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise ConversationModelValidationError(f"{field_name} must be a list")
    return value


def _require_positive_int(value: Any, field_name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ConversationStoreError(f"{field_name} must be a positive integer")


def _require_non_negative_int(value: Any, field_name: str) -> None:
    if type(value) is not int or value < 0:
        raise ConversationStoreError(f"{field_name} must be a non-negative integer")
