"""Stable plan-only mutation result model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


PLAN_RESULT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PlanResult:
    """JSON-stable dry-run payload for future mutation workflows."""

    schema_version: int = PLAN_RESULT_SCHEMA_VERSION
    dry_run: bool = True
    would_modify: bool = False
    blocked: bool = False
    elapsed_ms: int = 0
    plan_type: str = ""
    summary: str = ""
    target: Dict[str, Any] = field(default_factory=dict)
    affected_files: List[Dict[str, Any]] = field(default_factory=list)
    affected_configs: List[Dict[str, Any]] = field(default_factory=list)
    affected_categories: List[Dict[str, Any]] = field(default_factory=list)
    affected_sources: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    requires_snapshot: bool = False
    requires_confirmation: bool = False
    reversible: bool = True
    rollback_plan: List[str] = field(default_factory=list)
    validation_commands: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", PLAN_RESULT_SCHEMA_VERSION)
        object.__setattr__(self, "dry_run", True)
        object.__setattr__(self, "would_modify", False)
        object.__setattr__(self, "blocked", bool(self.blockers))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dry_run": self.dry_run,
            "would_modify": self.would_modify,
            "blocked": self.blocked,
            "elapsed_ms": self.elapsed_ms,
            "plan_type": self.plan_type,
            "summary": self.summary,
            "target": dict(self.target),
            "affected_files": [dict(item) for item in self.affected_files],
            "affected_configs": [dict(item) for item in self.affected_configs],
            "affected_categories": [dict(item) for item in self.affected_categories],
            "affected_sources": [dict(item) for item in self.affected_sources],
            "risks": list(self.risks),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "requires_snapshot": self.requires_snapshot,
            "requires_confirmation": self.requires_confirmation,
            "reversible": self.reversible,
            "rollback_plan": list(self.rollback_plan),
            "validation_commands": list(self.validation_commands),
            "actions": [dict(item) for item in self.actions],
        }
