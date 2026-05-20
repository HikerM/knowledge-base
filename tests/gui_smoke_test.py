#!/usr/bin/env python3
"""Qt offscreen smoke test for MainWindow wiring."""

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
        print(f"gui smoke skipped: PySide6 unavailable: {exc}")
        return 0

    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    adapter = FakeServiceAdapter()
    window = MainWindow(adapter=adapter)
    window.show()
    app.processEvents()
    assert window.shell.stack.currentWidget() is window.shell.dashboard_view
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
    assert "v2.0.0-alpha.3" in window.windowTitle()
    nav_labels = [button.text() for button in window.shell.sidebar._buttons.values()]
    for label in ["首页", "搜索", "知识库", "审核", "任务中心", "维护", "设置"]:
        assert label in nav_labels
    all_button_text = " ".join(button.text().lower() for button in window.findChildren(QPushButton))
    for forbidden in ["cancel", "retry", "cleanup", "archive", "delete", "merge", "restore"]:
        assert forbidden not in all_button_text
    window.close()
    app.processEvents()
    print("gui smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
