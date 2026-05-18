"""Knowledge lifecycle operations for raw, distilled, and formal cards."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .config import category_path, ensure_list_text, load_extract_rules
from .frontmatter import frontmatter_text, parse_frontmatter
from .markdown import SEARCHABLE_EXTENSIONS, first_heading, read_single_markdown, sha256_text, write_markdown_parts
from .paths import FORMAL_LAYERS, infer_category_layer, resolve_user_path, slugify, to_relative_posix, unique_path


class LifecycleError(ValueError):
    """Raised for controlled lifecycle command failures."""


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def today_iso() -> str:
    return datetime.now().date().isoformat()


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def build_new_card_content(
    title: str,
    category: str,
    card_type: str,
    status: str,
    source_url: str = "",
    source_type: str = "unknown",
) -> str:
    meta = {
        "title": title,
        "category": category,
        "type": card_type,
        "status": status,
        "confidence": "medium",
        "source_type": source_type,
        "source_url": source_url,
        "created_at": now_iso(),
        "last_reviewed": "",
        "reviewed_by": "",
        "valid_for": [],
        "not_valid_for": [],
        "project_scope": "",
        "topic_id": "",
        "canonical_id": "",
        "source_hash": sha256_text(source_url.strip().lower()) if source_url.strip() else "",
        "content_hash": "",
        "supersedes": [],
        "superseded_by": "",
        "deprecated_reason": "",
        "rejected_reason": "",
        "quarantined_reason": "",
        "risk_level": "medium",
        "verification_method": "",
        "review_required": True,
        "review_cycle_days": "",
    }
    body = f"""# 一句话结论

{title}

## 适用场景

- 说明这条知识适用的项目、技术栈、规模和约束。

## 不适用场景

- 说明不应套用的边界条件和风险。

## 背景

记录来源背景、问题上下文，以及为什么值得沉淀。

## 核心要点

- 待提炼。

## 推荐做法

写出可落地的做法、实现顺序和注意事项。

## 反例

记录常见误用、过度抽象或错误实践。

## 对我的项目有什么影响

说明它如何影响架构、代码、测试、性能、安全、UI 或 Agent 工作流。

## 可执行规则

- distilled 阶段的内容仍需人工审核，不能直接作为正式规则。

## 可给 Codex / Agent 使用的指令

审核通过前，不要把本卡片作为 Codex/Agent 的正式指导。

## 验证方式

- 需要补充测试、benchmark、官方来源或项目复盘证据。

## 来源与备注

- source_url: {source_url}
- source_type: {source_type}
- reviewer:
"""
    return frontmatter_text(meta) + body


def build_raw_note_content(category: str, title: str, source_url: str, text: str) -> str:
    meta = {
        "title": title,
        "category": category,
        "type": "raw",
        "status": "experimental",
        "confidence": "low",
        "source_type": "unknown",
        "source_url": source_url,
        "created_at": now_iso(),
        "last_reviewed": "",
        "reviewed_by": "",
        "valid_for": [],
        "not_valid_for": [],
        "project_scope": "",
        "topic_id": "",
        "canonical_id": "",
        "source_hash": sha256_text(source_url.strip().lower()) if source_url.strip() else "",
        "content_hash": "",
        "supersedes": [],
        "superseded_by": "",
        "deprecated_reason": "",
        "rejected_reason": "",
        "quarantined_reason": "",
        "risk_level": "medium",
        "verification_method": "",
        "review_required": True,
        "review_cycle_days": "",
    }
    body = f"""# 原始摘录

raw 只能作为参考，不得直接作为 Codex/Agent 的正式规则。

## 来源

- source_url: {source_url}
- captured_at: {now_iso()}

## 原文摘录或摘要

{text or "待补充。"}

## 我的初步理解

记录这条资料可能有价值的原因、疑问和可验证方向。

## 适用场景

记录它可能适用的技术栈、项目阶段和前置条件。

## 风险与待验证

- 来源权威性是否足够:
- 是否过期:
- 是否和现有规则冲突:
- 需要验证的实验或文档:

## 下一步处理

- 是否值得提炼到 distilled:
- 需要补充的来源:
- 需要人工审核的人或标准:

## 审核信息

- status: experimental
- confidence: low
- last_reviewed:
- reviewer:
"""
    return frontmatter_text(meta) + body


def new_card(title: str, category: str, card_type: str, status: str, source_url: str = "") -> Dict[str, Any]:
    start = time.perf_counter()
    target_dir = category_path(category) / "distilled"
    filename = f"{slugify(title)}.md"
    output_path = unique_path(target_dir, filename)
    content = build_new_card_content(
        title=title,
        category=category,
        card_type=card_type,
        status=status,
        source_url=source_url,
    )
    output_path.write_text(content, encoding="utf-8", newline="\n")
    return {
        "created": to_relative_posix(output_path),
        "layer": "distilled",
        "status": status,
        "elapsed_ms": elapsed_ms(start),
    }


def add_raw(category: str, title: str, source_url: str = "", text: str = "") -> Dict[str, Any]:
    start = time.perf_counter()
    target_dir = category_path(category) / "raw"
    filename = f"{slugify(title, fallback='raw-note')}.md"
    output_path = unique_path(target_dir, filename)
    content = build_raw_note_content(
        category=category,
        title=title,
        source_url=source_url,
        text=text,
    )
    output_path.write_text(content, encoding="utf-8", newline="\n")
    return {
        "created": to_relative_posix(output_path),
        "layer": "raw",
        "status": "experimental",
        "note": "raw 只能作为参考，不能作为正式规则。",
        "elapsed_ms": elapsed_ms(start),
    }


def promote(
    path_text: str,
    target_layer: str,
    reviewed_by: str,
    confidence: str,
    valid_for: str,
    verification_method: str,
    review_note: str,
) -> Dict[str, Any]:
    start = time.perf_counter()
    missing_review_inputs = [
        name
        for name, value in {
            "reviewed_by": reviewed_by,
            "confidence": confidence,
            "valid_for": valid_for,
            "verification_method": verification_method,
            "review_note": review_note,
        }.items()
        if not str(value or "").strip()
    ]
    if missing_review_inputs:
        raise LifecycleError(
            "promote is a manual review action. Missing required review fields: " + ", ".join(missing_review_inputs)
        )

    source_path = resolve_user_path(path_text)
    if not source_path.exists():
        raise LifecycleError(f"File not found: {source_path}")
    if source_path.suffix.lower() not in SEARCHABLE_EXTENSIONS:
        raise LifecycleError("promote only supports Markdown files")

    text = read_single_markdown(source_path)
    frontmatter, body, has_frontmatter = parse_frontmatter(text)
    if not has_frontmatter:
        raise LifecycleError("Source file has no frontmatter; cannot promote safely")

    category, layer = infer_category_layer(source_path)
    if layer != "distilled":
        raise LifecycleError("promote requires a source file from distilled/")
    if target_layer not in FORMAL_LAYERS:
        raise LifecycleError("target-layer must be one of rules, snippets, checklists")

    source_type = str(frontmatter.get("source_type") or "unknown")
    source_url = str(frontmatter.get("source_url") or "").strip()
    if not source_url and source_type != "internal_practice":
        raise LifecycleError(
            "promote requires source_url for formal knowledge. "
            "Only source_type=internal_practice may omit source_url, and it still requires reviewed_by, "
            "confidence, valid_for, verification_method, and review_note."
        )

    title = str(frontmatter.get("title") or first_heading(body) or source_path.stem)
    target_type = {"rules": "rule", "snippets": "snippet", "checklists": "checklist"}[target_layer]
    promoted_meta: Dict[str, Any] = {
        **frontmatter,
        "title": title,
        "category": str(frontmatter.get("category") or category),
        "type": target_type,
        "status": "active",
        "confidence": confidence,
        "source_type": source_type,
        "source_url": source_url,
        "created_at": str(frontmatter.get("created_at") or now_iso()),
        "last_reviewed": today_iso(),
        "reviewed_by": reviewed_by,
        "reviewed_at": now_iso(),
        "valid_for": split_csv(valid_for),
        "verification_method": verification_method,
        "review_required": False,
        "review_note": review_note,
        "promoted_from": to_relative_posix(source_path),
    }
    promoted_meta.setdefault("valid_for", [])
    promoted_meta.setdefault("not_valid_for", frontmatter.get("not_valid_for") or [])
    promoted_meta.setdefault("project_scope", frontmatter.get("project_scope") or "")
    promoted_meta.setdefault("supersedes", [])
    promoted_meta.setdefault("superseded_by", "")
    promoted_meta.setdefault("risk_level", frontmatter.get("risk_level") or "medium")

    target_dir = category_path(str(promoted_meta["category"])) / target_layer
    output_path = unique_path(target_dir, f"{slugify(title, fallback=target_type)}.md")
    output_path.write_text(frontmatter_text(promoted_meta) + body, encoding="utf-8", newline="\n")

    return {
        "promoted": to_relative_posix(output_path),
        "promoted_from": to_relative_posix(source_path),
        "message": "已审核知识已提升。建议运行: python scripts/kb.py index",
        "elapsed_ms": elapsed_ms(start),
    }


def move_to_layer(path: Path, target_layer: str) -> Path:
    category, _ = infer_category_layer(path)
    if category == "unknown":
        raise LifecycleError("Can only move Markdown files under knowledge/<category>/<layer>/")
    target_dir = category_path(category) / target_layer
    target_path = unique_path(target_dir, path.name)
    path.rename(target_path)
    return target_path


def deprecate(path: Path, reason: str, superseded_by: str, reviewed_by: str) -> Dict[str, Any]:
    start = time.perf_counter()
    if not path.exists():
        raise LifecycleError(f"File not found: {path}")
    frontmatter, body, has_frontmatter = parse_frontmatter(read_single_markdown(path))
    if not has_frontmatter:
        raise LifecycleError("Cannot deprecate a file without frontmatter")
    category, _ = infer_category_layer(path)
    if category == "unknown":
        raise LifecycleError("Can only deprecate files under knowledge/")
    frontmatter.update(
        {
            "status": "deprecated",
            "review_required": False,
            "last_reviewed": today_iso(),
            "reviewed_at": now_iso(),
            "reviewed_by": reviewed_by,
            "deprecation_reason": reason,
            "deprecated_reason": reason,
        }
    )
    if superseded_by:
        frontmatter["superseded_by"] = superseded_by
    write_markdown_parts(path, frontmatter, body)
    new_path = move_to_layer(path, "deprecated") if infer_category_layer(path)[1] != "deprecated" else path
    return {
        "deprecated": to_relative_posix(new_path),
        "reason": reason,
        "superseded_by": superseded_by or "",
        "message": "规则已标记为 deprecated。建议运行: python scripts/kb.py index",
        "elapsed_ms": elapsed_ms(start),
    }


def quarantine(path: Path, reason: str) -> Dict[str, Any]:
    start = time.perf_counter()
    if not path.exists():
        raise LifecycleError(f"File not found: {path}")
    frontmatter, body, has_frontmatter = parse_frontmatter(read_single_markdown(path))
    if not has_frontmatter:
        raise LifecycleError("Cannot quarantine a file without frontmatter")
    category, _ = infer_category_layer(path)
    if category == "unknown":
        raise LifecycleError("Can only quarantine files under knowledge/")
    frontmatter.update(
        {
            "status": "experimental" if frontmatter.get("status") != "rejected" else "rejected",
            "review_required": True,
            "risk_level": "high",
            "quarantine_reason": reason,
            "quarantined_reason": reason,
            "last_reviewed": today_iso(),
        }
    )
    write_markdown_parts(path, frontmatter, body)
    new_path = move_to_layer(path, "quarantine") if infer_category_layer(path)[1] != "quarantine" else path
    return {
        "quarantined": to_relative_posix(new_path),
        "reason": reason,
        "message": "内容已隔离到 quarantine。建议运行: python scripts/kb.py index",
        "elapsed_ms": elapsed_ms(start),
    }


def classify_distill_targets(body: str) -> List[str]:
    text = body.lower()
    scored = {
        "changelog": 0,
        "pitfall": 0,
        "checklist": 0,
        "snippet": 0,
        "rule": 0,
    }
    if any(term in text for term in ["breaking", "release", "changelog", "migration", "deprecated", "version", "upgrade"]):
        scored["changelog"] += 3
    if any(term in text for term in ["pitfall", "avoid", "risk", "bug", "error", "failure", "vulnerability", "xss", "injection", "不要", "禁止", "风险"]):
        scored["pitfall"] += 3
    if any(term in text for term in ["checklist", "verify", "review", "audit", "上线", "检查", "验收"]):
        scored["checklist"] += 3
    if "```" in body or any(term in text for term in ["npm ", "pip ", "curl ", "select ", "function ", "class ", "const ", "def "]):
        scored["snippet"] += 3
    if any(term in text for term in ["best practice", "should", "must", "recommend", "必须", "应该", "推荐", "默认"]):
        scored["rule"] += 2
    scored["rule"] += 1
    ordered = sorted(scored.items(), key=lambda item: item[1], reverse=True)
    return [name for name, score in ordered if score > 0][:3]


def distill_plan(path_text: str) -> Dict[str, Any]:
    start = time.perf_counter()
    path = resolve_user_path(path_text)
    if not path.exists():
        raise LifecycleError(f"File not found: {path}")
    category, layer = infer_category_layer(path)
    if layer != "raw":
        raise LifecycleError("distill-plan only accepts a single file from raw/")
    text = read_single_markdown(path)
    frontmatter, body, has_frontmatter = parse_frontmatter(text)
    if not has_frontmatter:
        raise LifecycleError("Raw file has no frontmatter; cannot build a reliable distill plan")
    extract_rules = load_extract_rules()
    targets = classify_distill_targets(body)
    plan_items = []
    for target in targets:
        rule_key = "best_practice" if target == "rule" else target
        rule = extract_rules.get(rule_key, {})
        plan_items.append(
            {
                "target_type": target,
                "extract_rule": rule_key,
                "required_fields": ensure_list_text(rule.get("required_fields")),
                "output_layer": rule.get("output_layer", "distilled"),
                "reason": "Heuristic match from raw content and category context.",
            }
        )
    return {
        "path": to_relative_posix(path),
        "title": frontmatter.get("title", path.stem),
        "category": category,
        "source_url": frontmatter.get("source_url", ""),
        "recommended_targets": targets,
        "plan": plan_items,
        "human_review_required": True,
        "warning": "distill-plan 只读取指定 raw 文件，只能生成提炼计划，不会写入 rules；提炼结果仍需人工审核。",
        "elapsed_ms": elapsed_ms(start),
    }
