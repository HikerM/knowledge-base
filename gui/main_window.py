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

    def __init__(self, adapter: Any | None = None, workspace_path: Path | str | None = None, gui_settings_path: Path | str | None = None, log_path: Path | str | None = None):
        super().__init__()
        self.gui_settings_path = resolve_settings_path(gui_settings_path)
        self.window_settings = load_window_settings(self.gui_settings_path)
        self.log_path = Path(log_path).resolve() if log_path else None
        self.workspace_path = self._resolve_initial_workspace(adapter, workspace_path)
        self.adapter = adapter or (ServiceAdapter(workspace_path=self.workspace_path) if self.workspace_path else None)
        self.shell = AppShell(
            self.adapter,
            gui_settings_provider=self.gui_settings_snapshot,
            reset_window_layout=self.reset_window_layout,
            workspace_selected=bool(self.workspace_path),
            select_workspace=self.select_workspace,
            unavailable_workspace=self._unavailable_last_workspace(workspace_path),
        )
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
            "last_opened_workspace": str(self.workspace_path) if self.workspace_path else self.window_settings.last_opened_workspace,
            "current_workspace": str(self.workspace_path) if self.workspace_path else "",
            "log_path": str(self.log_path) if self.log_path else "",
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
            last_opened_workspace=str(self.workspace_path) if self.workspace_path else self.window_settings.last_opened_workspace,
        )
        return save_window_settings(self.window_settings, self.gui_settings_path)

    def select_workspace(self, workspace_path: Path | str) -> tuple[bool, str]:
        path = Path(workspace_path).expanduser()
        if not path.exists() or not path.is_dir():
            return False, "这个文件夹不可用，请选择一个存在的知识库文件夹。"
        self.workspace_path = path.resolve()
        self.adapter = ServiceAdapter(workspace_path=self.workspace_path)
        self.window_settings.last_opened_workspace = str(self.workspace_path)
        self.persist_window_settings()
        self.shell.set_adapter(self.adapter)
        return True, ""

    def _resolve_initial_workspace(self, adapter: Any | None, workspace_path: Path | str | None) -> Path | None:
        if adapter is not None and workspace_path is None:
            return Path.cwd().resolve()
        if workspace_path is not None:
            return Path(workspace_path).resolve()
        remembered = self.window_settings.last_opened_workspace
        if remembered:
            remembered_path = Path(remembered).expanduser()
            if remembered_path.exists() and remembered_path.is_dir():
                return remembered_path.resolve()
        return None

    def _unavailable_last_workspace(self, explicit_workspace: Path | str | None) -> str:
        if explicit_workspace is not None:
            return ""
        remembered = self.window_settings.last_opened_workspace
        if not remembered:
            return ""
        remembered_path = Path(remembered).expanduser()
        return remembered if not remembered_path.exists() else ""

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
