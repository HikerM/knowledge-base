"""Application icon helpers for source and PyInstaller runtime."""

from __future__ import annotations

import ctypes
import logging
import sys
from pathlib import Path
from typing import Any

from PySide6.QtGui import QIcon


LOGGER = logging.getLogger(__name__)
APP_USER_MODEL_ID = "HikerM.PersonalKnowledgeBase.GUI"
ICON_RELATIVE_PATHS = (
    Path("assets") / "app-icon" / "app-icon.png",
    Path("assets") / "app-icon" / "app-icon.ico",
)


def configure_windows_app_id() -> None:
    """Set a stable Windows taskbar identity when available."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("failed to set Windows app user model id: %s", exc)


def resource_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root)
    return Path(__file__).resolve().parents[1]


def load_app_icon() -> QIcon:
    for relative_path in ICON_RELATIVE_PATHS:
        icon_path = resource_root() / relative_path
        if not icon_path.exists():
            continue
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            return icon
        LOGGER.warning("application icon could not be loaded: %s", icon_path)
    LOGGER.warning("application icon asset is missing")
    return QIcon()


def apply_application_icon(app: Any) -> QIcon:
    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    return icon


def apply_window_icon(window: Any) -> QIcon:
    icon = load_app_icon()
    if not icon.isNull():
        window.setWindowIcon(icon)
    return icon
