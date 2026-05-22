"""Minimal service-layer bootstrap for workspace-scoped AI persistence.

This service only creates the storage directories and manifest for v2.5.2. It
does not persist conversation, memory, or draft content.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List

from knowledge_app.ai.persistence_io import (
    AIPersistenceIOError,
    cleanup_partial_temp_files,
    ensure_directory,
    read_json,
    write_json_atomic,
)
from knowledge_app.ai.persistence_models import (
    AI_PERSISTENCE_SCHEMA_VERSION,
    AI_STORAGE_MANIFEST_VERSION,
    AIPersistenceModelValidationError,
    AIPersistencePlan,
    AIStorageLayout,
    AIStorageManifest,
)


AI_PERSISTENCE_WRITER_VERSION = "2.5.2-bootstrap"


class AIPersistenceServiceError(RuntimeError):
    """Controlled AI persistence service failure."""


class AIStorageBootstrapService:
    """Plan and explicitly bootstrap the minimal AI persistence layout."""

    def plan_bootstrap(self, workspace_root: Path | str) -> AIPersistencePlan:
        workspace = self._resolve_workspace(workspace_root)
        layout = self._layout(workspace, self._manifest(workspace, created_at=None))
        return AIPersistencePlan(
            schema_version=AI_PERSISTENCE_SCHEMA_VERSION,
            plan_id=f"ai-bootstrap-{self._workspace_id(workspace)}",
            workspace_id=self._workspace_id(workspace),
            layout=layout,
            scan_all=False,
            startup_scan_conversations=False,
            startup_scan_memory=False,
            startup_scan_drafts=False,
            inject_into_formal_search=False,
            list_conversations_paginated=True,
            list_memories_paginated=True,
            derived_index_rebuildable=True,
            privacy_mode=False,
            would_write_persistent_data=False,
            dry_run=True,
            would_modify=False,
            plan_first=True,
            requires_confirmation=True,
        ).validate()

    def bootstrap_storage(self, workspace_root: Path | str, confirmed: bool) -> AIStorageManifest:
        if confirmed is not True:
            raise AIPersistenceServiceError("AI persistence bootstrap requires confirmed=True")

        workspace = self._resolve_workspace(workspace_root)
        ai_root = workspace / "ai"
        manifest_path = ai_root / "manifest.json"

        if ai_root.exists():
            if not ai_root.is_dir():
                raise AIPersistenceServiceError("workspace/ai exists and is not a directory")
            if not manifest_path.exists():
                raise AIPersistenceServiceError("workspace/ai already exists without manifest.json")
            return self._read_existing_manifest(workspace, manifest_path)

        created_dirs: List[Path] = []
        allowed_dirs = [
            ai_root,
            ai_root / "conversations",
            ai_root / "memory",
            ai_root / "drafts",
            ai_root / "indexes",
        ]
        try:
            for directory in allowed_dirs:
                if directory.exists():
                    if not directory.is_dir():
                        raise AIPersistenceServiceError(f"planned AI storage path is not a directory: {directory}")
                    continue
                ensure_directory(directory)
                created_dirs.append(directory)

            manifest = self._manifest(workspace, created_at=_now_iso())
            self._layout(workspace, manifest).validate()
            write_json_atomic(manifest_path, manifest.to_dict())
            return self._read_existing_manifest(workspace, manifest_path)
        except (AIPersistenceIOError, AIPersistenceModelValidationError, AIPersistenceServiceError, OSError) as exc:
            cleanup_partial_temp_files(manifest_path)
            self._cleanup_created_dirs(created_dirs)
            raise AIPersistenceServiceError(f"AI persistence bootstrap failed: {exc}") from exc

    def _read_existing_manifest(self, workspace: Path, manifest_path: Path) -> AIStorageManifest:
        try:
            payload = read_json(manifest_path)
            manifest = AIStorageManifest.from_dict(payload)
            self._layout(workspace, manifest).validate()
            return manifest
        except (AIPersistenceIOError, AIPersistenceModelValidationError) as exc:
            raise AIPersistenceServiceError(f"AI storage manifest is corrupt or invalid: {exc}") from exc

    def _manifest(self, workspace: Path, created_at: str | None) -> AIStorageManifest:
        return AIStorageManifest(
            schema_version=AI_STORAGE_MANIFEST_VERSION,
            workspace_id=self._workspace_id(workspace),
            created_at=created_at,
            schema_min_reader_version=AI_PERSISTENCE_WRITER_VERSION,
            schema_writer_version=AI_PERSISTENCE_WRITER_VERSION,
        ).validate(str(workspace))

    def _layout(self, workspace: Path, manifest: AIStorageManifest) -> AIStorageLayout:
        ai_root = workspace / "ai"
        return AIStorageLayout(
            schema_version=AI_PERSISTENCE_SCHEMA_VERSION,
            workspace_id=self._workspace_id(workspace),
            workspace_root=str(workspace),
            storage_root=str(ai_root),
            conversations_path=str(ai_root / "conversations"),
            memory_path=str(ai_root / "memory"),
            drafts_path=str(ai_root / "drafts"),
            indexes_path=str(ai_root / "indexes"),
            manifest=manifest,
            install_root=None,
            source_records_are_truth=True,
            indexes_derived_only=True,
            indexes_rebuildable=True,
            storage_growth_limit_mb=1024,
        )

    @staticmethod
    def _resolve_workspace(workspace_root: Path | str) -> Path:
        workspace = Path(workspace_root).expanduser().resolve()
        if not workspace.exists():
            raise AIPersistenceServiceError(f"workspace_root does not exist: {workspace}")
        if not workspace.is_dir():
            raise AIPersistenceServiceError(f"workspace_root is not a directory: {workspace}")
        return workspace

    @staticmethod
    def _workspace_id(workspace: Path) -> str:
        text = workspace.name.strip().lower()
        safe = "".join(character if character.isalnum() else "_" for character in text).strip("_")
        return safe or "workspace"

    @staticmethod
    def _cleanup_created_dirs(created_dirs: List[Path]) -> None:
        for directory in sorted(created_dirs, key=lambda item: len(item.parts), reverse=True):
            try:
                if directory.exists():
                    directory.rmdir()
            except OSError:
                pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
