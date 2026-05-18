"""Benchmark command core."""

from __future__ import annotations

import argparse
import time
from typing import Any, Dict, List, Optional, Sequence

from .search import run_search


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def benchmark_queries() -> List[str]:
    return ["react", "api", "database index", "security", "agent workflow"]


def run_benchmark(queries: Optional[Sequence[str]], top_k: int) -> Dict[str, Any]:
    start = time.perf_counter()
    results = []
    for query in queries or benchmark_queries():
        search_args = argparse.Namespace(
            query=query,
            category=None,
            layer=None,
            type=None,
            status=None,
            confidence=None,
            source_type=None,
            top_k=top_k,
            include_distilled=False,
            include_raw=False,
            include_deprecated=False,
            slow_scan=False,
            force=False,
            research=False,
            explain_score=False,
        )
        item = run_search(search_args)
        results.append(
            {
                "query": query,
                "result_count": len(item["results"]),
                "elapsed_ms": item["elapsed_ms"],
            }
        )
    return {"elapsed_ms": elapsed_ms(start), "results": results}
