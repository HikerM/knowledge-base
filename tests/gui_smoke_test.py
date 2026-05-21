#!/usr/bin/env python3
"""Qt offscreen smoke test for MainWindow wiring."""

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
        from PySide6.QtWidgets import QApplication, QPushButton
    except Exception as exc:  # noqa: BLE001
        print(f"gui smoke skipped: PySide6 unavailable: {exc}")
        return 0

    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.app_icon import load_app_icon
    from gui.main_window import MainWindow
    from gui.styles.theme import apply_light_theme
    from gui.widgets.card import Card
    from gui.widgets.controls import Button, SearchInput, Select
    from gui.widgets.status_chip import StatusChip

    app = QApplication.instance() or QApplication(sys.argv)
    apply_light_theme(app)
    assert "QFrame#topbar" in app.styleSheet()
    assert not load_app_icon().isNull()
    chip = StatusChip("索引：就绪", "ready")
    assert chip.text() == "索引：就绪"
    assert SearchInput("搜索").placeholderText() == "搜索"
    assert isinstance(Select(), Select)
    assert Button("按钮", "secondary").property("buttonRole") == "secondary"
    with tempfile.TemporaryDirectory(prefix="pkb-gui-smoke-") as tmp:
        first_run_window = MainWindow(gui_settings_path=Path(tmp) / "first-run-settings.json")
        first_run_window.show()
        app.processEvents()
        assert first_run_window.shell.current_route == "workspace_gate"
        assert first_run_window.shell.stack.currentWidget() is first_run_window.shell.workspace_gate_view
        assert first_run_window.shell.workspace_gate_view.select_button.text() == "打开已有知识库"
        first_run_window.close()
        app.processEvents()

        adapter = FakeServiceAdapter()
        window = MainWindow(adapter=adapter, gui_settings_path=Path(tmp) / "gui-settings.json")
        window.show()
        app.processEvents()
        assert window.shell.stack.currentWidget() is window.shell.dashboard_view
        assert window.shell.sidebar._buttons["dashboard"].isChecked()
        assert window.shell.sidebar._buttons["dashboard"].property("navButton") is True
        assert all(isinstance(card, Card) for card in window.shell.dashboard_view.cards.values())
        assert {"workspace", "index", "documents", "backup", "tasks"} <= set(window.shell.dashboard_view.cards)
        window.shell.search_view.render_results(
            {
                "state": "empty",
                "data": {"query": "none", "results": [], "index_status": "ready", "page": {"limit": 25, "offset": 0, "count": 0, "has_more": False}},
                "errors": [],
            }
        )
        assert not window.shell.search_view.empty_state.isHidden()
        assert adapter.calls == [("load_workspace_status", {})]
        startup_forbidden = {
            "load_recent_tasks",
            "load_home_summary",
            "search",
            "load_library_summary",
            "open_document",
            "load_task_detail",
            "load_settings_entry",
        }
        assert not any(call[0] in startup_forbidden for call in adapter.calls)
        assert window.minimumWidth() >= 920
        assert "v2.0.0-beta.8" in window.windowTitle()
        assert not window.windowIcon().isNull()
        nav_labels = [button.text() for button in window.shell.sidebar._buttons.values()]
        for label in ["首页", "搜索", "知识库", "审核", "任务中心", "维护", "设置"]:
            assert label in nav_labels
        all_button_text = " ".join(button.text().lower() for button in window.findChildren(QPushButton))
        for forbidden in ["cancel", "retry", "cleanup", "archive", "delete", "merge", "restore", "rss", "vector", "ai", "归档", "删除", "合并", "恢复"]:
            assert forbidden not in all_button_text
        window.close()
        app.processEvents()
    print("gui smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
