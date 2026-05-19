#!/usr/bin/env python3
"""Manual 10k-document first-index profiling test.

This test is intentionally not part of default CI. It uses the same isolated
10k corpus as perf_10k_smoke.py, but calls the indexer directly with optional
profile hooks so the default CLI output remains unchanged.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from perf_10k_smoke import (
    DOCUMENT_COUNT,
    assert_default_search_stays_formal,
    copy_project,
    generate_corpus,
    run_json,
)

import sys
import tempfile


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_core import paths as core_paths
from knowledge_core.indexer import IndexProfile, perform_index


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pkb-perf-10k-profile-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)

        run_json([sys.executable, "scripts/kb.py", "init"], project)

        corpus_start = time.perf_counter()
        generate_corpus(project)
        corpus_generation_elapsed_ms = elapsed_ms(corpus_start)

        core_paths.configure_root(project)
        profile = IndexProfile()
        first_index = perform_index(profile=profile)
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
            "corpus_generation_elapsed_ms": corpus_generation_elapsed_ms,
            "first_index_elapsed_ms": first_index["elapsed_ms"],
            "second_index_elapsed_ms": second_index["elapsed_ms"],
            "search_elapsed_ms": search["elapsed_ms"],
            "skipped": second_index["skipped"],
            "hashed": second_index["hashed"],
            "index_size_bytes": stats["index_size_bytes"],
            "profile": first_index["profile"],
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
