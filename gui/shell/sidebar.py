"""Left-side primary navigation."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout

from gui.shell.navigation import NAVIGATION_ROUTES, NavigationRoute


class Sidebar(QFrame):
    route_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self._buttons: dict[str, QPushButton] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        for item in NAVIGATION_ROUTES:
            button = QPushButton(item.label)
            button.setAccessibleName(item.label)
            button.setEnabled(item.enabled)
            button.setCheckable(item.enabled)
            button.setToolTip(self._tooltip(item))
            if item.enabled:
                button.clicked.connect(lambda checked=False, key=item.route_id: self.set_active(key))
            else:
                button.setCheckable(False)
            self._buttons[item.route_id] = button
            layout.addWidget(button)
        layout.addStretch(1)
        self.setStyleSheet(
            "#sidebar { background: #FFFFFF; border-right: 1px solid #D8DEE8; } "
            "QPushButton { text-align: left; padding: 8px 10px; border: 0; border-radius: 8px; color: #1F2937; } "
            "QPushButton:checked { background: #E7F2FA; color: #0369A1; font-weight: 600; } "
            "QPushButton:disabled { color: #9CA3AF; }"
        )

    def set_active(self, route: str, *, emit: bool = True) -> bool:
        if route not in self._buttons or not self._buttons[route].isEnabled():
            return False
        for key, button in self._buttons.items():
            button.setChecked(key == route)
        if emit:
            self.route_changed.emit(route)
        return True

    @staticmethod
    def _tooltip(item: NavigationRoute) -> str:
        if item.enabled:
            return f"{item.label} {item.shortcut}"
        return f"{item.label} {item.shortcut} | {item.disabled_reason}"
