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
        from PySide6.QtWidgets import QApplication
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
    assert window.minimumWidth() >= 1100
    assert "read-only GUI skeleton" in window.windowTitle()
    window.close()
    app.processEvents()
    print("gui smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
