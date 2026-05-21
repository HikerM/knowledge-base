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
            button.setProperty("navButton", True)
            button.setProperty("routeId", item.route_id)
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

    def set_active(self, route: str, *, emit: bool = True) -> bool:
        if route not in self._buttons or not self._buttons[route].isEnabled():
            return False
        for key, button in self._buttons.items():
            button.setChecked(key == route)
        if emit:
            self.route_changed.emit(route)
        return True

    def clear_active(self) -> None:
        for button in self._buttons.values():
            button.setChecked(False)

    @staticmethod
    def _tooltip(item: NavigationRoute) -> str:
        if item.enabled:
            return f"{item.label} {item.shortcut}"
        return f"{item.label} {item.shortcut} | {item.disabled_reason}"
