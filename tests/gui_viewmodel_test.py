#!/usr/bin/env python3
"""GUI adapter/ViewModel guardrail tests that do not require a Qt window."""

from __future__ import annotations

import hashlib
import inspect
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from gui.adapters.service_adapter import ServiceAdapter
from gui.fixtures.fake_service_adapter import FakeServiceAdapter
from gui.viewmodels.document_viewmodel import DocumentViewModel
from gui.viewmodels.library_viewmodel import LibraryViewModel
from gui.viewmodels.search_viewmodel import SearchViewModel
from gui.viewmodels.task_viewmodel import TaskViewModel
from gui.viewmodels.workspace_viewmodel import WorkspaceViewModel


def assert_fake_viewmodels() -> None:
    adapter = FakeServiceAdapter()
    workspace = WorkspaceViewModel(adapter)
    status = workspace.load_status()
    assert status["data"]["startup_guards"]["auto_index_started"] is False
    assert adapter.calls == [("load_workspace_status", {})]

    search = SearchViewModel(adapter)
    empty = search.search(" ")
    assert empty["source_services"] == []
    assert adapter.calls == [("load_workspace_status", {})]
    results = search.search("fixture")
    assert results["data"]["results"]
    assert adapter.calls[-1][0] == "search"

    document = DocumentViewModel(adapter)
    opened = document.open_document(path=results["data"]["results"][0]["path"])
    assert opened["data"]["open_mode"] == "read_only"
    assert adapter.calls[-1][0] == "open_document"

    library = LibraryViewModel(adapter)
    summary = library.load_summary()
    assert summary["data"]["categories"][0]["edit_available"] is False
    assert adapter.calls[-1][0] == "load_library_summary"

    tasks = TaskViewModel(adapter)
    task_summary = tasks.load_recent_tasks()
    controls = task_summary["data"]["phase_1_controls"]
    assert controls["cancel_task_available"] is False
    assert controls["retry_task_available"] is False
    assert adapter.calls[-1][0] == "load_recent_tasks"

    caps = adapter.capabilities()
    assert all(value is False for value in caps.values())
    assert not hasattr(adapter, "execute_mutation")


def assert_boundary_imports() -> None:
    forbidden_in_views = ["knowledge_app.services", "knowledge_core", "sqlite3", "subprocess", "scripts/kb.py", ".read_text(", ".rglob("]
    for folder in ["gui/views", "gui/viewmodels", "gui/shell"]:
        for path in (SOURCE_ROOT / folder).glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in forbidden_in_views:
                assert token not in text, f"{path} contains forbidden boundary token {token!r}"

    adapter_text = (SOURCE_ROOT / "gui/adapters/service_adapter.py").read_text(encoding="utf-8")
    for token in ["subprocess", "scripts/kb.py", "knowledge_core", "sqlite3", ".read_text(", ".rglob("]:
        assert token not in adapter_text, f"service adapter contains forbidden token {token!r}"


def assert_service_adapter_startup_guards() -> None:
    adapter = ServiceAdapter()
    original_rglob = Path.rglob
    original_read_text = Path.read_text
    original_sha256 = hashlib.sha256
    knowledge_dir = (SOURCE_ROOT / "knowledge").resolve()

    def blocked_rglob(self: Path, pattern: str):
        if self.resolve() == knowledge_dir:
            raise AssertionError("GUI startup status must not scan knowledge/")
        return original_rglob(self, pattern)

    def blocked_read_text(self: Path, *args, **kwargs):
        if self.suffix.lower() in {".md", ".markdown"}:
            raise AssertionError(f"GUI startup status must not read Markdown: {self}")
        return original_read_text(self, *args, **kwargs)

    def blocked_sha256(*args, **kwargs):
        raise AssertionError("GUI startup status must not hash files")

    Path.rglob = blocked_rglob
    Path.read_text = blocked_read_text
    hashlib.sha256 = blocked_sha256
    try:
        result = adapter.load_workspace_status()
        assert result["view_id"] == "workspace_status"
        assert result["data"]["startup_guards"]["markdown_scan_performed"] is False
        assert result["data"]["startup_guards"]["markdown_body_read"] is False
        assert result["data"]["startup_guards"]["auto_index_started"] is False
    finally:
        Path.rglob = original_rglob
        Path.read_text = original_read_text
        hashlib.sha256 = original_sha256


def assert_viewmodels_do_not_import_services() -> None:
    modules = [WorkspaceViewModel, SearchViewModel, LibraryViewModel, DocumentViewModel, TaskViewModel]
    for cls in modules:
        source = inspect.getsource(sys.modules[cls.__module__])
        assert "knowledge_app.services" not in source
        assert "knowledge_core" not in source


def main() -> int:
    assert_fake_viewmodels()
    assert_boundary_imports()
    assert_service_adapter_startup_guards()
    assert_viewmodels_do_not_import_services()
    print("gui viewmodel tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
