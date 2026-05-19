"""Workspace startup status model for the SQLite-hot runtime path."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


INDEX_STATUS_VALUES = {"missing", "ready", "stale", "partial", "failed"}


@dataclass(frozen=True)
class WorkspaceStatus:
    """Stable startup payload for CLI and future GUI/EXE callers."""

    workspace_path: str
    index_path: str
    index_exists: bool
    index_status: str
    document_count: int = 0
    chunk_count: int = 0
    category_counts: Dict[str, int] = field(default_factory=dict)
    layer_counts: Dict[str, int] = field(default_factory=dict)
    status_counts: Dict[str, int] = field(default_factory=dict)
    index_size_bytes: int = 0
    last_indexed_at: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def __post_init__(self) -> None:
        if self.index_status not in INDEX_STATUS_VALUES:
            raise ValueError(f"Unknown index_status: {self.index_status}")

    def to_dict(self) -> Dict[str, object]:
        return {
            "workspace_path": self.workspace_path,
            "index_path": self.index_path,
            "index_exists": self.index_exists,
            "index_status": self.index_status,
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "category_counts": dict(self.category_counts),
            "layer_counts": dict(self.layer_counts),
            "status_counts": dict(self.status_counts),
            "index_size_bytes": self.index_size_bytes,
            "last_indexed_at": self.last_indexed_at,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "elapsed_ms": self.elapsed_ms,
        }
