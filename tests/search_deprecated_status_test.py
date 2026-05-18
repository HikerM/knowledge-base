#!/usr/bin/env python3
"""Deprecated status and layer search filtering checks."""

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
    "backend-deprecated.md": "knowledge/02-backend/deprecated/backend-deprecated.md",
    "backend-formal-deprecated-status.md": "knowledge/02-backend/rules/backend-formal-deprecated-status.md",
}

REQUIRED_BREAKDOWN_KEYS = {
    "bm25",
    "title_boost",
    "heading_boost",
    "layer_weight",
    "status_weight",
    "source_type_weight",
    "confidence_weight",
    "content_boost",
    "recency_boost",
    "final_score",
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


def assert_no_result(result: dict, message: str) -> None:
    if result["results"]:
        raise AssertionError(f"{message}: {result}")


def assert_any_path_contains(result: dict, expected: str) -> None:
    paths = result_paths(result)
    if not any(expected in path for path in paths):
        raise AssertionError(f"expected result path containing {expected}, got {paths}")


def assert_layer_deprecated_requires_include(project: Path) -> None:
    proc = run(
        [
            sys.executable,
            "scripts/kb.py",
            "search",
            "--query",
            "legacy cache timeout marker",
            "--layer",
            "deprecated",
        ],
        project,
        expect=1,
    )
    combined_output = f"{proc.stdout}\n{proc.stderr}"
    if "deprecated" not in combined_output or "include-deprecated" not in combined_output:
        raise AssertionError(f"deprecated layer without include flag should explain the failure: {combined_output}")
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return
        if payload.get("results"):
            raise AssertionError(f"deprecated layer failure must not return results: {payload}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkb-search-deprecated-status-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)
        install_benchmark_corpus(project)

        run_json([sys.executable, "scripts/kb.py", "init"], project)
        run_json([sys.executable, "scripts/kb.py", "index"], project)

        formal_status_default = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "formal deprecated sentinel cache marker"],
            project,
        )
        assert_no_result(formal_status_default, "default search should not return formal layer deprecated status")

        formal_status_included = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "search",
                "--query",
                "formal deprecated sentinel cache marker",
                "--include-deprecated",
            ],
            project,
        )
        assert_any_path_contains(formal_status_included, "knowledge/02-backend/rules/backend-formal-deprecated-status.md")

        layer_default = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "legacy cache timeout marker"],
            project,
        )
        assert_no_result(layer_default, "default search should not return deprecated layer content")
        assert_layer_deprecated_requires_include(project)

        layer_included = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "search",
                "--query",
                "legacy cache timeout marker",
                "--include-deprecated",
            ],
            project,
        )
        assert_any_path_contains(layer_included, "knowledge/02-backend/deprecated/backend-deprecated.md")

        active_rule = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "react hydration boundary"],
            project,
        )
        assert_any_path_contains(active_rule, "knowledge/01-frontend/rules/frontend-rule.md")
        if any(item.get("status") != "active" for item in active_rule["results"]):
            raise AssertionError(f"active rule query returned unexpected statuses: {active_rule}")

        explained = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "react hydration boundary", "--explain-score"],
            project,
        )
        if not explained["results"]:
            raise AssertionError(f"explained search produced no results: {explained}")
        breakdown = explained["results"][0].get("score_breakdown")
        if not isinstance(breakdown, dict):
            raise AssertionError(f"explained search result missing score_breakdown: {explained}")
        missing = REQUIRED_BREAKDOWN_KEYS - set(breakdown)
        if missing:
            raise AssertionError(f"score_breakdown missing keys {sorted(missing)}: {breakdown}")
        if breakdown["final_score"] != explained["results"][0]["score"]:
            raise AssertionError(f"final_score should match result score: {explained['results'][0]}")

    print("search deprecated status tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
