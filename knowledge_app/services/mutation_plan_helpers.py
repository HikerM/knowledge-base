"""Shared helpers for plan-only mutation services."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from knowledge_core import paths as core_paths
from knowledge_core.config import DEFAULT_CATEGORIES, parse_config_scalar
from knowledge_core.paths import LAYERS


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def resolve_workspace_path(workspace_path: Path | str | None = None) -> Path:
    return Path(workspace_path).resolve() if workspace_path else core_paths.ROOT.resolve()


def relative_to_workspace(path: Path, workspace_path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_path.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def config_path(workspace_path: Path, relative_path: str) -> Path:
    return workspace_path / relative_path


def load_categories_for_workspace(workspace_path: Path) -> Dict[str, Dict[str, str]]:
    path = workspace_path / "config" / "categories.yaml"
    if not path.exists():
        return {key: dict(value) for key, value in DEFAULT_CATEGORIES.items()}

    categories: Dict[str, Dict[str, str]] = {}
    current: Optional[str] = None
    category_indent = 0
    in_categories_root = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if indent == 0 and stripped == "categories:":
            in_categories_root = True
            category_indent = 2
            current = None
            continue
        if indent == category_indent and stripped.endswith(":"):
            current = stripped[:-1].strip()
            categories[current] = {}
            continue
        if current and indent > category_indent and ":" in stripped:
            key, value = stripped.split(":", 1)
            categories[current][key.strip()] = str(parse_config_scalar(value))

    return categories or {key: dict(value) for key, value in DEFAULT_CATEGORIES.items()}


def load_sources_for_workspace(workspace_path: Path) -> List[Dict[str, Any]]:
    path = workspace_path / "config" / "sources.yaml"
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


def source_references_for_category(workspace_path: Path, category_id: str) -> List[Dict[str, Any]]:
    return [
        {
            "name": str(source.get("name") or ""),
            "category": str(source.get("category") or ""),
            "type": str(source.get("type") or ""),
            "url": str(source.get("url") or ""),
            "enabled": bool(source.get("enabled", False)),
        }
        for source in load_sources_for_workspace(workspace_path)
        if str(source.get("category") or "") == category_id
    ]


def empty_layer_counts() -> Dict[str, int]:
    return {layer: 0 for layer in LAYERS}


def read_document_counts(
    workspace_path: Path,
    category_id: Optional[str] = None,
    sample_limit: int = 10,
) -> Tuple[Dict[str, Any], List[str]]:
    index_path = workspace_path / ".kb" / "index.sqlite"
    result: Dict[str, Any] = {
        "known": False,
        "document_count": 0,
        "layer_counts": empty_layer_counts(),
        "status_counts": {},
        "paths_sample": [],
        "count_source": "unavailable",
        "index_path": relative_to_workspace(index_path, workspace_path),
    }
    warnings: List[str] = []
    if not index_path.exists():
        warnings.append("index.sqlite missing; exact affected file counts require index or explicit scan")
        return result, warnings

    try:
        uri = f"{index_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            where = ""
            params: List[Any] = []
            if category_id is not None:
                where = "WHERE category = ?"
                params.append(category_id)
            count_row = conn.execute(f"SELECT COUNT(*) AS count FROM documents {where}", params).fetchone()
            result["document_count"] = int(count_row["count"] if count_row else 0)
            for row in conn.execute(f"SELECT layer, COUNT(*) AS count FROM documents {where} GROUP BY layer", params):
                layer = str(row["layer"] or "unknown")
                result["layer_counts"][layer] = int(row["count"])
            for row in conn.execute(f"SELECT status, COUNT(*) AS count FROM documents {where} GROUP BY status", params):
                status = str(row["status"] or "unknown")
                result["status_counts"][status] = int(row["count"])
            sample_sql = f"SELECT path FROM documents {where} ORDER BY path LIMIT ?"
            result["paths_sample"] = [str(row["path"]) for row in conn.execute(sample_sql, [*params, sample_limit])]
            result["known"] = True
            result["count_source"] = "sqlite_documents_metadata"
    except (sqlite3.DatabaseError, OSError) as exc:
        warnings.append(f"index metadata unavailable; exact affected file counts require index or explicit scan: {exc}")
    return result, warnings
