"""Read-only restore planning service."""

from __future__ import annotations

import hashlib
import json
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List

from knowledge_app.models.backup_models import BackupManifest, RestorePlan
from knowledge_app.models.operation_result import OperationResult
from knowledge_app.services.backup_service import MANIFEST_NAME
from knowledge_app.services.mutation_plan_helpers import elapsed_ms, resolve_workspace_path


class RestorePlanService:
    """Create restore plans without extracting or overwriting files."""

    def __init__(self, workspace_path: Path | str | None = None):
        self.workspace_path = resolve_workspace_path(workspace_path)

    def create_restore_plan(self, backup_path: Path | str, target_workspace: Path | str) -> OperationResult:
        start = time.perf_counter()
        backup = Path(backup_path)
        target = Path(target_workspace).resolve()
        if not backup.exists():
            return OperationResult(success=False, errors=[f"backup not found: {backup}"], elapsed_ms=elapsed_ms(start))

        try:
            with zipfile.ZipFile(backup, "r") as archive:
                if MANIFEST_NAME not in archive.namelist():
                    return OperationResult(success=False, errors=[f"{MANIFEST_NAME} missing"], elapsed_ms=elapsed_ms(start))
                manifest_payload = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
                if not isinstance(manifest_payload, dict):
                    return OperationResult(success=False, errors=["backup manifest must be a JSON object"], elapsed_ms=elapsed_ms(start))
                manifest = BackupManifest.from_dict(manifest_payload)
                plan = self._build_plan(backup, target, archive, manifest, elapsed_ms(start))
                return OperationResult(success=True, data=plan, elapsed_ms=plan.elapsed_ms)
        except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
            return OperationResult(success=False, errors=[f"restore plan failed: {exc}"], elapsed_ms=elapsed_ms(start))

    def _build_plan(
        self,
        backup_path: Path,
        target_workspace: Path,
        archive: zipfile.ZipFile,
        manifest: BackupManifest,
        elapsed: int,
    ) -> RestorePlan:
        files_to_restore: List[Dict[str, Any]] = []
        files_to_overwrite: List[Dict[str, Any]] = []
        files_to_create: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []

        for name in sorted(item for item in archive.namelist() if item != MANIFEST_NAME and not item.endswith("/")):
            unsafe_reason = self._unsafe_member_reason(name)
            if unsafe_reason:
                conflicts.append({"path": name, "reason": unsafe_reason})
                continue

            payload = archive.read(name)
            payload_sha = hashlib.sha256(payload).hexdigest()
            entry = {"path": name, "size": len(payload), "sha256": payload_sha}
            files_to_restore.append(entry)

            target_path = target_workspace / Path(*PurePosixPath(name).parts)
            parent_conflict = self._parent_file_conflict(target_path, target_workspace)
            if parent_conflict:
                conflicts.append({"path": name, "reason": f"target parent is a file: {parent_conflict}"})
                continue
            if target_path.exists() and target_path.is_dir():
                conflicts.append({"path": name, "reason": "target path is a directory"})
                continue
            if target_path.exists():
                current_payload = target_path.read_bytes()
                files_to_overwrite.append(
                    {
                        **entry,
                        "target_path": str(target_path),
                        "same_content": hashlib.sha256(current_payload).hexdigest() == payload_sha,
                    }
                )
            else:
                files_to_create.append({**entry, "target_path": str(target_path)})

        return RestorePlan(
            backup_path=str(backup_path),
            target_workspace=str(target_workspace),
            manifest_summary={
                "schema_version": manifest.schema_version,
                "backup_id": manifest.backup_id,
                "created_at": manifest.created_at,
                "workspace_path": manifest.workspace_path,
                "reason": manifest.reason,
                "include_index": manifest.include_index,
                "file_count": manifest.file_count,
                "total_bytes": manifest.total_bytes,
                "sha256": manifest.sha256,
            },
            files_to_restore=files_to_restore,
            files_to_overwrite=files_to_overwrite,
            files_to_create=files_to_create,
            conflicts=conflicts,
            risks=[
                "restore-plan is read-only; future restore execution must require explicit confirmation",
                "restore execution may overwrite user files listed in files_to_overwrite",
                "Git is optional and is not required for restore planning",
            ],
            requires_confirmation=True,
            validation_commands=[
                "python scripts/kb.py workspace-status",
                "python scripts/kb.py doctor",
                "python scripts/kb.py audit",
                "python scripts/kb.py secret-scan",
            ],
            elapsed_ms=elapsed,
        )

    @staticmethod
    def _unsafe_member_reason(name: str) -> str:
        path = PurePosixPath(name)
        if path.is_absolute():
            return "absolute paths are not allowed"
        if ".." in path.parts:
            return "path traversal is not allowed"
        return ""

    @staticmethod
    def _parent_file_conflict(target_path: Path, target_workspace: Path) -> str:
        current = target_path.parent
        workspace = target_workspace.resolve()
        while current != workspace and workspace in current.resolve().parents:
            if current.exists() and current.is_file():
                return str(current)
            current = current.parent
        if current.exists() and current.is_file():
            return str(current)
        return ""
