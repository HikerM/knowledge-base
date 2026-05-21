"""MainWindow assembly for the PySide6 GUI skeleton."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMainWindow

from gui.app_icon import apply_window_icon
from gui import APP_NAME, PHASE
from gui.adapters.service_adapter import ServiceAdapter
from gui.settings.gui_settings import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    MIN_HEIGHT,
    MIN_WIDTH,
    GuiWindowSettings,
    load_window_settings,
    reset_window_settings,
    resolve_settings_path,
    save_window_settings,
)
from gui.shell.app_shell import AppShell


class MainWindow(QMainWindow):
    """Top-level window that only mounts the AppShell."""

    def __init__(self, adapter: Any | None = None, workspace_path: Path | str | None = None, gui_settings_path: Path | str | None = None):
        super().__init__()
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else Path.cwd().resolve()
        self.gui_settings_path = resolve_settings_path(gui_settings_path)
        self.window_settings = load_window_settings(self.gui_settings_path)
        self.adapter = adapter or ServiceAdapter(workspace_path=self.workspace_path)
        self.shell = AppShell(self.adapter, gui_settings_provider=self.gui_settings_snapshot, reset_window_layout=self.reset_window_layout)
        self.setCentralWidget(self.shell)
        self.setWindowTitle(f"{APP_NAME} - {PHASE}")
        apply_window_icon(self)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self._restore_window_geometry()

    def gui_settings_snapshot(self) -> dict[str, Any]:
        geometry = self.normalGeometry() if self.isMaximized() and self.normalGeometry().isValid() else self.geometry()
        return {
            "settings_path": str(self.gui_settings_path),
            "window_width": geometry.width(),
            "window_height": geometry.height(),
            "window_x": geometry.x(),
            "window_y": geometry.y(),
            "maximized": self.isMaximized(),
            "last_opened_workspace": str(self.workspace_path),
            "schema_version": self.window_settings.schema_version,
        }

    def reset_window_layout(self) -> tuple[bool, str]:
        ok = reset_window_settings(self.gui_settings_path)
        self.window_settings = GuiWindowSettings(last_opened_workspace=str(self.workspace_path))
        self._restore_window_geometry()
        message = "窗口布局已重置" if ok else "窗口布局重置失败，请查看日志"
        return ok, message

    def persist_window_settings(self) -> bool:
        geometry = self.normalGeometry() if self.isMaximized() and self.normalGeometry().isValid() else self.geometry()
        self.window_settings = GuiWindowSettings(
            window_width=geometry.width(),
            window_height=geometry.height(),
            window_x=geometry.x(),
            window_y=geometry.y(),
            maximized=self.isMaximized(),
            last_opened_workspace=str(self.workspace_path),
        )
        return save_window_settings(self.window_settings, self.gui_settings_path)

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        self.persist_window_settings()
        super().closeEvent(event)

    def _restore_window_geometry(self) -> None:
        available = self._available_geometry()
        width = min(max(self.window_settings.window_width, MIN_WIDTH), max(available.width(), MIN_WIDTH))
        height = min(max(self.window_settings.window_height, MIN_HEIGHT), max(available.height(), MIN_HEIGHT))
        x = self.window_settings.window_x
        y = self.window_settings.window_y
        rect = QRect(int(x or 0), int(y or 0), width, height)
        if x is None or y is None or not self._rect_on_screen(rect):
            rect.moveCenter(available.center())
        if not self.window_settings.maximized and self.isMaximized():
            self.showNormal()
        self.setGeometry(rect)
        if self.window_settings.maximized:
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    @staticmethod
    def _available_geometry() -> QRect:
        screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen else QRect(0, 0, DEFAULT_WIDTH, DEFAULT_HEIGHT)

    @staticmethod
    def _rect_on_screen(rect: QRect) -> bool:
        return any(screen.availableGeometry().contains(rect.center()) for screen in QGuiApplication.screens())
