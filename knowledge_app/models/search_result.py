"""Structured search result model for service-layer callers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class SearchResult:
    """Stable wrapper around the existing SQLite FTS search payload."""

    query: str
    top_k: int
    allowed_layers: List[str]
    elapsed_ms: int
    results: List[Dict[str, Any]] = field(default_factory=list)
    mode: str = ""
    warning: str = ""

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "SearchResult":
        return cls(
            query=str(payload.get("query") or ""),
            top_k=int(payload.get("top_k") or 0),
            allowed_layers=[str(item) for item in payload.get("allowed_layers", [])],
            elapsed_ms=int(payload.get("elapsed_ms") or 0),
            results=[dict(item) for item in payload.get("results", [])],
            mode=str(payload.get("mode") or ""),
            warning=str(payload.get("warning") or ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "query": self.query,
            "top_k": self.top_k,
            "allowed_layers": list(self.allowed_layers),
            "elapsed_ms": self.elapsed_ms,
            "results": [dict(item) for item in self.results],
        }
        if self.mode:
            payload["mode"] = self.mode
        if self.warning:
            payload["warning"] = self.warning
        return payload
