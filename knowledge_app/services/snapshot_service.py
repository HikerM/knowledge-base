"""Snapshot service built on top of BackupService."""

from __future__ import annotations

import time
from pathlib import Path

from knowledge_app.models.backup_models import SnapshotResult
from knowledge_app.services.backup_service import BackupService
from knowledge_app.services.mutation_plan_helpers import elapsed_ms, resolve_workspace_path


class SnapshotService:
    """Create pre-operation snapshots without requiring Git."""

    def __init__(self, workspace_path: Path | str | None = None):
        self.workspace_path = resolve_workspace_path(workspace_path)

    def create_snapshot(self, reason: str, include_index: bool = False) -> SnapshotResult:
        start = time.perf_counter()
        reason = reason.strip()
        if not reason:
            return SnapshotResult(success=False, elapsed_ms=elapsed_ms(start), errors=["reason must not be empty"])
        snapshot_reason = reason if reason.startswith("snapshot-") else f"snapshot-{reason}"
        result = BackupService(self.workspace_path).create_backup(snapshot_reason, include_index=include_index)
        return SnapshotResult(
            success=result.success,
            backup_path=result.backup_path,
            manifest=result.manifest,
            elapsed_ms=elapsed_ms(start),
            warnings=list(result.warnings),
            errors=list(result.errors),
        )
