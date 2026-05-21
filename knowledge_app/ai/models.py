"""Stable models for the AI control-plane static contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CapabilityLevel(str, Enum):
    """Allowed AI capability levels."""

    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


@dataclass(frozen=True)
class CapabilityAuditSpec:
    """Audit metadata flags declared by a capability entry."""

    record_intent: bool
    record_citations: bool
    record_context_ids: bool
    record_task_id: bool = False

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CapabilityAuditSpec":
        return cls(
            record_intent=bool(payload["record_intent"]),
            record_citations=bool(payload["record_citations"]),
            record_context_ids=bool(payload["record_context_ids"]),
            record_task_id=bool(payload.get("record_task_id", False)),
        )

    def to_dict(self) -> Dict[str, bool]:
        return {
            "record_intent": self.record_intent,
            "record_citations": self.record_citations,
            "record_context_ids": self.record_context_ids,
            "record_task_id": self.record_task_id,
        }


@dataclass(frozen=True)
class Capability:
    """One capability declared in the AI capability registry example."""

    id: str
    intent: str
    level: CapabilityLevel
    read_only: bool
    requires_ai: bool
    requires_confirmation: bool
    requires_cloud_context_preview: bool
    allowed_context: List[str]
    audit: CapabilityAuditSpec
    current_version: str
    service: Optional[str] = None
    provider: Optional[str] = None
    default_filters: Dict[str, Any] = field(default_factory=dict)
    output_policy: Dict[str, Any] = field(default_factory=dict)
    execution_contract: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Capability":
        return cls(
            id=str(payload["id"]),
            intent=str(payload["intent"]),
            level=CapabilityLevel(str(payload["level"])),
            service=_optional_string(payload.get("service")),
            provider=_optional_string(payload.get("provider")),
            read_only=bool(payload["read_only"]),
            requires_ai=bool(payload["requires_ai"]),
            requires_confirmation=bool(payload["requires_confirmation"]),
            requires_cloud_context_preview=bool(payload["requires_cloud_context_preview"]),
            allowed_context=[str(item) for item in payload["allowed_context"]],
            audit=CapabilityAuditSpec.from_dict(payload["audit"]),
            current_version=str(payload["current_version"]),
            default_filters=dict(payload.get("default_filters") or {}),
            output_policy=dict(payload.get("output_policy") or {}),
            execution_contract=dict(payload.get("execution_contract") or {}),
            raw=dict(payload),
        )

    @property
    def requires_task_queue(self) -> bool:
        return bool(self.execution_contract.get("requires_task_queue", False))

    @property
    def requires_snapshot(self) -> bool:
        return bool(self.execution_contract.get("requires_snapshot", False))

    @property
    def requires_approval(self) -> bool:
        return bool(self.execution_contract.get("requires_approval", False))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "intent": self.intent,
            "level": self.level.value,
            "service": self.service,
            "provider": self.provider,
            "read_only": self.read_only,
            "requires_ai": self.requires_ai,
            "requires_confirmation": self.requires_confirmation,
            "requires_cloud_context_preview": self.requires_cloud_context_preview,
            "allowed_context": list(self.allowed_context),
            "audit": self.audit.to_dict(),
            "current_version": self.current_version,
            "default_filters": dict(self.default_filters),
            "output_policy": dict(self.output_policy),
            "execution_contract": dict(self.execution_contract),
        }


@dataclass(frozen=True)
class PermissionDecision:
    """Static permission policy output for a requested capability."""

    decision: str
    reason: str
    required_cards: List[str] = field(default_factory=list)
    allowed_context: List[str] = field(default_factory=list)
    blocked_context: List[str] = field(default_factory=list)
    requires_task_queue: bool = False
    requires_snapshot: bool = False
    requires_approval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "required_cards": list(self.required_cards),
            "allowed_context": list(self.allowed_context),
            "blocked_context": list(self.blocked_context),
            "requires_task_queue": self.requires_task_queue,
            "requires_snapshot": self.requires_snapshot,
            "requires_approval": self.requires_approval,
        }


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
