"""IO-free static memory models for future AI MemoryService boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


MEMORY_SCHEMA_VERSION = "0.1"


class MemoryModelValidationError(ValueError):
    """Raised when a static memory model violates its schema."""


class MemoryType(str, Enum):
    """Allowed long-term memory categories."""

    PREFERENCE = "preference"
    FORMAT = "format"
    WORKFLOW = "workflow"
    PERSONAL_RULE = "personal_rule"
    LONG_TERM_GOAL = "long_term_goal"


class MemorySensitivity(str, Enum):
    """Sensitivity levels for memory candidates and saved memory."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class MemoryStatus(str, Enum):
    """Candidate and saved-memory lifecycle states."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


CANDIDATE_STATUSES = {
    MemoryStatus.PENDING.value,
    MemoryStatus.ACCEPTED.value,
    MemoryStatus.REJECTED.value,
    MemoryStatus.EXPIRED.value,
}
SAVED_MEMORY_STATUSES = {
    MemoryStatus.ACTIVE.value,
    MemoryStatus.DISABLED.value,
    MemoryStatus.DELETED.value,
}
MEMORY_TYPE_VALUES = {item.value for item in MemoryType}
SENSITIVITY_VALUES = {item.value for item in MemorySensitivity}


@dataclass(frozen=True)
class MemorySource:
    """Traceable source metadata for user-confirmed saved memory."""

    candidate_id: str
    conversation_id: str
    source_message_ids: List[str]

    def validate(self) -> "MemorySource":
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.conversation_id, "conversation_id")
        _require_list(self.source_message_ids, "source_message_ids")
        if not self.source_message_ids:
            raise MemoryModelValidationError("source_message_ids is required")
        for index, message_id in enumerate(self.source_message_ids):
            _require_text(message_id, f"source_message_ids[{index}]")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "candidate_id": self.candidate_id,
            "conversation_id": self.conversation_id,
            "source_message_ids": list(self.source_message_ids),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "MemorySource":
        _require_dict(payload, "MemorySource")
        _require_keys(payload, ["candidate_id", "conversation_id", "source_message_ids"], "MemorySource")
        source_message_ids = _require_list(payload["source_message_ids"], "source_message_ids")
        return cls(
            candidate_id=str(payload["candidate_id"]),
            conversation_id=str(payload["conversation_id"]),
            source_message_ids=[str(item) for item in source_message_ids],
        ).validate()


@dataclass(frozen=True)
class MemoryCandidate:
    """User-review draft memory that is never saved without confirmation."""

    candidate_id: str
    conversation_id: str
    workspace_id: str
    type: str
    proposed_text: str
    source_message_ids: List[str]
    sensitivity: str
    requires_confirmation: bool = True
    status: str = MemoryStatus.PENDING.value
    metadata: Dict[str, Any] = field(default_factory=lambda: {"schema_version": MEMORY_SCHEMA_VERSION})

    def validate(self) -> "MemoryCandidate":
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.conversation_id, "conversation_id")
        _require_text(self.workspace_id, "workspace_id")
        _require_choice(self.type, MEMORY_TYPE_VALUES, "type")
        _require_text(self.proposed_text, "proposed_text")
        _require_list(self.source_message_ids, "source_message_ids")
        if not self.source_message_ids:
            raise MemoryModelValidationError("source_message_ids is required")
        for index, message_id in enumerate(self.source_message_ids):
            _require_text(message_id, f"source_message_ids[{index}]")
        _require_choice(self.sensitivity, SENSITIVITY_VALUES, "sensitivity")
        _require_choice(self.status, CANDIDATE_STATUSES, "status")
        _require_bool(self.requires_confirmation, "requires_confirmation")
        _require_dict(self.metadata, "metadata")
        if self.requires_confirmation is not True:
            raise MemoryModelValidationError("MemoryCandidate requires requires_confirmation=true")
        if _enum_value(self.sensitivity) == MemorySensitivity.BLOCKED.value and _enum_value(self.status) == MemoryStatus.ACCEPTED.value:
            raise MemoryModelValidationError("blocked sensitivity candidate cannot be accepted")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        metadata = dict(self.metadata)
        metadata.setdefault("schema_version", MEMORY_SCHEMA_VERSION)
        return {
            "candidate_id": self.candidate_id,
            "conversation_id": self.conversation_id,
            "workspace_id": self.workspace_id,
            "type": _enum_value(self.type),
            "proposed_text": self.proposed_text,
            "source_message_ids": list(self.source_message_ids),
            "sensitivity": _enum_value(self.sensitivity),
            "requires_confirmation": True,
            "status": _enum_value(self.status),
            "metadata": metadata,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "MemoryCandidate":
        _require_dict(payload, "MemoryCandidate")
        _require_keys(
            payload,
            [
                "candidate_id",
                "conversation_id",
                "workspace_id",
                "type",
                "proposed_text",
                "source_message_ids",
                "sensitivity",
                "requires_confirmation",
                "status",
            ],
            "MemoryCandidate",
        )
        source_message_ids = _require_list(payload["source_message_ids"], "source_message_ids")
        return cls(
            candidate_id=str(payload["candidate_id"]),
            conversation_id=str(payload["conversation_id"]),
            workspace_id=str(payload["workspace_id"]),
            type=_enum_value(payload["type"]),
            proposed_text=str(payload["proposed_text"]),
            source_message_ids=[str(item) for item in source_message_ids],
            sensitivity=_enum_value(payload["sensitivity"]),
            requires_confirmation=_require_bool(payload["requires_confirmation"], "requires_confirmation"),
            status=_enum_value(payload["status"]),
            metadata=_optional_dict(payload, "metadata", {}),
        ).validate()


@dataclass(frozen=True)
class SavedMemory:
    """User-confirmed long-term memory metadata without persistence behavior."""

    memory_id: str
    workspace_id: str
    type: str
    text: str
    created_at: str
    updated_at: str
    source: MemorySource
    sensitivity: str
    status: str = MemoryStatus.ACTIVE.value
    metadata: Dict[str, Any] = field(default_factory=lambda: {"confirmed_by": "user", "schema_version": MEMORY_SCHEMA_VERSION})

    def validate(self) -> "SavedMemory":
        _require_text(self.memory_id, "memory_id")
        _require_text(self.workspace_id, "workspace_id")
        _require_choice(self.type, MEMORY_TYPE_VALUES, "type")
        _require_text(self.text, "text")
        _require_text(self.created_at, "created_at")
        _require_text(self.updated_at, "updated_at")
        if not isinstance(self.source, MemorySource):
            raise MemoryModelValidationError("source must be a MemorySource")
        self.source.validate()
        _require_choice(self.sensitivity, SENSITIVITY_VALUES, "sensitivity")
        _require_choice(self.status, SAVED_MEMORY_STATUSES, "status")
        _require_dict(self.metadata, "metadata")
        _validate_known_metadata_bools(self.metadata)
        if _enum_value(self.sensitivity) == MemorySensitivity.BLOCKED.value:
            raise MemoryModelValidationError("blocked sensitivity cannot be saved as long-term memory")
        confirmed_by = str(self.metadata.get("confirmed_by") or "")
        if confirmed_by != "user":
            raise MemoryModelValidationError("SavedMemory requires metadata.confirmed_by=user")
        if _metadata_marks_formal_knowledge(self.metadata):
            raise MemoryModelValidationError("SavedMemory cannot be formal knowledge")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        metadata = dict(self.metadata)
        metadata.setdefault("schema_version", MEMORY_SCHEMA_VERSION)
        metadata.setdefault("confirmed_by", "user")
        metadata.setdefault("not_formal_knowledge", True)
        metadata.setdefault("cloud_send_allowed", False)
        return {
            "memory_id": self.memory_id,
            "workspace_id": self.workspace_id,
            "type": _enum_value(self.type),
            "text": self.text,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source.to_dict(),
            "sensitivity": _enum_value(self.sensitivity),
            "status": _enum_value(self.status),
            "metadata": metadata,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SavedMemory":
        _require_dict(payload, "SavedMemory")
        _require_keys(
            payload,
            [
                "memory_id",
                "workspace_id",
                "type",
                "text",
                "created_at",
                "updated_at",
                "source",
                "sensitivity",
                "status",
                "metadata",
            ],
            "SavedMemory",
        )
        return cls(
            memory_id=str(payload["memory_id"]),
            workspace_id=str(payload["workspace_id"]),
            type=_enum_value(payload["type"]),
            text=str(payload["text"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            source=MemorySource.from_dict(payload["source"]),
            sensitivity=_enum_value(payload["sensitivity"]),
            status=_enum_value(payload["status"]),
            metadata=dict(_require_dict(payload["metadata"], "metadata")),
        ).validate()


def _require_keys(payload: Dict[str, Any], keys: List[str], model_name: str) -> None:
    _require_dict(payload, model_name)
    missing = [key for key in keys if key not in payload]
    if missing:
        raise MemoryModelValidationError(f"{model_name} missing required fields: {', '.join(missing)}")


def _require_text(value: Any, field_name: str) -> None:
    if value is None or not str(value).strip():
        raise MemoryModelValidationError(f"{field_name} is required")


def _require_choice(value: Any, allowed: set[str], field_name: str) -> None:
    text = _enum_value(value)
    if text not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise MemoryModelValidationError(f"{field_name} must be one of: {allowed_text}")


def _require_bool(value: Any, field_name: str) -> bool:
    if type(value) is not bool:
        raise MemoryModelValidationError(f"{field_name} must be a boolean")
    return value


def _require_list(value: Any, field_name: str) -> List[Any]:
    if not isinstance(value, list):
        raise MemoryModelValidationError(f"{field_name} must be a list")
    return value


def _require_dict(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise MemoryModelValidationError(f"{field_name} must be a dictionary")
    return value


def _optional_dict(payload: Dict[str, Any], field_name: str, default: Dict[str, Any]) -> Dict[str, Any]:
    if field_name not in payload:
        return dict(default)
    return dict(_require_dict(payload[field_name], field_name))


def _enum_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if not isinstance(value, str):
        raise MemoryModelValidationError("enum fields must be string enum values")
    return str(value)


def _validate_known_metadata_bools(metadata: Dict[str, Any]) -> None:
    for key in ["formal_knowledge", "is_formal_knowledge", "not_formal_knowledge", "cloud_send_allowed"]:
        if key in metadata:
            _require_bool(metadata[key], f"metadata.{key}")


def _metadata_marks_formal_knowledge(metadata: Dict[str, Any]) -> bool:
    if metadata.get("formal_knowledge") is True:
        return True
    if metadata.get("is_formal_knowledge") is True:
        return True
    if metadata.get("not_formal_knowledge") is False:
        return True
    layer = str(metadata.get("layer") or "")
    return layer in {"rules", "checklists", "snippets"}
