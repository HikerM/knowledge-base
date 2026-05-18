#!/usr/bin/env python3
"""Search score explanation checks using the controlled benchmark corpus."""

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

REQUIRED_BREAKDOWN_KEYS = {
    "bm25",
    "title_boost",
    "heading_boost",
    "layer_weight",
    "status_weight",
    "source_type_weight",
    "confidence_weight",
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


def paths(result: dict) -> list[str]:
    return [str(item.get("path", "")) for item in result.get("results", [])]


def assert_no_layer(result: dict, layer: str) -> None:
    marker = f"/{layer}/"
    result_paths = paths(result)
    if any(marker in path for path in result_paths):
        raise AssertionError(f"default search returned {layer} content: {result_paths}")


def assert_first_path_contains(result: dict, expected: str) -> None:
    result_paths = paths(result)
    if not result_paths or expected not in result_paths[0]:
        raise AssertionError(f"expected first result to contain {expected}, got {result_paths}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkb-search-explain-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)
        install_benchmark_corpus(project)

        run_json([sys.executable, "scripts/kb.py", "init"], project)
        run_json([sys.executable, "scripts/kb.py", "index"], project)

        default = run_json([sys.executable, "scripts/kb.py", "search", "--query", "react hydration"], project)
        if not default["results"]:
            raise AssertionError(f"default search produced no results: {default}")
        if any("score_breakdown" in item for item in default["results"]):
            raise AssertionError(f"default search must not include score_breakdown: {default}")
        assert_no_layer(default, "raw")
        assert_no_layer(default, "deprecated")
        assert_first_path_contains(default, "knowledge/01-frontend/rules/frontend-rule.md")

        explained = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "react hydration", "--explain-score"],
            project,
        )
        first = explained["results"][0]
        breakdown = first.get("score_breakdown")
        if not isinstance(breakdown, dict):
            raise AssertionError(f"explained search result missing score_breakdown: {explained}")
        missing = REQUIRED_BREAKDOWN_KEYS - set(breakdown)
        if missing:
            raise AssertionError(f"score_breakdown missing keys {sorted(missing)}: {breakdown}")
        if breakdown["final_score"] != first["score"]:
            raise AssertionError(f"final_score should match result score: {first}")

        agent = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "search",
                "--query",
                "context retrieval",
                "--category",
                "ai_agent",
                "--explain-score",
            ],
            project,
        )
        assert_first_path_contains(agent, "knowledge/09-ai-agent/rules/ai-agent-rule.md")

        wrong_category = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "search",
                "--query",
                "context retrieval",
                "--category",
                "frontend",
                "--explain-score",
            ],
            project,
        )
        if wrong_category["results"]:
            raise AssertionError(f"category filter did not exclude unrelated results: {wrong_category}")

        checklist = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "search",
                "--query",
                "sql injection",
                "--category",
                "security",
                "--layer",
                "checklists",
                "--explain-score",
            ],
            project,
        )
        assert_first_path_contains(checklist, "knowledge/08-security/checklists/security-checklist.md")

        wrong_layer = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "search",
                "--query",
                "sql injection",
                "--category",
                "security",
                "--layer",
                "rules",
                "--explain-score",
            ],
            project,
        )
        if wrong_layer["results"]:
            raise AssertionError(f"layer filter did not exclude checklist result: {wrong_layer}")

        raw_only = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "raw-only folklore signal", "--explain-score"],
            project,
        )
        if raw_only["results"]:
            raise AssertionError(f"default explained search should not return raw content: {raw_only}")

        deprecated_only = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "legacy cache timeout marker", "--explain-score"],
            project,
        )
        if deprecated_only["results"]:
            raise AssertionError(f"default explained search should not return deprecated content: {deprecated_only}")

    print("search explain tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
