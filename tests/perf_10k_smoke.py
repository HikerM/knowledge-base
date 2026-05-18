#!/usr/bin/env python3
"""Manual 10k-document performance smoke test.

This test is intentionally not part of default CI. It creates an isolated
temporary project copy, generates 10,000 Markdown documents, indexes them,
checks that a second index mostly skips unchanged files without hashing, then
runs search and stats.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_COUNT = 10_000

LAYERS = ["raw", "distilled", "rules", "checklists", "snippets", "deprecated"]
CATEGORY_DIRS = [
    ("frontend", "knowledge/01-frontend"),
    ("backend", "knowledge/02-backend"),
    ("performance", "knowledge/07-performance"),
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
    title = f"Perf 10k {layer.title()} {index:05d}"
    review_required = review_required_for_layer(layer)
    reviewed_by = "perf-10k" if review_required == "false" else ""
    last_reviewed = "2026-05-18" if review_required == "false" else ""
    verification = "manual 10k performance smoke" if review_required == "false" else ""
    deprecated_reason = "superseded 10k fixture" if layer == "deprecated" else ""
    superseded_by = "perf-10k-current" if layer == "deprecated" else ""
    destination = project / category_dir / layer / f"perf-10k-{index:05d}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        f"""---
title: "{title}"
category: {category}
type: {type_for_layer(layer)}
status: {status_for_layer(layer)}
confidence: medium
source_type: internal_practice
source_url: "https://example.com/perf-10k/{index:05d}"
created_at: "2026-05-18T00:00:00"
last_reviewed: "{last_reviewed}"
reviewed_by: "{reviewed_by}"
valid_for: ["perf-10k"]
not_valid_for: []
project_scope: "tests"
topic_id: "perf.10k.{index % 200:03d}"
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

Large scale smoke marker perf10kscaletoken category {category} layer {layer}.

## Note

This tiny fixture exercises FTS indexing, metadata filters, default formal search behavior, and unchanged-file skip logic without using the real knowledge directory.
""",
        encoding="utf-8",
        newline="\n",
    )


def generate_corpus(project: Path, count: int = DOCUMENT_COUNT) -> None:
    for index in range(count):
        write_document(project, index)


def assert_default_search_stays_formal(search_result: dict) -> None:
    if not search_result["results"]:
        raise AssertionError(f"10k search returned no results: {search_result}")
    forbidden = [item for item in search_result["results"] if item["layer"] in {"raw", "distilled", "deprecated"}]
    if forbidden:
        raise AssertionError(f"default search returned non-formal layers: {forbidden}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkb-perf-10k-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)

        run_json([sys.executable, "scripts/kb.py", "init"], project)
        generate_corpus(project)

        first_index = run_json([sys.executable, "scripts/kb.py", "index"], project)
        second_index = run_json([sys.executable, "scripts/kb.py", "index"], project)
        search = run_json(
            [sys.executable, "scripts/kb.py", "search", "--query", "perf10kscaletoken", "--top-k", "10"],
            project,
        )
        stats = run_json([sys.executable, "scripts/kb.py", "stats"], project)

        if stats["documents"] != DOCUMENT_COUNT:
            raise AssertionError(f"expected {DOCUMENT_COUNT} indexed documents, got stats={stats}")
        if stats["chunks"] < DOCUMENT_COUNT:
            raise AssertionError(f"expected at least one chunk per document, got stats={stats}")
        if first_index["indexed"] != DOCUMENT_COUNT:
            raise AssertionError(f"first index should index all generated docs: {first_index}")
        if second_index["skipped"] < DOCUMENT_COUNT - 100:
            raise AssertionError(f"second index should skip nearly all unchanged docs: {second_index}")
        if second_index["hashed"] > 100:
            raise AssertionError(f"second index should avoid hashing unchanged docs: {second_index}")

        assert_default_search_stays_formal(search)

        summary = {
            "document_count": stats["documents"],
            "chunk_count": stats["chunks"],
            "first_index_elapsed_ms": first_index["elapsed_ms"],
            "second_index_elapsed_ms": second_index["elapsed_ms"],
            "search_elapsed_ms": search["elapsed_ms"],
            "skipped": second_index["skipped"],
            "hashed": second_index["hashed"],
            "index_size_bytes": stats["index_size_bytes"],
        }

        if summary["first_index_elapsed_ms"] > 300000:
            raise AssertionError(f"first 10k index took unexpectedly long: {summary}")
        if summary["second_index_elapsed_ms"] > 60000:
            raise AssertionError(f"second 10k index took unexpectedly long: {summary}")
        if summary["search_elapsed_ms"] > 15000:
            raise AssertionError(f"10k search took unexpectedly long: {summary}")

        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
