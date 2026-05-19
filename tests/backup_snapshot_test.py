#!/usr/bin/env python3
"""Backup, snapshot, and restore-plan tests."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable


SOURCE_ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path, expect: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if proc.returncode != expect:
        raise AssertionError(
            f"Command failed: {' '.join(cmd)}\n"
            f"Expected: {expect}, got: {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def run_json(cmd: list[str], cwd: Path, expect: int = 0) -> Dict[str, Any]:
    proc = run(cmd, cwd, expect=expect)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Command did not return JSON: {' '.join(cmd)}\n{proc.stdout}") from exc


def copy_project(dst: Path) -> None:
    ignore = shutil.ignore_patterns(".git", ".kb", "backups", "__pycache__", "*.pyc", "reports")
    shutil.copytree(SOURCE_ROOT, dst, ignore=ignore)


def hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def zip_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path, "r") as archive:
        return sorted(archive.namelist())


def read_manifest(path: Path) -> dict:
    with zipfile.ZipFile(path, "r") as archive:
        return json.loads(archive.read("backup-manifest.json").decode("utf-8"))


def write_excluded_fixtures(project: Path) -> None:
    for rel_path in [
        ".git/config",
        "docs/__pycache__/ignored.pyc",
        "knowledge/.venv/ignored.txt",
        "config/tmp/ignored.txt",
        "templates/exports/ignored.txt",
    ]:
        path = project / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("must not enter backup", encoding="utf-8")


def assert_no_excluded_entries(names: Iterable[str]) -> None:
    excluded = {".git", "__pycache__", ".venv", "tmp", "exports"}
    for name in names:
        parts = set(Path(name).parts)
        if excluded & parts:
            raise AssertionError(f"excluded path entered backup: {name}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkb-backup-snapshot-") as temp:
        root = Path(temp)
        project = root / "personal-knowledge-base"
        copy_project(project)
        write_excluded_fixtures(project)

        run_json([sys.executable, "scripts/kb.py", "init"], project)
        run_json([sys.executable, "scripts/kb.py", "index"], project)

        default_backup = run_json([sys.executable, "scripts/kb.py", "backup-create", "--reason", "test backup"], project)
        if not default_backup["success"]:
            raise AssertionError(default_backup)
        backup_path = Path(default_backup["backup_path"])
        if not backup_path.exists() or backup_path.suffix != ".zip":
            raise AssertionError(f"backup zip missing: {default_backup}")

        names = zip_names(backup_path)
        if "backup-manifest.json" not in names:
            raise AssertionError(f"backup-manifest.json missing from zip: {names}")
        if ".kb/index.sqlite" in names:
            raise AssertionError("default backup must not include .kb/index.sqlite")
        assert_no_excluded_entries(names)

        manifest = read_manifest(backup_path)
        if manifest["include_index"] is not False or not manifest["sha256"]:
            raise AssertionError(f"default manifest invalid: {manifest}")
        if manifest["metadata"].get("git_required") is not False:
            raise AssertionError(f"backup must not require Git: {manifest}")

        indexed_backup = run_json(
            [sys.executable, "scripts/kb.py", "backup-create", "--reason", "include index", "--include-index"],
            project,
        )
        indexed_path = Path(indexed_backup["backup_path"])
        indexed_manifest = read_manifest(indexed_path)
        if indexed_manifest["include_index"] is not True:
            raise AssertionError(f"include_index manifest flag missing: {indexed_manifest}")
        if ".kb/index.sqlite" not in zip_names(indexed_path):
            raise AssertionError("include_index backup should include .kb/index.sqlite")

        listed = run_json([sys.executable, "scripts/kb.py", "backup-list"], project)
        listed_paths = {item["backup_path"] for item in listed["results"]}
        if str(backup_path) not in listed_paths or str(indexed_path) not in listed_paths:
            raise AssertionError(f"backup-list did not include created backups: {listed}")

        verified = run_json([sys.executable, "scripts/kb.py", "backup-verify", "--path", str(backup_path)], project)
        if verified["valid"] is not True or verified["sha256"] != manifest["sha256"]:
            raise AssertionError(f"backup-verify failed: {verified}")

        run([sys.executable, "scripts/kb.py", "snapshot-create"], project, expect=1)
        empty_reason = run_json([sys.executable, "scripts/kb.py", "snapshot-create", "--reason", ""], project, expect=1)
        if empty_reason["success"] is not False or not empty_reason["errors"]:
            raise AssertionError(f"snapshot-create should reject empty reason: {empty_reason}")
        snapshot = run_json([sys.executable, "scripts/kb.py", "snapshot-create", "--reason", "test snapshot"], project)
        if not snapshot["success"] or not Path(snapshot["backup_path"]).exists():
            raise AssertionError(f"snapshot-create failed: {snapshot}")

        target = root / "target-workspace"
        target.mkdir()
        (target / "README.md").write_text("different readme", encoding="utf-8")
        (target / "config").write_text("parent file conflict", encoding="utf-8")
        before_restore_plan = hash_tree(target)
        restore_plan = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "restore-plan",
                "--backup",
                str(backup_path),
                "--target",
                str(target),
            ],
            project,
        )
        after_restore_plan = hash_tree(target)
        if before_restore_plan != after_restore_plan:
            raise AssertionError("restore-plan modified target workspace")
        if not restore_plan["files_to_create"]:
            raise AssertionError(f"restore-plan should list files_to_create: {restore_plan}")
        if not restore_plan["files_to_overwrite"]:
            raise AssertionError(f"restore-plan should list files_to_overwrite: {restore_plan}")
        if not restore_plan["conflicts"]:
            raise AssertionError(f"restore-plan should list conflicts: {restore_plan}")
        if restore_plan["requires_confirmation"] is not True:
            raise AssertionError(f"restore-plan must require confirmation: {restore_plan}")

    print("backup snapshot tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
