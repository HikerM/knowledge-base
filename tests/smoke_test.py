#!/usr/bin/env python3
"""Smoke tests for kb.py using an isolated temporary project copy."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


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


def run_json(cmd: list[str], cwd: Path, expect: int = 0) -> dict:
    proc = run(cmd, cwd, expect=expect)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Command did not return JSON: {' '.join(cmd)}\n{proc.stdout}") from exc


def copy_project(dst: Path) -> None:
    ignore = shutil.ignore_patterns(".git", ".kb", "__pycache__", "*.pyc", "reports")
    shutil.copytree(SOURCE_ROOT, dst, ignore=ignore)


def copy_fixture(project: Path, fixture_name: str, relative_target: str) -> Path:
    src = SOURCE_ROOT / "tests" / "fixtures" / fixture_name
    dst = project / relative_target
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def assert_result_paths_do_not_contain(result: dict, text: str) -> None:
    paths = [item.get("path", "") for item in result.get("results", [])]
    if any(text in path for path in paths):
        raise AssertionError(f"Unexpected path containing {text}: {paths}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkb-smoke-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)

        run_json([sys.executable, "scripts/kb.py", "init"], project)

        raw = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "add-raw",
                "--category",
                "frontend",
                "--title",
                "Smoke Raw React",
                "--source-url",
                "https://example.com/smoke-raw",
                "--text",
                "Smoke raw React content should not appear in default search.",
            ],
            project,
        )
        raw_path = raw["created"]
        if "/raw/" not in raw_path and "\\raw\\" not in raw_path:
            raise AssertionError(f"add-raw did not create a raw file: {raw_path}")

        copy_fixture(project, "frontend-raw.md", "knowledge/01-frontend/raw/fixture-frontend-raw.md")
        distilled_path = copy_fixture(project, "ui-ux-distilled.md", "knowledge/03-ui-ux/distilled/fixture-ui-ux-distilled.md")
        copy_fixture(project, "security-rule.md", "knowledge/08-security/rules/fixture-security-rule.md")
        copy_fixture(project, "deprecated-rule.md", "knowledge/02-backend/deprecated/fixture-deprecated-rule.md")

        index_result = run_json([sys.executable, "scripts/kb.py", "index"], project)
        if index_result["indexed"] < 5 or index_result["hashed"] < 5:
            raise AssertionError(f"index did not index/hash expected files: {index_result}")

        search_raw = run_json([sys.executable, "scripts/kb.py", "search", "--query", "React"], project)
        assert_result_paths_do_not_contain(search_raw, "/raw/")

        rejected = run(
            [
                sys.executable,
                "scripts/kb.py",
                "promote",
                "--path",
                str(distilled_path.relative_to(project)),
                "--target-layer",
                "rules",
                "--reviewed-by",
                "smoke",
                "--confidence",
                "high",
                "--valid-for",
                "smoke",
                "--verification-method",
                "smoke test",
                "--review-note",
                "should fail without internal_practice or source_url",
            ],
            project,
            expect=0,
        )
        if "promoted" not in rejected.stdout:
            raise AssertionError("internal_practice distilled fixture should promote with review fields")

        no_source = project / "knowledge/03-ui-ux/distilled/no-source.md"
        no_source.write_text(
            """---
title: No Source Formal Candidate
category: ui_ux
type: rule
status: experimental
confidence: medium
source_type: unknown
source_url: ""
created_at: "2026-01-01T00:00:00"
last_reviewed: ""
reviewed_by: ""
valid_for: ["smoke"]
not_valid_for: []
project_scope: "tests"
supersedes: []
superseded_by: ""
risk_level: medium
verification_method: ""
review_required: true
---

# No Source Formal Candidate

This must be rejected by promote.
""",
            encoding="utf-8",
            newline="\n",
        )
        denied = run(
            [
                sys.executable,
                "scripts/kb.py",
                "promote",
                "--path",
                str(no_source.relative_to(project)),
                "--target-layer",
                "rules",
                "--reviewed-by",
                "smoke",
                "--confidence",
                "high",
                "--valid-for",
                "smoke",
                "--verification-method",
                "smoke test",
                "--review-note",
                "should fail",
            ],
            project,
            expect=1,
        )
        if "promote requires source_url" not in denied.stderr:
            raise AssertionError(f"promote missing source_url did not fail clearly:\n{denied.stderr}")

        run_json([sys.executable, "scripts/kb.py", "index"], project)
        formal_search = run_json([sys.executable, "scripts/kb.py", "search", "--query", "adaptive"], project)
        if not any("rules" in item.get("path", "") for item in formal_search.get("results", [])):
            raise AssertionError(f"promoted rule was not searchable: {formal_search}")

        opened = run([sys.executable, "scripts/kb.py", "open", "--path", raw_path], project)
        if "Smoke raw React content" not in opened.stdout or "Fixture Security Rule" in opened.stdout:
            raise AssertionError("open did not read exactly the requested raw file")

        run_json([sys.executable, "scripts/kb.py", "stats"], project)
        run_json([sys.executable, "scripts/kb.py", "doctor"], project)
        run_json([sys.executable, "scripts/kb.py", "benchmark"], project)

    print("smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
