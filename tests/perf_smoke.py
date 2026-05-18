#!/usr/bin/env python3
"""Large-corpus smoke checks for index/search performance behavior."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]

LAYERS = ["raw", "distilled", "rules", "checklists", "snippets", "deprecated"]
CATEGORY_DIRS = [
    ("frontend", "knowledge/01-frontend"),
    ("backend", "knowledge/02-backend"),
    ("security", "knowledge/08-security"),
    ("ai_agent", "knowledge/09-ai-agent"),
]


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


def type_for_layer(layer: str) -> str:
    return {
        "raw": "raw",
        "distilled": "rule",
        "rules": "rule",
        "checklists": "checklist",
        "snippets": "snippet",
        "deprecated": "rule",
    }[layer]


def status_for_layer(layer: str) -> str:
    if layer == "deprecated":
        return "deprecated"
    if layer in {"rules", "checklists", "snippets"}:
        return "active"
    return "experimental"


def review_required_for_layer(layer: str) -> str:
    return "false" if layer in {"rules", "checklists", "snippets", "deprecated"} else "true"


def write_document(project: Path, index: int) -> None:
    layer = LAYERS[index % len(LAYERS)]
    category, category_dir = CATEGORY_DIRS[index % len(CATEGORY_DIRS)]
    title = f"Perf Smoke {layer.title()} {index:04d}"
    doc_type = type_for_layer(layer)
    status = status_for_layer(layer)
    review_required = review_required_for_layer(layer)
    confidence = "high" if layer in {"rules", "checklists", "snippets"} else "medium"
    reviewed_by = "perf" if review_required == "false" else ""
    last_reviewed = "2026-05-18" if review_required == "false" else ""
    verification = "perf smoke fixture" if review_required == "false" else ""
    deprecated_reason = "superseded perf fixture" if layer == "deprecated" else ""
    superseded_by = "perf-smoke-current" if layer == "deprecated" else ""
    destination = project / category_dir / layer / f"perf-smoke-{index:04d}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        f"""---
title: "{title}"
category: {category}
type: {doc_type}
status: {status}
confidence: {confidence}
source_type: internal_practice
source_url: "https://example.com/perf-smoke/{index:04d}"
created_at: "2026-05-18T00:00:00"
last_reviewed: "{last_reviewed}"
reviewed_by: "{reviewed_by}"
valid_for: ["perf-smoke"]
not_valid_for: []
project_scope: "tests"
topic_id: "perf.smoke.{index % 50:02d}"
canonical_id: ""
source_hash: ""
content_hash: ""
supersedes: []
superseded_by: "{superseded_by}"
deprecated_reason: "{deprecated_reason}"
rejected_reason: ""
quarantined_reason: ""
risk_level: medium
verification_method: "{verification}"
review_required: {review_required}
review_cycle_days: 180
---

# {title}

Perf smoke indexed corpus marker stable-search-token category {category} layer {layer}.

## Guidance

Use SQLite FTS search for stable-search-token lookups. This fixture has enough body text to form a chunk and exercise ranking without loading the full knowledge tree during search.
""",
        encoding="utf-8",
        newline="\n",
    )


def generate_corpus(project: Path, count: int = 1000) -> None:
    for index in range(count):
        write_document(project, index)


def assert_search_uses_default_layers(search_result: dict) -> None:
    if not search_result["results"]:
        raise AssertionError(f"large-corpus search returned no results: {search_result}")
    forbidden = [item for item in search_result["results"] if item["layer"] in {"raw", "distilled", "deprecated"}]
    if forbidden:
        raise AssertionError(f"default search returned non-formal layers: {forbidden}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkb-perf-smoke-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)

        run_json([sys.executable, "scripts/kb.py", "init"], project)
        generate_corpus(project)

        first_index = run_json([sys.executable, "scripts/kb.py", "index"], project)
        second_index = run_json([sys.executable, "scripts/kb.py", "index"], project)
        search = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "stable-search-token", "--top-k", "10"],
            project,
        )
        stats = run_json([sys.executable, "scripts/kb.py", "stats"], project)
        doctor = run_json([sys.executable, "scripts/kb.py", "doctor"], project)

        if stats["documents"] != 1000:
            raise AssertionError(f"expected 1000 indexed documents, got stats={stats}")
        if stats["chunks"] < 1000:
            raise AssertionError(f"expected at least one chunk per document, got stats={stats}")
        if first_index["indexed"] != 1000:
            raise AssertionError(f"first index should index all generated docs: {first_index}")
        if second_index["skipped"] < 990:
            raise AssertionError(f"second index should skip unchanged docs: {second_index}")
        if second_index["hashed"] > 10:
            raise AssertionError(f"second index should avoid hashing unchanged docs: {second_index}")
        if doctor["indexed_document_count"] != 1000 or doctor["stale_index"]:
            raise AssertionError(f"doctor reported index inconsistency: {doctor}")

        assert_search_uses_default_layers(search)

        summary = {
            "document_count": stats["documents"],
            "chunk_count": stats["chunks"],
            "first_index_elapsed_ms": first_index["elapsed_ms"],
            "second_index_elapsed_ms": second_index["elapsed_ms"],
            "search_elapsed_ms": search["elapsed_ms"],
            "skipped": second_index["skipped"],
            "hashed": second_index["hashed"],
        }
        if summary["first_index_elapsed_ms"] > 60000:
            raise AssertionError(f"first index took unexpectedly long: {summary}")
        if summary["second_index_elapsed_ms"] > 30000:
            raise AssertionError(f"second index took unexpectedly long: {summary}")
        if summary["search_elapsed_ms"] > 10000:
            raise AssertionError(f"search took unexpectedly long: {summary}")

        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
