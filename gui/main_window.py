"""MainWindow assembly for the PySide6 GUI skeleton."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QMainWindow

from gui import APP_NAME, PHASE
from gui.adapters.service_adapter import ServiceAdapter
from gui.shell.app_shell import AppShell


class MainWindow(QMainWindow):
    """Top-level window that only mounts the AppShell."""

    def __init__(self, adapter: Any | None = None):
        super().__init__()
        self.adapter = adapter or ServiceAdapter()
        self.shell = AppShell(self.adapter)
        self.setCentralWidget(self.shell)
        self.setWindowTitle(f"{APP_NAME} - {PHASE}")
        self.resize(1280, 800)
        self.setMinimumSize(1100, 720)
