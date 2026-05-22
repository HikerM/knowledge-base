"""In-memory MemoryService harness for service-layer behavior tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
from typing import Any, Dict, List
import uuid

from knowledge_app.ai.memory_models import (
    MEMORY_SCHEMA_VERSION,
    CANDIDATE_STATUSES,
    MemoryCandidate,
    MemoryModelValidationError,
    MemorySensitivity,
    MemorySource,
    MemoryStatus,
    SavedMemory,
)
from knowledge_app.ai.retention_models import RetentionPolicy


class MemoryServiceError(ValueError):
    """Raised when the in-memory memory harness cannot satisfy a request."""


class MemoryService:
    """Process-local MemoryService harness with no persistence behavior."""

    def __init__(self, retention_policy: RetentionPolicy | None = None) -> None:
        self.retention_policy = (retention_policy or RetentionPolicy()).validate()
        self._candidates: Dict[str, MemoryCandidate] = {}
        self._memories: Dict[str, SavedMemory] = {}

    def create_candidate(
        self,
        conversation_id: str,
        workspace_id: str,
        proposed_text: str,
        type: str,
        source_message_ids: List[str],
        sensitivity: str = MemorySensitivity.LOW.value,
        now: datetime | None = None,
    ) -> MemoryCandidate:
        self._assert_memory_candidate_allowed()
        now_dt = _coerce_datetime(now)
        expires_at = now_dt + timedelta(days=self.retention_policy.memory_candidate_expiry_days)
        candidate = MemoryCandidate(
            candidate_id=_new_id("memcand"),
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            type=type,
            proposed_text=proposed_text,
            source_message_ids=list(_require_list(source_message_ids, "source_message_ids")),
            sensitivity=sensitivity,
            requires_confirmation=True,
            status=MemoryStatus.PENDING.value,
            metadata={
                "schema_version": MEMORY_SCHEMA_VERSION,
                "created_at": _format_iso(now_dt),
                "expires_at": _format_iso(expires_at),
                "retention_policy_id": self.retention_policy.policy_id,
                "rejection_fingerprint": _candidate_fingerprint(workspace_id, type, proposed_text),
                "storage": "in_memory",
                "not_formal_knowledge": True,
                "cloud_send_allowed": False,
                "mutation_authority": False,
            },
        ).validate()
        self._candidates[candidate.candidate_id] = candidate
        return _clone_candidate(candidate)

    def list_candidates(self, workspace_id: str, status: str | None = None) -> List[MemoryCandidate]:
        _require_text(workspace_id, "workspace_id")
        if status is not None and status not in CANDIDATE_STATUSES:
            raise MemoryServiceError(f"status must be one of: {', '.join(sorted(CANDIDATE_STATUSES))}")
        candidates = [
            candidate
            for candidate in self._candidates.values()
            if candidate.workspace_id == workspace_id and (status is None or candidate.status == status)
        ]
        candidates.sort(key=lambda item: (str(item.metadata.get("created_at") or ""), item.candidate_id), reverse=True)
        return [_clone_candidate(candidate) for candidate in candidates]

    def accept_candidate(
        self,
        candidate_id: str,
        confirmed: bool = False,
        confirmation_id: str | None = None,
        now: datetime | None = None,
    ) -> SavedMemory:
        self._assert_memory_save_allowed()
        if confirmed is not True:
            raise MemoryServiceError("accept_candidate requires explicit user confirmation")
        candidate = self._get_candidate(candidate_id)
        if candidate.status != MemoryStatus.PENDING.value:
            raise MemoryServiceError(f"only pending candidates can be accepted: {candidate_id}")
        if candidate.sensitivity == MemorySensitivity.BLOCKED.value:
            raise MemoryServiceError("blocked sensitivity candidate cannot be accepted")
        if candidate.requires_confirmation is not True:
            raise MemoryModelValidationError("MemoryCandidate requires requires_confirmation=true")
        now_dt = _coerce_datetime(now)
        if _candidate_is_expired(candidate, now_dt):
            expired = self._expire_candidate(candidate, now_dt)
            self._candidates[candidate_id] = expired
            raise MemoryServiceError(f"candidate expired before confirmation: {candidate_id}")

        now_text = _format_iso(now_dt)
        accepted = replace(
            candidate,
            status=MemoryStatus.ACCEPTED.value,
            metadata={
                **dict(candidate.metadata),
                "accepted_at": now_text,
                "confirmation_id": str(confirmation_id or _new_id("confirm")),
            },
        ).validate()
        memory = SavedMemory(
            memory_id=_new_id("mem"),
            workspace_id=accepted.workspace_id,
            type=accepted.type,
            text=accepted.proposed_text,
            created_at=now_text,
            updated_at=now_text,
            source=MemorySource(
                candidate_id=accepted.candidate_id,
                conversation_id=accepted.conversation_id,
                source_message_ids=list(accepted.source_message_ids),
            ),
            sensitivity=accepted.sensitivity,
            status=MemoryStatus.ACTIVE.value,
            metadata={
                "schema_version": MEMORY_SCHEMA_VERSION,
                "confirmed_by": "user",
                "confirmation_required": True,
                "confirmation_id": str(confirmation_id or accepted.metadata.get("confirmation_id") or _new_id("confirm")),
                "retention_policy_id": self.retention_policy.long_term_memory_retention,
                "storage": "in_memory",
                "not_formal_knowledge": True,
                "cloud_send_allowed": False,
                "backup_default_included": False,
                "export_writes_file": False,
                "mutation_authority": False,
            },
        ).validate()
        self._candidates[candidate_id] = accepted
        self._memories[memory.memory_id] = memory
        return _clone_memory(memory)

    def reject_candidate(self, candidate_id: str) -> MemoryCandidate:
        candidate = self._get_candidate(candidate_id)
        if candidate.status != MemoryStatus.PENDING.value:
            raise MemoryServiceError(f"only pending candidates can be rejected: {candidate_id}")
        now_dt = _coerce_datetime(None)
        suppressed_until = now_dt + timedelta(days=self.retention_policy.rejected_candidate_suppression_days)
        rejected = replace(
            candidate,
            status=MemoryStatus.REJECTED.value,
            metadata={
                **dict(candidate.metadata),
                "rejected_at": _format_iso(now_dt),
                "suppressed_until": _format_iso(suppressed_until),
                "rejection_reason": "user_rejected",
            },
        ).validate()
        self._candidates[candidate_id] = rejected
        return _clone_candidate(rejected)

    def expire_candidate(self, candidate_id: str, now: datetime | None = None) -> MemoryCandidate:
        candidate = self._get_candidate(candidate_id)
        if candidate.status != MemoryStatus.PENDING.value:
            raise MemoryServiceError(f"only pending candidates can expire: {candidate_id}")
        expired = self._expire_candidate(candidate, _coerce_datetime(now))
        self._candidates[candidate_id] = expired
        return _clone_candidate(expired)

    def enforce_retention(self, workspace_id: str | None = None, now: datetime | None = None) -> Dict[str, Any]:
        if workspace_id is not None:
            _require_text(workspace_id, "workspace_id")
        now_dt = _coerce_datetime(now)
        expired_ids: List[str] = []
        for candidate_id, candidate in list(self._candidates.items()):
            if workspace_id is not None and candidate.workspace_id != workspace_id:
                continue
            if candidate.status == MemoryStatus.PENDING.value and _candidate_is_expired(candidate, now_dt):
                self._candidates[candidate_id] = self._expire_candidate(candidate, now_dt)
                expired_ids.append(candidate_id)
        return {
            "schema_version": MEMORY_SCHEMA_VERSION,
            "storage": "in_memory",
            "writes_file": False,
            "policy_id": self.retention_policy.policy_id,
            "expired_candidate_ids": expired_ids,
            "expired_count": len(expired_ids),
            "saved_memory_auto_expired": 0,
            "not_formal_knowledge": True,
        }

    def list_memories(
        self,
        workspace_id: str,
        include_disabled: bool = True,
        include_deleted: bool = False,
    ) -> List[SavedMemory]:
        _require_text(workspace_id, "workspace_id")
        memories = []
        for memory in self._memories.values():
            if memory.workspace_id != workspace_id:
                continue
            if memory.status == MemoryStatus.DELETED.value and not include_deleted:
                continue
            if memory.status == MemoryStatus.DISABLED.value and not include_disabled:
                continue
            memories.append(memory)
        memories.sort(key=lambda item: (item.updated_at, item.created_at, item.memory_id), reverse=True)
        return [_clone_memory(memory) for memory in memories]

    def delete_memory(self, memory_id: str, reason: str = "user_deleted", now: datetime | None = None) -> SavedMemory:
        memory = self._get_memory(memory_id)
        now_text = _format_iso(_coerce_datetime(now))
        deleted = replace(
            memory,
            text="",
            updated_at=now_text,
            status=MemoryStatus.DELETED.value,
            metadata={
                **dict(memory.metadata),
                "deleted_at": now_text,
                "delete_reason": str(reason or "user_deleted"),
                "text_redacted": True,
            },
        ).validate()
        self._memories[memory_id] = deleted
        return _clone_memory(deleted)

    def disable_memory(self, memory_id: str) -> SavedMemory:
        memory = self._get_memory(memory_id)
        if memory.status == MemoryStatus.DELETED.value:
            raise MemoryServiceError(f"deleted memory cannot be disabled: {memory_id}")
        disabled = replace(memory, updated_at=_now_iso(), status=MemoryStatus.DISABLED.value).validate()
        self._memories[memory_id] = disabled
        return _clone_memory(disabled)

    def clear_memory(self, workspace_id: str) -> int:
        _require_text(workspace_id, "workspace_id")
        memory_ids = [
            memory_id
            for memory_id, memory in self._memories.items()
            if memory.workspace_id == workspace_id and memory.status != MemoryStatus.DELETED.value
        ]
        for memory_id in memory_ids:
            self.delete_memory(memory_id, reason="clear_memory")
        return len(memory_ids)

    def backup_policy_preview(self, workspace_id: str) -> Dict[str, Any]:
        _require_text(workspace_id, "workspace_id")
        backup = self.retention_policy.backup.validate().to_dict()
        return {
            "schema_version": MEMORY_SCHEMA_VERSION,
            "workspace_id": workspace_id,
            "storage": "in_memory",
            "writes_file": False,
            "default_backup": {
                "include_ai_memory": backup["include_ai_memory"],
                "include_ai_drafts": backup["include_ai_drafts"],
                "include_ai_conversations": backup["include_ai_conversations"],
            },
            "memory_default_included": bool(backup["include_ai_memory"]),
            "drafts_default_included": bool(backup["include_ai_drafts"]),
            "privacy_warning_required_for_ai_memory": True,
            "not_formal_knowledge": True,
        }

    def export_memory_preview(
        self,
        workspace_id: str,
        include_disabled: bool = True,
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        _require_text(workspace_id, "workspace_id")
        memories = [
            memory.to_dict()
            for memory in self.list_memories(
                workspace_id,
                include_disabled=include_disabled,
                include_deleted=include_deleted,
            )
        ]
        return {
            "schema_version": MEMORY_SCHEMA_VERSION,
            "workspace_id": workspace_id,
            "export_mode": "preview",
            "writes_file": False,
            "storage": "in_memory",
            "not_formal_knowledge": True,
            "cloud_send_allowed": False,
            "includes": {
                "memory": True,
                "disabled_memory": include_disabled,
                "deleted_memory": include_deleted,
                "formal_search_records": False,
                "knowledge_markdown": False,
            },
            "memory_count": len(memories),
            "memories": memories,
            "warning": "AI memory export previews are not formal knowledge and are not written to disk.",
        }

    def _get_candidate(self, candidate_id: str) -> MemoryCandidate:
        _require_text(candidate_id, "candidate_id")
        try:
            return self._candidates[candidate_id]
        except KeyError as exc:
            raise MemoryServiceError(f"candidate not found: {candidate_id}") from exc

    def _get_memory(self, memory_id: str) -> SavedMemory:
        _require_text(memory_id, "memory_id")
        try:
            return self._memories[memory_id]
        except KeyError as exc:
            raise MemoryServiceError(f"memory not found: {memory_id}") from exc

    def _assert_memory_candidate_allowed(self) -> None:
        privacy = self.retention_policy.privacy.validate()
        if privacy.privacy_mode:
            raise MemoryServiceError("privacy mode blocks memory candidate creation")
        if not privacy.memory_candidate_creation_allowed:
            raise MemoryServiceError("memory candidate creation is disabled by privacy policy")
        if privacy.cloud_memory_send_allowed:
            raise MemoryServiceError("memory harness does not allow cloud memory send")

    def _assert_memory_save_allowed(self) -> None:
        privacy = self.retention_policy.privacy.validate()
        if privacy.privacy_mode:
            raise MemoryServiceError("privacy mode blocks saved memory creation")
        if privacy.cloud_memory_send_allowed:
            raise MemoryServiceError("memory harness does not allow cloud memory send")

    @staticmethod
    def _expire_candidate(candidate: MemoryCandidate, now: datetime) -> MemoryCandidate:
        return replace(
            candidate,
            status=MemoryStatus.EXPIRED.value,
            metadata={**dict(candidate.metadata), "expired_at": _format_iso(now)},
        ).validate()


def _clone_candidate(candidate: MemoryCandidate) -> MemoryCandidate:
    return MemoryCandidate.from_dict(candidate.to_dict())


def _clone_memory(memory: SavedMemory) -> SavedMemory:
    return SavedMemory.from_dict(memory.to_dict())


def _now_iso() -> str:
    return _format_iso(_coerce_datetime(None))


def _coerce_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_iso(value: datetime) -> str:
    return _coerce_datetime(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_iso(value: Any) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except ValueError as exc:
        raise MemoryServiceError(f"invalid datetime: {value}") from exc


def _candidate_is_expired(candidate: MemoryCandidate, now: datetime) -> bool:
    expires_at = _parse_iso(candidate.metadata.get("expires_at"))
    return bool(expires_at and expires_at <= _coerce_datetime(now))


def _candidate_fingerprint(workspace_id: str, type: str, proposed_text: str) -> str:
    normalized = " ".join(str(proposed_text).strip().lower().split())
    raw = f"{workspace_id}\0{type}\0{normalized}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _require_text(value: Any, field_name: str) -> None:
    if value is None or not str(value).strip():
        raise MemoryServiceError(f"{field_name} is required")


def _require_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise MemoryModelValidationError(f"{field_name} must be a list")
    return value
