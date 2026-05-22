"""Service-layer JSON file helpers for AI persistence bootstrap.

These helpers are generic IO primitives only. They do not write conversation,
memory, or draft records, and they do not import SQLite, subprocesses, or core
knowledge modules.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class AIPersistenceIOError(RuntimeError):
    """Controlled AI persistence IO failure."""


def ensure_directory(path: Path | str) -> Path:
    """Create a directory if needed and return its resolved path."""

    directory = Path(path)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AIPersistenceIOError(f"could not create directory: {directory}: {exc}") from exc
    if not directory.is_dir():
        raise AIPersistenceIOError(f"path exists and is not a directory: {directory}")
    return directory.resolve()


def read_json(path: Path | str) -> Any:
    """Read a JSON file with controlled errors."""

    target = Path(path)
    try:
        with target.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AIPersistenceIOError(f"could not read JSON: {target}: {exc}") from exc


def write_json_atomic(path: Path | str, data: Any) -> Path:
    """Write deterministic JSON via temp file and atomic replace."""

    target = Path(path)
    parent = target.parent
    if not parent.exists() or not parent.is_dir():
        raise AIPersistenceIOError(f"target parent directory does not exist: {parent}")

    temp_path: Path | None = None
    try:
        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=str(parent),
            text=True,
        )
        temp_path = Path(temp_name)
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            _fsync_file(handle)
        os.replace(str(temp_path), str(target))
        _fsync_directory(parent)
        return target.resolve()
    except (OSError, TypeError, ValueError) as exc:
        if temp_path is not None:
            _remove_temp_file(temp_path)
        raise AIPersistenceIOError(f"could not write JSON atomically: {target}: {exc}") from exc


def cleanup_partial_temp_files(path: Path | str) -> int:
    """Remove temp files produced for one target path and return count removed."""

    target = Path(path)
    parent = target.parent
    if not parent.exists() or not parent.is_dir():
        return 0

    removed = 0
    for temp_path in parent.glob(f".{target.name}.*.tmp"):
        if temp_path.is_file():
            _remove_temp_file(temp_path)
            removed += 1
    return removed


def _fsync_file(handle: Any) -> None:
    try:
        os.fsync(handle.fileno())
    except OSError:
        pass


def _fsync_directory(directory: Path) -> None:
    try:
        descriptor = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _remove_temp_file(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
