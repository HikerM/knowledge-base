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
from gui.viewmodels.assistant_viewmodel import AssistantViewModel
from gui.viewmodels.conversation_history_viewmodel import ConversationHistoryViewModel
from gui.viewmodels.dashboard_viewmodel import DashboardViewModel
from gui.viewmodels.document_viewmodel import DocumentViewModel
from gui.viewmodels.library_viewmodel import LibraryViewModel
from gui.viewmodels.search_viewmodel import SearchViewModel
from gui.viewmodels.settings_viewmodel import SettingsViewModel
from gui.viewmodels.task_viewmodel import TaskViewModel
from gui.viewmodels.workspace_creation_viewmodel import WorkspaceCreationViewModel
from gui.viewmodels.workspace_viewmodel import WorkspaceViewModel


def assert_fake_viewmodels() -> None:
    adapter = FakeServiceAdapter()
    workspace = WorkspaceViewModel(adapter)
    status = workspace.load_status()
    assert status["data"]["startup_guards"]["auto_index_started"] is False
    assert adapter.calls == [("load_workspace_status", {})]

    dashboard = DashboardViewModel(adapter)
    home = dashboard.load_summary()
    assert home["data"]["index"]["document_count"] == 12
    assert len(home["data"]["recommended_actions"]) <= 3
    assert adapter.calls[-1][0] == "load_home_summary"

    search = SearchViewModel(adapter)
    empty = search.search(" ")
    assert empty["source_services"] == []
    assert adapter.calls[-1][0] == "load_home_summary"
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
    assert summary["data"]["page"]["limit"] <= 50
    assert {item["layer"] for item in summary["data"]["documents"]} <= {"rules", "checklists", "snippets"}
    assert adapter.calls[-1][0] == "load_library_summary"

    tasks = TaskViewModel(adapter)
    task_summary = tasks.load_recent_tasks()
    controls = task_summary["data"]["phase_1_controls"]
    assert controls["cancel_task_available"] is False
    assert controls["retry_task_available"] is False
    assert adapter.calls[-1][0] == "load_recent_tasks"
    detail = tasks.load_task_detail(task_summary["data"]["tasks"][0]["task_id"])
    assert detail["data"]["log_entries"]
    assert adapter.calls[-1][0] == "load_task_detail"

    settings = SettingsViewModel(adapter)
    entry = settings.load_entry()
    assert entry["data"]["mutation_actions_available"] is False
    assert all(section["editable"] is False for section in entry["data"]["sections"])
    assert adapter.calls[-1][0] == "load_settings_entry"

    creation = WorkspaceCreationViewModel(adapter)
    templates = creation.list_templates()
    assert {item["template_id"] for item in templates["data"]["templates"]} == {"personal", "learning", "work", "developer", "custom"}
    plan = creation.create_plan("D:/Temp/planned-kb", "计划知识库", "developer")
    assert plan["data"]["dry_run"] is True
    assert plan["data"]["would_modify"] is False
    assert plan["data"]["estimated_result"]["auto_index_started"] is False
    assert adapter.calls[-1][0] == "create_workspace_plan"
    create_result = creation.create_workspace_from_current_plan(confirmed=True)
    assert create_result["data"]["success"] is True
    assert create_result["data"]["workspace_path"] == "D:/Temp/planned-kb"
    assert adapter.calls[-1][0] == "create_workspace_from_plan"

    assistant = AssistantViewModel(adapter)
    snapshot = assistant.snapshot()
    assert snapshot["provider_mode"] == "mock"
    assert snapshot["mutation_actions_available"] is False
    assistant_result = assistant.send_message("搜索 GUI")
    assert assistant_result["messages"][-1]["author"] == "AI 助手"
    assert adapter.calls[-1][0] == "send_assistant_message_mock"

    history = ConversationHistoryViewModel(adapter)
    initial_history = history.snapshot()
    assert initial_history["state"] == "idle"
    assert not any(call[0] == "list_ai_conversations" for call in adapter.calls)
    history_page = history.load_page(limit=25, offset=0)
    assert history_page["conversations"]
    assert history_page["page"]["limit"] <= 50
    assert adapter.calls[-1][0] == "list_ai_conversations"
    detail = history.open_conversation(history_page["conversations"][0]["conversation_id"])
    assert detail["selected_conversation"]["messages"]
    assert adapter.calls[-1][0] == "get_ai_conversation"
    export = history.export_conversation(history_page["conversations"][0]["conversation_id"])
    assert '"not_formal_knowledge": true' in export["export_preview"]
    assert adapter.calls[-1][0] == "export_ai_conversation"

    caps = adapter.capabilities()
    assert all(value is False for value in caps.values())
    assert not hasattr(adapter, "execute_mutation")


def assert_boundary_imports() -> None:
    forbidden_common = ["knowledge_core", "sqlite3", "subprocess", "scripts/kb.py", ".read_text(", ".rglob("]
    for folder in ["gui/adapters", "gui/views", "gui/viewmodels", "gui/shell", "gui/widgets"]:
        for path in (SOURCE_ROOT / folder).glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in forbidden_common:
                assert token not in text, f"{path} contains forbidden boundary token {token!r}"
            if path.name != "service_adapter.py":
                assert "knowledge_app.services" not in text, f"{path} bypasses ServiceAdapter service boundary"


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
        home = adapter.load_home_summary()
        assert home["view_id"] == "home"
        assert home["data"]["index"]["status"] in {"ready", "missing", "partial", "failed", "stale"}
    finally:
        Path.rglob = original_rglob
        Path.read_text = original_read_text
        hashlib.sha256 = original_sha256


def assert_viewmodels_do_not_import_services() -> None:
    modules = [WorkspaceViewModel, WorkspaceCreationViewModel, DashboardViewModel, SearchViewModel, LibraryViewModel, DocumentViewModel, TaskViewModel, SettingsViewModel, AssistantViewModel, ConversationHistoryViewModel]
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
