"""IO-free static retention, backup, and privacy policy models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


RETENTION_SCHEMA_VERSION = "0.1"
LONG_TERM_MEMORY_UNTIL_USER_DELETION = "until_user_deletion"


class RetentionModelValidationError(ValueError):
    """Raised when a static retention model violates its schema."""


@dataclass(frozen=True)
class BackupInclusionPolicy:
    """Privacy-first backup inclusion flags for AI data."""

    include_ai_conversations: bool = False
    include_ai_memory: bool = False
    include_ai_drafts: bool = False
    metadata: Dict[str, Any] = field(default_factory=lambda: {"schema_version": RETENTION_SCHEMA_VERSION})

    def validate(self) -> "BackupInclusionPolicy":
        _require_bool(self.include_ai_conversations, "include_ai_conversations")
        _require_bool(self.include_ai_memory, "include_ai_memory")
        _require_bool(self.include_ai_drafts, "include_ai_drafts")
        _require_dict(self.metadata, "metadata")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        metadata = dict(self.metadata)
        metadata.setdefault("schema_version", RETENTION_SCHEMA_VERSION)
        return {
            "include_ai_conversations": self.include_ai_conversations,
            "include_ai_memory": self.include_ai_memory,
            "include_ai_drafts": self.include_ai_drafts,
            "metadata": metadata,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "BackupInclusionPolicy":
        _require_dict(payload, "BackupInclusionPolicy")
        return cls(
            include_ai_conversations=_optional_bool(payload, "include_ai_conversations", False),
            include_ai_memory=_optional_bool(payload, "include_ai_memory", False),
            include_ai_drafts=_optional_bool(payload, "include_ai_drafts", False),
            metadata=_optional_dict(payload, "metadata", {}),
        ).validate()


@dataclass(frozen=True)
class PrivacyModePolicy:
    """Static cloud/context-send privacy defaults for AI data."""

    privacy_mode: bool = False
    persistent_conversation_allowed: bool = True
    memory_candidate_creation_allowed: bool = True
    cloud_memory_send_allowed: bool = False
    cloud_conversation_send_allowed: bool = False
    context_preview_required_for_cloud: bool = True
    secret_scan_blocks_cloud_send: bool = True
    metadata: Dict[str, Any] = field(default_factory=lambda: {"schema_version": RETENTION_SCHEMA_VERSION})

    def validate(self) -> "PrivacyModePolicy":
        _require_bool(self.privacy_mode, "privacy_mode")
        _require_bool(self.persistent_conversation_allowed, "persistent_conversation_allowed")
        _require_bool(self.memory_candidate_creation_allowed, "memory_candidate_creation_allowed")
        _require_bool(self.cloud_memory_send_allowed, "cloud_memory_send_allowed")
        _require_bool(self.cloud_conversation_send_allowed, "cloud_conversation_send_allowed")
        _require_bool(self.context_preview_required_for_cloud, "context_preview_required_for_cloud")
        _require_bool(self.secret_scan_blocks_cloud_send, "secret_scan_blocks_cloud_send")
        _require_dict(self.metadata, "metadata")
        if self.cloud_memory_send_allowed and not self.context_preview_required_for_cloud:
            raise RetentionModelValidationError("cloud memory send requires context preview")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        metadata = dict(self.metadata)
        metadata.setdefault("schema_version", RETENTION_SCHEMA_VERSION)
        return {
            "privacy_mode": self.privacy_mode,
            "persistent_conversation_allowed": self.persistent_conversation_allowed,
            "memory_candidate_creation_allowed": self.memory_candidate_creation_allowed,
            "cloud_memory_send_allowed": self.cloud_memory_send_allowed,
            "cloud_conversation_send_allowed": self.cloud_conversation_send_allowed,
            "context_preview_required_for_cloud": self.context_preview_required_for_cloud,
            "secret_scan_blocks_cloud_send": self.secret_scan_blocks_cloud_send,
            "metadata": metadata,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PrivacyModePolicy":
        _require_dict(payload, "PrivacyModePolicy")
        return cls(
            privacy_mode=_optional_bool(payload, "privacy_mode", False),
            persistent_conversation_allowed=_optional_bool(payload, "persistent_conversation_allowed", True),
            memory_candidate_creation_allowed=_optional_bool(payload, "memory_candidate_creation_allowed", True),
            cloud_memory_send_allowed=_optional_bool(payload, "cloud_memory_send_allowed", False),
            cloud_conversation_send_allowed=_optional_bool(payload, "cloud_conversation_send_allowed", False),
            context_preview_required_for_cloud=_optional_bool(payload, "context_preview_required_for_cloud", True),
            secret_scan_blocks_cloud_send=_optional_bool(payload, "secret_scan_blocks_cloud_send", True),
            metadata=_optional_dict(payload, "metadata", {}),
        ).validate()


@dataclass(frozen=True)
class RetentionPolicy:
    """Configurable retention defaults without any persistence behavior."""

    policy_id: str = "default_local"
    conversation_retention_days: int = 365
    memory_candidate_expiry_days: int = 30
    rejected_candidate_suppression_days: int = 180
    long_term_memory_retention: str = LONG_TERM_MEMORY_UNTIL_USER_DELETION
    conversation_retention_configurable: bool = True
    memory_candidate_expiry_configurable: bool = True
    backup: BackupInclusionPolicy = field(default_factory=BackupInclusionPolicy)
    privacy: PrivacyModePolicy = field(default_factory=PrivacyModePolicy)
    metadata: Dict[str, Any] = field(default_factory=lambda: {"schema_version": RETENTION_SCHEMA_VERSION})

    @property
    def schema_version(self) -> str:
        return str(self.metadata.get("schema_version") or RETENTION_SCHEMA_VERSION)

    def validate(self) -> "RetentionPolicy":
        _require_text(self.policy_id, "policy_id")
        _require_positive_int(self.conversation_retention_days, "conversation_retention_days")
        _require_positive_int(self.memory_candidate_expiry_days, "memory_candidate_expiry_days")
        _require_positive_int(self.rejected_candidate_suppression_days, "rejected_candidate_suppression_days")
        if self.long_term_memory_retention != LONG_TERM_MEMORY_UNTIL_USER_DELETION:
            raise RetentionModelValidationError("long_term_memory_retention must be until_user_deletion")
        _require_bool(self.conversation_retention_configurable, "conversation_retention_configurable")
        _require_bool(self.memory_candidate_expiry_configurable, "memory_candidate_expiry_configurable")
        _require_dict(self.metadata, "metadata")
        _require_text(self.schema_version, "metadata.schema_version")
        if not isinstance(self.backup, BackupInclusionPolicy):
            raise RetentionModelValidationError("backup must be a BackupInclusionPolicy")
        if not isinstance(self.privacy, PrivacyModePolicy):
            raise RetentionModelValidationError("privacy must be a PrivacyModePolicy")
        self.backup.validate()
        self.privacy.validate()
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        metadata = dict(self.metadata)
        metadata.setdefault("schema_version", RETENTION_SCHEMA_VERSION)
        return {
            "policy_id": self.policy_id,
            "conversation_retention_days": int(self.conversation_retention_days),
            "memory_candidate_expiry_days": int(self.memory_candidate_expiry_days),
            "rejected_candidate_suppression_days": int(self.rejected_candidate_suppression_days),
            "long_term_memory_retention": self.long_term_memory_retention,
            "conversation_retention_configurable": self.conversation_retention_configurable,
            "memory_candidate_expiry_configurable": self.memory_candidate_expiry_configurable,
            "backup": self.backup.to_dict(),
            "privacy": self.privacy.to_dict(),
            "metadata": metadata,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RetentionPolicy":
        _require_dict(payload, "RetentionPolicy")
        return cls(
            policy_id=str(payload.get("policy_id") or "default_local"),
            conversation_retention_days=_optional_int(payload, "conversation_retention_days", 365),
            memory_candidate_expiry_days=_optional_int(payload, "memory_candidate_expiry_days", 30),
            rejected_candidate_suppression_days=_optional_int(payload, "rejected_candidate_suppression_days", 180),
            long_term_memory_retention=str(
                payload.get("long_term_memory_retention") or LONG_TERM_MEMORY_UNTIL_USER_DELETION
            ),
            conversation_retention_configurable=_optional_bool(payload, "conversation_retention_configurable", True),
            memory_candidate_expiry_configurable=_optional_bool(payload, "memory_candidate_expiry_configurable", True),
            backup=BackupInclusionPolicy.from_dict(_optional_dict(payload, "backup", {})),
            privacy=PrivacyModePolicy.from_dict(_optional_dict(payload, "privacy", {})),
            metadata=_optional_dict(payload, "metadata", {}),
        ).validate()


def _require_text(value: Any, field_name: str) -> None:
    if value is None or not str(value).strip():
        raise RetentionModelValidationError(f"{field_name} is required")


def _require_bool(value: Any, field_name: str) -> None:
    if type(value) is not bool:
        raise RetentionModelValidationError(f"{field_name} must be a boolean")


def _require_positive_int(value: Any, field_name: str) -> None:
    if type(value) is not int or value <= 0:
        raise RetentionModelValidationError(f"{field_name} must be a positive integer")


def _optional_bool(payload: Dict[str, Any], field_name: str, default: bool) -> bool:
    if field_name not in payload:
        return default
    _require_bool(payload[field_name], field_name)
    return payload[field_name]


def _optional_int(payload: Dict[str, Any], field_name: str, default: int) -> int:
    if field_name not in payload:
        return default
    _require_positive_int(payload[field_name], field_name)
    return payload[field_name]


def _require_dict(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise RetentionModelValidationError(f"{field_name} must be a dictionary")
    return value


def _optional_dict(payload: Dict[str, Any], field_name: str, default: Dict[str, Any]) -> Dict[str, Any]:
    if field_name not in payload:
        return dict(default)
    return dict(_require_dict(payload[field_name], field_name))
