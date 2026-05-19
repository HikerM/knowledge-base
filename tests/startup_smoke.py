#!/usr/bin/env python3
"""Startup-path smoke test for the SQLite-hot workspace status service.

This test is intentionally not part of default CI. It creates 10,000 Markdown
files to prove workspace-status stays on the SQLite/config/cache path: no
Markdown scan, no Markdown reads, no hashing, and no implicit indexing.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_COUNT = 10_000

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_core import paths as core_paths
from knowledge_app.services.workspace_status_service import WorkspaceStatusService
from perf_10k_smoke import generate_corpus


def run(cmd: list[str], cwd: Path, expect: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if proc.returncode != expect:
        raise AssertionError(
            f"Command failed: {' '.join(cmd)}\n"
            f"Expected: {expect}, got: {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def run_json(cmd: list[str], cwd: Path, expect: int = 0) -> dict:
    proc = run(cmd, cwd, expect=expect)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Command did not return JSON: {' '.join(cmd)}\n{proc.stdout}") from exc


def copy_project(dst: Path) -> None:
    ignore = shutil.ignore_patterns(".git", ".kb", "__pycache__", "*.pyc", "reports", "knowledge")
    shutil.copytree(SOURCE_ROOT, dst, ignore=ignore)


def assert_service_does_not_touch_markdown(project: Path, expected_status: str) -> dict:
    original_root = core_paths.ROOT
    original_rglob = Path.rglob
    original_read_text = Path.read_text
    original_sha256 = hashlib.sha256
    knowledge_dir = (project / "knowledge").resolve()

    def blocked_rglob(self: Path, pattern: str):
        if self.resolve() == knowledge_dir:
            raise AssertionError("workspace-status must not scan knowledge/")
        return original_rglob(self, pattern)

    def blocked_read_text(self: Path, *args, **kwargs):
        if self.suffix.lower() == ".md":
            raise AssertionError(f"workspace-status must not read Markdown: {self}")
        return original_read_text(self, *args, **kwargs)

    def blocked_sha256(*args, **kwargs):
        raise AssertionError("workspace-status must not hash files")

    Path.rglob = blocked_rglob
    Path.read_text = blocked_read_text
    hashlib.sha256 = blocked_sha256
    core_paths.configure_root(project)
    try:
        result = WorkspaceStatusService().get_status()
        if result.data is None:
            raise AssertionError(f"workspace-status returned no data: {result}")
        payload = result.data.to_dict()
        if payload["index_status"] != expected_status:
            raise AssertionError(f"expected {expected_status}, got {payload}")
        return payload
    finally:
        core_paths.configure_root(original_root)
        Path.rglob = original_rglob
        Path.read_text = original_read_text
        hashlib.sha256 = original_sha256


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkb-startup-smoke-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)
        generate_corpus(project, DOCUMENT_COUNT)

        db_path = project / ".kb" / "index.sqlite"
        missing_status = run_json([sys.executable, "scripts/kb.py", "workspace-status"], project)
        if missing_status["index_status"] != "missing":
            raise AssertionError(f"workspace-status should report missing before index: {missing_status}")
        if db_path.exists():
            raise AssertionError("workspace-status created index.sqlite before index ran")
        if missing_status["document_count"] != 0 or missing_status["chunk_count"] != 0:
            raise AssertionError(f"missing index should not infer Markdown counts: {missing_status}")

        direct_missing = assert_service_does_not_touch_markdown(project, "missing")
        if direct_missing["index_exists"]:
            raise AssertionError(f"direct service call unexpectedly created an index: {direct_missing}")

        first_index = run_json([sys.executable, "scripts/kb.py", "index"], project)
        ready_status = run_json([sys.executable, "scripts/kb.py", "workspace-status"], project)
        direct_ready = assert_service_does_not_touch_markdown(project, "ready")

        if ready_status["index_status"] != "ready":
            raise AssertionError(f"workspace-status should report ready after index: {ready_status}")
        if ready_status["document_count"] != DOCUMENT_COUNT:
            raise AssertionError(f"expected {DOCUMENT_COUNT} documents, got {ready_status}")
        if ready_status["chunk_count"] < DOCUMENT_COUNT:
            raise AssertionError(f"expected at least one chunk per document, got {ready_status}")
        if direct_ready["document_count"] != DOCUMENT_COUNT:
            raise AssertionError(f"direct service returned inconsistent document count: {direct_ready}")

        startup_elapsed_ms = int(ready_status["elapsed_ms"])
        first_index_elapsed_ms = int(first_index["elapsed_ms"])
        threshold_ms = max(1000, first_index_elapsed_ms // 5)
        if startup_elapsed_ms >= threshold_ms:
            raise AssertionError(
                "workspace-status should be far faster than first index: "
                f"startup={startup_elapsed_ms}ms first_index={first_index_elapsed_ms}ms"
            )

        summary = {
            "document_count": ready_status["document_count"],
            "chunk_count": ready_status["chunk_count"],
            "missing_elapsed_ms": missing_status["elapsed_ms"],
            "startup_elapsed_ms": startup_elapsed_ms,
            "first_index_elapsed_ms": first_index_elapsed_ms,
            "index_status_before_index": missing_status["index_status"],
            "index_status_after_index": ready_status["index_status"],
            "index_created_by_workspace_status": False,
            "markdown_scan_blocked": True,
            "markdown_read_blocked": True,
            "hash_blocked": True,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
