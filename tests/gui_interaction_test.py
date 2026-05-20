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
        from PySide6.QtWidgets import QApplication, QPushButton
    except Exception as exc:  # noqa: BLE001
        print(f"gui interaction skipped: PySide6 unavailable: {exc}")
        return 0

    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    adapter = FakeServiceAdapter()
    window = MainWindow(adapter=adapter)
    window.show()
    app.processEvents()

    window.shell.sidebar.set_active("search")
    window.shell.search_view.query.setText("fixture")
    window.shell.search_view.button.click()
    app.processEvents()
    assert adapter.calls[-1][0] == "search"
    assert window.shell.search_view.results.count() == 2
    item = window.shell.search_view.results.item(0)
    window.shell.search_view.results.itemActivated.emit(item)
    app.processEvents()
    assert adapter.calls[-1][0] == "open_document"
    assert "Read-only preview body" in window.shell.search_view.preview.body.toPlainText()

    window.shell.sidebar.set_active("library")
    app.processEvents()
    assert any(call[0] == "load_library_summary" for call in adapter.calls)
    rows = window.shell.library_view.library_vm.summary["data"]["documents"]
    assert {row["layer"] for row in rows} <= {"rules", "checklists", "snippets"}
    assert window.shell.library_view.table.rowCount() <= 50

    window.shell.sidebar.set_active("tasks")
    app.processEvents()
    assert adapter.calls[-1][0] == "load_recent_tasks"
    window.shell.task_view.table.selectRow(0)
    app.processEvents()
    assert adapter.calls[-1][0] == "load_task_detail"
    assert "fixture log" in window.shell.task_view.detail.toPlainText()

    window.shell.sidebar.set_active("settings")
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
