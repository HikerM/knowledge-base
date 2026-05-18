"""Path constants and path resolution helpers for the knowledge base."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple


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


class PathConfigError(ValueError):
    """Raised when a configured knowledge path cannot be resolved."""


def configure_root(root: Path) -> None:
    """Point core path constants at a different project root.

    This is used by tests that import the CLI module directly with a temporary
    knowledge base root.
    """

    global ROOT, KNOWLEDGE_DIR, CONFIG_DIR, TEMPLATES_DIR, REPORTS_DIR, KB_DIR, DB_PATH
    ROOT = Path(root).resolve()
    KNOWLEDGE_DIR = ROOT / "knowledge"
    CONFIG_DIR = ROOT / "config"
    TEMPLATES_DIR = ROOT / "templates"
    REPORTS_DIR = ROOT / "reports"
    KB_DIR = ROOT / ".kb"
    DB_PATH = KB_DIR / "index.sqlite"


def category_path(category: str, categories: Mapping[str, Mapping[str, str]]) -> Path:
    if category not in categories:
        raise PathConfigError(f"Unknown category: {category}. Valid: {', '.join(sorted(categories))}")
    return ROOT / categories[category]["path"]


def ensure_directories(categories: Optional[Mapping[str, Mapping[str, str]]] = None) -> None:
    if categories is None:
        from .config import load_categories

        categories = load_categories()
    KB_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for meta in categories.values():
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


def infer_category_layer(path: Path, categories: Optional[Mapping[str, Mapping[str, str]]] = None) -> Tuple[str, str]:
    if categories is None:
        from .config import load_categories

        categories = load_categories()

    rel_parts = path.resolve().relative_to(ROOT.resolve()).parts
    if len(rel_parts) < 4 or rel_parts[0] != "knowledge":
        return "unknown", "unknown"

    category_dir = f"knowledge/{rel_parts[1]}"
    layer = rel_parts[2]
    for category, meta in categories.items():
        if Path(meta["path"]).as_posix() == category_dir.replace("\\", "/"):
            return category, layer
    return "unknown", layer

