#!/usr/bin/env python3
"""Qt offscreen checks for the explicit AI conversation history viewer."""

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
        print(f"gui conversation history skipped: PySide6 unavailable: {exc}")
        return 0

    from gui.adapters.service_adapter import ServiceAdapter
    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.main_window import MainWindow
    from gui.styles.theme import apply_light_theme
    from knowledge_app.ai.conversation_persistence_service import ConversationPersistenceService
    from knowledge_app.ai.persistence_service import AIStorageBootstrapService

    app = QApplication.instance() or QApplication(sys.argv)
    apply_light_theme(app)
    with tempfile.TemporaryDirectory(prefix="pkb-gui-history-") as tmp:
        adapter = FakeServiceAdapter()
        window = MainWindow(adapter=adapter, gui_settings_path=Path(tmp) / "gui-settings.json")
        window.show()
        app.processEvents()

        overlay = window.shell.assistant_overlay
        assert not _has_call(adapter, "list_ai_conversations")
        QTest.mouseClick(overlay.launcher, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert overlay.panel.isVisible()
        assert overlay.panel.history_button.objectName() == "assistantHistoryButton"
        assert overlay.panel.history_button.text() == "对话历史"
        assert not _has_call(adapter, "list_ai_conversations")

        QTest.mouseClick(overlay.panel.history_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert adapter.calls[-1][0] == "list_ai_conversations"
        assert adapter.calls[-1][1]["limit"] <= 50
        history_view = overlay.panel.history_view
        assert history_view.isVisible()
        history_list = history_view.findChild(QListWidget, "conversationHistoryList")
        assert history_list is not None
        assert history_list.count() == 2

        first_item = history_list.item(0)
        QTest.mouseClick(history_list.viewport(), Qt.MouseButton.LeftButton, pos=history_list.visualItemRect(first_item).center())
        app.processEvents()
        assert adapter.calls[-1][0] == "get_ai_conversation"
        assert adapter.calls[-1][1]["conversation_id"] == "conv_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        message_text = " ".join(label.text() for label in history_view.findChildren(QLabel, "historyMessageContent"))
        assert "ServiceAdapter" in message_text or "service layer" in message_text
        detail_text = " ".join(label.text() for label in history_view.findChildren(QLabel))
        assert "policy_1" in detail_text
        assert "task_snapshot_1" in detail_text

        QTest.mouseClick(history_view.export_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert adapter.calls[-1][0] == "export_ai_conversation"
        preview = history_view.findChild(QPlainTextEdit, "conversationExportPreview")
        assert preview is not None
        assert '"not_formal_knowledge": true' in preview.toPlainText()
        assert '"formal_search_records": false' in preview.toPlainText()

        original_question = QMessageBox.question
        try:
            QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No)
            QTest.mouseClick(history_view.delete_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert not _has_call(adapter, "delete_ai_conversation")

            QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
            QTest.mouseClick(history_view.delete_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            assert _has_call(adapter, "delete_ai_conversation")
            assert adapter.calls[-1][0] == "list_ai_conversations"
            assert history_list.count() == 1
        finally:
            QMessageBox.question = original_question

        assert not _has_call(adapter, "search")
        assert not _has_call(adapter, "load_recent_tasks")
        window.close()
        app.processEvents()

    with tempfile.TemporaryDirectory(prefix="pkb-gui-history-missing-") as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        adapter = ServiceAdapter(workspace_path=workspace)
        response = adapter.list_ai_conversations(limit=25, offset=0)
        assert response["state"] == "not_bootstrapped"
        assert response["data"]["storage"]["auto_bootstrap_started"] is False
        assert not (workspace / "ai").exists()

    with tempfile.TemporaryDirectory(prefix="pkb-gui-history-service-") as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        workspace_id = AIStorageBootstrapService().bootstrap_storage(workspace, confirmed=True).workspace_id
        service = ConversationPersistenceService()
        conversation = service.create_conversation(workspace, workspace_id, title="Adapter integration")
        service.append_message(
            workspace,
            conversation.conversation_id,
            {
                "message_id": "msg_adapter_1",
                "role": "user",
                "type": "user_text",
                "created_at": "2026-05-22T10:00:00+08:00",
                "content": {"text": "show saved conversation"},
                "citations": [],
                "policy_decision_id": None,
                "task_id": None,
                "metadata": {"not_formal_knowledge": True},
            },
        )
        adapter = ServiceAdapter(workspace_path=workspace)
        listed = adapter.list_ai_conversations(limit=10, offset=0)
        assert listed["state"] == "ready"
        assert listed["data"]["conversations"][0]["message_count"] == 1
        detail = adapter.get_ai_conversation(conversation.conversation_id)
        assert detail["state"] == "ready"
        assert detail["data"]["messages"][0]["content_text"] == "show saved conversation"
        exported = adapter.export_ai_conversation(conversation.conversation_id)
        assert exported["data"]["writes_file"] is False
        deleted = adapter.delete_ai_conversation(conversation.conversation_id)
        assert deleted["data"]["deleted"] is True
        assert adapter.list_ai_conversations(limit=10, offset=0)["state"] == "empty"
        assert not list((workspace / "ai" / "memory").glob("*.jsonl"))

    with tempfile.TemporaryDirectory(prefix="pkb-gui-history-ui-missing-") as tmp:
        adapter = FakeServiceAdapter(ai_storage_bootstrapped=False)
        window = MainWindow(adapter=adapter, gui_settings_path=Path(tmp) / "gui-settings.json")
        window.show()
        app.processEvents()
        overlay = window.shell.assistant_overlay
        QTest.mouseClick(overlay.launcher, Qt.MouseButton.LeftButton)
        app.processEvents()
        QTest.mouseClick(overlay.panel.history_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        state_label = overlay.panel.history_view.findChild(QLabel, "conversationHistoryState")
        assert state_label is not None
        assert "尚未启用 AI 对话记录存储" in state_label.text()
        assert _has_call(adapter, "list_ai_conversations")
        assert not _has_call(adapter, "bootstrap_storage")
        window.close()
        app.processEvents()

    assert_no_direct_file_access()
    print("gui conversation history tests passed")
    return 0


def _has_call(adapter: object, name: str) -> bool:
    return any(item[0] == name for item in getattr(adapter, "calls", []))


def assert_no_direct_file_access() -> None:
    files = [
        SOURCE_ROOT / "gui" / "assistant" / "assistant_panel.py",
        SOURCE_ROOT / "gui" / "assistant" / "assistant_overlay.py",
        SOURCE_ROOT / "gui" / "assistant" / "conversation_history_view.py",
        SOURCE_ROOT / "gui" / "viewmodels" / "conversation_history_viewmodel.py",
    ]
    forbidden = [
        "knowledge_app.ai",
        "knowledge_app.services",
        "knowledge_core",
        "sqlite3",
        "subprocess",
        "scripts/kb.py",
        ".read_text(",
        ".write_text(",
        ".rglob(",
        "MemoryService",
        "SearchService",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} contains forbidden boundary token {token!r}"


if __name__ == "__main__":
    raise SystemExit(main())
