#!/usr/bin/env python3
"""AI persistence atomic JSON IO tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.persistence_io import (  # noqa: E402
    AIPersistenceIOError,
    cleanup_partial_temp_files,
    ensure_directory,
    read_json,
    write_json_atomic,
)


def expect_io_error(callable_) -> None:
    try:
        callable_()
    except AIPersistenceIOError:
        return
    raise AssertionError("expected AIPersistenceIOError")


def assert_atomic_writer_writes_and_reads_json() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-io-") as temp:
        target = Path(temp) / "manifest.json"
        write_json_atomic(target, {"b": 2, "a": 1})
        if not target.exists():
            raise AssertionError("atomic writer did not create target JSON")
        payload = read_json(target)
        if payload != {"a": 1, "b": 2}:
            raise AssertionError(f"read_json returned unexpected payload: {payload}")
        text = target.read_text(encoding="utf-8")
        if text.index('"a"') > text.index('"b"'):
            raise AssertionError("JSON formatting must be deterministic with sorted keys")
        if not text.endswith("\n"):
            raise AssertionError("JSON output should end with a newline")


def assert_ensure_directory() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-io-") as temp:
        directory = Path(temp) / "ai" / "indexes"
        resolved = ensure_directory(directory)
        if not resolved.exists() or not resolved.is_dir():
            raise AssertionError("ensure_directory did not create directory")


def assert_temp_file_cleanup() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-io-") as temp:
        target = Path(temp) / "manifest.json"
        temp_file = target.parent / f".{target.name}.manual.tmp"
        temp_file.write_text("partial", encoding="utf-8")
        removed = cleanup_partial_temp_files(target)
        if removed != 1:
            raise AssertionError(f"expected one temp file cleanup, got {removed}")
        if temp_file.exists():
            raise AssertionError("temp cleanup did not remove temp file")


def assert_write_failure_is_controlled() -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-ai-io-") as temp:
        target = Path(temp) / "missing" / "manifest.json"
        expect_io_error(lambda: write_json_atomic(target, {"ok": True}))


def main() -> int:
    assert_atomic_writer_writes_and_reads_json()
    assert_ensure_directory()
    assert_temp_file_cleanup()
    assert_write_failure_is_controlled()

    print("AI persistence IO tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
