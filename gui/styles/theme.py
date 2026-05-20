"""Theme application entrypoint."""

from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from gui.styles.qss import build_light_qss
from gui.styles.tokens import COLORS


def apply_light_theme(app: QApplication) -> None:
    """Apply the shared light theme to a QApplication."""
    app.setStyle("Fusion")
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, COLORS.app_bg)
    palette.setColor(QPalette.ColorRole.Base, COLORS.card_bg)
    palette.setColor(QPalette.ColorRole.AlternateBase, COLORS.subtle_bg)
    palette.setColor(QPalette.ColorRole.Text, COLORS.text_primary)
    palette.setColor(QPalette.ColorRole.WindowText, COLORS.text_primary)
    palette.setColor(QPalette.ColorRole.PlaceholderText, COLORS.text_muted)
    palette.setColor(QPalette.ColorRole.Highlight, COLORS.selected)
    palette.setColor(QPalette.ColorRole.HighlightedText, COLORS.text_primary)
    app.setPalette(palette)
    app.setStyleSheet(build_light_qss())

