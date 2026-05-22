"""In-memory MemoryService harness for service-layer behavior tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
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


class MemoryServiceError(ValueError):
    """Raised when the in-memory memory harness cannot satisfy a request."""


class MemoryService:
    """Process-local MemoryService harness with no persistence behavior."""

    def __init__(self) -> None:
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
    ) -> MemoryCandidate:
        now = _now_iso()
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
                "created_at": now,
                "storage": "in_memory",
                "not_formal_knowledge": True,
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

    def accept_candidate(self, candidate_id: str) -> SavedMemory:
        candidate = self._get_candidate(candidate_id)
        if candidate.status != MemoryStatus.PENDING.value:
            raise MemoryServiceError(f"only pending candidates can be accepted: {candidate_id}")
        if candidate.sensitivity == MemorySensitivity.BLOCKED.value:
            raise MemoryServiceError("blocked sensitivity candidate cannot be accepted")
        if candidate.requires_confirmation is not True:
            raise MemoryModelValidationError("MemoryCandidate requires requires_confirmation=true")

        now = _now_iso()
        accepted = replace(candidate, status=MemoryStatus.ACCEPTED.value).validate()
        memory = SavedMemory(
            memory_id=_new_id("mem"),
            workspace_id=accepted.workspace_id,
            type=accepted.type,
            text=accepted.proposed_text,
            created_at=now,
            updated_at=now,
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
                "storage": "in_memory",
                "not_formal_knowledge": True,
                "cloud_send_allowed": False,
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
        rejected = replace(candidate, status=MemoryStatus.REJECTED.value).validate()
        self._candidates[candidate_id] = rejected
        return _clone_candidate(rejected)

    def expire_candidate(self, candidate_id: str) -> MemoryCandidate:
        candidate = self._get_candidate(candidate_id)
        if candidate.status != MemoryStatus.PENDING.value:
            raise MemoryServiceError(f"only pending candidates can expire: {candidate_id}")
        expired = replace(candidate, status=MemoryStatus.EXPIRED.value).validate()
        self._candidates[candidate_id] = expired
        return _clone_candidate(expired)

    def list_memories(self, workspace_id: str) -> List[SavedMemory]:
        _require_text(workspace_id, "workspace_id")
        memories = [memory for memory in self._memories.values() if memory.workspace_id == workspace_id]
        memories.sort(key=lambda item: (item.updated_at, item.created_at, item.memory_id), reverse=True)
        return [_clone_memory(memory) for memory in memories]

    def delete_memory(self, memory_id: str) -> bool:
        self._get_memory(memory_id)
        del self._memories[memory_id]
        return True

    def disable_memory(self, memory_id: str) -> SavedMemory:
        memory = self._get_memory(memory_id)
        disabled = replace(memory, updated_at=_now_iso(), status=MemoryStatus.DISABLED.value).validate()
        self._memories[memory_id] = disabled
        return _clone_memory(disabled)

    def clear_memory(self, workspace_id: str) -> int:
        _require_text(workspace_id, "workspace_id")
        memory_ids = [memory_id for memory_id, memory in self._memories.items() if memory.workspace_id == workspace_id]
        for memory_id in memory_ids:
            del self._memories[memory_id]
        return len(memory_ids)

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


def _clone_candidate(candidate: MemoryCandidate) -> MemoryCandidate:
    return MemoryCandidate.from_dict(candidate.to_dict())


def _clone_memory(memory: SavedMemory) -> SavedMemory:
    return SavedMemory.from_dict(memory.to_dict())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _require_text(value: Any, field_name: str) -> None:
    if value is None or not str(value).strip():
        raise MemoryServiceError(f"{field_name} is required")


def _require_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise MemoryModelValidationError(f"{field_name} must be a list")
    return value
