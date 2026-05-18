"""Search core for the Markdown knowledge base."""

from __future__ import annotations

import argparse
import re
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .frontmatter import parse_frontmatter
from .indexer import (
    connect_db,
    ensure_schema,
    iter_markdown_files,
    normalize_document_meta,
)
from .markdown import chunk_markdown, read_single_markdown
from .paths import DEFAULT_SEARCH_LAYERS, EXPLORATORY_LAYERS


MAX_SNIPPET_CHARS = 500
DEFAULT_TOP_K = 10
MAX_TOP_K = 50


class SearchError(Exception):
    """Controlled search error."""


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def build_fts_query(query: str) -> str:
    tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
    if not tokens:
        raise SearchError("Query contains no searchable tokens")
    return " ".join(f'"{token}"' for token in tokens)


def parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    value = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None


def metadata_weight(row: sqlite3.Row, query_tokens: Sequence[str]) -> float:
    return sum(metadata_weight_components(row, query_tokens).values())


def metadata_weight_components(row: sqlite3.Row | Dict[str, Any], query_tokens: Sequence[str]) -> Dict[str, float]:
    layer_weight = {
        "rules": 5.0,
        "checklists": 4.5,
        "snippets": 4.0,
        "distilled": 2.0,
        "raw": 0.3,
        "deprecated": -4.0,
        "rejected": -8.0,
        "quarantine": -10.0,
    }
    status_weight = {"active": 2.0, "experimental": 0.8, "deprecated": -3.0, "rejected": -6.0}
    source_weight = {
        "official": 2.0,
        "github": 1.5,
        "paper": 1.4,
        "blog": 0.5,
        "forum": 0.1,
        "video": 0.1,
        "internal_practice": 1.2,
        "unknown": 0.0,
    }
    confidence_weight = {"high": 1.5, "medium": 0.7, "low": -0.5}

    components = {
        "layer_weight": layer_weight.get((row["layer"] or "").lower(), 0.0),
        "status_weight": status_weight.get((row["status"] or "").lower(), 0.0),
        "source_type_weight": source_weight.get((row["source_type"] or "").lower(), 0.0),
        "confidence_weight": confidence_weight.get((row["confidence"] or "").lower(), 0.0),
        "title_boost": 0.0,
        "heading_boost": 0.0,
        "content_boost": 0.0,
        "recency_boost": 0.0,
    }

    title = (row["title"] or "").lower()
    heading = (row["heading"] or "").lower()
    content = (row["content"] or "").lower()
    for token in query_tokens:
        token_l = token.lower()
        if token_l in title:
            components["title_boost"] += 3.0
        if token_l in heading:
            components["heading_boost"] += 1.5
        if token_l in content:
            components["content_boost"] += 0.2

    reviewed = parse_date(str(row["last_reviewed"] or row["reviewed_at"] or ""))
    if reviewed:
        age_days = max(0, (datetime.now() - reviewed.replace(tzinfo=None)).days)
        if age_days <= 30:
            components["recency_boost"] += 1.0
        elif age_days <= 90:
            components["recency_boost"] += 0.6
        elif age_days <= 180:
            components["recency_boost"] += 0.2
    return components


def score_breakdown(row: sqlite3.Row | Dict[str, Any], query_tokens: Sequence[str], bm25: float, final_score: float) -> Dict[str, float]:
    components = metadata_weight_components(row, query_tokens)
    return {
        "bm25": round(bm25, 4),
        "title_boost": round(components["title_boost"], 4),
        "heading_boost": round(components["heading_boost"], 4),
        "layer_weight": round(components["layer_weight"], 4),
        "status_weight": round(components["status_weight"], 4),
        "source_type_weight": round(components["source_type_weight"], 4),
        "confidence_weight": round(components["confidence_weight"], 4),
        "content_boost": round(components["content_boost"], 4),
        "recency_boost": round(components["recency_boost"], 4),
        "final_score": round(final_score, 4),
    }


def snippet_for(content: str, query_tokens: Sequence[str], max_chars: int = MAX_SNIPPET_CHARS) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    if len(normalized) <= max_chars:
        return normalized
    lower = normalized.lower()
    hit_index = -1
    for token in query_tokens:
        idx = lower.find(token.lower())
        if idx != -1 and (hit_index == -1 or idx < hit_index):
            hit_index = idx
    if hit_index == -1:
        return normalized[: max_chars - 1].rstrip() + "…"
    start = max(0, hit_index - max_chars // 3)
    end = min(len(normalized), start + max_chars)
    snippet = normalized[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(normalized):
        snippet += "…"
    return snippet


def validate_top_k(top_k: int, force: bool) -> int:
    if top_k <= 0:
        raise SearchError("--top-k must be positive")
    if top_k > MAX_TOP_K and not force:
        raise SearchError(f"--top-k max is {MAX_TOP_K}. Use --force to exceed it explicitly.")
    return top_k


def allowed_layers_for_search(args: argparse.Namespace, research: bool = False) -> List[str]:
    if research:
        if args.layer:
            return [args.layer]
        return sorted(EXPLORATORY_LAYERS)

    if args.layer:
        if args.layer == "raw" and not args.include_raw:
            raise SearchError("search excludes raw by default. Use --include-raw explicitly, or use research.")
        if args.layer == "distilled" and not args.include_distilled:
            raise SearchError("search excludes distilled by default. Use --include-distilled explicitly, or use research.")
        if args.layer == "deprecated" and not args.include_deprecated:
            raise SearchError("search excludes deprecated by default. Use --include-deprecated explicitly.")
        if args.layer in {"rejected", "quarantine"}:
            raise SearchError("search does not return rejected/quarantine content. Use list/open/audit for governance review.")
        return [args.layer]

    layers = set(DEFAULT_SEARCH_LAYERS)
    if args.include_distilled:
        layers.add("distilled")
    if args.include_raw:
        layers.add("raw")
    if args.include_deprecated:
        layers.add("deprecated")
    return sorted(layers)


def row_matches_filters(row: Dict[str, Any], args: argparse.Namespace, allowed_layers: Sequence[str]) -> bool:
    if args.category and row.get("category") != args.category:
        return False
    if row.get("layer") not in allowed_layers:
        return False
    if not getattr(args, "include_deprecated", False) and row.get("status") == "deprecated":
        return False
    if args.type and row.get("type") != args.type:
        return False
    if args.status and row.get("status") != args.status:
        return False
    if args.confidence and row.get("confidence") != args.confidence:
        return False
    if args.source_type and row.get("source_type") != args.source_type:
        return False
    if row.get("status") in {"deprecated", "rejected"} and row.get("layer") not in allowed_layers:
        return False
    return True


def run_slow_scan(args: argparse.Namespace) -> Dict[str, Any]:
    start = time.perf_counter()
    top_k = validate_top_k(args.top_k, args.force)
    query_tokens = re.findall(r"[\w]+", args.query, flags=re.UNICODE)
    if not query_tokens:
        raise SearchError("Query contains no searchable tokens")

    allowed_layers = allowed_layers_for_search(args, research=bool(getattr(args, "research", False)))

    def execute() -> List[Tuple[float, Dict[str, Any]]]:
        matches: List[Tuple[float, Dict[str, Any]]] = []
        for path in iter_markdown_files():
            text = read_single_markdown(path)
            frontmatter, body, _ = parse_frontmatter(text)
            meta = normalize_document_meta(path, frontmatter, body)
            if not row_matches_filters(meta, args, allowed_layers):
                continue
            chunks = chunk_markdown(body, meta["title"])
            for chunk in chunks:
                haystack = f"{meta['title']} {chunk['heading']} {chunk['content']}".lower()
                if not all(token.lower() in haystack for token in query_tokens):
                    continue
                row = {
                    **meta,
                    "heading": chunk["heading"],
                    "content": chunk["content"],
                    "reviewed_at": meta.get("reviewed_at", ""),
                }
                score = metadata_weight(row, query_tokens)
                matches.append((score, row))
        matches.sort(key=lambda item: item[0], reverse=True)
        return matches

    ranked = execute()

    elapsed = elapsed_ms(start)
    results = []
    for score, row in ranked[:top_k]:
        item = {
            "path": row["path"],
            "title": row["title"],
            "category": row["category"],
            "layer": row["layer"],
            "type": row["type"],
            "status": row["status"],
            "confidence": row["confidence"],
            "source_type": row["source_type"],
            "score": round(score, 4),
            "heading": row["heading"],
            "snippet": snippet_for(row["content"], query_tokens),
            "elapsed_ms": elapsed,
        }
        if getattr(args, "explain_score", False):
            item["score_breakdown"] = score_breakdown(row, query_tokens, 0.0, score)
        results.append(item)
    return {
        "query": args.query,
        "top_k": top_k,
        "mode": "slow_scan_explicit",
        "warning": "Explicit --slow-scan reads Markdown files and is intended only as an emergency fallback.",
        "allowed_layers": allowed_layers,
        "elapsed_ms": elapsed,
        "results": results,
    }


def run_search(args: argparse.Namespace) -> Dict[str, Any]:
    start = time.perf_counter()
    if args.slow_scan:
        return run_slow_scan(args)
    top_k = validate_top_k(args.top_k, args.force)
    conn = connect_db(must_exist=True)
    ensure_schema(conn)

    fts_query = build_fts_query(args.query)
    query_tokens = re.findall(r"[\w]+", args.query, flags=re.UNICODE)
    allowed_layers = allowed_layers_for_search(args, research=bool(getattr(args, "research", False)))

    def execute() -> List[sqlite3.Row]:
        where = ["chunks_fts MATCH ?"]
        params: List[Any] = [fts_query]

        if args.category:
            where.append("d.category = ?")
            params.append(args.category)
        where.append("d.layer IN (" + ",".join("?" for _ in allowed_layers) + ")")
        params.extend(allowed_layers)
        if not getattr(args, "include_deprecated", False):
            where.append("COALESCE(d.status, '') != ?")
            params.append("deprecated")
        if args.type:
            where.append("d.type = ?")
            params.append(args.type)
        if args.status:
            where.append("d.status = ?")
            params.append(args.status)
        if args.confidence:
            where.append("d.confidence = ?")
            params.append(args.confidence)
        if args.source_type:
            where.append("d.source_type = ?")
            params.append(args.source_type)

        sql = f"""
            SELECT
              d.id AS document_id,
              d.path,
              d.title,
              d.category,
              d.layer,
              d.type,
              d.status,
              d.confidence,
              d.source_type,
              d.source_url,
              d.last_reviewed,
              d.reviewed_at,
              c.heading,
              c.content,
              bm25(chunks_fts, 8.0, 4.0, 1.0) AS bm25_score
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.chunk_id
            JOIN documents d ON d.id = chunks_fts.document_id
            WHERE {" AND ".join(where)}
            ORDER BY bm25(chunks_fts, 8.0, 4.0, 1.0)
            LIMIT ?
        """
        params.append(max(top_k * 8, 50))
        return list(conn.execute(sql, params))

    rows = execute()

    ranked = []
    for row in rows:
        bm25_score = float(row["bm25_score"] or 0.0)
        base = 1.0 / (1.0 + abs(bm25_score))
        score = base + metadata_weight(row, query_tokens)
        ranked.append((score, row, base))
    ranked.sort(key=lambda item: item[0], reverse=True)

    elapsed = elapsed_ms(start)
    results = []
    for score, row, bm25 in ranked[:top_k]:
        item = {
            "path": row["path"],
            "title": row["title"],
            "category": row["category"],
            "layer": row["layer"],
            "type": row["type"],
            "status": row["status"],
            "confidence": row["confidence"],
            "source_type": row["source_type"],
            "score": round(score, 4),
            "heading": row["heading"],
            "snippet": snippet_for(row["content"], query_tokens),
            "elapsed_ms": elapsed,
        }
        if getattr(args, "explain_score", False):
            item["score_breakdown"] = score_breakdown(row, query_tokens, bm25, score)
        results.append(item)
    return {
        "query": args.query,
        "top_k": top_k,
        "allowed_layers": allowed_layers,
        "elapsed_ms": elapsed,
        "results": results,
    }
