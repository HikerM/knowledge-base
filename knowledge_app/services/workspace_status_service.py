"""Stable workspace startup status service."""

from __future__ import annotations

import time
from pathlib import Path

from knowledge_core import paths as core_paths

from knowledge_app.models.operation_result import OperationResult
from knowledge_app.models.workspace_status import WorkspaceStatus
from knowledge_app.services.index_metadata_service import IndexMetadataService


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


class WorkspaceStatusService:
    """Return startup-safe workspace/index status without touching Markdown."""

    def __init__(self, workspace_path: Path | None = None):
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else core_paths.ROOT.resolve()
        self.index_path = self.workspace_path / ".kb" / "index.sqlite"

    def get_status(self) -> OperationResult:
        start = time.perf_counter()
        index_status, metadata, warnings, errors = IndexMetadataService(self.index_path).read_metadata()
        status = WorkspaceStatus(
            workspace_path=str(self.workspace_path),
            index_path=str(self.index_path),
            index_exists=self.index_path.exists(),
            index_status=index_status,
            document_count=int(metadata["document_count"]),
            chunk_count=int(metadata["chunk_count"]),
            category_counts=dict(metadata["category_counts"]),
            layer_counts=dict(metadata["layer_counts"]),
            status_counts=dict(metadata["status_counts"]),
            index_size_bytes=int(metadata["index_size_bytes"]),
            last_indexed_at=str(metadata["last_indexed_at"]),
            warnings=warnings,
            errors=errors,
            elapsed_ms=elapsed_ms(start),
        )
        return OperationResult(
            success=index_status not in {"failed"},
            data=status,
            warnings=warnings,
            errors=errors,
            elapsed_ms=status.elapsed_ms,
        )
