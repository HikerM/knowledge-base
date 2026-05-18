"""Frontmatter parsing, rendering, and schema metadata."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


STATUS_VALUES = {"active", "experimental", "deprecated", "rejected"}
CONFIDENCE_VALUES = {"high", "medium", "low"}
SOURCE_TYPE_VALUES = {"official", "github", "paper", "blog", "forum", "video", "internal_practice", "unknown"}
RISK_LEVEL_VALUES = {"low", "medium", "high"}
REQUIRED_SCHEMA_FIELDS = [
    "title",
    "category",
    "type",
    "status",
    "confidence",
    "source_type",
    "source_url",
    "created_at",
    "last_reviewed",
    "reviewed_by",
    "valid_for",
    "not_valid_for",
    "project_scope",
    "supersedes",
    "superseded_by",
    "risk_level",
    "verification_method",
    "review_required",
]
FORMAL_REQUIRED_FIELDS = ["reviewed_by", "verification_method", "last_reviewed"]
GOVERNANCE_OPTIONAL_FIELDS = [
    "topic_id",
    "canonical_id",
    "source_hash",
    "content_hash",
    "deprecated_reason",
    "rejected_reason",
    "quarantined_reason",
    "review_cycle_days",
]


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str, bool]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, False

    end_index: Optional[int] = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
    if end_index is None:
        return {}, text, False

    frontmatter: Dict[str, Any] = {}
    for line in lines[1:end_index]:
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = parse_frontmatter_value(value.strip())
    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")
    return frontmatter, body, True


def parse_frontmatter_value(value: str) -> Any:
    if value == "":
        return ""
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"').strip("'") for item in inner.split(",")]
    return value.strip().strip('"').strip("'")


def frontmatter_text(meta: Dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            rendered = "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in value) + "]"
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        elif value is None:
            rendered = '""'
        else:
            rendered = str(value)
            if rendered == "":
                rendered = '""'
            elif any(ch in rendered for ch in [":", "#", "[", "]"]) or rendered.strip() != rendered:
                rendered = json.dumps(rendered, ensure_ascii=False)
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def metadata_string(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def list_value(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None or value == "":
        return []
    raw = str(value).strip()
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in raw.split(",") if item.strip()]

