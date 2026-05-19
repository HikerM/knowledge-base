"""Safe mutation approval and execution result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


MUTATION_APPROVAL_SCHEMA_VERSION = 1
MUTATION_RESULT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MutationApproval:
    """Human approval bound to one immutable mutation plan hash."""

    schema_version: int = MUTATION_APPROVAL_SCHEMA_VERSION
    approval_id: str = ""
    plan_type: str = ""
    target: Dict[str, Any] = field(default_factory=dict)
    approved_at: str = ""
    approved_by: str = ""
    plan_hash: str = ""
    snapshot_path: str = ""
    expires_at: str = ""
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", MUTATION_APPROVAL_SCHEMA_VERSION)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "approval_id": self.approval_id,
            "plan_type": self.plan_type,
            "target": dict(self.target),
            "approved_at": self.approved_at,
            "approved_by": self.approved_by,
            "plan_hash": self.plan_hash,
            "snapshot_path": self.snapshot_path,
            "expires_at": self.expires_at,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "MutationApproval":
        return cls(
            schema_version=int(payload.get("schema_version") or MUTATION_APPROVAL_SCHEMA_VERSION),
            approval_id=str(payload.get("approval_id") or ""),
            plan_type=str(payload.get("plan_type") or ""),
            target=dict(payload.get("target") or {}),
            approved_at=str(payload.get("approved_at") or ""),
            approved_by=str(payload.get("approved_by") or ""),
            plan_hash=str(payload.get("plan_hash") or ""),
            snapshot_path=str(payload.get("snapshot_path") or ""),
            expires_at=str(payload.get("expires_at") or ""),
            warnings=[str(item) for item in payload.get("warnings") or []],
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass(frozen=True)
class MutationResult:
    """Stable result emitted after a safe mutation task executes."""

    schema_version: int = MUTATION_RESULT_SCHEMA_VERSION
    success: bool = False
    mutation_type: str = ""
    target: Dict[str, Any] = field(default_factory=dict)
    changed_files: List[str] = field(default_factory=list)
    changed_configs: List[str] = field(default_factory=list)
    snapshot_path: str = ""
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    rollback_hint: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", MUTATION_RESULT_SCHEMA_VERSION)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "success": self.success,
            "mutation_type": self.mutation_type,
            "target": dict(self.target),
            "changed_files": list(self.changed_files),
            "changed_configs": list(self.changed_configs),
            "snapshot_path": self.snapshot_path,
            "validation_results": [dict(item) for item in self.validation_results],
            "rollback_hint": self.rollback_hint,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "elapsed_ms": self.elapsed_ms,
        }
