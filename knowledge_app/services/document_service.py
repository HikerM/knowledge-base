"""Single-document read service for explicit open operations."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

from knowledge_core import paths as core_paths
from knowledge_core.frontmatter import parse_frontmatter
from knowledge_core.markdown import SEARCHABLE_EXTENSIONS, read_single_markdown

from knowledge_app.models.operation_result import OperationResult


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


class DocumentService:
    """Open exactly one Markdown document by SQLite id/path or explicit path."""

    def __init__(self, workspace_path: Path | None = None):
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else core_paths.ROOT.resolve()
        self.index_path = self.workspace_path / ".kb" / "index.sqlite"

    def open_document(self, document_id: Optional[int] = None, path: Optional[str | Path] = None) -> OperationResult:
        start = time.perf_counter()
        if document_id is None and not path:
            return OperationResult(success=False, errors=["open_document requires document_id or path"], elapsed_ms=elapsed_ms(start))

        metadata: Dict[str, Any] = {}
        try:
            if document_id is not None:
                resolved_path, metadata = self._path_from_document_id(document_id)
            else:
                resolved_path = self._resolve_explicit_path(Path(str(path)))
                metadata = self._metadata_for_path(resolved_path)
        except (ValueError, FileNotFoundError) as exc:
            return OperationResult(success=False, errors=[str(exc)], elapsed_ms=elapsed_ms(start))
        except sqlite3.DatabaseError as exc:
            return OperationResult(success=False, errors=[f"sqlite read failed: {exc}"], elapsed_ms=elapsed_ms(start))
        except OSError as exc:
            return OperationResult(success=False, errors=[f"document open failed: {exc}"], elapsed_ms=elapsed_ms(start))

        if not resolved_path.exists():
            return OperationResult(success=False, errors=[f"file not found: {resolved_path}"], elapsed_ms=elapsed_ms(start))
        if resolved_path.suffix.lower() not in SEARCHABLE_EXTENSIONS:
            return OperationResult(success=False, errors=[f"not a Markdown document: {resolved_path}"], elapsed_ms=elapsed_ms(start))

        try:
            text = read_single_markdown(resolved_path)
        except OSError as exc:
            return OperationResult(success=False, errors=[f"document read failed: {exc}"], elapsed_ms=elapsed_ms(start))

        frontmatter, body, has_frontmatter = parse_frontmatter(text)
        rel_path = self._relative_path(resolved_path)
        payload = {
            "path": rel_path,
            "absolute_path": str(resolved_path),
            "metadata": metadata,
            "frontmatter": frontmatter,
            "body": body,
            "content": text,
            "has_frontmatter": has_frontmatter,
            "elapsed_ms": elapsed_ms(start),
        }
        return OperationResult(success=True, data=payload, elapsed_ms=payload["elapsed_ms"])

    def _path_from_document_id(self, document_id: int) -> tuple[Path, Dict[str, Any]]:
        if not self.index_path.exists():
            raise FileNotFoundError("index.sqlite missing; cannot resolve document_id")
        with self._connect_readonly() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM documents
                WHERE id = ?
                """,
                (document_id,),
            ).fetchone()
        if not row:
            raise FileNotFoundError(f"no document with id={document_id}")
        rel_path = str(row["path"])
        return (self.workspace_path / rel_path).resolve(), dict(row)

    def _metadata_for_path(self, path: Path) -> Dict[str, Any]:
        if not self.index_path.exists():
            return {}
        rel_path = self._relative_path(path)
        with self._connect_readonly() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM documents
                WHERE path = ?
                """,
                (rel_path,),
            ).fetchone()
        return dict(row) if row else {}

    def _resolve_explicit_path(self, path: Path) -> Path:
        resolved = path if path.is_absolute() else self.workspace_path / path
        resolved = resolved.resolve()
        self._relative_path(resolved)
        return resolved

    def _relative_path(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.workspace_path).as_posix()
        except ValueError as exc:
            raise ValueError(f"path is outside workspace: {path}") from exc

    def _connect_readonly(self) -> sqlite3.Connection:
        uri = f"{self.index_path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn
