#!/usr/bin/env python3
"""Checks for local GUI window settings persistence."""

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
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # noqa: BLE001
        print(f"gui settings skipped: PySide6 unavailable: {exc}")
        return 0

    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.main_window import MainWindow
    from gui.settings.gui_settings import (
        DEFAULT_HEIGHT,
        DEFAULT_WIDTH,
        MIN_HEIGHT,
        MIN_WIDTH,
        GuiWindowSettings,
        load_window_settings,
        reset_window_settings,
        save_window_settings,
    )

    app = QApplication.instance() or QApplication(sys.argv)
    with tempfile.TemporaryDirectory(prefix="pkb-gui-settings-") as tmp:
        settings_path = Path(tmp) / "gui-settings.json"
        default_settings = load_window_settings(settings_path)
        assert default_settings.window_width == DEFAULT_WIDTH
        assert default_settings.window_height == DEFAULT_HEIGHT
        assert default_settings.maximized is False

        saved = GuiWindowSettings(window_width=1000, window_height=700, window_x=40, window_y=50, maximized=True, last_opened_workspace="D:/workspace")
        assert save_window_settings(saved, settings_path)
        reloaded = load_window_settings(settings_path)
        assert reloaded.window_width == 1000
        assert reloaded.window_height == 700
        assert reloaded.window_x == 40
        assert reloaded.window_y == 50
        assert reloaded.maximized is True
        assert reloaded.last_opened_workspace == "D:/workspace"

        reset_window_settings(settings_path)
        assert not settings_path.exists()

        window = MainWindow(adapter=FakeServiceAdapter(), workspace_path=SOURCE_ROOT, gui_settings_path=settings_path)
        window.resize(1040, 720)
        window.show()
        app.processEvents()
        assert window.minimumWidth() == MIN_WIDTH
        assert window.minimumHeight() == MIN_HEIGHT
        assert window.persist_window_settings()
        window.close()
        app.processEvents()
        written = load_window_settings(settings_path)
        assert written.window_width >= MIN_WIDTH
        assert written.window_height >= MIN_HEIGHT
        assert written.last_opened_workspace == str(SOURCE_ROOT)

    print("gui settings tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
