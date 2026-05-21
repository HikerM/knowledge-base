"""IO-free static conversation models for the AI assistant control plane."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


CONVERSATION_SCHEMA_VERSION = "0.1"

ALLOWED_MESSAGE_TYPES = {
    "user_text",
    "assistant_text",
    "system_notice",
    "citation_list",
    "search_result_cards",
    "document_summary",
    "plan_card",
    "confirmation_card",
    "task_progress_card",
    "error_card",
    "memory_candidate_card",
    "privacy_notice_card",
}

ALLOWED_ROLES = {"user", "assistant", "system", "tool"}
ALLOWED_PROVIDER_KINDS = {"mock", "local", "cloud", "none"}
ALLOWED_POLICY_DECISIONS = {"allow", "confirm", "context_preview_required", "deny"}
ALLOWED_POLICY_LEVELS = {"L0", "L1", "L2", "L3", "L4"}
ALLOWED_TASK_STATUSES = {"pending", "running", "succeeded", "failed", "cancelled"}
FORBIDDEN_TASK_LOG_KEYS = {"log", "logs", "log_path", "task_log", "task_logs", "progress_log"}


class ConversationModelValidationError(ValueError):
    """Raised when a static conversation model violates its schema."""


@dataclass(frozen=True)
class CitationRecord:
    """Citation metadata preserved for AI answers and cards."""

    citation_id: str
    document_id: str
    title: str
    layer: str
    status: str
    source_type: str
    confidence: str
    review_required: bool = False
    chunk_id: Optional[str] = None
    warning: Optional[str] = None

    def validate(self) -> "CitationRecord":
        _require_text(self.citation_id, "citation_id")
        _require_text(self.document_id, "document_id")
        _require_text(self.title, "title")
        _require_text(self.layer, "layer")
        _require_text(self.status, "status")
        _require_text(self.source_type, "source_type")
        _require_text(self.confidence, "confidence")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "citation_id": self.citation_id,
            "document_id": self.document_id,
            "title": self.title,
            "layer": self.layer,
            "status": self.status,
            "source_type": self.source_type,
            "confidence": self.confidence,
            "review_required": self.review_required,
            "chunk_id": self.chunk_id,
            "warning": self.warning,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CitationRecord":
        _require_keys(
            payload,
            ["citation_id", "document_id", "title", "layer", "status", "source_type", "confidence"],
            "CitationRecord",
        )
        return cls(
            citation_id=str(payload["citation_id"]),
            document_id=str(payload["document_id"]),
            title=str(payload["title"]),
            layer=str(payload["layer"]),
            status=str(payload["status"]),
            source_type=str(payload["source_type"]),
            confidence=str(payload["confidence"]),
            review_required=bool(payload.get("review_required", False)),
            chunk_id=_optional_string(payload.get("chunk_id")),
            warning=_optional_string(payload.get("warning")),
        ).validate()


@dataclass(frozen=True)
class TaskReference:
    """Snapshot reference to a TaskQueue task without storing task logs."""

    task_id: str
    capability_id: str
    status_at_last_render: str
    progress_percent_at_last_render: int = 0
    message_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> "TaskReference":
        _require_text(self.task_id, "task_id")
        _require_text(self.capability_id, "capability_id")
        _require_choice(self.status_at_last_render, ALLOWED_TASK_STATUSES, "status_at_last_render")
        if not 0 <= int(self.progress_percent_at_last_render) <= 100:
            raise ConversationModelValidationError("progress_percent_at_last_render must be between 0 and 100")
        _reject_task_log_keys(self.metadata)
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "task_id": self.task_id,
            "capability_id": self.capability_id,
            "status_at_last_render": self.status_at_last_render,
            "progress_percent_at_last_render": int(self.progress_percent_at_last_render),
            "message_id": self.message_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TaskReference":
        _require_keys(payload, ["task_id", "capability_id", "status_at_last_render"], "TaskReference")
        _reject_task_log_keys(payload)
        return cls(
            task_id=str(payload["task_id"]),
            capability_id=str(payload["capability_id"]),
            status_at_last_render=str(payload["status_at_last_render"]),
            progress_percent_at_last_render=int(payload.get("progress_percent_at_last_render", 0)),
            message_id=_optional_string(payload.get("message_id")),
            metadata=dict(payload.get("metadata") or {}),
        ).validate()


@dataclass(frozen=True)
class PolicyDecisionRecord:
    """Auditable permission and context decision metadata."""

    policy_decision_id: str
    created_at: str
    capability_id: str
    level: str
    decision: str
    reason: str
    provider_kind: str
    context_preview_id: Optional[str] = None
    confirmation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> "PolicyDecisionRecord":
        _require_text(self.policy_decision_id, "policy_decision_id")
        _require_text(self.created_at, "created_at")
        _require_text(self.capability_id, "capability_id")
        _require_choice(self.level, ALLOWED_POLICY_LEVELS, "level")
        _require_choice(self.decision, ALLOWED_POLICY_DECISIONS, "decision")
        _require_text(self.reason, "reason")
        _require_choice(self.provider_kind, ALLOWED_PROVIDER_KINDS, "provider_kind")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "policy_decision_id": self.policy_decision_id,
            "created_at": self.created_at,
            "capability_id": self.capability_id,
            "level": self.level,
            "decision": self.decision,
            "reason": self.reason,
            "provider_kind": self.provider_kind,
            "context_preview_id": self.context_preview_id,
            "confirmation_id": self.confirmation_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "PolicyDecisionRecord":
        _require_keys(
            payload,
            ["policy_decision_id", "created_at", "capability_id", "level", "decision", "reason", "provider_kind"],
            "PolicyDecisionRecord",
        )
        return cls(
            policy_decision_id=str(payload["policy_decision_id"]),
            created_at=str(payload["created_at"]),
            capability_id=str(payload["capability_id"]),
            level=str(payload["level"]),
            decision=str(payload["decision"]),
            reason=str(payload["reason"]),
            provider_kind=str(payload["provider_kind"]),
            context_preview_id=_optional_string(payload.get("context_preview_id")),
            confirmation_id=_optional_string(payload.get("confirmation_id")),
            metadata=dict(payload.get("metadata") or {}),
        ).validate()


@dataclass(frozen=True)
class ConversationSummary:
    """Short non-authoritative summary that is explicitly not memory."""

    text: str
    created_at: str
    source_message_ids: List[str]
    not_long_term_memory: bool = True

    def validate(self) -> "ConversationSummary":
        _require_text(self.text, "text")
        _require_text(self.created_at, "created_at")
        if not self.source_message_ids:
            raise ConversationModelValidationError("source_message_ids is required")
        if self.not_long_term_memory is not True:
            raise ConversationModelValidationError("conversation summary must set not_long_term_memory=true")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "text": self.text,
            "created_at": self.created_at,
            "source_message_ids": list(self.source_message_ids),
            "not_long_term_memory": True,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ConversationSummary":
        _require_keys(payload, ["text", "created_at", "source_message_ids", "not_long_term_memory"], "ConversationSummary")
        return cls(
            text=str(payload["text"]),
            created_at=str(payload["created_at"]),
            source_message_ids=[str(item) for item in payload["source_message_ids"]],
            not_long_term_memory=bool(payload["not_long_term_memory"]),
        ).validate()


@dataclass(frozen=True)
class MessageRecord:
    """One ordered conversation message or structured assistant card."""

    message_id: str
    role: str
    type: str
    created_at: str
    content: Dict[str, Any]
    citations: List[str] = field(default_factory=list)
    policy_decision_id: Optional[str] = None
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> "MessageRecord":
        _require_text(self.message_id, "message_id")
        _require_choice(self.role, ALLOWED_ROLES, "role")
        _require_choice(self.type, ALLOWED_MESSAGE_TYPES, "type")
        _require_text(self.created_at, "created_at")
        if not isinstance(self.content, dict):
            raise ConversationModelValidationError("content must be a dictionary")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "message_id": self.message_id,
            "role": self.role,
            "type": self.type,
            "created_at": self.created_at,
            "content": dict(self.content),
            "citations": list(self.citations),
            "policy_decision_id": self.policy_decision_id,
            "task_id": self.task_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "MessageRecord":
        _require_keys(payload, ["message_id", "role", "type", "created_at", "content"], "MessageRecord")
        content = payload["content"]
        if not isinstance(content, dict):
            raise ConversationModelValidationError("MessageRecord.content must be a dictionary")
        return cls(
            message_id=str(payload["message_id"]),
            role=str(payload["role"]),
            type=str(payload["type"]),
            created_at=str(payload["created_at"]),
            content=dict(content),
            citations=[str(item) for item in payload.get("citations") or []],
            policy_decision_id=_optional_string(payload.get("policy_decision_id")),
            task_id=_optional_string(payload.get("task_id")),
            metadata=dict(payload.get("metadata") or {}),
        ).validate()


@dataclass(frozen=True)
class ConversationRecord:
    """Workspace-scoped conversation record with no persistence behavior."""

    conversation_id: str
    workspace_id: str
    created_at: str
    updated_at: str
    title: str
    messages: List[MessageRecord]
    citations: List[CitationRecord]
    tasks: List[TaskReference]
    policy_decisions: List[PolicyDecisionRecord]
    provider_kind: str
    summary: Optional[ConversationSummary] = None
    metadata: Dict[str, Any] = field(default_factory=lambda: {"schema_version": CONVERSATION_SCHEMA_VERSION})

    @property
    def schema_version(self) -> str:
        return str(self.metadata.get("schema_version") or CONVERSATION_SCHEMA_VERSION)

    def validate(self) -> "ConversationRecord":
        _require_text(self.conversation_id, "conversation_id")
        _require_text(self.workspace_id, "workspace_id")
        _require_text(self.created_at, "created_at")
        _require_text(self.updated_at, "updated_at")
        _require_text(self.title, "title")
        _require_choice(self.provider_kind, ALLOWED_PROVIDER_KINDS, "provider_kind")
        if not isinstance(self.metadata, dict):
            raise ConversationModelValidationError("metadata must be a dictionary")
        _require_text(self.schema_version, "metadata.schema_version")
        for message in self.messages:
            message.validate()
        for citation in self.citations:
            citation.validate()
        for task in self.tasks:
            task.validate()
        for decision in self.policy_decisions:
            decision.validate()
        if self.summary is not None:
            self.summary.validate()
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        metadata = dict(self.metadata)
        metadata.setdefault("schema_version", CONVERSATION_SCHEMA_VERSION)
        return {
            "conversation_id": self.conversation_id,
            "workspace_id": self.workspace_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "title": self.title,
            "messages": [message.to_dict() for message in self.messages],
            "citations": [citation.to_dict() for citation in self.citations],
            "tasks": [task.to_dict() for task in self.tasks],
            "policy_decisions": [decision.to_dict() for decision in self.policy_decisions],
            "provider_kind": self.provider_kind,
            "summary": self.summary.to_dict() if self.summary else None,
            "metadata": metadata,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ConversationRecord":
        _require_keys(
            payload,
            [
                "conversation_id",
                "workspace_id",
                "created_at",
                "updated_at",
                "title",
                "messages",
                "citations",
                "tasks",
                "policy_decisions",
                "provider_kind",
                "metadata",
            ],
            "ConversationRecord",
        )
        metadata = dict(payload.get("metadata") or {})
        if "schema_version" not in metadata and payload.get("schema_version"):
            metadata["schema_version"] = str(payload["schema_version"])
        return cls(
            conversation_id=str(payload["conversation_id"]),
            workspace_id=str(payload["workspace_id"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            title=str(payload["title"]),
            messages=[MessageRecord.from_dict(item) for item in payload["messages"]],
            citations=[CitationRecord.from_dict(item) for item in payload["citations"]],
            tasks=[TaskReference.from_dict(item) for item in payload["tasks"]],
            policy_decisions=[PolicyDecisionRecord.from_dict(item) for item in payload["policy_decisions"]],
            provider_kind=str(payload["provider_kind"]),
            summary=ConversationSummary.from_dict(payload["summary"]) if payload.get("summary") else None,
            metadata=metadata,
        ).validate()


def _require_keys(payload: Dict[str, Any], keys: List[str], model_name: str) -> None:
    missing = [key for key in keys if key not in payload]
    if missing:
        raise ConversationModelValidationError(f"{model_name} missing required fields: {', '.join(missing)}")


def _require_text(value: Any, field_name: str) -> None:
    if value is None or not str(value).strip():
        raise ConversationModelValidationError(f"{field_name} is required")


def _require_choice(value: Any, allowed: set[str], field_name: str) -> None:
    text = str(value)
    if text not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ConversationModelValidationError(f"{field_name} must be one of: {allowed_text}")


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _reject_task_log_keys(payload: Dict[str, Any]) -> None:
    for key, value in payload.items():
        if str(key).lower() in FORBIDDEN_TASK_LOG_KEYS:
            raise ConversationModelValidationError("TaskReference must not include task logs or log paths")
        if isinstance(value, dict):
            _reject_task_log_keys(value)
