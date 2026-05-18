"""Quality, governance, duplicate, stale, and conflict checks."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .frontmatter import (
    CONFIDENCE_VALUES,
    REQUIRED_SCHEMA_FIELDS,
    RISK_LEVEL_VALUES,
    SOURCE_TYPE_VALUES,
    STATUS_VALUES,
    bool_value,
    list_value,
)
from .markdown import read_markdown_parts
from .paths import FORMAL_LAYERS, infer_category_layer, to_relative_posix


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


def lint_file(path: Path) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    rel = to_relative_posix(path)
    frontmatter, _, has_frontmatter = read_markdown_parts(path)
    category, layer = infer_category_layer(path)

    def add(severity: str, issue: str, detail: str = "") -> None:
        item = {"severity": severity, "path": rel, "issue": issue}
        if detail:
            item["detail"] = detail
        issues.append(item)

    if not has_frontmatter:
        add("error", "missing_frontmatter")
        return issues

    for field in REQUIRED_SCHEMA_FIELDS:
        if field not in frontmatter:
            add("error", "missing_required_field", field)

    if not str(frontmatter.get("source_url") or "").strip():
        add("warning", "missing_source_url")
    if frontmatter.get("status") == "active" and not str(frontmatter.get("last_reviewed") or "").strip():
        add("error", "active_missing_last_reviewed")
    if layer in FORMAL_LAYERS:
        formal_source_type = str(frontmatter.get("source_type") or "")
        if not str(frontmatter.get("source_url") or "").strip() and formal_source_type != "internal_practice":
            add("error", "formal_missing_source_url", "formal knowledge requires source_url unless source_type=internal_practice")
        if not str(frontmatter.get("reviewed_by") or "").strip():
            add("error", "formal_missing_reviewed_by")
        if not str(frontmatter.get("verification_method") or "").strip():
            add("error", "formal_missing_verification_method")
        if frontmatter.get("type") == "raw" or bool_value(frontmatter.get("review_required")):
            add("error", "formal_layer_contains_unreviewed_or_raw")

    status = str(frontmatter.get("status") or "")
    if status and status not in STATUS_VALUES:
        add("error", "invalid_status", status)
    confidence = str(frontmatter.get("confidence") or "")
    if confidence and confidence not in CONFIDENCE_VALUES:
        add("error", "invalid_confidence", confidence)
    source_type = str(frontmatter.get("source_type") or "")
    if source_type and source_type not in SOURCE_TYPE_VALUES:
        add("error", "invalid_source_type", source_type)
    risk_level = str(frontmatter.get("risk_level") or "")
    if risk_level and risk_level not in RISK_LEVEL_VALUES:
        add("error", "invalid_risk_level", risk_level)

    if status == "deprecated" or layer == "deprecated":
        if (
            not str(frontmatter.get("superseded_by") or "").strip()
            and not str(frontmatter.get("deprecation_reason") or frontmatter.get("deprecated_reason") or "").strip()
        ):
            add("error", "deprecated_missing_superseded_by_or_reason")
    if layer == "raw" and status == "active":
        add("error", "raw_must_not_be_active")
    if layer in {"rejected", "quarantine"} and status == "active":
        add("error", f"{layer}_must_not_be_active")
    if category != "unknown" and frontmatter.get("category") and frontmatter.get("category") != category:
        add("warning", "category_mismatch", f"frontmatter={frontmatter.get('category')} path={category}")
    return issues


def lint(paths: Iterable[Path], category_filter: Optional[str], layer_filter: Optional[str], limit: int) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    files_checked = 0
    for path in paths:
        category, layer = infer_category_layer(path)
        if category_filter and category != category_filter:
            continue
        if layer_filter and layer != layer_filter:
            continue
        files_checked += 1
        issues.extend(lint_file(path))
    return {
        "files_checked": files_checked,
        "error_count": sum(1 for issue in issues if issue["severity"] == "error"),
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
        "issues": issues[:limit],
        "truncated": len(issues) > limit,
    }


def group_counts(rows: Sequence[sqlite3.Row], field: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        key = str(row[field] or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def is_stale_row(row: sqlite3.Row, default_days: int) -> bool:
    cycle_text = str(row["review_cycle_days"] or "").strip()
    try:
        cycle_days = int(cycle_text) if cycle_text else default_days
    except ValueError:
        cycle_days = default_days
    reviewed = parse_date(str(row["last_reviewed"] or row["reviewed_at"] or ""))
    if not reviewed:
        return True
    return datetime.now() - reviewed.replace(tzinfo=None) > timedelta(days=cycle_days)


def title_key(title: str) -> str:
    tokens = re.findall(r"[\w]+", title.lower(), flags=re.UNICODE)
    stop = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "如何", "怎么"}
    return " ".join(token for token in tokens if token not in stop)


def title_similarity(a: str, b: str) -> float:
    a_tokens = set(title_key(a).split())
    b_tokens = set(title_key(b).split())
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def row_summary(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "path": row["path"],
        "title": row["title"],
        "category": row["category"],
        "layer": row["layer"],
        "status": row["status"],
        "type": row["type"],
        "confidence": row["confidence"],
        "source_type": row["source_type"],
        "topic_id": row["topic_id"],
        "canonical_id": row["canonical_id"],
    }


def canonical_rank(row: sqlite3.Row) -> Tuple[int, int, int, int, int, str]:
    layer_rank = {
        "rules": 60,
        "checklists": 55,
        "snippets": 50,
        "distilled": 30,
        "raw": 20,
        "deprecated": 5,
        "rejected": 0,
        "quarantine": 0,
    }.get(str(row["layer"] or ""), 10)
    status_rank = {"active": 30, "experimental": 15, "deprecated": 4, "rejected": 0}.get(str(row["status"] or ""), 5)
    confidence_rank = {"high": 20, "medium": 10, "low": 0}.get(str(row["confidence"] or ""), 0)
    source_rank = {
        "official": 16,
        "github": 14,
        "paper": 12,
        "internal_practice": 11,
        "blog": 6,
        "forum": 3,
        "video": 2,
        "unknown": 0,
    }.get(str(row["source_type"] or ""), 0)
    review_rank = 5 if str(row["last_reviewed"] or row["reviewed_at"] or "").strip() else 0
    return (layer_rank, status_rank, confidence_rank, source_rank, review_rank, str(row["path"]))


def recommended_canonical(rows: Sequence[sqlite3.Row]) -> sqlite3.Row:
    return sorted(rows, key=canonical_rank, reverse=True)[0]


def suggested_duplicate_action(kind: str, rows: Sequence[sqlite3.Row], canonical: sqlite3.Row) -> str:
    non_canonical = [row for row in rows if int(row["id"]) != int(canonical["id"])]
    if any(row["layer"] == "quarantine" or row["status"] == "rejected" for row in non_canonical):
        return "reject"
    if kind in {"content_hash", "source_url", "normalized_title"}:
        if any(row["layer"] in FORMAL_LAYERS for row in rows):
            return "merge"
        return "keep"
    if kind == "topic_id" and len([row for row in rows if row["status"] == "active" and row["layer"] in FORMAL_LAYERS]) > 1:
        return "merge"
    if any(row["status"] == "deprecated" for row in non_canonical):
        return "keep"
    return "merge"


def make_duplicate_group(kind: str, key: str, rows: Sequence[sqlite3.Row], evidence: Dict[str, Any]) -> Dict[str, Any]:
    canonical = recommended_canonical(rows)
    return {
        "kind": kind,
        "key": key,
        "duplicate_group": [row_summary(row) for row in rows],
        "recommended_canonical_file": row_summary(canonical),
        "suggested_action": suggested_duplicate_action(kind, rows, canonical),
        "evidence": evidence,
    }


def build_dedupe_groups(rows: Sequence[sqlite3.Row], limit: int = 100) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []

    source_buckets: Dict[str, List[sqlite3.Row]] = {}
    title_buckets: Dict[Tuple[str, str], List[sqlite3.Row]] = {}
    content_hash_buckets: Dict[str, List[sqlite3.Row]] = {}
    topic_buckets: Dict[Tuple[str, str], List[sqlite3.Row]] = {}

    for row in rows:
        url = str(row["source_url"] or "").strip()
        if url:
            source_buckets.setdefault(url, []).append(row)
        normalized_title = title_key(str(row["title"] or ""))
        if normalized_title:
            title_buckets.setdefault((str(row["category"]), normalized_title), []).append(row)
        content_hash = str(row["content_hash"] or "").strip()
        if content_hash:
            content_hash_buckets.setdefault(content_hash, []).append(row)
        topic_id = str(row["topic_id"] or "").strip()
        if topic_id:
            topic_buckets.setdefault((str(row["category"]), topic_id), []).append(row)

    for url, bucket in source_buckets.items():
        if len(bucket) > 1:
            groups.append(make_duplicate_group("source_url", url, bucket, {"source_url": url}))
    for (category, normalized_title), bucket in title_buckets.items():
        if len(bucket) > 1:
            groups.append(
                make_duplicate_group(
                    "normalized_title",
                    f"{category}:{normalized_title}",
                    bucket,
                    {"category": category, "normalized_title": normalized_title},
                )
            )
    for content_hash, bucket in content_hash_buckets.items():
        if len(bucket) > 1:
            groups.append(make_duplicate_group("content_hash", content_hash, bucket, {"content_hash": content_hash}))
    for (category, topic_id), bucket in topic_buckets.items():
        if len(bucket) > 1:
            groups.append(
                make_duplicate_group(
                    "topic_id",
                    f"{category}:{topic_id}",
                    bucket,
                    {"category": category, "topic_id": topic_id},
                )
            )

    groups.sort(key=lambda item: (item["kind"], item["key"]))
    return groups[:limit]


def duplicate_titles(rows: Sequence[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [group for group in build_dedupe_groups(rows, 10000) if group["kind"] == "normalized_title"]


def source_url_duplicates(rows: Sequence[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [group for group in build_dedupe_groups(rows, 10000) if group["kind"] == "source_url"]


def content_hash_duplicates(rows: Sequence[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [group for group in build_dedupe_groups(rows, 10000) if group["kind"] == "content_hash"]


def topic_id_duplicates(rows: Sequence[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [group for group in build_dedupe_groups(rows, 10000) if group["kind"] == "topic_id"]


def sha_duplicates(rows: Sequence[sqlite3.Row]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[sqlite3.Row]] = {}
    for row in rows:
        sha = str(row["sha256"] or "")
        if sha:
            buckets.setdefault(sha, []).append(row)
    return [
        make_duplicate_group("sha256", sha, bucket, {"sha256": sha})
        for sha, bucket in buckets.items()
        if len(bucket) > 1
    ]


def similar_filenames(rows: Sequence[sqlite3.Row], threshold: float = 0.82) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    by_category: Dict[str, List[sqlite3.Row]] = {}
    for row in rows:
        by_category.setdefault(str(row["category"]), []).append(row)
    for category, bucket in by_category.items():
        for i, left in enumerate(bucket):
            left_stem = Path(str(left["path"])).stem
            for right in bucket[i + 1 :]:
                right_stem = Path(str(right["path"])).stem
                sim = title_similarity(left_stem, right_stem)
                if sim >= threshold and left_stem != right_stem:
                    result.append(
                        {
                            "category": category,
                            "similarity": round(sim, 3),
                            "items": [
                                {"id": left["id"], "path": left["path"], "title": left["title"]},
                                {"id": right["id"], "path": right["path"], "title": right["title"]},
                            ],
                        }
                    )
    return result


def reference_index(rows: Sequence[sqlite3.Row]) -> Dict[str, sqlite3.Row]:
    index: Dict[str, sqlite3.Row] = {}
    for row in rows:
        for value in (row["path"], row["title"], row["canonical_id"], row["topic_id"]):
            text = str(value or "").strip()
            if text:
                index[text] = row
    return index


def marker_hits(content: str, markers: Sequence[str]) -> List[str]:
    return [marker for marker in markers if marker.lower() in content]


def add_conflict(conflicts: List[Dict[str, Any]], item: Dict[str, Any], limit: int) -> bool:
    conflicts.append(item)
    return len(conflicts) >= limit


def possible_conflicts(conn: sqlite3.Connection, rows: Sequence[sqlite3.Row], limit: int = 50) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    active_formal = [row for row in rows if row["status"] == "active" and row["layer"] in FORMAL_LAYERS]
    active_rules = [row for row in active_formal if row["layer"] == "rules"]

    by_topic: Dict[Tuple[str, str], List[sqlite3.Row]] = {}
    for row in active_rules:
        topic_id = str(row["topic_id"] or "").strip()
        if topic_id:
            by_topic.setdefault((str(row["category"]), topic_id), []).append(row)
    for (category, topic_id), bucket in by_topic.items():
        if len(bucket) > 1:
            if add_conflict(
                conflicts,
                {
                    "kind": "multiple_active_rules_same_topic_id",
                    "severity": "high",
                    "category": category,
                    "topic_id": topic_id,
                    "items": [row_summary(row) for row in bucket],
                    "evidence": {
                        "active_rule_count": len(bucket),
                        "paths": [row["path"] for row in bucket],
                        "reason": "同一 topic_id 下存在多个 active rules，正式层 canonical 规则不唯一。",
                    },
                },
                limit,
            ):
                return conflicts

    for i, left in enumerate(active_formal):
        for right in active_formal[i + 1 :]:
            if left["category"] != right["category"]:
                continue
            sim = title_similarity(str(left["title"]), str(right["title"]))
            if sim >= 0.75:
                if add_conflict(
                    conflicts,
                    {
                        "kind": "similar_active_titles",
                        "severity": "medium",
                        "category": left["category"],
                        "similarity": round(sim, 3),
                        "items": [row_summary(left), row_summary(right)],
                        "evidence": {
                            "left_title_key": title_key(str(left["title"])),
                            "right_title_key": title_key(str(right["title"])),
                            "reason": "active formal 内容标题高度相似，可能是重复或拆分不清。",
                        },
                    },
                    limit,
                ):
                    return conflicts

    refs = reference_index(rows)
    deprecated_rows = [row for row in rows if row["status"] == "deprecated" or row["layer"] == "deprecated"]
    deprecated_identities: Dict[str, sqlite3.Row] = {}
    for row in deprecated_rows:
        for value in (row["path"], row["title"], row["canonical_id"], row["topic_id"]):
            text = str(value or "").strip()
            if text:
                deprecated_identities[text] = row

    for row in rows:
        target = str(row["superseded_by"] or "").strip()
        if target and target not in refs:
            if add_conflict(
                conflicts,
                {
                    "kind": "superseded_by_missing_target",
                    "severity": "high",
                    "item": row_summary(row),
                    "evidence": {
                        "superseded_by": target,
                        "reason": "superseded_by 指向的 path/title/canonical_id/topic_id 在索引中不存在。",
                    },
                },
                limit,
            ):
                return conflicts

    for row in active_formal:
        for item in list_value(row["supersedes"]):
            old = refs.get(item)
            if old and old["status"] == "active":
                if add_conflict(
                    conflicts,
                    {
                        "kind": "active_rule_supersedes_still_active_rule",
                        "severity": "high",
                        "new": row_summary(row),
                        "old": row_summary(old),
                        "evidence": {
                            "reference_field": "supersedes",
                            "reference_value": item,
                            "reason": "新 active 规则声明 supersedes 旧规则，但旧规则仍是 active。",
                        },
                    },
                    limit,
                ):
                    return conflicts
            deprecated = deprecated_identities.get(item)
            if deprecated:
                if add_conflict(
                    conflicts,
                    {
                        "kind": "deprecated_referenced_by_active_rule",
                        "severity": "low",
                        "active": row_summary(row),
                        "deprecated": row_summary(deprecated),
                        "evidence": {
                            "reference_field": "supersedes",
                            "reference_value": item,
                            "reason": "active 规则引用 deprecated 内容。作为历史 supersedes 可接受；若作为依赖或依据则需要改为引用 canonical active 规则。",
                        },
                    },
                    limit,
                ):
                    return conflicts

    opposite_markers = ("禁止", "不得", "不要", "avoid", "must not", "do not", "never")
    positive_markers = ("必须", "应该", "推荐", "默认", "should", "must", "recommend")
    content_by_doc: Dict[int, str] = {}
    for row in conn.execute(
        """
        SELECT document_id, GROUP_CONCAT(content, '\n') AS content
        FROM chunks
        GROUP BY document_id
        """
    ):
        content_by_doc[int(row["document_id"])] = str(row["content"] or "").lower()
    for i, left in enumerate(active_rules):
        left_scope = set(list_value(left["valid_for"]))
        left_content = content_by_doc.get(int(left["id"]), "")
        for right in active_rules[i + 1 :]:
            if left["category"] != right["category"]:
                continue
            right_scope = set(list_value(right["valid_for"]))
            overlap = sorted(left_scope & right_scope)
            if left_scope and right_scope and not overlap:
                continue
            sim = title_similarity(str(left["title"]), str(right["title"]))
            same_topic = bool(str(left["topic_id"] or "").strip() and left["topic_id"] == right["topic_id"])
            if sim < 0.45 and not same_topic:
                continue
            right_content = content_by_doc.get(int(right["id"]), "")
            left_positive_hits = marker_hits(left_content, positive_markers)
            left_negative_hits = marker_hits(left_content, opposite_markers)
            right_positive_hits = marker_hits(right_content, positive_markers)
            right_negative_hits = marker_hits(right_content, opposite_markers)
            if (left_positive_hits and right_negative_hits) or (left_negative_hits and right_positive_hits):
                if add_conflict(
                    conflicts,
                    {
                        "kind": "possible_opposite_conclusion",
                        "severity": "medium",
                        "category": left["category"],
                        "topic_id": left["topic_id"] if same_topic else "",
                        "valid_for_overlap": overlap,
                        "items": [row_summary(left), row_summary(right)],
                        "evidence": {
                            "title_similarity": round(sim, 3),
                            "same_topic_id": same_topic,
                            "left_positive_markers": left_positive_hits,
                            "left_negative_markers": left_negative_hits,
                            "right_positive_markers": right_positive_hits,
                            "right_negative_markers": right_negative_hits,
                            "reason": "适用范围重叠且一侧包含推荐/必须信号、另一侧包含禁止/避免信号，需人工核对是否结论相反。",
                        },
                    },
                    limit,
                ):
                    return conflicts
    return conflicts


def audit(conn: sqlite3.Connection, rows: Sequence[sqlite3.Row], days: int, limit: int) -> Dict[str, Any]:
    missing_source = [dict(row) for row in rows if not str(row["source_url"] or "").strip()]
    missing_review = [
        dict(row)
        for row in rows
        if row["layer"] in FORMAL_LAYERS and (not str(row["reviewed_by"] or "").strip() or not str(row["verification_method"] or "").strip())
    ]
    formal_missing_source = [
        dict(row)
        for row in rows
        if row["layer"] in FORMAL_LAYERS
        and not str(row["source_url"] or "").strip()
        and str(row["source_type"] or "") != "internal_practice"
    ]
    stale_rows = [dict(row) for row in rows if row["status"] == "active" and is_stale_row(row, days)]
    low_conf_rules = [dict(row) for row in rows if row["layer"] == "rules" and row["confidence"] == "low"]
    unknown_source = [dict(row) for row in rows if row["source_type"] == "unknown"]
    raw_in_formal = [
        dict(row)
        for row in rows
        if row["layer"] in FORMAL_LAYERS and (row["type"] == "raw" or bool_value(row["review_required"]))
    ]
    return {
        "documents": len(rows),
        "by_category": group_counts(rows, "category"),
        "by_layer": group_counts(rows, "layer"),
        "by_status": group_counts(rows, "status"),
        "missing_source": missing_source[:limit],
        "formal_missing_source": formal_missing_source[:limit],
        "missing_formal_review": missing_review[:limit],
        "stale_active": stale_rows[:limit],
        "low_confidence_rules": low_conf_rules[:limit],
        "unknown_source_type": unknown_source[:limit],
        "raw_in_formal_layer": raw_in_formal[:limit],
        "duplicate_groups": build_dedupe_groups(rows, limit),
        "duplicate_titles": duplicate_titles(rows)[:limit],
        "possible_conflicts": possible_conflicts(conn, rows, limit),
    }


def review_queue(rows: Sequence[sqlite3.Row], days: int, limit: int) -> Dict[str, Any]:
    cutoff = datetime.now() - timedelta(days=days)
    queue: List[Dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        reasons: List[str] = []
        created = parse_date(str(row["created_at"] or ""))
        if row["layer"] == "distilled" and row["confidence"] in {"high", "medium"}:
            reasons.append("distilled_confidence_high_or_medium")
        if row["source_type"] in {"official", "github", "paper"} and row["layer"] in {"raw", "distilled"}:
            reasons.append("authoritative_source")
        if row["layer"] == "raw" and created and created.replace(tzinfo=None) >= cutoff:
            if row["confidence"] in {"high", "medium"} or row["source_type"] in {"official", "github", "paper"}:
                reasons.append("recent_high_priority_raw")
        if bool_value(row["review_required"]):
            reasons.append("review_required_true")
        if reasons and int(row["id"]) not in seen:
            item = dict(row)
            item["reasons"] = reasons
            queue.append(item)
            seen.add(int(row["id"]))
    return {"count": len(queue), "results": queue[:limit]}


def stale(rows: Sequence[sqlite3.Row], days: int, limit: int) -> Dict[str, Any]:
    stale_rows = [dict(row) for row in rows if row["status"] == "active" and is_stale_row(row, days)]
    return {"days": days, "count": len(stale_rows), "results": stale_rows[:limit]}


def conflicts(conn: sqlite3.Connection, rows: Sequence[sqlite3.Row], limit: int) -> Dict[str, Any]:
    conflict_rows = possible_conflicts(conn, rows, limit)
    return {"count": len(conflict_rows), "results": conflict_rows}


def dedupe(rows: Sequence[sqlite3.Row], limit: int) -> Dict[str, Any]:
    duplicate_groups = build_dedupe_groups(rows, limit)
    return {
        "duplicate_groups": duplicate_groups,
        "count": len(duplicate_groups),
        "duplicate_titles": duplicate_titles(rows)[:limit],
        "duplicate_source_urls": source_url_duplicates(rows)[:limit],
        "duplicate_content_hash": content_hash_duplicates(rows)[:limit],
        "duplicate_topic_ids": topic_id_duplicates(rows)[:limit],
        "duplicate_sha256": sha_duplicates(rows)[:limit],
        "similar_filenames": similar_filenames(rows)[:limit],
    }


def conflict_matches_topic(conflict: Dict[str, Any], topic_id: str, paths: set[str]) -> bool:
    if str(conflict.get("topic_id") or "") == topic_id:
        return True
    for key in ("items",):
        for item in conflict.get(key, []) or []:
            if str(item.get("path") or "") in paths or str(item.get("topic_id") or "") == topic_id:
                return True
    for key in ("item", "new", "old", "active", "deprecated"):
        item = conflict.get(key)
        if isinstance(item, dict) and (str(item.get("path") or "") in paths or str(item.get("topic_id") or "") == topic_id):
            return True
    return False


def canonical_file_for(rows: Sequence[sqlite3.Row], layer: str) -> Optional[Dict[str, Any]]:
    candidates = [row for row in rows if row["layer"] == layer and row["status"] == "active"]
    if not candidates:
        return None
    return row_summary(recommended_canonical(candidates))


def collect_lint_issues(paths: Iterable[Path], limit: int) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    files_checked = 0
    for path in paths:
        files_checked += 1
        issues.extend(lint_file(path))
    return {
        "files_checked": files_checked,
        "error_count": sum(1 for issue in issues if issue["severity"] == "error"),
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
        "issues": issues[:limit],
        "truncated": len(issues) > limit,
    }


def collect_audit_summary(conn: sqlite3.Connection, rows: Sequence[sqlite3.Row], days: int, limit: int) -> Dict[str, Any]:
    missing_source = [dict(row) for row in rows if not str(row["source_url"] or "").strip()]
    missing_review = [
        dict(row)
        for row in rows
        if row["layer"] in FORMAL_LAYERS and (not str(row["reviewed_by"] or "").strip() or not str(row["verification_method"] or "").strip())
    ]
    formal_missing_source = [
        dict(row)
        for row in rows
        if row["layer"] in FORMAL_LAYERS
        and not str(row["source_url"] or "").strip()
        and str(row["source_type"] or "") != "internal_practice"
    ]
    stale_rows = [dict(row) for row in rows if row["status"] == "active" and is_stale_row(row, days)]
    low_conf_rules = [dict(row) for row in rows if row["layer"] == "rules" and row["confidence"] == "low"]
    raw_in_formal = [
        dict(row)
        for row in rows
        if row["layer"] in FORMAL_LAYERS and (row["type"] == "raw" or bool_value(row["review_required"]))
    ]
    return {
        "documents": len(rows),
        "by_category": group_counts(rows, "category"),
        "by_layer": group_counts(rows, "layer"),
        "by_status": group_counts(rows, "status"),
        "missing_source_count": len(missing_source),
        "formal_missing_source_count": len(formal_missing_source),
        "missing_formal_review_count": len(missing_review),
        "stale_active_count": len(stale_rows),
        "low_confidence_rules_count": len(low_conf_rules),
        "raw_in_formal_layer_count": len(raw_in_formal),
        "missing_source": missing_source[:limit],
        "formal_missing_source": formal_missing_source[:limit],
        "missing_formal_review": missing_review[:limit],
        "stale_active": stale_rows[:limit],
        "raw_in_formal_layer": raw_in_formal[:limit],
    }
