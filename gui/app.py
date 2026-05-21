"""Application entry for the PySide6 read-only GUI."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from gui import APP_NAME, ORGANIZATION_NAME, PRODUCT_NAME
from gui.app_icon import apply_application_icon, configure_windows_app_id
from gui.main_window import MainWindow
from gui.styles.theme import apply_light_theme


def _default_log_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "PersonalKnowledgeBase" / "logs"
    return Path.home() / ".personal-knowledge-base" / "logs"


def _configure_logging() -> Path:
    log_dir = _default_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "pkb-gui.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger(__name__).info("starting GUI")
    return log_path


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--help", action="store_true")
    parsed, qt_args = parser.parse_known_args(argv[1:])
    if parsed.help:
        print("Usage: python -m gui.app [--workspace PATH] [Qt options]")
        raise SystemExit(0)
    return parsed, [argv[0], *qt_args]


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv or sys.argv)
    parsed, qt_argv = _parse_args(raw_argv)
    workspace_path = parsed.workspace.resolve() if parsed.workspace else None
    log_path = _configure_logging()
    logging.getLogger(__name__).info("workspace=%s log=%s", workspace_path, log_path)
    configure_windows_app_id()
    app = QApplication(qt_argv)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setApplicationName(PRODUCT_NAME)
    app.setApplicationDisplayName(APP_NAME)
    apply_light_theme(app)
    apply_application_icon(app)
    window = MainWindow(workspace_path=workspace_path, log_path=log_path)
    app.aboutToQuit.connect(window.persist_window_settings)
    window.show()
    auto_close = os.environ.get("PKB_GUI_AUTO_CLOSE_MS")
    if auto_close:
        QTimer.singleShot(max(0, int(auto_close)), app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
