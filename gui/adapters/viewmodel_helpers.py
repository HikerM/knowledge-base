"""Shared GUI ViewModel mapping helpers for read-only adapter payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


FORMAL_LAYERS = ["rules", "checklists", "snippets"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def envelope(
    view_id: str,
    state: str,
    data: Optional[Dict[str, Any]],
    services: Iterable[str],
    warnings: Optional[list[Dict[str, Any]]] = None,
    errors: Optional[list[Dict[str, Any]]] = None,
    elapsed_ms: int = 0,
) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "view_id": view_id,
        "state": state,
        "data": data,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
        "source_services": list(services),
        "elapsed_ms": int(elapsed_ms or 0),
        "generated_at": now_iso(),
    }


def ui_error(service: str, message: str, code: str = "service_error", recoverable: bool = True) -> Dict[str, Any]:
    return {"code": code, "message": message, "service": service, "recoverable": recoverable}


def ui_warning(service: str, message: str, code: str = "service_warning") -> Dict[str, Any]:
    return {"code": code, "message": message, "service": service}


def as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    return dict(value.to_dict() if hasattr(value, "to_dict") else value)


def formal_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    filters = dict(filters or {})
    layer = filters.get("layer")
    filters["status"] = filters.get("status") or "active"
    if layer not in FORMAL_LAYERS:
        filters.pop("layer", None)
    return filters


def empty_search(query: str, limit: int, offset: int, index_status: str = "unknown") -> Dict[str, Any]:
    return {
        "query": query,
        "filters": {"layers": FORMAL_LAYERS, "status": ["active"]},
        "page": {"limit": limit, "offset": offset, "count": 0, "has_more": False},
        "results": [],
        "index_status": index_status,
    }


def route_action(action_id: str, label: str, kind: str, target: str, enabled: bool, reason: str = "") -> Dict[str, Any]:
    payload = {"action_id": action_id, "label": label, "kind": kind, "target": target, "execute": False, "enabled": enabled}
    if reason:
        payload["reason"] = reason
    return payload


def search_row(item: Dict[str, Any]) -> Dict[str, Any]:
    path = str(item.get("path") or "")
    document_id = str(item.get("document_id") or item.get("id") or path)
    return {
        "document_id": document_id,
        "path": path,
        "title": str(item.get("title") or path or "未命名文档"),
        "category_id": str(item.get("category_id") or item.get("category") or ""),
        "layer": str(item.get("layer") or ""),
        "status": str(item.get("status") or ""),
        "confidence": str(item.get("confidence") or ""),
        "source_type": str(item.get("source_type") or ""),
        "review_required": _truthy(item.get("review_required", False)),
        "snippet": str(item.get("snippet") or ""),
        "updated_at": str(item.get("updated_at") or item.get("indexed_at") or "") or None,
        "open_document_action": route_action("open_document", "打开文档", "open_document", path, bool(path)),
    }


def category_row(item: Dict[str, Any]) -> Dict[str, Any]:
    layer_counts = dict(item.get("layer_counts") or {})
    formal_counts = {layer: int(layer_counts.get(layer) or 0) for layer in FORMAL_LAYERS}
    return {
        "category_id": str(item.get("category_id") or ""),
        "display_name": str(item.get("display_name") or item.get("category_id") or ""),
        "path": str(item.get("path") or ""),
        "description": str(item.get("description") or ""),
        "document_count": sum(formal_counts.values()),
        "layer_counts": formal_counts,
        "status_counts": dict(item.get("status_counts") or {}),
        "review_required_count": int(item.get("review_required_count") or 0),
        "edit_available": False,
    }


def formal_totals(rows: list[Dict[str, Any]]) -> Dict[str, int]:
    return {layer: sum(int((row.get("layer_counts") or {}).get(layer) or 0) for row in rows) for layer in FORMAL_LAYERS}


def document_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    metadata = dict(payload.get("metadata") or {})
    frontmatter = dict(payload.get("frontmatter") or {})
    layer = str(frontmatter.get("layer") or metadata.get("layer") or layer_from_path(payload.get("path", "")))
    status = str(frontmatter.get("status") or metadata.get("status") or "")
    review_required = _truthy(frontmatter.get("review_required", metadata.get("review_required", False)))
    trust_warning = "未经审核，不能作为正式项目规则" if layer in {"raw", "distilled"} or review_required or status in {"quarantine", "rejected"} else None
    return {
        "document_id": str(metadata.get("id") or payload.get("path") or ""),
        "path": str(payload.get("path") or ""),
        "title": str(frontmatter.get("title") or metadata.get("title") or payload.get("path") or "未命名文档"),
        "category_id": str(frontmatter.get("category") or metadata.get("category") or ""),
        "layer": layer,
        "status": status,
        "confidence": str(frontmatter.get("confidence") or metadata.get("confidence") or ""),
        "source_type": str(frontmatter.get("source_type") or metadata.get("source_type") or ""),
        "source_url": frontmatter.get("source_url") or metadata.get("source_url"),
        "review_required": review_required,
        "last_reviewed": frontmatter.get("last_reviewed") or metadata.get("last_reviewed"),
        "frontmatter": frontmatter,
        "body": str(payload.get("body") or ""),
        "open_mode": "read_only",
        "trust_warning": trust_warning,
        "mutation_actions_available": False,
    }


def task_row(record: Any) -> Dict[str, Any]:
    payload = record.to_dict() if hasattr(record, "to_dict") else dict(record)
    meta = dict(payload.get("metadata") or {})
    return {
        "task_id": str(payload.get("task_id") or ""),
        "task_type": str(payload.get("task_type") or ""),
        "status": str(payload.get("status") or ""),
        "title": str(payload.get("title") or payload.get("task_type") or ""),
        "progress_percent": int(payload.get("progress_percent") or 0),
        "progress_message": str(payload.get("progress_message") or ""),
        "cancel_requested": bool(payload.get("cancel_requested", False)),
        "error": dict(payload.get("error") or {}),
        "log_available": bool(payload.get("log_path")),
        "result_summary": dict(payload.get("result_summary") or {}),
        "elapsed_ms": int(payload.get("elapsed_ms") or 0),
        "created_at": str(payload.get("created_at") or ""),
        "started_at": str(payload.get("started_at") or ""),
        "finished_at": str(payload.get("finished_at") or ""),
        "retry_of": meta.get("retry_of"),
        "retry_root": meta.get("retry_root"),
    }


def layer_from_path(path: str) -> str:
    parts = Path(path).parts
    for layer in ["raw", "distilled", "rules", "checklists", "snippets", "deprecated", "rejected", "quarantine"]:
        if layer in parts:
            return layer
    return ""


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)
