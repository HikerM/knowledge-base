"""Configuration loading for categories, sources, radar, and extract rules."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import paths
from .frontmatter import parse_frontmatter_value


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


def load_categories() -> Dict[str, Dict[str, str]]:
    path = paths.CONFIG_DIR / "categories.yaml"
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
    path = paths.CONFIG_DIR / "sources.yaml"
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
    path = paths.CONFIG_DIR / filename
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


def category_path(category: str):
    return paths.category_path(category, load_categories())

