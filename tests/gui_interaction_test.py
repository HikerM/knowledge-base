#!/usr/bin/env python3
"""Qt offscreen interaction checks for the read-only GUI MVP."""

from __future__ import annotations

import os
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication, QPushButton
    except Exception as exc:  # noqa: BLE001
        print(f"gui interaction skipped: PySide6 unavailable: {exc}")
        return 0

    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)

    def build_window() -> tuple[MainWindow, FakeServiceAdapter]:
        adapter = FakeServiceAdapter()
        window = MainWindow(adapter=adapter)
        window.show()
        app.processEvents()
        assert adapter.calls == [("load_workspace_status", {})]
        return window, adapter

    def assert_route(window: MainWindow, route: str) -> None:
        assert window.shell.current_route == route
        assert window.shell.stack.currentWidget() is window.shell.routes[route]
        assert window.shell.sidebar._buttons[route].isChecked()

    def press_shortcut(window: MainWindow, key: Qt.Key) -> None:
        QTest.keyClick(window, key, Qt.KeyboardModifier.AltModifier)
        app.processEvents()

    nav_window, _nav_adapter = build_window()
    assert_route(nav_window, "dashboard")
    assert {route: shortcut.key().toString() for route, shortcut in nav_window.shell.navigation_shortcuts.items()} == {
        "dashboard": "Alt+1",
        "search": "Alt+2",
        "library": "Alt+3",
        "review": "Alt+4",
        "tasks": "Alt+5",
        "maintenance": "Alt+6",
        "settings": "Alt+7",
    }
    assert all(button.shortcut().isEmpty() for button in nav_window.shell.sidebar._buttons.values())

    for route, key in [
        ("dashboard", Qt.Key.Key_1),
        ("search", Qt.Key.Key_2),
        ("library", Qt.Key.Key_3),
        ("tasks", Qt.Key.Key_5),
        ("settings", Qt.Key.Key_7),
    ]:
        press_shortcut(nav_window, key)
        assert_route(nav_window, route)
        nav_window.shell.sidebar._buttons["dashboard"].click()
        app.processEvents()
        assert_route(nav_window, "dashboard")
        nav_window.shell.sidebar._buttons[route].click()
        app.processEvents()
        assert_route(nav_window, route)

    nav_window.shell.sidebar._buttons["search"].click()
    app.processEvents()
    assert_route(nav_window, "search")
    assert not nav_window.shell.navigate("review")
    assert_route(nav_window, "search")
    nav_window.shell.sidebar._buttons["review"].click()
    app.processEvents()
    assert_route(nav_window, "search")
    press_shortcut(nav_window, Qt.Key.Key_4)
    assert_route(nav_window, "search")
    assert "未启用" in nav_window.shell.statusbar.notice.text()

    assert not nav_window.shell.navigate("maintenance")
    assert_route(nav_window, "search")
    nav_window.shell.sidebar._buttons["maintenance"].click()
    app.processEvents()
    assert_route(nav_window, "search")
    press_shortcut(nav_window, Qt.Key.Key_6)
    assert_route(nav_window, "search")
    assert "未启用" in nav_window.shell.statusbar.notice.text()
    nav_window.close()
    app.processEvents()

    window, adapter = build_window()

    window.shell.dashboard_view.refresh_button.click()
    app.processEvents()
    assert adapter.calls[-1][0] == "load_home_summary"

    window.shell.sidebar._buttons["search"].click()
    window.shell.search_view.query.setText("fixture")
    window.shell.search_view.button.click()
    app.processEvents()
    assert adapter.calls[-1][0] == "search"
    assert window.shell.search_view.results.count() == 2
    item = window.shell.search_view.results.item(0)
    window.shell.search_view.results.setCurrentItem(item)
    app.processEvents()
    assert adapter.calls[-1][0] == "open_document"
    assert "只读预览正文" not in window.shell.search_view.preview.summary_card.value_label.text()
    assert "示例正式搜索结果" in window.shell.search_view.preview.summary_card.value_label.text()
    window.shell.search_view.preview_button.click()
    app.processEvents()
    assert not window.shell.search_view.preview.isVisible()
    window.shell.search_view.preview_button.click()
    app.processEvents()
    assert window.shell.search_view.preview.isVisible()
    window.shell.search_view.open_button.click()
    app.processEvents()
    assert adapter.calls[-1][0] == "open_document"
    assert window.shell.search_view.main_stack.currentWidget() is window.shell.search_view.reader
    assert "只读预览正文" in window.shell.search_view.reader.body.toPlainText()
    assert window.shell.search_view.reader.body.isReadOnly()
    window.shell.search_view.reader.return_button.click()
    app.processEvents()
    assert window.shell.search_view.main_stack.currentWidget() is window.shell.search_view.result_page

    window.shell.sidebar._buttons["library"].click()
    app.processEvents()
    assert any(call[0] == "load_library_summary" for call in adapter.calls)
    rows = window.shell.library_view.library_vm.summary["data"]["documents"]
    assert {row["layer"] for row in rows} <= {"rules", "checklists", "snippets"}
    assert window.shell.library_view.table.rowCount() <= 25
    window.shell.library_view.next_button.click()
    app.processEvents()
    assert adapter.calls[-1] == ("load_library_summary", {"limit": 25, "offset": 25, "layer": None, "category_id": None})
    window.shell.library_view.table.selectRow(0)
    app.processEvents()
    assert adapter.calls[-1][0] == "open_document"
    assert "只读预览正文" not in window.shell.library_view.preview.summary_card.value_label.text()
    window.shell.library_view.open_button.click()
    app.processEvents()
    assert adapter.calls[-1][0] == "open_document"
    assert window.shell.library_view.main_stack.currentWidget() is window.shell.library_view.reader
    assert "只读预览正文" in window.shell.library_view.reader.body.toPlainText()
    assert window.shell.library_view.reader.body.isReadOnly()

    window.shell.sidebar._buttons["tasks"].click()
    app.processEvents()
    assert adapter.calls[-1][0] == "load_recent_tasks"
    window.shell.task_view.table.selectRow(0)
    app.processEvents()
    assert adapter.calls[-1][0] == "load_recent_tasks"
    window.shell.task_view.detail_button.click()
    app.processEvents()
    assert adapter.calls[-1][0] == "load_task_detail"
    assert "示例日志" in window.shell.task_view.detail.toPlainText()

    window.shell.sidebar._buttons["settings"].click()
    app.processEvents()
    assert adapter.calls[-1][0] == "load_settings_entry"
    all_button_text = " ".join(button.text().lower() for button in window.findChildren(QPushButton))
    for forbidden in ["cancel", "retry", "cleanup", "archive", "delete", "merge", "restore"]:
        assert forbidden not in all_button_text

    window.close()
    app.processEvents()
    print("gui interaction tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
