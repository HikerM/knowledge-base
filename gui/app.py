"""Application entry for the PySide6 read-only GUI skeleton."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv or sys.argv)
    window = MainWindow()
    window.show()
    auto_close = os.environ.get("PKB_GUI_AUTO_CLOSE_MS")
    if auto_close:
        QTimer.singleShot(max(0, int(auto_close)), app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
