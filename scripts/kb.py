#!/usr/bin/env python3
"""Markdown-first personal knowledge base CLI.

The knowledge source is Markdown under knowledge/. SQLite is only an index.
Search commands must use SQLite FTS5 and must not scan Markdown files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
CONFIG_DIR = ROOT / "config"
TEMPLATES_DIR = ROOT / "templates"
REPORTS_DIR = ROOT / "reports"
KB_DIR = ROOT / ".kb"
DB_PATH = KB_DIR / "index.sqlite"

LAYERS = ["raw", "distilled", "rules", "snippets", "checklists", "deprecated", "rejected", "quarantine"]
FORMAL_LAYERS = {"rules", "snippets", "checklists"}
DEFAULT_SEARCH_LAYERS = {"rules", "checklists", "snippets"}
EXPLORATORY_LAYERS = {"raw", "distilled"}
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
SEARCHABLE_EXTENSIONS = {".md", ".markdown"}
MAX_SNIPPET_CHARS = 500
DEFAULT_TOP_K = 10
MAX_TOP_K = 50
CHUNK_TARGET_CHARS = 1200
CHUNK_HARD_MAX_CHARS = 1500

DEFAULT_CATEGORIES: Dict[str, Dict[str, str]] = {
    "frontend": {
        "path": "knowledge/01-frontend",
        "description": "前端、组件、状态管理、响应式、构建、测试、可访问性",
    },
    "backend": {
        "path": "knowledge/02-backend",
        "description": "API、服务分层、鉴权、权限、日志、缓存、队列、部署",
    },
    "ui_ux": {
        "path": "knowledge/03-ui-ux",
        "description": "自适应 UI、设计系统、组件状态、Unity UI、Dashboard、游戏 UI",
    },
    "product": {
        "path": "knowledge/04-product",
        "description": "PRD、MVP、用户路径、功能优先级、指标、竞品分析",
    },
    "algorithm": {
        "path": "knowledge/05-algorithm",
        "description": "算法、数据结构、复杂度、搜索、图、动态规划、推荐、游戏 AI",
    },
    "database": {
        "path": "knowledge/06-database",
        "description": "数据建模、索引、事务、迁移、查询优化、缓存一致性",
    },
    "performance": {
        "path": "knowledge/07-performance",
        "description": "Web、后端、数据库、Unity、网络、内存、渲染、压测、Profiling",
    },
    "security": {
        "path": "knowledge/08-security",
        "description": "鉴权、授权、输入校验、XSS、SQL 注入、依赖漏洞、密钥管理",
    },
    "ai_agent": {
        "path": "knowledge/09-ai-agent",
        "description": "Codex、Skill、AGENTS.md、RAG、工具调用、上下文管理、Agent 工作流",
    },
}

DEFAULT_CONFIG_FILES = {
    "config/categories.yaml": """frontend:
  path: knowledge/01-frontend
  description: 前端、组件、状态管理、响应式、构建、测试、可访问性

backend:
  path: knowledge/02-backend
  description: API、服务分层、鉴权、权限、日志、缓存、队列、部署

ui_ux:
  path: knowledge/03-ui-ux
  description: 自适应 UI、设计系统、组件状态、Unity UI、Dashboard、游戏 UI

product:
  path: knowledge/04-product
  description: PRD、MVP、用户路径、功能优先级、指标、竞品分析

algorithm:
  path: knowledge/05-algorithm
  description: 算法、数据结构、复杂度、搜索、图、动态规划、推荐、游戏 AI

database:
  path: knowledge/06-database
  description: 数据建模、索引、事务、迁移、查询优化、缓存一致性

performance:
  path: knowledge/07-performance
  description: Web、后端、数据库、Unity、网络、内存、渲染、压测、Profiling

security:
  path: knowledge/08-security
  description: 鉴权、授权、输入校验、XSS、SQL 注入、依赖漏洞、密钥管理

ai_agent:
  path: knowledge/09-ai-agent
  description: Codex、Skill、AGENTS.md、RAG、工具调用、上下文管理、Agent 工作流
""",
    "config/quality-rules.yaml": """score_dimensions:
  - source_authority
  - recency
  - relevance_to_my_projects
  - actionability
  - implementation_detail
  - risk_level
  - verification_needed

policy:
  - raw 不得直接作为 Codex 的正式规则。
  - distilled 是 AI 提炼层，仍需人工审核。
  - rules、snippets、checklists 才是正式可执行知识。
  - 不允许存储真实密钥、密码、token、客户隐私数据。
""",
    "config/sources.yaml": """sources:
  - name: OpenAI Codex Docs
    category: ai_agent
    type: official_docs
    url: https://developers.openai.com/codex
    priority: high
    enabled: true
    learn_focus:
      - Codex workflow
      - project instructions
      - agent usage
    output_targets:
      - rules
      - templates
      - checklists
    notes: Codex、Skill、AGENTS.md、Agent 工作流相关官方文档。
""",
    "config/learning-radar.yaml": """ai_agent:
  learning_goal: 沉淀 Codex、Skill、AGENTS.md、RAG、工具调用、上下文管理和 Agent 工作流规则。
  frequency: weekly
  focus:
    - Codex workflow
    - agent instructions
    - tool use
  ignore:
    - prompt hacks without reproducible workflow
  preferred_outputs:
    - rules
    - templates
    - checklists
""",
    "config/extract-rules.yaml": """best_practice:
  description: 从外部内容提炼可执行工程规则。
  required_fields:
    - title
    - source_url
    - applicable_context
    - recommended_practice
    - verification_method
    - review_required
  output_layer: distilled
""",
}

DEFAULT_TEMPLATE_FILES = {
    "templates/knowledge-card.md": """---
title: ""
category: ""
type: rule
status: experimental
confidence: medium
source_type: ""
source_url: ""
created_at: ""
last_reviewed: ""
reviewed_by: ""
valid_for: []
not_valid_for: []
project_scope: ""
supersedes: []
superseded_by: ""
risk_level: medium
verification_method: ""
review_required: true
---

# 一句话结论

## 适用场景

## 不适用场景

## 背景

## 核心要点

## 推荐做法

## 反例

## 对我的项目有什么影响

## 可执行规则

## 可给 Codex / Agent 使用的指令

## 验证方式

## 来源与备注
""",
    "templates/raw-note.md": """---
title: ""
category: ""
type: raw
status: experimental
confidence: low
source_type: ""
source_url: ""
created_at: ""
last_reviewed: ""
reviewed_by: ""
valid_for: []
not_valid_for: []
project_scope: ""
supersedes: []
superseded_by: ""
risk_level: medium
verification_method: ""
review_required: true
---

# 原始摘录

raw 只能作为参考，不得直接作为正式规则。

## 来源

## 原文摘录或摘要

## 我的初步理解

## 适用场景

## 风险与待验证

## 审核信息
""",
}


class KBError(Exception):
    """Controlled CLI error."""


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def today_iso() -> str:
    return datetime.now().date().isoformat()


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def die(message: str, code: int = 1) -> None:
    raise KBError(message)


def load_categories() -> Dict[str, Dict[str, str]]:
    path = CONFIG_DIR / "categories.yaml"
    if not path.exists():
        return DEFAULT_CATEGORIES

    categories: Dict[str, Dict[str, str]] = {}
    current: Optional[str] = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current = line[:-1].strip()
            categories[current] = {}
            continue
        if current and line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            categories[current][key.strip()] = value.strip().strip('"').strip("'")
    return categories or DEFAULT_CATEGORIES


def parse_config_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        return parse_frontmatter_value(value)
    return value.strip().strip('"').strip("'")


def load_sources_config() -> List[Dict[str, Any]]:
    path = CONFIG_DIR / "sources.yaml"
    if not path.exists():
        return []
    sources: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    pending_key: Optional[str] = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if stripped == "sources:":
            continue
        if indent == 2 and stripped.startswith("- "):
            if current:
                sources.append(current)
            current = {}
            pending_key = None
            rest = stripped[2:].strip()
            if ":" in rest:
                key, value = rest.split(":", 1)
                current[key.strip()] = parse_config_scalar(value)
            continue
        if current is None:
            continue
        if indent >= 4 and stripped.startswith("- ") and pending_key:
            current.setdefault(pending_key, [])
            if not isinstance(current[pending_key], list):
                current[pending_key] = [current[pending_key]]
            current[pending_key].append(parse_config_scalar(stripped[2:]))
            continue
        if indent >= 4 and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                current[key] = []
                pending_key = key
            else:
                current[key] = parse_config_scalar(value)
                pending_key = None
    if current:
        sources.append(current)
    return sources


def load_mapping_config(filename: str) -> Dict[str, Dict[str, Any]]:
    path = CONFIG_DIR / filename
    if not path.exists():
        return {}
    result: Dict[str, Dict[str, Any]] = {}
    current_key: Optional[str] = None
    pending_key: Optional[str] = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if indent == 0 and stripped.endswith(":"):
            current_key = stripped[:-1].strip()
            result[current_key] = {}
            pending_key = None
            continue
        if current_key is None:
            continue
        if indent >= 4 and stripped.startswith("- ") and pending_key:
            result[current_key].setdefault(pending_key, [])
            result[current_key][pending_key].append(parse_config_scalar(stripped[2:]))
            continue
        if indent >= 2 and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                result[current_key][key] = []
                pending_key = key
            else:
                result[current_key][key] = parse_config_scalar(value)
                pending_key = None
    return result


def load_learning_radar() -> Dict[str, Dict[str, Any]]:
    return load_mapping_config("learning-radar.yaml")


def load_extract_rules() -> Dict[str, Dict[str, Any]]:
    return load_mapping_config("extract-rules.yaml")


def ensure_list_text(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None or value == "":
        return []
    return [str(value)]


def category_choices() -> List[str]:
    return sorted(load_categories().keys())


def category_path(category: str) -> Path:
    categories = load_categories()
    if category not in categories:
        die(f"Unknown category: {category}. Valid: {', '.join(sorted(categories))}")
    return ROOT / categories[category]["path"]


def ensure_directories() -> None:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for meta in load_categories().values():
        base = ROOT / meta["path"]
        for layer in LAYERS:
            (base / layer).mkdir(parents=True, exist_ok=True)


def write_if_missing(relative_path: str, content: str) -> bool:
    path = ROOT / relative_path
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def slugify(value: str, fallback: str = "knowledge-card") -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    ascii_slug = value.encode("ascii", "ignore").decode("ascii").strip("-")
    if ascii_slug:
        return ascii_slug[:80]
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10] if value else datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{fallback}-{digest}"


def unique_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = directory / filename
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate


def to_relative_posix(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def resolve_user_path(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_single_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def first_heading(body: str) -> Optional[str]:
    for line in body.splitlines():
        match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return None


def infer_category_layer(path: Path) -> Tuple[str, str]:
    rel_parts = path.resolve().relative_to(ROOT.resolve()).parts
    if len(rel_parts) < 4 or rel_parts[0] != "knowledge":
        return "unknown", "unknown"

    category_dir = f"knowledge/{rel_parts[1]}"
    layer = rel_parts[2]
    for category, meta in load_categories().items():
        if Path(meta["path"]).as_posix() == category_dir.replace("\\", "/"):
            return category, layer
    return "unknown", layer


def normalize_document_meta(path: Path, frontmatter: Dict[str, Any], body: str) -> Dict[str, Any]:
    category, layer = infer_category_layer(path)
    title = str(frontmatter.get("title") or first_heading(body) or path.stem)
    status_default = "experimental"
    if layer == "deprecated":
        status_default = "deprecated"
    elif layer == "rejected":
        status_default = "rejected"
    return {
        "path": to_relative_posix(path),
        "title": title,
        "category": str(frontmatter.get("category") or category),
        "layer": layer,
        "type": str(frontmatter.get("type") or ("raw" if layer == "raw" else "note")),
        "status": str(frontmatter.get("status") or status_default),
        "confidence": str(frontmatter.get("confidence") or "medium"),
        "source_type": str(frontmatter.get("source_type") or "unknown"),
        "source_url": str(frontmatter.get("source_url") or ""),
        "created_at": str(frontmatter.get("created_at") or ""),
        "last_reviewed": str(frontmatter.get("last_reviewed") or ""),
        "reviewed_by": str(frontmatter.get("reviewed_by") or ""),
        "reviewed_at": str(frontmatter.get("reviewed_at") or ""),
        "valid_for": metadata_string(frontmatter.get("valid_for") or []),
        "not_valid_for": metadata_string(frontmatter.get("not_valid_for") or []),
        "project_scope": str(frontmatter.get("project_scope") or ""),
        "supersedes": metadata_string(frontmatter.get("supersedes") or []),
        "superseded_by": str(frontmatter.get("superseded_by") or ""),
        "risk_level": str(frontmatter.get("risk_level") or "medium"),
        "verification_method": str(frontmatter.get("verification_method") or ""),
        "review_required": metadata_string(frontmatter.get("review_required") if "review_required" in frontmatter else layer not in FORMAL_LAYERS),
        "promoted_from": str(frontmatter.get("promoted_from") or ""),
        "deprecation_reason": str(frontmatter.get("deprecation_reason") or ""),
        "rejection_reason": str(frontmatter.get("rejection_reason") or ""),
        "quarantine_reason": str(frontmatter.get("quarantine_reason") or ""),
        "review_note": str(frontmatter.get("review_note") or ""),
        "review_cycle_days": str(frontmatter.get("review_cycle_days") or ""),
    }


def split_long_text(text: str, target: int = CHUNK_TARGET_CHARS) -> List[str]:
    text = text.strip()
    if len(text) <= CHUNK_HARD_MAX_CHARS:
        return [text] if text else []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    paragraphs = re.split(r"(\n\s*\n)", text)
    for part in paragraphs:
        if not part:
            continue
        if len(part) > CHUNK_HARD_MAX_CHARS:
            if current:
                chunks.append("".join(current).strip())
                current, current_len = [], 0
            for idx in range(0, len(part), target):
                segment = part[idx : idx + target].strip()
                if segment:
                    chunks.append(segment)
            continue
        if current_len + len(part) > target and current:
            chunks.append("".join(current).strip())
            current, current_len = [], 0
        current.append(part)
        current_len += len(part)
    if current:
        chunks.append("".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def chunk_markdown(body: str, title: str) -> List[Dict[str, Any]]:
    sections: List[Tuple[str, str]] = []
    current_heading = title
    current_lines: List[str] = []

    def flush() -> None:
        nonlocal current_lines
        text = "\n".join(current_lines).strip()
        if text:
            sections.append((current_heading, text))
        current_lines = []

    for line in body.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush()
            current_heading = match.group(2).strip()
            current_lines.append(line)
        else:
            current_lines.append(line)
    flush()

    if not sections:
        sections = [(title, body.strip() or title)]

    chunks: List[Dict[str, Any]] = []
    index = 0
    for heading, section_text in sections:
        for part in split_long_text(section_text):
            chunks.append(
                {
                    "chunk_index": index,
                    "heading": heading,
                    "content": part,
                    "token_estimate": max(1, len(part) // 4),
                }
            )
            index += 1
    return chunks


def connect_db(must_exist: bool = False) -> sqlite3.Connection:
    if must_exist and not DB_PATH.exists():
        die("index.sqlite does not exist. Run: python scripts/kb.py index")
    KB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def check_fts5(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("CREATE VIRTUAL TABLE temp.fts5_check USING fts5(content)")
        conn.execute("DROP TABLE temp.fts5_check")
    except sqlite3.Error as exc:
        die(f"SQLite FTS5 is not available: {exc}")


def ensure_schema(conn: sqlite3.Connection) -> None:
    check_fts5(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
          id INTEGER PRIMARY KEY,
          path TEXT UNIQUE NOT NULL,
          title TEXT,
          category TEXT NOT NULL,
          layer TEXT NOT NULL,
          type TEXT,
          status TEXT,
          confidence TEXT,
          source_type TEXT,
          source_url TEXT,
          created_at TEXT,
          last_reviewed TEXT,
          reviewed_by TEXT,
          reviewed_at TEXT,
          valid_for TEXT,
          not_valid_for TEXT,
          project_scope TEXT,
          supersedes TEXT,
          superseded_by TEXT,
          risk_level TEXT,
          verification_method TEXT,
          review_required TEXT,
          promoted_from TEXT,
          deprecation_reason TEXT,
          rejection_reason TEXT,
          quarantine_reason TEXT,
          review_note TEXT,
          review_cycle_days TEXT,
          mtime REAL NOT NULL,
          size INTEGER NOT NULL,
          sha256 TEXT NOT NULL,
          indexed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chunks (
          id INTEGER PRIMARY KEY,
          document_id INTEGER NOT NULL,
          chunk_index INTEGER NOT NULL,
          heading TEXT,
          content TEXT NOT NULL,
          token_estimate INTEGER,
          FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
          document_id UNINDEXED,
          chunk_id UNINDEXED,
          title,
          heading,
          content
        );

        CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
        CREATE INDEX IF NOT EXISTS idx_documents_layer ON documents(layer);
        CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
        CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(type);
        CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
        CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
        """
    )
    ensure_document_columns(conn)


def ensure_document_columns(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
    columns = {
        "reviewed_by": "TEXT",
        "valid_for": "TEXT",
        "not_valid_for": "TEXT",
        "project_scope": "TEXT",
        "supersedes": "TEXT",
        "risk_level": "TEXT",
        "verification_method": "TEXT",
        "review_required": "TEXT",
        "deprecation_reason": "TEXT",
        "rejection_reason": "TEXT",
        "quarantine_reason": "TEXT",
        "review_note": "TEXT",
        "review_cycle_days": "TEXT",
    }
    for name, column_type in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE documents ADD COLUMN {name} {column_type}")


def delete_document_by_id(conn: sqlite3.Connection, document_id: int) -> None:
    conn.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
    conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


def index_one_file(conn: sqlite3.Connection, path: Path, stat: os.stat_result, digest: str) -> str:
    rel_path = to_relative_posix(path)
    text = read_single_markdown(path)
    frontmatter, body, _ = parse_frontmatter(text)
    meta = normalize_document_meta(path, frontmatter, body)
    chunks = chunk_markdown(body, meta["title"])
    indexed_at = now_iso()

    existing = conn.execute("SELECT id FROM documents WHERE path = ?", (rel_path,)).fetchone()
    action = "indexed"
    if existing:
        delete_document_by_id(conn, int(existing["id"]))
        action = "updated"

    cur = conn.execute(
        """
        INSERT INTO documents (
          path, title, category, layer, type, status, confidence, source_type,
          source_url, created_at, last_reviewed, reviewed_by, reviewed_at,
          valid_for, not_valid_for, project_scope, supersedes, superseded_by,
          risk_level, verification_method, review_required, promoted_from,
          deprecation_reason, rejection_reason, quarantine_reason, review_note,
          review_cycle_days, mtime, size, sha256, indexed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rel_path,
            meta["title"],
            meta["category"],
            meta["layer"],
            meta["type"],
            meta["status"],
            meta["confidence"],
            meta["source_type"],
            meta["source_url"],
            meta["created_at"],
            meta["last_reviewed"],
            meta["reviewed_by"],
            meta["reviewed_at"],
            meta["valid_for"],
            meta["not_valid_for"],
            meta["project_scope"],
            meta["supersedes"],
            meta["superseded_by"],
            meta["risk_level"],
            meta["verification_method"],
            meta["review_required"],
            meta["promoted_from"],
            meta["deprecation_reason"],
            meta["rejection_reason"],
            meta["quarantine_reason"],
            meta["review_note"],
            meta["review_cycle_days"],
            stat.st_mtime,
            stat.st_size,
            digest,
            indexed_at,
        ),
    )
    document_id = int(cur.lastrowid)

    for chunk in chunks:
        chunk_cur = conn.execute(
            """
            INSERT INTO chunks (document_id, chunk_index, heading, content, token_estimate)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                document_id,
                chunk["chunk_index"],
                chunk["heading"],
                chunk["content"],
                chunk["token_estimate"],
            ),
        )
        chunk_id = int(chunk_cur.lastrowid)
        conn.execute(
            """
            INSERT INTO chunks_fts (document_id, chunk_id, title, heading, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, chunk_id, meta["title"], chunk["heading"], chunk["content"]),
        )
    return action


def iter_markdown_files() -> Iterable[Path]:
    if not KNOWLEDGE_DIR.exists():
        return []
    return (
        path
        for path in KNOWLEDGE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in SEARCHABLE_EXTENSIONS
    )


def perform_index(force_hash: bool = False) -> Dict[str, Any]:
    start = time.perf_counter()
    ensure_directories()
    conn = connect_db()
    ensure_schema(conn)

    indexed_rows = conn.execute("SELECT id, path, mtime, size, sha256 FROM documents").fetchall()
    indexed_by_path = {row["path"]: row for row in indexed_rows}
    current_paths = set()
    counts = {"indexed": 0, "updated": 0, "deleted": 0, "skipped": 0, "hashed": 0}

    with conn:
        for path in iter_markdown_files():
            rel_path = to_relative_posix(path)
            current_paths.add(rel_path)
            stat = path.stat()
            existing = indexed_by_path.get(rel_path)
            if (
                existing
                and float(existing["mtime"]) == float(stat.st_mtime)
                and int(existing["size"]) == int(stat.st_size)
                and not force_hash
            ):
                counts["skipped"] += 1
                continue
            digest = sha256_file(path)
            counts["hashed"] += 1
            action = index_one_file(conn, path, stat, digest)
            counts[action] += 1

        for rel_path, row in indexed_by_path.items():
            if rel_path not in current_paths:
                delete_document_by_id(conn, int(row["id"]))
                counts["deleted"] += 1

    counts["elapsed_ms"] = elapsed_ms(start)
    return counts


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
        "supersedes": [],
        "superseded_by": "",
        "risk_level": "medium",
        "verification_method": "",
        "review_required": True,
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
        "supersedes": [],
        "superseded_by": "",
        "risk_level": "medium",
        "verification_method": "",
        "review_required": True,
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


def command_init(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    ensure_directories()
    created_files: List[str] = []
    for rel_path, content in {**DEFAULT_CONFIG_FILES, **DEFAULT_TEMPLATE_FILES}.items():
        if write_if_missing(rel_path, content):
            created_files.append(rel_path)
    result = {
        "status": "ok",
        "root": str(ROOT),
        "created_files": created_files,
        "elapsed_ms": elapsed_ms(start),
    }
    print_json(result)


def command_new_card(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    target_dir = category_path(args.category) / "distilled"
    filename = f"{slugify(args.title)}.md"
    output_path = unique_path(target_dir, filename)
    content = build_new_card_content(
        title=args.title,
        category=args.category,
        card_type=args.type,
        status=args.status,
        source_url=args.source_url or "",
    )
    output_path.write_text(content, encoding="utf-8", newline="\n")
    print_json(
        {
            "created": to_relative_posix(output_path),
            "layer": "distilled",
            "status": args.status,
            "elapsed_ms": elapsed_ms(start),
        }
    )


def command_add_raw(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    target_dir = category_path(args.category) / "raw"
    filename = f"{slugify(args.title, fallback='raw-note')}.md"
    output_path = unique_path(target_dir, filename)
    content = build_raw_note_content(
        category=args.category,
        title=args.title,
        source_url=args.source_url or "",
        text=args.text or "",
    )
    output_path.write_text(content, encoding="utf-8", newline="\n")
    print_json(
        {
            "created": to_relative_posix(output_path),
            "layer": "raw",
            "status": "experimental",
            "note": "raw 只能作为参考，不能作为正式规则。",
            "elapsed_ms": elapsed_ms(start),
        }
    )


def command_promote(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    missing_review_inputs = [
        name
        for name in ["reviewed_by", "confidence", "valid_for", "verification_method", "review_note"]
        if not str(getattr(args, name, "") or "").strip()
    ]
    if missing_review_inputs:
        die("promote is a manual review action. Missing required review fields: " + ", ".join(missing_review_inputs))
    source_path = resolve_user_path(args.path)
    if not source_path.exists():
        die(f"File not found: {source_path}")
    if source_path.suffix.lower() not in SEARCHABLE_EXTENSIONS:
        die("promote only supports Markdown files")

    text = read_single_markdown(source_path)
    frontmatter, body, has_frontmatter = parse_frontmatter(text)
    if not has_frontmatter:
        die("Source file has no frontmatter; cannot promote safely")

    category, layer = infer_category_layer(source_path)
    if layer != "distilled":
        die("promote requires a source file from distilled/")
    if args.target_layer not in FORMAL_LAYERS:
        die("target-layer must be one of rules, snippets, checklists")

    source_type = str(frontmatter.get("source_type") or "unknown")
    source_url = str(frontmatter.get("source_url") or "").strip()
    if not source_url and source_type != "internal_practice":
        die(
            "promote requires source_url for formal knowledge. "
            "Only source_type=internal_practice may omit source_url, and it still requires reviewed_by, "
            "confidence, valid_for, verification_method, and review_note."
        )

    title = str(frontmatter.get("title") or first_heading(body) or source_path.stem)
    target_type = {"rules": "rule", "snippets": "snippet", "checklists": "checklist"}[args.target_layer]
    promoted_meta: Dict[str, Any] = {
        **frontmatter,
        "title": title,
        "category": str(frontmatter.get("category") or category),
        "type": target_type,
        "status": "active",
        "confidence": args.confidence,
        "source_type": source_type,
        "source_url": source_url,
        "created_at": str(frontmatter.get("created_at") or now_iso()),
        "last_reviewed": today_iso(),
        "reviewed_by": args.reviewed_by,
        "reviewed_at": now_iso(),
        "valid_for": split_csv(args.valid_for),
        "verification_method": args.verification_method,
        "review_required": False,
        "review_note": args.review_note,
        "promoted_from": to_relative_posix(source_path),
    }
    promoted_meta.setdefault("valid_for", [])
    promoted_meta.setdefault("not_valid_for", frontmatter.get("not_valid_for") or [])
    promoted_meta.setdefault("project_scope", frontmatter.get("project_scope") or "")
    promoted_meta.setdefault("supersedes", [])
    promoted_meta.setdefault("superseded_by", "")
    promoted_meta.setdefault("risk_level", frontmatter.get("risk_level") or "medium")

    target_dir = category_path(str(promoted_meta["category"])) / args.target_layer
    output_path = unique_path(target_dir, f"{slugify(title, fallback=target_type)}.md")
    output_path.write_text(frontmatter_text(promoted_meta) + body, encoding="utf-8", newline="\n")

    print_json(
        {
            "promoted": to_relative_posix(output_path),
            "promoted_from": to_relative_posix(source_path),
            "message": "已审核知识已提升。建议运行: python scripts/kb.py index",
            "elapsed_ms": elapsed_ms(start),
        }
    )


def command_index(args: argparse.Namespace) -> None:
    print_json(perform_index(force_hash=bool(getattr(args, "force_hash", False))))


def command_reindex(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    KB_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in ["", "-wal", "-shm"]:
        path = Path(str(DB_PATH) + suffix)
        if path.exists():
            path.unlink()
    result = perform_index()
    result["reindexed"] = True
    result["elapsed_ms"] = elapsed_ms(start)
    print_json(result)


def build_fts_query(query: str) -> str:
    tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
    if not tokens:
        die("Query contains no searchable tokens")
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

    score = 0.0
    score += layer_weight.get((row["layer"] or "").lower(), 0.0)
    score += status_weight.get((row["status"] or "").lower(), 0.0)
    score += source_weight.get((row["source_type"] or "").lower(), 0.0)
    score += confidence_weight.get((row["confidence"] or "").lower(), 0.0)

    title = (row["title"] or "").lower()
    heading = (row["heading"] or "").lower()
    content = (row["content"] or "").lower()
    for token in query_tokens:
        token_l = token.lower()
        if token_l in title:
            score += 3.0
        if token_l in heading:
            score += 1.5
        if token_l in content:
            score += 0.2

    reviewed = parse_date(str(row["last_reviewed"] or row["reviewed_at"] or ""))
    if reviewed:
        age_days = max(0, (datetime.now() - reviewed.replace(tzinfo=None)).days)
        if age_days <= 30:
            score += 1.0
        elif age_days <= 90:
            score += 0.6
        elif age_days <= 180:
            score += 0.2
    return score


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
        die("--top-k must be positive")
    if top_k > MAX_TOP_K and not force:
        die(f"--top-k max is {MAX_TOP_K}. Use --force to exceed it explicitly.")
    return top_k


def allowed_layers_for_search(args: argparse.Namespace, research: bool = False) -> List[str]:
    if research:
        if args.layer:
            return [args.layer]
        return sorted(EXPLORATORY_LAYERS)

    if args.layer:
        if args.layer == "raw" and not args.include_raw:
            die("search excludes raw by default. Use --include-raw explicitly, or use research.")
        if args.layer == "distilled" and not args.include_distilled:
            die("search excludes distilled by default. Use --include-distilled explicitly, or use research.")
        if args.layer == "deprecated" and not args.include_deprecated:
            die("search excludes deprecated by default. Use --include-deprecated explicitly.")
        if args.layer in {"rejected", "quarantine"}:
            die("search does not return rejected/quarantine content. Use list/open/audit for governance review.")
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
        die("Query contains no searchable tokens")

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
        results.append(
            {
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
        )
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
        ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)

    elapsed = elapsed_ms(start)
    results = []
    for score, row in ranked[:top_k]:
        results.append(
            {
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
        )
    return {
        "query": args.query,
        "top_k": top_k,
        "allowed_layers": allowed_layers,
        "elapsed_ms": elapsed,
        "results": results,
    }


def command_search(args: argparse.Namespace) -> None:
    print_json(run_search(args))


def command_open(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    path: Optional[Path] = None
    metadata: Dict[str, Any] = {}

    if args.id is not None:
        conn = connect_db(must_exist=True)
        row = conn.execute("SELECT id, path, title, category, layer FROM documents WHERE id = ?", (args.id,)).fetchone()
        if not row:
            die(f"No document with id={args.id}")
        path = ROOT / row["path"]
        metadata = dict(row)
    elif args.path:
        path = resolve_user_path(args.path)
        metadata = {"path": to_relative_posix(path) if path.exists() else args.path}
    else:
        die("open requires --path or --id")

    if not path.exists():
        die(f"File not found: {path}")
    content = read_single_markdown(path)
    print("--- kb-open-meta ---")
    print_json({**metadata, "elapsed_ms": elapsed_ms(start)})
    print("--- kb-open-content ---")
    print(content)


def command_list(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    where: List[str] = []
    params: List[Any] = []
    if args.category:
        where.append("category = ?")
        params.append(args.category)
    if args.layer:
        where.append("layer = ?")
        params.append(args.layer)
    sql = """
        SELECT id, path, title, category, layer, type, status, confidence, source_type,
               created_at, last_reviewed, reviewed_at, indexed_at
        FROM documents
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY category, layer, title LIMIT ?"
    params.append(args.limit)
    rows = [dict(row) for row in conn.execute(sql, params)]
    print_json({"elapsed_ms": elapsed_ms(start), "count": len(rows), "results": rows})


def read_markdown_parts(path: Path) -> Tuple[Dict[str, Any], str, bool]:
    text = read_single_markdown(path)
    return parse_frontmatter(text)


def write_markdown_parts(path: Path, meta: Dict[str, Any], body: str) -> None:
    path.write_text(frontmatter_text(meta) + body, encoding="utf-8", newline="\n")


def resolve_document_path(path_text: Optional[str], document_id: Optional[int]) -> Path:
    if document_id is not None:
        conn = connect_db(must_exist=True)
        ensure_schema(conn)
        row = conn.execute("SELECT path FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            die(f"No document with id={document_id}")
        return (ROOT / row["path"]).resolve()
    if path_text:
        return resolve_user_path(path_text)
    die("This command requires --path or --id")


def move_to_layer(path: Path, target_layer: str) -> Path:
    category, _ = infer_category_layer(path)
    if category == "unknown":
        die("Can only move Markdown files under knowledge/<category>/<layer>/")
    target_dir = category_path(category) / target_layer
    target_path = unique_path(target_dir, path.name)
    path.rename(target_path)
    return target_path


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
        if not str(frontmatter.get("superseded_by") or "").strip() and not str(frontmatter.get("deprecation_reason") or "").strip():
            add("error", "deprecated_missing_superseded_by_or_reason")
    if layer == "raw" and status == "active":
        add("error", "raw_must_not_be_active")
    if layer in {"rejected", "quarantine"} and status == "active":
        add("error", f"{layer}_must_not_be_active")
    if category != "unknown" and frontmatter.get("category") and frontmatter.get("category") != category:
        add("warning", "category_mismatch", f"frontmatter={frontmatter.get('category')} path={category}")
    return issues


def command_lint(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    issues: List[Dict[str, Any]] = []
    files_checked = 0
    for path in iter_markdown_files():
        category, layer = infer_category_layer(path)
        if args.category and category != args.category:
            continue
        if args.layer and layer != args.layer:
            continue
        files_checked += 1
        issues.extend(lint_file(path))
    result = {
        "files_checked": files_checked,
        "error_count": sum(1 for issue in issues if issue["severity"] == "error"),
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
        "issues": issues[: args.limit],
        "truncated": len(issues) > args.limit,
        "elapsed_ms": elapsed_ms(start),
    }
    print_json(result)


def query_documents(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT id, path, title, category, layer, type, status, confidence,
                   source_type, source_url, created_at, last_reviewed, reviewed_by,
                   reviewed_at, valid_for, not_valid_for, project_scope, supersedes,
                   superseded_by, risk_level, verification_method, review_required,
                   promoted_from, deprecation_reason, rejection_reason, quarantine_reason,
                   review_note, review_cycle_days, sha256, indexed_at
            FROM documents
            ORDER BY category, layer, title
            """
        )
    )


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


def duplicate_titles(rows: Sequence[sqlite3.Row]) -> List[Dict[str, Any]]:
    buckets: Dict[Tuple[str, str], List[sqlite3.Row]] = {}
    for row in rows:
        key = (str(row["category"]), title_key(str(row["title"])))
        buckets.setdefault(key, []).append(row)
    return [
        {
            "category": key[0],
            "title_key": key[1],
            "items": [{"id": row["id"], "path": row["path"], "title": row["title"]} for row in bucket],
        }
        for key, bucket in buckets.items()
        if key[1] and len(bucket) > 1
    ]


def source_url_duplicates(rows: Sequence[sqlite3.Row]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[sqlite3.Row]] = {}
    for row in rows:
        url = str(row["source_url"] or "").strip()
        if url:
            buckets.setdefault(url, []).append(row)
    return [
        {"source_url": url, "items": [{"id": row["id"], "path": row["path"], "title": row["title"]} for row in bucket]}
        for url, bucket in buckets.items()
        if len(bucket) > 1
    ]


def sha_duplicates(rows: Sequence[sqlite3.Row]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[sqlite3.Row]] = {}
    for row in rows:
        sha = str(row["sha256"] or "")
        if sha:
            buckets.setdefault(sha, []).append(row)
    return [
        {"sha256": sha, "items": [{"id": row["id"], "path": row["path"], "title": row["title"]} for row in bucket]}
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


def possible_conflicts(conn: sqlite3.Connection, rows: Sequence[sqlite3.Row], limit: int = 50) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    active_rules = [row for row in rows if row["status"] == "active" and row["layer"] in FORMAL_LAYERS]
    for i, left in enumerate(active_rules):
        for right in active_rules[i + 1 :]:
            if left["category"] != right["category"]:
                continue
            sim = title_similarity(str(left["title"]), str(right["title"]))
            if sim >= 0.75:
                conflicts.append(
                    {
                        "kind": "similar_active_titles",
                        "category": left["category"],
                        "similarity": round(sim, 3),
                        "items": [
                            {"id": left["id"], "path": left["path"], "title": left["title"]},
                            {"id": right["id"], "path": right["path"], "title": right["title"]},
                        ],
                    }
                )
            if len(conflicts) >= limit:
                return conflicts

    docs_by_path_title: Dict[str, sqlite3.Row] = {}
    for row in rows:
        docs_by_path_title[str(row["path"])] = row
        docs_by_path_title[str(row["title"])] = row
    for row in active_rules:
        for item in list_value(row["supersedes"]):
            old = docs_by_path_title.get(item)
            if old and old["status"] == "active":
                conflicts.append(
                    {
                        "kind": "active_rule_supersedes_still_active_rule",
                        "new": {"id": row["id"], "path": row["path"], "title": row["title"]},
                        "old": {"id": old["id"], "path": old["path"], "title": old["title"]},
                    }
                )
            if len(conflicts) >= limit:
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
            if left_scope and right_scope and not (left_scope & right_scope):
                continue
            if title_similarity(str(left["title"]), str(right["title"])) < 0.45:
                continue
            right_content = content_by_doc.get(int(right["id"]), "")
            left_positive = any(marker in left_content for marker in positive_markers)
            left_negative = any(marker in left_content for marker in opposite_markers)
            right_positive = any(marker in right_content for marker in positive_markers)
            right_negative = any(marker in right_content for marker in opposite_markers)
            if (left_positive and right_negative) or (left_negative and right_positive):
                conflicts.append(
                    {
                        "kind": "possible_opposite_conclusion",
                        "category": left["category"],
                        "valid_for_overlap": sorted(left_scope & right_scope),
                        "items": [
                            {"id": left["id"], "path": left["path"], "title": left["title"]},
                            {"id": right["id"], "path": right["path"], "title": right["title"]},
                        ],
                    }
                )
            if len(conflicts) >= limit:
                return conflicts
    return conflicts


def command_audit(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)
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
    stale_rows = [dict(row) for row in rows if row["status"] == "active" and is_stale_row(row, args.days)]
    low_conf_rules = [dict(row) for row in rows if row["layer"] == "rules" and row["confidence"] == "low"]
    unknown_source = [dict(row) for row in rows if row["source_type"] == "unknown"]
    raw_in_formal = [
        dict(row)
        for row in rows
        if row["layer"] in FORMAL_LAYERS and (row["type"] == "raw" or bool_value(row["review_required"]))
    ]
    result = {
        "documents": len(rows),
        "by_category": group_counts(rows, "category"),
        "by_layer": group_counts(rows, "layer"),
        "by_status": group_counts(rows, "status"),
        "missing_source": missing_source[: args.limit],
        "formal_missing_source": formal_missing_source[: args.limit],
        "missing_formal_review": missing_review[: args.limit],
        "stale_active": stale_rows[: args.limit],
        "low_confidence_rules": low_conf_rules[: args.limit],
        "unknown_source_type": unknown_source[: args.limit],
        "raw_in_formal_layer": raw_in_formal[: args.limit],
        "duplicate_titles": duplicate_titles(rows)[: args.limit],
        "possible_conflicts": possible_conflicts(conn, rows, args.limit),
        "elapsed_ms": elapsed_ms(start),
    }
    print_json(result)


def command_review_queue(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)
    cutoff = datetime.now() - timedelta(days=args.days)
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
    print_json({"count": len(queue), "results": queue[: args.limit], "elapsed_ms": elapsed_ms(start)})


def command_stale(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)
    stale_rows = [dict(row) for row in rows if row["status"] == "active" and is_stale_row(row, args.days)]
    print_json({"days": args.days, "count": len(stale_rows), "results": stale_rows[: args.limit], "elapsed_ms": elapsed_ms(start)})


def command_conflicts(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)
    conflicts = possible_conflicts(conn, rows, args.limit)
    print_json({"count": len(conflicts), "results": conflicts, "elapsed_ms": elapsed_ms(start)})


def command_dedupe(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    rows = query_documents(conn)
    result = {
        "duplicate_titles": duplicate_titles(rows)[: args.limit],
        "duplicate_source_urls": source_url_duplicates(rows)[: args.limit],
        "duplicate_sha256": sha_duplicates(rows)[: args.limit],
        "similar_filenames": similar_filenames(rows)[: args.limit],
        "elapsed_ms": elapsed_ms(start),
    }
    print_json(result)


def command_deprecate(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    path = resolve_document_path(args.path, args.id)
    if not path.exists():
        die(f"File not found: {path}")
    frontmatter, body, has_frontmatter = read_markdown_parts(path)
    if not has_frontmatter:
        die("Cannot deprecate a file without frontmatter")
    category, _ = infer_category_layer(path)
    if category == "unknown":
        die("Can only deprecate files under knowledge/")
    frontmatter.update(
        {
            "status": "deprecated",
            "review_required": False,
            "last_reviewed": today_iso(),
            "reviewed_at": now_iso(),
            "reviewed_by": args.reviewed_by,
            "deprecation_reason": args.reason,
        }
    )
    if args.superseded_by:
        frontmatter["superseded_by"] = args.superseded_by
    write_markdown_parts(path, frontmatter, body)
    new_path = move_to_layer(path, "deprecated") if infer_category_layer(path)[1] != "deprecated" else path
    print_json(
        {
            "deprecated": to_relative_posix(new_path),
            "reason": args.reason,
            "superseded_by": args.superseded_by or "",
            "message": "规则已标记为 deprecated。建议运行: python scripts/kb.py index",
            "elapsed_ms": elapsed_ms(start),
        }
    )


def command_quarantine(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    path = resolve_document_path(args.path, args.id)
    if not path.exists():
        die(f"File not found: {path}")
    frontmatter, body, has_frontmatter = read_markdown_parts(path)
    if not has_frontmatter:
        die("Cannot quarantine a file without frontmatter")
    category, _ = infer_category_layer(path)
    if category == "unknown":
        die("Can only quarantine files under knowledge/")
    frontmatter.update(
        {
            "status": "experimental" if frontmatter.get("status") != "rejected" else "rejected",
            "review_required": True,
            "risk_level": "high",
            "quarantine_reason": args.reason,
            "last_reviewed": today_iso(),
        }
    )
    write_markdown_parts(path, frontmatter, body)
    new_path = move_to_layer(path, "quarantine") if infer_category_layer(path)[1] != "quarantine" else path
    print_json(
        {
            "quarantined": to_relative_posix(new_path),
            "reason": args.reason,
            "message": "内容已隔离到 quarantine。建议运行: python scripts/kb.py index",
            "elapsed_ms": elapsed_ms(start),
        }
    )


def command_research(args: argparse.Namespace) -> None:
    args.research = True
    result = run_search(args)
    result["warning"] = "以下内容未经审核，不能作为正式项目规则。"
    print_json(result)


def priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 9)


def command_sources(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    rows = []
    for source in load_sources_config():
        if args.category and source.get("category") != args.category:
            continue
        if args.enabled_only and not bool_value(source.get("enabled")):
            continue
        rows.append(
            {
                "name": source.get("name", ""),
                "category": source.get("category", ""),
                "type": source.get("type", ""),
                "priority": source.get("priority", ""),
                "enabled": bool_value(source.get("enabled")),
                "url": source.get("url", ""),
                "learn_focus": ensure_list_text(source.get("learn_focus")),
            }
        )
    rows.sort(key=lambda item: (priority_rank(str(item["priority"])), str(item["category"]), str(item["name"])))
    print_json({"count": len(rows), "results": rows, "elapsed_ms": elapsed_ms(start)})


def markdown_list(items: Sequence[str]) -> str:
    if not items:
        return "未配置"
    return ", ".join(str(item) for item in items)


def learning_quality_warning(source: Dict[str, Any]) -> str:
    source_type = str(source.get("type") or "")
    priority = str(source.get("priority") or "")
    if source_type in {"manual", "rss"}:
        return "只生成学习任务，不抓取全文；进入 raw 后仍需人工审核，不能直接进入 rules。"
    if priority == "low":
        return "低优先级来源只适合补充参考，默认不得影响正式规则。"
    return "即使是高优先级来源，也必须 raw -> distilled -> review-queue -> promote 后才可进入正式知识。"


def command_learning_queue(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    sources = [source for source in load_sources_config() if bool_value(source.get("enabled"))]
    radar = load_learning_radar()
    sources.sort(key=lambda source: (priority_rank(str(source.get("priority"))), str(source.get("category")), str(source.get("name"))))
    today = today_iso()
    lines = [
        "---",
        f'title: "Learning Queue {today}"',
        "type: learning_queue",
        "status: experimental",
        "source_type: internal_practice",
        f'created_at: "{now_iso()}"',
        "review_required: true",
        "---",
        "",
        f"# Learning Queue {today}",
        "",
        "本报告只生成待学习任务，不抓取全文，不创建 raw/distilled/rules。所有学习结果必须先进入 raw，不能直接进入正式规则层。",
        "",
    ]
    task_count = 0
    current_group: Optional[Tuple[str, str]] = None
    for source in sources:
        category = str(source.get("category") or "unknown")
        priority = str(source.get("priority") or "unknown")
        group = (priority, category)
        if group != current_group:
            lines.extend([f"## {priority.upper()} / {category}", ""])
            current_group = group
        radar_meta = radar.get(category, {})
        learn_focus = ensure_list_text(source.get("learn_focus")) or ensure_list_text(radar_meta.get("focus"))
        expected = ensure_list_text(source.get("output_targets")) or ensure_list_text(radar_meta.get("preferred_outputs"))
        lines.extend(
            [
                f"### {source.get('name', '')}",
                "",
                f"- source name: {source.get('name', '')}",
                f"- category: {category}",
                f"- url: {source.get('url', '')}",
                f"- learn_focus: {markdown_list(learn_focus)}",
                f"- expected output: {markdown_list(expected)}",
                f"- quality warning: {learning_quality_warning(source)}",
                f"- radar goal: {radar_meta.get('learning_goal', '未配置')}",
                "",
            ]
        )
        task_count += 1
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"learning-queue-{today}.md"
    report_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print_json({"report": to_relative_posix(report_path), "task_count": task_count, "elapsed_ms": elapsed_ms(start)})


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


def command_distill_plan(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    path = resolve_user_path(args.path)
    if not path.exists():
        die(f"File not found: {path}")
    category, layer = infer_category_layer(path)
    if layer != "raw":
        die("distill-plan only accepts a single file from raw/")
    text = read_single_markdown(path)
    frontmatter, body, has_frontmatter = parse_frontmatter(text)
    if not has_frontmatter:
        die("Raw file has no frontmatter; cannot build a reliable distill plan")
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
    result = {
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
    print_json(result)


def command_digest(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    docs = query_documents(conn)
    radar = load_learning_radar()
    sources = load_sources_config()
    high_sources_by_category: Dict[str, List[str]] = {}
    for source in sources:
        if source.get("priority") == "high" and bool_value(source.get("enabled")):
            high_sources_by_category.setdefault(str(source.get("category") or "unknown"), []).append(str(source.get("name") or ""))
    categories = sorted(load_categories().keys())
    rows: List[Dict[str, Any]] = []
    for category in categories:
        category_docs = [row for row in docs if row["category"] == category]
        rows.append(
            {
                "category": category,
                "raw": sum(1 for row in category_docs if row["layer"] == "raw"),
                "distilled": sum(1 for row in category_docs if row["layer"] == "distilled"),
                "rules": sum(1 for row in category_docs if row["layer"] == "rules"),
                "pending_review": sum(1 for row in category_docs if bool_value(row["review_required"]) or row["layer"] in EXPLORATORY_LAYERS),
                "stale": sum(1 for row in category_docs if row["status"] == "active" and is_stale_row(row, 180)),
                "high_priority_sources": high_sources_by_category.get(category, []),
                "learning_frequency": radar.get(category, {}).get("frequency", ""),
            }
        )

    today = today_iso()
    lines = [
        "---",
        f'title: "Category Digest {today}"',
        "type: category_digest",
        "status: active",
        "source_type: internal_practice",
        f'created_at: "{now_iso()}"',
        "review_required: false",
        "---",
        "",
        f"# Category Digest {today}",
        "",
        "本摘要基于 SQLite 索引元数据生成，不全量读取 Markdown 正文。",
        "",
        "| category | raw | distilled | rules | pending_review | stale | high_priority_sources | frequency |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {category} | {raw} | {distilled} | {rules} | {pending_review} | {stale} | {sources} | {frequency} |".format(
                category=row["category"],
                raw=row["raw"],
                distilled=row["distilled"],
                rules=row["rules"],
                pending_review=row["pending_review"],
                stale=row["stale"],
                sources=", ".join(row["high_priority_sources"]),
                frequency=row["learning_frequency"],
            )
        )
    report_path = REPORTS_DIR / f"category-digest-{today}.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print_json({"report": to_relative_posix(report_path), "categories": rows, "elapsed_ms": elapsed_ms(start)})


def command_stats(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)

    def grouped(field: str) -> Dict[str, int]:
        return {
            str(row[field] or "unknown"): int(row["count"])
            for row in conn.execute(f"SELECT {field}, COUNT(*) AS count FROM documents GROUP BY {field}")
        }

    result = {
        "documents": int(conn.execute("SELECT COUNT(*) AS count FROM documents").fetchone()["count"]),
        "chunks": int(conn.execute("SELECT COUNT(*) AS count FROM chunks").fetchone()["count"]),
        "by_category": grouped("category"),
        "by_layer": grouped("layer"),
        "by_status": grouped("status"),
        "index_size_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
        "last_indexed_at": conn.execute("SELECT MAX(indexed_at) AS value FROM documents").fetchone()["value"],
        "elapsed_ms": elapsed_ms(start),
    }
    print_json(result)


def frontmatter_missing_warnings() -> List[Dict[str, Any]]:
    required = REQUIRED_SCHEMA_FIELDS
    warnings: List[Dict[str, Any]] = []
    for path in iter_markdown_files():
        text = read_single_markdown(path)
        frontmatter, _, has_frontmatter = parse_frontmatter(text)
        rel = to_relative_posix(path)
        if not has_frontmatter:
            warnings.append({"path": rel, "issue": "missing_frontmatter"})
            continue
        missing = [key for key in required if key not in frontmatter]
        if missing:
            warnings.append({"path": rel, "issue": "missing_frontmatter_keys", "keys": missing})
    return warnings


def command_doctor(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    checks: Dict[str, Any] = {
        "index_exists": DB_PATH.exists(),
        "fts5_available": False,
        "knowledge_file_count": 0,
        "indexed_document_count": 0,
        "missing_files": [],
        "orphan_chunks": 0,
        "stale_index": [],
        "frontmatter_warnings": [],
        "deprecated_without_superseded_by": [],
        "raw_misplaced_in_formal_layers": [],
    }

    memory_conn = sqlite3.connect(":memory:")
    try:
        check_fts5(memory_conn)
        checks["fts5_available"] = True
    except KBError:
        checks["fts5_available"] = False
    finally:
        memory_conn.close()

    files = list(iter_markdown_files())
    checks["knowledge_file_count"] = len(files)
    checks["frontmatter_warnings"] = frontmatter_missing_warnings()

    if DB_PATH.exists():
        conn = connect_db(must_exist=True)
        ensure_schema(conn)
        docs = conn.execute("SELECT id, path, mtime, size, sha256 FROM documents").fetchall()
        checks["indexed_document_count"] = len(docs)
        for row in docs:
            path = ROOT / row["path"]
            if not path.exists():
                checks["missing_files"].append(row["path"])
                continue
            stat = path.stat()
            digest = sha256_file(path)
            if (
                float(row["mtime"]) != float(stat.st_mtime)
                or int(row["size"]) != int(stat.st_size)
                or str(row["sha256"]) != digest
            ):
                checks["stale_index"].append(row["path"])
        orphan = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM chunks c
            LEFT JOIN documents d ON d.id = c.document_id
            WHERE d.id IS NULL
            """
        ).fetchone()
        checks["orphan_chunks"] = int(orphan["count"])
        deprecated = conn.execute(
            """
            SELECT path, title FROM documents
            WHERE (layer = 'deprecated' OR status = 'deprecated')
              AND COALESCE(type, '') = 'rule'
              AND COALESCE(superseded_by, '') = ''
              AND COALESCE(deprecation_reason, '') = ''
            """
        ).fetchall()
        checks["deprecated_without_superseded_by"] = [dict(row) for row in deprecated]
        raw_misplaced = conn.execute(
            """
            SELECT path, title, layer, type, status FROM documents
            WHERE layer IN ('rules', 'checklists', 'snippets')
              AND (COALESCE(type, '') = 'raw' OR COALESCE(review_required, '') = 'true')
            """
        ).fetchall()
        checks["raw_misplaced_in_formal_layers"] = [dict(row) for row in raw_misplaced]

    checks["elapsed_ms"] = elapsed_ms(start)
    print_json(checks)


def command_vacuum(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    conn.execute("VACUUM")
    print_json({"status": "ok", "elapsed_ms": elapsed_ms(start)})


def benchmark_queries() -> List[str]:
    return ["react", "api", "database index", "security", "agent workflow"]


def command_benchmark(args: argparse.Namespace) -> None:
    start = time.perf_counter()
    results = []
    for query in args.query or benchmark_queries():
        search_args = argparse.Namespace(
            query=query,
            category=None,
            layer=None,
            type=None,
            status=None,
            confidence=None,
            source_type=None,
            top_k=args.top_k,
            include_distilled=False,
            include_raw=False,
            include_deprecated=False,
            slow_scan=False,
            force=False,
            research=False,
        )
        item = run_search(search_args)
        results.append(
            {
                "query": query,
                "result_count": len(item["results"]),
                "elapsed_ms": item["elapsed_ms"],
            }
        )
    print_json({"elapsed_ms": elapsed_ms(start), "results": results})


def is_current_iso_week(value: str, year: int, week: int) -> bool:
    parsed = parse_date(value)
    if not parsed:
        return False
    iso = parsed.isocalendar()
    return iso.year == year and iso.week == week


def stale_or_missing_review(value: str) -> bool:
    parsed = parse_date(value)
    if not parsed:
        return True
    return datetime.now() - parsed.replace(tzinfo=None) > timedelta(days=90)


def markdown_table(rows: Sequence[sqlite3.Row], fields: Sequence[str]) -> str:
    if not rows:
        return "_无_\n"
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in rows:
        values = [str(row[field] or "").replace("|", "\\|") for field in fields]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def command_weekly_report(_: argparse.Namespace) -> None:
    start = time.perf_counter()
    conn = connect_db(must_exist=True)
    ensure_schema(conn)
    today = datetime.now()
    iso = today.isocalendar()
    year, week = iso.year, iso.week

    docs = conn.execute(
        """
        SELECT id, path, title, category, layer, type, status, confidence,
               source_type, created_at, last_reviewed, reviewed_at, promoted_from
        FROM documents
        ORDER BY category, layer, title
        """
    ).fetchall()

    new_raw = [row for row in docs if row["layer"] == "raw" and is_current_iso_week(row["created_at"], year, week)]
    new_distilled = [row for row in docs if row["layer"] == "distilled" and is_current_iso_week(row["created_at"], year, week)]
    promoted = [
        row
        for row in docs
        if row["layer"] in FORMAL_LAYERS and (is_current_iso_week(row["reviewed_at"], year, week) or row["promoted_from"])
    ]
    pending = [
        row
        for row in docs
        if row["layer"] in {"raw", "distilled"} and row["status"] in {"experimental", "rejected"}
    ][:50]
    stale = [
        row
        for row in docs
        if row["status"] == "active" and stale_or_missing_review(row["last_reviewed"])
    ][:50]

    report = f"""---
title: "{year}-{week:02d} Weekly Knowledge Report"
category: ""
type: report
status: active
confidence: medium
source_type: internal_practice
source_url: ""
created_at: "{now_iso()}"
last_reviewed: "{today_iso()}"
week: "{year}-{week:02d}"
---

# {year}-{week:02d} 本周知识报告

本报告基于 SQLite 索引元数据生成，不全量读取 Markdown 正文。

## 本周新增 raw

{markdown_table(new_raw, ["id", "path", "title", "category", "status", "source_type"])}

## 本周新增 distilled

{markdown_table(new_distilled, ["id", "path", "title", "category", "status", "confidence"])}

## 本周 promoted 到 rules/snippets/checklists

{markdown_table(promoted, ["id", "path", "title", "category", "layer", "reviewed_at"])}

## 高优先级待审核内容

{markdown_table(pending, ["id", "path", "title", "category", "layer", "confidence"])}

## 过期或待复查内容

{markdown_table(stale, ["id", "path", "title", "category", "layer", "last_reviewed"])}
"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"{year}-{week:02d}-weekly-report.md"
    report_path.write_text(report, encoding="utf-8", newline="\n")
    print_json(
        {
            "report": to_relative_posix(report_path),
            "new_raw": len(new_raw),
            "new_distilled": len(new_distilled),
            "promoted": len(promoted),
            "pending_review": len(pending),
            "stale_or_missing_review": len(stale),
            "elapsed_ms": elapsed_ms(start),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kb.py",
        description="Markdown-first personal development knowledge base with SQLite FTS5 indexing.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize directories, config, templates, and .kb without overwriting files.")
    p_init.set_defaults(func=command_init)

    p_new = sub.add_parser("new-card", help="Create a distilled knowledge card.")
    p_new.add_argument("--category", required=True, choices=category_choices())
    p_new.add_argument("--type", required=True, choices=["rule", "pattern", "pitfall", "changelog", "snippet", "checklist", "case", "adr"])
    p_new.add_argument("--title", required=True)
    p_new.add_argument("--status", required=True, choices=sorted(STATUS_VALUES))
    p_new.add_argument("--source-url", default="")
    p_new.set_defaults(func=command_new_card)

    p_raw = sub.add_parser("add-raw", help="Add a raw note that requires review.")
    p_raw.add_argument("--category", required=True, choices=category_choices())
    p_raw.add_argument("--title", required=True)
    p_raw.add_argument("--source-url", default="")
    p_raw.add_argument("--text", default="")
    p_raw.set_defaults(func=command_add_raw)

    p_promote = sub.add_parser("promote", help="Promote a distilled card into rules, snippets, or checklists.")
    p_promote.add_argument("--path", required=True)
    p_promote.add_argument("--target-layer", required=True, choices=["rules", "snippets", "checklists"])
    p_promote.add_argument("--reviewed-by", required=True, help="Human reviewer name or handle.")
    p_promote.add_argument("--confidence", required=True, choices=sorted(CONFIDENCE_VALUES))
    p_promote.add_argument("--valid-for", required=True, help="Comma-separated reviewed applicability scope.")
    p_promote.add_argument("--verification-method", required=True, help="How this knowledge was verified.")
    p_promote.add_argument("--review-note", required=True, help="Human review note explaining why promotion is safe.")
    p_promote.set_defaults(func=command_promote)

    p_index = sub.add_parser("index", help="Incrementally index changed Markdown files.")
    p_index.add_argument("--force-hash", action="store_true", help="Compute sha256 even when mtime/size are unchanged.")
    p_index.set_defaults(func=command_index)

    p_reindex = sub.add_parser("reindex", help="Delete .kb/index.sqlite and rebuild the full index explicitly.")
    p_reindex.set_defaults(func=command_reindex)

    p_search = sub.add_parser("search", help="Search via SQLite FTS5. Does not scan Markdown files.")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--category", choices=category_choices())
    p_search.add_argument("--layer", choices=LAYERS)
    p_search.add_argument("--type")
    p_search.add_argument("--status", choices=sorted(STATUS_VALUES))
    p_search.add_argument("--confidence", choices=sorted(CONFIDENCE_VALUES))
    p_search.add_argument("--source-type", dest="source_type", choices=sorted(SOURCE_TYPE_VALUES))
    p_search.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    p_search.add_argument("--include-distilled", action="store_true", help="Explicitly include distilled content in search.")
    p_search.add_argument("--include-raw", action="store_true", help="Explicitly include raw content in search.")
    p_search.add_argument("--include-deprecated", action="store_true")
    p_search.add_argument("--slow-scan", action="store_true", help="Explicit emergency fallback that reads Markdown files.")
    p_search.add_argument("--force", action="store_true", help="Allow --top-k above 50.")
    p_search.set_defaults(func=command_search)

    p_open = sub.add_parser("open", help="Open exactly one Markdown document by path or document id.")
    group = p_open.add_mutually_exclusive_group(required=True)
    group.add_argument("--path")
    group.add_argument("--id", type=int)
    p_open.set_defaults(func=command_open)

    p_list = sub.add_parser("list", help="List documents from index metadata only.")
    p_list.add_argument("--category", choices=category_choices())
    p_list.add_argument("--layer", choices=LAYERS)
    p_list.add_argument("--limit", type=int, default=50)
    p_list.set_defaults(func=command_list)

    p_sources = sub.add_parser("sources", help="List configured learning sources without fetching content.")
    p_sources.add_argument("--category", choices=category_choices())
    p_sources.add_argument("--enabled-only", action="store_true")
    p_sources.set_defaults(func=command_sources)

    p_learning_queue = sub.add_parser("learning-queue", help="Generate a learning queue report from sources and radar config.")
    p_learning_queue.set_defaults(func=command_learning_queue)

    p_distill_plan = sub.add_parser("distill-plan", help="Read one raw file and output a distillation plan.")
    p_distill_plan.add_argument("--path", required=True)
    p_distill_plan.set_defaults(func=command_distill_plan)

    p_digest = sub.add_parser("digest", help="Generate a category digest from SQLite index metadata.")
    p_digest.set_defaults(func=command_digest)

    p_lint = sub.add_parser("lint", help="Lint frontmatter schema and quality gates.")
    p_lint.add_argument("--category", choices=category_choices())
    p_lint.add_argument("--layer", choices=LAYERS)
    p_lint.add_argument("--limit", type=int, default=200)
    p_lint.set_defaults(func=command_lint)

    p_audit = sub.add_parser("audit", help="Output a full quality governance report from index metadata.")
    p_audit.add_argument("--days", type=int, default=180, help="Default stale threshold when review_cycle_days is absent.")
    p_audit.add_argument("--limit", type=int, default=50)
    p_audit.set_defaults(func=command_audit)

    p_review = sub.add_parser("review-queue", help="List content that should receive human review.")
    p_review.add_argument("--days", type=int, default=14, help="Recent raw window in days.")
    p_review.add_argument("--limit", type=int, default=50)
    p_review.set_defaults(func=command_review_queue)

    p_stale = sub.add_parser("stale", help="Find active knowledge past last_reviewed/review_cycle_days.")
    p_stale.add_argument("--days", type=int, default=180)
    p_stale.add_argument("--limit", type=int, default=100)
    p_stale.set_defaults(func=command_stale)

    p_conflicts = sub.add_parser("conflicts", help="Detect basic duplicate and conflicting active rules.")
    p_conflicts.add_argument("--limit", type=int, default=50)
    p_conflicts.set_defaults(func=command_conflicts)

    p_dedupe = sub.add_parser("dedupe", help="Detect duplicate titles, URLs, hashes, and similar filenames.")
    p_dedupe.add_argument("--limit", type=int, default=50)
    p_dedupe.set_defaults(func=command_dedupe)

    p_deprecate = sub.add_parser("deprecate", help="Mark a rule as deprecated and move it to deprecated/.")
    dep_group = p_deprecate.add_mutually_exclusive_group(required=True)
    dep_group.add_argument("--path")
    dep_group.add_argument("--id", type=int)
    p_deprecate.add_argument("--reason", required=True)
    p_deprecate.add_argument("--superseded-by", default="")
    p_deprecate.add_argument("--reviewed-by", required=True)
    p_deprecate.set_defaults(func=command_deprecate)

    p_quarantine = sub.add_parser("quarantine", help="Move questionable content into quarantine/.")
    q_group = p_quarantine.add_mutually_exclusive_group(required=True)
    q_group.add_argument("--path")
    q_group.add_argument("--id", type=int)
    p_quarantine.add_argument("--reason", required=True)
    p_quarantine.set_defaults(func=command_quarantine)

    p_research = sub.add_parser("research", help="Explore raw/distilled content. Results are not formal rules.")
    p_research.add_argument("--query", required=True)
    p_research.add_argument("--category", choices=category_choices())
    p_research.add_argument("--layer", choices=sorted(EXPLORATORY_LAYERS))
    p_research.add_argument("--type")
    p_research.add_argument("--status", choices=sorted(STATUS_VALUES))
    p_research.add_argument("--confidence", choices=sorted(CONFIDENCE_VALUES))
    p_research.add_argument("--source-type", dest="source_type", choices=sorted(SOURCE_TYPE_VALUES))
    p_research.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    p_research.add_argument("--include-distilled", action="store_true")
    p_research.add_argument("--include-raw", action="store_true")
    p_research.add_argument("--include-deprecated", action="store_true")
    p_research.add_argument("--slow-scan", action="store_true")
    p_research.add_argument("--force", action="store_true")
    p_research.set_defaults(func=command_research, research=True)

    p_stats = sub.add_parser("stats", help="Show index statistics.")
    p_stats.set_defaults(func=command_stats)

    p_doctor = sub.add_parser("doctor", help="Validate index, lifecycle metadata, and frontmatter quality.")
    p_doctor.set_defaults(func=command_doctor)

    p_vacuum = sub.add_parser("vacuum", help="VACUUM the SQLite index.")
    p_vacuum.set_defaults(func=command_vacuum)

    p_bench = sub.add_parser("benchmark", help="Run several FTS5 search benchmark queries.")
    p_bench.add_argument("--query", action="append", help="Custom query. Can be repeated.")
    p_bench.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    p_bench.set_defaults(func=command_benchmark)

    p_report = sub.add_parser("weekly-report", help="Generate a weekly report from index metadata.")
    p_report.set_defaults(func=command_weekly_report)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except KBError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except sqlite3.Error as exc:
        print(f"SQLite ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
