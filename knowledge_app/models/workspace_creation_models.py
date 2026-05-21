"""Workspace creation planning and execution models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


WORKSPACE_CREATION_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class WorkspaceTemplateSummary:
    """Template option shown by the workspace creation wizard."""

    template_id: str
    display_name: str
    description: str
    intended_use: List[str] = field(default_factory=list)
    not_intended_for: List[str] = field(default_factory=list)
    default_dirs: List[str] = field(default_factory=list)
    default_files: List[str] = field(default_factory=list)
    default_configs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "display_name": self.display_name,
            "description": self.description,
            "intended_use": list(self.intended_use),
            "not_intended_for": list(self.not_intended_for),
            "default_dirs": list(self.default_dirs),
            "default_files": list(self.default_files),
            "default_configs": list(self.default_configs),
        }


@dataclass(frozen=True)
class WorkspaceCreationRequest:
    """Inputs for building a dry-run workspace creation plan."""

    target_path: str
    workspace_name: str
    template_id: str
    description: str = ""
    default_language: str = "zh-CN"
    create_backups_directory: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_path": self.target_path,
            "workspace_name": self.workspace_name,
            "template_id": self.template_id,
            "description": self.description,
            "default_language": self.default_language,
            "create_backups_directory": self.create_backups_directory,
        }


@dataclass(frozen=True)
class WorkspaceCreationPlan:
    """Stable dry-run payload for the workspace creation wizard."""

    plan_id: str
    workspace_name: str
    target_path: str
    template_id: str
    would_create_dirs: List[str] = field(default_factory=list)
    would_create_files: List[str] = field(default_factory=list)
    would_write_configs: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    requires_confirmation: bool = True
    reversible: bool = True
    validation_commands: List[str] = field(default_factory=list)
    estimated_result: Dict[str, Any] = field(default_factory=dict)
    elapsed_ms: int = 0
    schema_version: str = WORKSPACE_CREATION_SCHEMA_VERSION
    dry_run: bool = True
    would_modify: bool = False
    blocked: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", WORKSPACE_CREATION_SCHEMA_VERSION)
        object.__setattr__(self, "dry_run", True)
        object.__setattr__(self, "would_modify", False)
        object.__setattr__(self, "blocked", bool(self.blockers))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "workspace_name": self.workspace_name,
            "target_path": self.target_path,
            "template_id": self.template_id,
            "would_create_dirs": list(self.would_create_dirs),
            "would_create_files": list(self.would_create_files),
            "would_write_configs": list(self.would_write_configs),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "requires_confirmation": self.requires_confirmation,
            "dry_run": self.dry_run,
            "would_modify": self.would_modify,
            "blocked": self.blocked,
            "reversible": self.reversible,
            "validation_commands": list(self.validation_commands),
            "estimated_result": dict(self.estimated_result),
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass(frozen=True)
class WorkspaceCreationResult:
    """Result returned after a confirmed minimal workspace creation attempt."""

    success: bool
    plan_id: str
    workspace_path: str
    created_dirs: List[str] = field(default_factory=list)
    created_files: List[str] = field(default_factory=list)
    skipped_existing: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    elapsed_ms: int = 0
    next_steps: List[str] = field(default_factory=list)
    schema_version: str = WORKSPACE_CREATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_version", WORKSPACE_CREATION_SCHEMA_VERSION)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "success": self.success,
            "plan_id": self.plan_id,
            "workspace_path": self.workspace_path,
            "created_dirs": list(self.created_dirs),
            "created_files": list(self.created_files),
            "skipped_existing": list(self.skipped_existing),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "elapsed_ms": self.elapsed_ms,
            "next_steps": list(self.next_steps),
        }
