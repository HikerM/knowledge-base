#!/usr/bin/env python3
"""Qt offscreen checks for the mock floating AI assistant."""

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
        from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton
    except Exception as exc:  # noqa: BLE001
        print(f"gui AI assistant skipped: PySide6 unavailable: {exc}")
        return 0

    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.main_window import MainWindow
    from gui.styles.theme import apply_light_theme

    app = QApplication.instance() or QApplication(sys.argv)
    apply_light_theme(app)
    with tempfile.TemporaryDirectory(prefix="pkb-gui-ai-") as tmp:
        adapter = FakeServiceAdapter()
        window = MainWindow(adapter=adapter, gui_settings_path=Path(tmp) / "gui-settings.json")
        window.show()
        app.processEvents()

        overlay = window.shell.assistant_overlay
        assert overlay.objectName() == "assistantOverlay"
        assert overlay.launcher.objectName() == "assistantLauncher"
        assert overlay.launcher.accessibleName() == "AI 助手"
        assert overlay.panel.isHidden()

        QTest.mouseClick(overlay.launcher, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert overlay.panel.isVisible()
        assert overlay.panel.composer.input.placeholderText() == "问我的资料，或输入想整理的内容…"
        assert "你好，我是 AI 助手" in overlay.panel.conversation.findChild(QLabel, "messageContent").text()
        for button in [overlay.panel.ask_button, overlay.panel.summary_button, overlay.panel.organize_button, overlay.panel.checklist_button]:
            assert button.isVisible()

        overlay.panel.composer.input.setText("搜索 service layer")
        QTest.mouseClick(overlay.panel.ask_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert adapter.calls[-1][0] == "send_assistant_message_mock"
        assert adapter.calls[-1][1]["intent"] == "search_knowledge"
        user_bubbles = overlay.panel.conversation.findChildren(QFrame, "userMessageBubble")
        assistant_bubbles = overlay.panel.conversation.findChildren(QFrame, "assistantMessageBubble")
        assert user_bubbles
        assert assistant_bubbles
        assert user_bubbles[-1].property("alignment") == "right"
        assert assistant_bubbles[-1].property("alignment") == "left"
        authors = [label.text() for label in overlay.panel.conversation.findChildren(QLabel, "messageAuthor")]
        assert "我" in authors
        assert "AI 助手" in authors
        assert overlay.panel.conversation.findChildren(QFrame, "SearchResultCard")
        assert overlay.panel.conversation.findChildren(QFrame, "CitationCard")

        QTest.mouseClick(overlay.panel.summary_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert adapter.calls[-1][1]["intent"] == "summarize_document"
        assert "请先打开一篇文档" in " ".join(label.text() for label in overlay.panel.conversation.findChildren(QLabel))

        window.shell.current_route = "search"
        window.shell.search_view.reader.render_document(
            {
                "state": "ready",
                "data": {
                    "document_id": "101",
                    "path": "knowledge/09-ai-agent/rules/agentsmd-project-guidance-rule.md",
                    "title": "AGENTS.md Project Guidance Rule",
                    "layer": "rules",
                    "status": "active",
                    "confidence": "medium",
                    "source_type": "official",
                    "review_required": False,
                    "body": "GUI 和 AI 助手必须通过 service layer 工作。",
                },
                "errors": [],
            }
        )
        window.shell.search_view.main_stack.setCurrentWidget(window.shell.search_view.reader)
        QTest.mouseClick(overlay.panel.summary_button, Qt.MouseButton.LeftButton)
        app.processEvents()
        assert overlay.panel.conversation.findChildren(QFrame, "DocumentSummaryCard")

        for text in ["记住我只使用正式层", "给我一个整理计划", "删除这些资料"]:
            overlay.panel.composer.input.setText(text)
            QTest.mouseClick(overlay.panel.composer.send_button, Qt.MouseButton.LeftButton)
            app.processEvents()
        QTest.mouseClick(overlay.panel.checklist_button, Qt.MouseButton.LeftButton)
        app.processEvents()

        expected_cards = [
            "SystemNotice",
            "CitationCard",
            "PlanCard",
            "ConfirmationCard",
            "TaskProgressCard",
            "RiskNoticeCard",
            "MemoryCandidateCard",
            "DocumentSummaryCard",
        ]
        for object_name in expected_cards:
            assert overlay.panel.conversation.findChildren(QFrame, object_name), f"missing {object_name}"

        button_text = " ".join(button.text().lower() for button in window.findChildren(QPushButton))
        for forbidden in ["delete", "archive", "restore", "promote", "删除", "归档", "恢复"]:
            assert forbidden not in button_text

        assert_no_boundary_bypass()
        overlay.panel.close_button.click()
        app.processEvents()
        assert overlay.panel.isHidden()
        window.close()
        app.processEvents()

    print("gui AI assistant tests passed")
    return 0


def assert_no_boundary_bypass() -> None:
    files = list((SOURCE_ROOT / "gui" / "assistant").glob("*.py")) + [SOURCE_ROOT / "gui" / "viewmodels" / "assistant_viewmodel.py"]
    for path in files:
        text = path.read_text(encoding="utf-8")
        for token in ["knowledge_app.services", "knowledge_core", "sqlite3", "subprocess", "scripts/kb.py", ".read_text(", ".rglob("]:
            assert token not in text, f"{path} contains forbidden boundary token {token!r}"


if __name__ == "__main__":
    raise SystemExit(main())
