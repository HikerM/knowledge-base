"""Backup, snapshot, and restore plan models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


BACKUP_MANIFEST_SCHEMA_VERSION = 1
RESTORE_PLAN_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BackupManifest:
    """Stable manifest written into every backup zip."""

    schema_version: int = BACKUP_MANIFEST_SCHEMA_VERSION
    backup_id: str = ""
    created_at: str = ""
    workspace_path: str = ""
    app_version: str = ""
    included_paths: List[str] = field(default_factory=list)
    excluded_paths: List[str] = field(default_factory=list)
    include_index: bool = False
    file_count: int = 0
    total_bytes: int = 0
    sha256: str = ""
    reason: str = ""
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "backup_id": self.backup_id,
            "created_at": self.created_at,
            "workspace_path": self.workspace_path,
            "app_version": self.app_version,
            "included_paths": list(self.included_paths),
            "excluded_paths": list(self.excluded_paths),
            "include_index": self.include_index,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "sha256": self.sha256,
            "reason": self.reason,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "BackupManifest":
        return cls(
            schema_version=int(payload.get("schema_version") or BACKUP_MANIFEST_SCHEMA_VERSION),
            backup_id=str(payload.get("backup_id") or ""),
            created_at=str(payload.get("created_at") or ""),
            workspace_path=str(payload.get("workspace_path") or ""),
            app_version=str(payload.get("app_version") or ""),
            included_paths=[str(item) for item in payload.get("included_paths") or []],
            excluded_paths=[str(item) for item in payload.get("excluded_paths") or []],
            include_index=bool(payload.get("include_index", False)),
            file_count=int(payload.get("file_count") or 0),
            total_bytes=int(payload.get("total_bytes") or 0),
            sha256=str(payload.get("sha256") or ""),
            reason=str(payload.get("reason") or ""),
            warnings=[str(item) for item in payload.get("warnings") or []],
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass(frozen=True)
class SnapshotResult:
    """Result returned by backup and snapshot creation."""

    success: bool
    backup_path: str = ""
    manifest: Optional[BackupManifest] = None
    elapsed_ms: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "backup_path": self.backup_path,
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "elapsed_ms": self.elapsed_ms,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class RestorePlan:
    """Dry-run restore plan; never writes target files."""

    schema_version: int = RESTORE_PLAN_SCHEMA_VERSION
    backup_path: str = ""
    target_workspace: str = ""
    manifest_summary: Dict[str, Any] = field(default_factory=dict)
    files_to_restore: List[Dict[str, Any]] = field(default_factory=list)
    files_to_overwrite: List[Dict[str, Any]] = field(default_factory=list)
    files_to_create: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    requires_confirmation: bool = True
    validation_commands: List[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "backup_path": self.backup_path,
            "target_workspace": self.target_workspace,
            "manifest_summary": dict(self.manifest_summary),
            "files_to_restore": [dict(item) for item in self.files_to_restore],
            "files_to_overwrite": [dict(item) for item in self.files_to_overwrite],
            "files_to_create": [dict(item) for item in self.files_to_create],
            "conflicts": [dict(item) for item in self.conflicts],
            "risks": list(self.risks),
            "requires_confirmation": self.requires_confirmation,
            "validation_commands": list(self.validation_commands),
            "elapsed_ms": self.elapsed_ms,
        }
