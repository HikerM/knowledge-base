#!/usr/bin/env python3
"""Qt offscreen checks for the explicit AI memory settings GUI."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QMessageBox, QPlainTextEdit, QPushButton
    except Exception as exc:  # noqa: BLE001
        print(f"gui memory settings skipped: PySide6 unavailable: {exc}")
        return 0

    from gui.adapters.service_adapter import ServiceAdapter
    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.main_window import MainWindow
    from gui.viewmodels.memory_settings_viewmodel import MemorySettingsViewModel
    from knowledge_app.ai.memory_service import MemoryService
    from knowledge_app.ai.retention_models import PrivacyModePolicy, RetentionPolicy

    app = QApplication.instance() or QApplication(sys.argv)
    assert_viewmodel_memory_flow()
    assert_privacy_mode_blocks_candidate_save()
    assert_real_adapter_does_not_write_disk(ServiceAdapter, MemoryService)
    assert_no_direct_gui_boundary_access()

    with tempfile.TemporaryDirectory(prefix="pkb-gui-memory-") as tmp:
        adapter = FakeServiceAdapter()
        window = MainWindow(adapter=adapter, gui_settings_path=Path(tmp) / "gui-settings.json")
        window.show()
        app.processEvents()

        assert adapter.calls == [("load_workspace_status", {})]
        assert not _has_call(adapter, "list_memory_candidates")
        window.shell.sidebar._buttons["settings"].click()
        app.processEvents()
        assert adapter.calls[-1][0] == "load_settings_entry"
        assert not _has_call(adapter, "list_memory_candidates")

        entry_button = window.findChild(QPushButton, "memorySettingsEntryButton")
        assert entry_button is not None
        assert entry_button.text() == "AI 记忆"
        QTest.mouseClick(entry_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        memory_view = window.shell.settings_view.memory_view
        assert memory_view.isVisible()
        mode_notice = memory_view.findChild(QLabel, "memoryModeNotice")
        assert mode_notice is not None
        assert "内存模拟模式" in mode_notice.text()
        safety_text = " ".join(label.text() for label in memory_view.findChildren(QLabel))
        for expected in ["长期记忆必须由你确认后才会保存", "不会进入搜索规则", "当前不会发送到云端", "删除为删除记录"]:
            assert expected in safety_text
        assert not _has_call(adapter, "list_memory_candidates")

        load_candidates = memory_view.findChild(QPushButton, "memoryLoadCandidatesButton")
        assert load_candidates is not None
        QTest.mouseClick(load_candidates, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert adapter.calls[-1][0] == "list_memory_candidates"
        candidates = memory_view.findChild(QListWidget, "memoryCandidatesList")
        assert candidates is not None
        candidate_text = _list_text(candidates)
        for expected_status in ["pending", "accepted", "rejected", "expired"]:
            assert expected_status in candidate_text
        assert "source_message_ids" in candidate_text

        original_question = QMessageBox.question
        try:
            pending_item = _find_item(candidates, "用户偏好简洁")
            candidates.setCurrentItem(pending_item)
            app.processEvents()
            QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No)
            QTest.mouseClick(memory_view.accept_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert not _has_call(adapter, "accept_memory_candidate")
            state_label = memory_view.findChild(QLabel, "memoryStateLabel")
            assert state_label is not None
            assert "需要明确确认" in state_label.text()

            pending_item = _find_item(candidates, "用户偏好简洁")
            candidates.setCurrentItem(pending_item)
            app.processEvents()
            QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
            QTest.mouseClick(memory_view.accept_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert adapter.calls[-1][0] == "accept_memory_candidate"
            assert "不会写入磁盘" in state_label.text()

            QTest.mouseClick(load_candidates, Qt.MouseButton.LeftButton)
            app.processEvents()
            blocked_item = _find_item(candidates, "高敏感信息")
            candidates.setCurrentItem(blocked_item)
            app.processEvents()
            QTest.mouseClick(memory_view.accept_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert adapter.calls[-1][0] == "accept_memory_candidate"
            assert "blocked" in state_label.text()

            adapter.memory_service.create_candidate(
                conversation_id="conv_ui_reject",
                workspace_id=adapter.memory_workspace_id,
                proposed_text="用于 GUI 拒绝测试。",
                type="preference",
                source_message_ids=["msg_ui_reject"],
            )
            QTest.mouseClick(load_candidates, Qt.MouseButton.LeftButton)
            app.processEvents()
            reject_item = _find_item(candidates, "用于 GUI 拒绝测试")
            candidates.setCurrentItem(reject_item)
            app.processEvents()
            QTest.mouseClick(memory_view.reject_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert adapter.calls[-1][0] == "reject_memory_candidate"
            assert "已拒绝" in state_label.text()

            load_memories = memory_view.findChild(QPushButton, "memoryLoadMemoriesButton")
            assert load_memories is not None
            QTest.mouseClick(load_memories, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert adapter.calls[-1][0] == "list_saved_memories"
            memories = memory_view.findChild(QListWidget, "memorySavedList")
            assert memories is not None
            memory_text = _list_text(memories)
            assert "active" in memory_text
            assert "disabled" in memory_text
            assert "deleted" in memory_text
            assert "已删除，仅保留删除记录" in memory_text
            assert "内容已删除" in memory_text

            active_item = _find_item(memories, "active")
            memories.setCurrentItem(active_item)
            app.processEvents()
            QTest.mouseClick(memory_view.disable_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert adapter.calls[-1][0] == "disable_memory"

            deletable_item = _find_item(memories, "disabled")
            memories.setCurrentItem(deletable_item)
            app.processEvents()
            QTest.mouseClick(memory_view.delete_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert adapter.calls[-1][0] == "delete_memory"
            assert "内容已删除" in _list_text(memories)
        finally:
            QMessageBox.question = original_question

        refresh = memory_view.findChild(QPushButton, "memoryRefreshPreviewsButton")
        assert refresh is not None
        QTest.mouseClick(refresh, Qt.MouseButton.LeftButton)
        app.processEvents()
        backup_preview = memory_view.findChild(QPlainTextEdit, "memoryBackupPreview")
        export_preview = memory_view.findChild(QPlainTextEdit, "memoryExportPreview")
        privacy_status = memory_view.findChild(QPlainTextEdit, "memoryPrivacyStatus")
        assert backup_preview is not None
        assert export_preview is not None
        assert privacy_status is not None
        assert "include_ai_memory=false" in backup_preview.toPlainText()
        assert "include_ai_drafts=false" in backup_preview.toPlainText()
        assert "writes_file=false" in export_preview.toPlainText()
        assert "cloud_send_allowed=false" in export_preview.toPlainText()
        assert "formal_search_records=false" in export_preview.toPlainText()
        assert "privacy_mode=false" in privacy_status.toPlainText()

        assert not _has_call(adapter, "search")
        assert not _has_call(adapter, "load_library_summary")
        assert not _has_call(adapter, "open_document")
        window.close()
        app.processEvents()

    with tempfile.TemporaryDirectory(prefix="pkb-gui-memory-privacy-") as tmp:
        adapter = FakeServiceAdapter(memory_privacy_mode=True)
        window = MainWindow(adapter=adapter, gui_settings_path=Path(tmp) / "gui-settings.json")
        window.show()
        app.processEvents()
        window.shell.sidebar._buttons["settings"].click()
        app.processEvents()
        window.shell.settings_view.open_memory_settings()
        memory_view = window.shell.settings_view.memory_view
        memory_view.refresh_previews()
        assert "禁止保存 AI 记忆" in memory_view.privacy_status.toPlainText()
        memory_view.load_candidates()
        pending_item = _find_item(memory_view.candidates_list, "用户偏好简洁")
        memory_view.candidates_list.setCurrentItem(pending_item)
        app.processEvents()
        original_question = QMessageBox.question
        try:
            QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
            memory_view.accept_selected_candidate()
            app.processEvents()
            assert "privacy mode" in memory_view.state_label.text() or "隐私模式" in memory_view.state_label.text()
        finally:
            QMessageBox.question = original_question
        window.close()
        app.processEvents()

    print("gui memory settings tests passed")
    return 0


def assert_viewmodel_memory_flow() -> None:
    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.viewmodels.memory_settings_viewmodel import MemorySettingsViewModel

    adapter = FakeServiceAdapter()
    vm = MemorySettingsViewModel(adapter)
    initial = vm.snapshot()
    assert initial["state"] == "idle"
    assert initial["mode"]["writes_file"] is False
    assert not _has_call(adapter, "list_memory_candidates")

    candidates = vm.load_candidates()
    assert candidates["candidates"]
    assert {row["status"] for row in candidates["candidates"]} >= {"pending", "accepted", "rejected", "expired"}
    assert adapter.calls[-1] == ("list_memory_candidates", {"status": None})

    pending_id = next(row["candidate_id"] for row in candidates["candidates"] if row["status"] == "pending" and row["sensitivity"] != "blocked")
    before_calls = list(adapter.calls)
    unconfirmed = vm.accept_candidate(pending_id, confirmed=False)
    assert "需要明确确认" in unconfirmed["message"]
    assert adapter.calls == before_calls
    accepted = vm.accept_candidate(pending_id, confirmed=True)
    assert accepted["memories"]
    assert adapter.calls[-1][0] == "accept_memory_candidate"

    adapter = FakeServiceAdapter()
    vm = MemorySettingsViewModel(adapter)
    candidates = vm.load_candidates()
    blocked_id = next(row["candidate_id"] for row in candidates["candidates"] if row["sensitivity"] == "blocked")
    blocked = vm.accept_candidate(blocked_id, confirmed=True)
    assert "blocked" in blocked["message"]
    assert not any(row["sensitivity"] == "blocked" for row in vm.memories)

    reject_candidate = adapter.memory_service.create_candidate(
        conversation_id="conv_vm_reject",
        workspace_id=adapter.memory_workspace_id,
        proposed_text="用于 ViewModel 拒绝测试。",
        type="preference",
        source_message_ids=["msg_vm_reject"],
    )
    rejected = vm.reject_candidate(reject_candidate.candidate_id)
    assert any(row["candidate_id"] == reject_candidate.candidate_id and row["status"] == "rejected" for row in rejected["candidates"])

    memories = vm.load_memories()
    assert {row["status"] for row in memories["memories"]} >= {"active", "disabled", "deleted"}
    active_id = next(row["memory_id"] for row in memories["memories"] if row["status"] == "active")
    disabled = vm.disable_memory(active_id)
    assert any(row["memory_id"] == active_id and row["status"] == "disabled" for row in disabled["memories"])
    deleted = vm.delete_memory(active_id, confirmed=True)
    assert any(row["memory_id"] == active_id and row["status"] == "deleted" and row["text_redacted"] is True for row in deleted["memories"])
    cleared = vm.clear_memory(confirmed=True)
    assert all(row["status"] == "deleted" for row in cleared["memories"])

    previews = vm.refresh_previews()
    assert previews["backup_preview"]["default_backup"]["include_ai_memory"] is False
    assert previews["backup_preview"]["default_backup"]["include_ai_drafts"] is False
    assert previews["export_preview"]["writes_file"] is False
    assert previews["export_preview"]["cloud_send_allowed"] is False
    assert previews["export_preview"]["includes"]["formal_search_records"] is False
    assert previews["privacy_status"]["formal_search_records"] is False


def assert_privacy_mode_blocks_candidate_save() -> None:
    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.viewmodels.memory_settings_viewmodel import MemorySettingsViewModel

    adapter = FakeServiceAdapter(memory_privacy_mode=True)
    vm = MemorySettingsViewModel(adapter)
    status = vm.refresh_previews()
    assert status["privacy_status"]["memory_save_allowed"] is False
    assert "禁止保存 AI 记忆" in status["save_blocked_reason"]
    candidates = vm.load_candidates()
    pending_id = next(row["candidate_id"] for row in candidates["candidates"] if row["status"] == "pending")
    result = vm.accept_candidate(pending_id, confirmed=True)
    assert "privacy mode" in result["message"] or "隐私模式" in result["message"]


def assert_real_adapter_does_not_write_disk(service_adapter_cls: object, memory_service_cls: object) -> None:
    with tempfile.TemporaryDirectory(prefix="pkb-memory-adapter-") as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        service = memory_service_cls()
        adapter = service_adapter_cls(workspace_path=workspace, memory_service=service)
        workspace_id = adapter._ai_workspace_id()
        candidate = service.create_candidate(
            conversation_id="conv_no_disk",
            workspace_id=workspace_id,
            proposed_text="用户偏好测试前先说明命令。",
            type="workflow",
            source_message_ids=["msg_no_disk"],
        )
        listed = adapter.list_memory_candidates()
        assert listed["state"] == "ready"
        accepted = adapter.accept_memory_candidate(candidate.candidate_id, confirmed=True)
        assert accepted["state"] == "ready"
        saved = adapter.list_saved_memories()
        assert saved["data"]["memories"][0]["not_formal_knowledge"] is True
        assert adapter.preview_memory_backup()["data"]["default_backup"]["include_ai_memory"] is False
        assert adapter.preview_memory_export()["data"]["includes"]["formal_search_records"] is False
        assert adapter.get_memory_privacy_status()["data"]["cloud_send_allowed"] is False
        assert not (workspace / "ai").exists()
        assert not list(workspace.rglob("*.jsonl"))
        assert not list(workspace.rglob("*.sqlite"))


def assert_no_direct_gui_boundary_access() -> None:
    files = [
        SOURCE_ROOT / "gui" / "views" / "memory_settings_view.py",
        SOURCE_ROOT / "gui" / "viewmodels" / "memory_settings_viewmodel.py",
    ]
    forbidden = [
        "knowledge_app.services",
        "knowledge_core",
        "sqlite3",
        "subprocess",
        "scripts/kb.py",
        ".read_text(",
        ".write_text(",
        ".rglob(",
        "SearchService",
        "OpenAI",
        "ModelScope",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} contains forbidden boundary token {token!r}"


def _has_call(adapter: object, name: str) -> bool:
    return any(item[0] == name for item in getattr(adapter, "calls", []))


def _list_text(widget: object) -> str:
    return "\n".join(widget.item(index).text() for index in range(widget.count()))


def _find_item(widget: object, needle: str):
    for index in range(widget.count()):
        item = widget.item(index)
        if needle in item.text():
            return item
    raise AssertionError(f"list item containing {needle!r} not found")


if __name__ == "__main__":
    raise SystemExit(main())
