"""Local zip backup service."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Tuple

from knowledge_core.paths import slugify
from knowledge_core.security import run_secret_scan

from knowledge_app.models.backup_models import BackupManifest, SnapshotResult
from knowledge_app.models.operation_result import OperationResult
from knowledge_app.services.mutation_plan_helpers import elapsed_ms, resolve_workspace_path


APP_VERSION = "1.6.0"
MANIFEST_NAME = "backup-manifest.json"
DEFAULT_BACKUP_PATHS = ["knowledge", "config", "templates", "reports", "docs", "README.md", "AGENTS.md"]
EXCLUDED_PATHS = [".git", "__pycache__", ".venv", "tmp", "exports", "backups"]


class BackupService:
    """Create, list, and verify local zip backups without requiring Git."""

    def __init__(self, workspace_path: Path | str | None = None):
        self.workspace_path = resolve_workspace_path(workspace_path)
        self.backups_root = self.workspace_path / "backups"

    def create_backup(self, reason: str, include_index: bool = False) -> SnapshotResult:
        start = time.perf_counter()
        reason = reason.strip()
        if not reason:
            return SnapshotResult(success=False, elapsed_ms=elapsed_ms(start), errors=["reason must not be empty"])

        warnings = self._secret_scan_warnings()
        created_at = datetime.now(timezone.utc)
        backup_id = f"{created_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        backup_path = self._backup_path(created_at, backup_id, reason)
        files = self._collect_files(include_index=include_index)
        digest, total_bytes = self._payload_digest(files)
        manifest = BackupManifest(
            backup_id=backup_id,
            created_at=created_at.isoformat().replace("+00:00", "Z"),
            workspace_path=str(self.workspace_path),
            app_version=APP_VERSION,
            included_paths=self._included_paths(include_index),
            excluded_paths=self._excluded_paths(include_index),
            include_index=include_index,
            file_count=len(files),
            total_bytes=total_bytes,
            sha256=digest,
            reason=reason,
            warnings=warnings,
            metadata={
                "format": "zip",
                "manifest_name": MANIFEST_NAME,
                "sha256_scope": "zip payload entries excluding backup-manifest.json",
                "git_required": False,
            },
        )

        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(MANIFEST_NAME, json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))
                for rel_path, path in files:
                    archive.write(path, rel_path)
        except OSError as exc:
            return SnapshotResult(
                success=False,
                elapsed_ms=elapsed_ms(start),
                warnings=warnings,
                errors=[f"backup write failed: {exc}"],
            )

        return SnapshotResult(
            success=True,
            backup_path=str(backup_path),
            manifest=manifest,
            elapsed_ms=elapsed_ms(start),
            warnings=warnings,
            errors=[],
        )

    def list_backups(self) -> OperationResult:
        start = time.perf_counter()
        results: List[Dict[str, Any]] = []
        warnings: List[str] = []
        if not self.backups_root.exists():
            return OperationResult(
                success=True,
                data={"count": 0, "results": [], "elapsed_ms": elapsed_ms(start)},
                elapsed_ms=elapsed_ms(start),
            )
        for path in sorted(self.backups_root.rglob("*.zip")):
            item: Dict[str, Any] = {"backup_path": str(path)}
            try:
                manifest = self._read_manifest(path)
                item.update(
                    {
                        "backup_id": manifest.backup_id,
                        "created_at": manifest.created_at,
                        "reason": manifest.reason,
                        "include_index": manifest.include_index,
                        "file_count": manifest.file_count,
                        "total_bytes": manifest.total_bytes,
                        "sha256": manifest.sha256,
                    }
                )
            except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError) as exc:
                item["error"] = str(exc)
                warnings.append(f"could not read backup manifest for {path}: {exc}")
            results.append(item)
        return OperationResult(
            success=True,
            data={"count": len(results), "results": results, "elapsed_ms": elapsed_ms(start)},
            warnings=warnings,
            elapsed_ms=elapsed_ms(start),
        )

    def verify_backup(self, backup_path: Path | str) -> OperationResult:
        start = time.perf_counter()
        path = Path(backup_path)
        warnings: List[str] = []
        errors: List[str] = []
        if not path.exists():
            return OperationResult(success=False, errors=[f"backup not found: {path}"], elapsed_ms=elapsed_ms(start))
        try:
            manifest = self._read_manifest(path)
            digest, total_bytes, file_count = self._zip_payload_digest(path)
            if digest != manifest.sha256:
                errors.append("backup sha256 mismatch")
            if total_bytes != manifest.total_bytes:
                errors.append("backup total_bytes mismatch")
            if file_count != manifest.file_count:
                errors.append("backup file_count mismatch")
            payload = {
                "backup_path": str(path),
                "valid": not errors,
                "sha256": digest,
                "manifest": manifest.to_dict(),
                "file_count": file_count,
                "total_bytes": total_bytes,
                "elapsed_ms": elapsed_ms(start),
            }
            return OperationResult(success=not errors, data=payload, warnings=warnings, errors=errors, elapsed_ms=payload["elapsed_ms"])
        except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError) as exc:
            return OperationResult(success=False, errors=[f"backup verify failed: {exc}"], elapsed_ms=elapsed_ms(start))

    def _backup_path(self, created_at: datetime, backup_id: str, reason: str) -> Path:
        workspace_slug = slugify(self.workspace_path.name, fallback="workspace")
        reason_slug = slugify(reason, fallback="backup")
        filename = f"pkb-backup-{workspace_slug}-{created_at.strftime('%Y%m%d-%H%M%S')}-{reason_slug}-{backup_id[-8:]}.zip"
        return self.backups_root / created_at.strftime("%Y") / created_at.strftime("%m") / filename

    def _collect_files(self, include_index: bool) -> List[Tuple[str, Path]]:
        rel_roots = list(DEFAULT_BACKUP_PATHS)
        if include_index:
            rel_roots.append(".kb")
        files: List[Tuple[str, Path]] = []
        for rel_root in rel_roots:
            root = self.workspace_path / rel_root
            if not root.exists():
                continue
            if root.is_file():
                rel_path = root.relative_to(self.workspace_path).as_posix()
                if not self._is_excluded(rel_path):
                    files.append((rel_path, root))
                continue
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                rel_path = path.relative_to(self.workspace_path).as_posix()
                if not self._is_excluded(rel_path):
                    files.append((rel_path, path))
        return sorted(files, key=lambda item: item[0])

    def _payload_digest(self, files: Iterable[Tuple[str, Path]]) -> Tuple[str, int]:
        digest = hashlib.sha256()
        total_bytes = 0
        for rel_path, path in files:
            payload = path.read_bytes()
            total_bytes += len(payload)
            digest.update(rel_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(payload)
            digest.update(b"\0")
        return digest.hexdigest(), total_bytes

    def _zip_payload_digest(self, backup_path: Path) -> Tuple[str, int, int]:
        digest = hashlib.sha256()
        total_bytes = 0
        file_count = 0
        with zipfile.ZipFile(backup_path, "r") as archive:
            names = sorted(name for name in archive.namelist() if name != MANIFEST_NAME and not name.endswith("/"))
            for name in names:
                self._validate_zip_member_name(name)
                payload = archive.read(name)
                total_bytes += len(payload)
                file_count += 1
                digest.update(name.encode("utf-8"))
                digest.update(b"\0")
                digest.update(payload)
                digest.update(b"\0")
        return digest.hexdigest(), total_bytes, file_count

    def _read_manifest(self, backup_path: Path) -> BackupManifest:
        with zipfile.ZipFile(backup_path, "r") as archive:
            if MANIFEST_NAME not in archive.namelist():
                raise KeyError(f"{MANIFEST_NAME} missing")
            payload = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("backup manifest must be a JSON object")
        return BackupManifest.from_dict(payload)

    def _secret_scan_warnings(self) -> List[str]:
        try:
            result = run_secret_scan(limit=200)
        except Exception as exc:  # pragma: no cover - defensive warning path
            return [f"secret-scan could not run before backup: {exc}"]
        findings_count = int(result.get("findings_count", 0))
        high_risk_count = int(result.get("high_risk_count", 0))
        if high_risk_count:
            return [f"secret-scan found {high_risk_count} high-risk finding(s); backup was created but should be reviewed"]
        if findings_count:
            return [f"secret-scan found {findings_count} finding(s); backup was created but should be reviewed"]
        return []

    def _included_paths(self, include_index: bool) -> List[str]:
        paths = [f"{item}/" if (self.workspace_path / item).is_dir() else item for item in DEFAULT_BACKUP_PATHS]
        if include_index:
            paths.append(".kb/")
        return paths

    @staticmethod
    def _excluded_paths(include_index: bool) -> List[str]:
        paths = [f"{item}/" for item in EXCLUDED_PATHS]
        if not include_index:
            paths.append(".kb/")
        return paths

    @staticmethod
    def _validate_zip_member_name(name: str) -> None:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe zip member path: {name}")

    @staticmethod
    def _is_excluded(rel_path: str) -> bool:
        parts = PurePosixPath(rel_path).parts
        return any(part in EXCLUDED_PATHS for part in parts)
