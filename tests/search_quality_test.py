#!/usr/bin/env python3
"""Search quality checks using a controlled benchmark corpus."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]

BENCHMARK_TARGETS = {
    "frontend-rule.md": "knowledge/01-frontend/rules/frontend-rule.md",
    "ui-ux-rule.md": "knowledge/03-ui-ux/rules/ui-ux-rule.md",
    "security-checklist.md": "knowledge/08-security/checklists/security-checklist.md",
    "ai-agent-rule.md": "knowledge/09-ai-agent/rules/ai-agent-rule.md",
    "frontend-raw.md": "knowledge/01-frontend/raw/frontend-raw.md",
    "backend-deprecated.md": "knowledge/02-backend/deprecated/backend-deprecated.md",
}


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


def install_benchmark_corpus(project: Path) -> None:
    corpus = SOURCE_ROOT / "tests" / "benchmark_corpus"
    for source_name, target in BENCHMARK_TARGETS.items():
        destination = project / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(corpus / source_name, destination)


def result_paths(result: dict) -> list[str]:
    return [str(item.get("path", "")) for item in result.get("results", [])]


def assert_no_layer(paths: list[str], layer: str) -> None:
    marker = f"/{layer}/"
    if any(marker in path for path in paths):
        raise AssertionError(f"default search returned {layer} content: {paths}")


def assert_first_path_contains(result: dict, expected: str) -> None:
    paths = result_paths(result)
    if not paths:
        raise AssertionError(f"expected results containing {expected}, got none")
    if expected not in paths[0]:
        raise AssertionError(f"expected first result to contain {expected}, got {paths}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkb-search-quality-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)
        install_benchmark_corpus(project)

        run_json([sys.executable, "scripts/kb.py", "init"], project)
        indexed = run_json([sys.executable, "scripts/kb.py", "index"], project)
        if indexed["indexed"] < len(BENCHMARK_TARGETS):
            raise AssertionError(f"benchmark corpus was not fully indexed: {indexed}")

        react = run_json([sys.executable, "scripts/kb.py", "search", "--query", "react hydration", "--top-k", "5"], project)
        react_paths = result_paths(react)
        assert_no_layer(react_paths, "raw")
        assert_no_layer(react_paths, "deprecated")
        assert_first_path_contains(react, "knowledge/01-frontend/rules/frontend-rule.md")

        raw_only = run_json([sys.executable, "scripts/kb.py", "search", "--query", "raw-only folklore signal"], project)
        if raw_only["results"]:
            raise AssertionError(f"default search should not return raw-only content: {raw_only}")

        deprecated_only = run_json([sys.executable, "scripts/kb.py", "search", "--query", "legacy cache timeout marker"], project)
        if deprecated_only["results"]:
            raise AssertionError(f"default search should not return deprecated content: {deprecated_only}")

        agent = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "context retrieval", "--category", "ai_agent"],
            project,
        )
        assert_first_path_contains(agent, "knowledge/09-ai-agent/rules/ai-agent-rule.md")

        wrong_category = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "context retrieval", "--category", "frontend"],
            project,
        )
        if wrong_category["results"]:
            raise AssertionError(f"category filter did not exclude unrelated results: {wrong_category}")

        checklist = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "sql injection", "--category", "security", "--layer", "checklists"],
            project,
        )
        assert_first_path_contains(checklist, "knowledge/08-security/checklists/security-checklist.md")

        wrong_layer = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "sql injection", "--category", "security", "--layer", "rules"],
            project,
        )
        if wrong_layer["results"]:
            raise AssertionError(f"layer filter did not exclude checklist result: {wrong_layer}")

        ranked = run_json([sys.executable, "scripts/kb.py", "search", "--query", "sql injection parameterized queries"], project)
        assert_first_path_contains(ranked, "knowledge/08-security/checklists/security-checklist.md")

        benchmark = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "benchmark",
                "--query",
                "react hydration",
                "--query",
                "sql injection",
                "--query",
                "context retrieval",
            ],
            project,
        )
        empty = [item for item in benchmark["results"] if item["result_count"] <= 0]
        if empty:
            raise AssertionError(f"benchmark corpus queries should have results: {benchmark}")

    print("search quality tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
