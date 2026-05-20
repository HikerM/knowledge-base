"""Left-side primary navigation."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout


class Sidebar(QFrame):
    route_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self._buttons: dict[str, QPushButton] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        for route, label, enabled in [
            ("dashboard", "首页", True),
            ("search", "搜索", True),
            ("library", "知识库", True),
            ("review", "审核", False),
            ("tasks", "任务中心", True),
            ("maintenance", "维护", False),
            ("settings", "设置", True),
        ]:
            button = QPushButton(label)
            button.setEnabled(enabled)
            button.setCheckable(enabled)
            if enabled:
                button.clicked.connect(lambda checked=False, key=route: self.set_active(key))
            else:
                button.setToolTip("Phase 1 read-only skeleton 中暂不开放")
            self._buttons[route] = button
            layout.addWidget(button)
        layout.addStretch(1)
        self.setStyleSheet(
            "#sidebar { background: #FFFFFF; border-right: 1px solid #D8DEE8; } "
            "QPushButton { text-align: left; padding: 8px 10px; border: 0; border-radius: 8px; color: #1F2937; } "
            "QPushButton:checked { background: #E7F2FA; color: #0369A1; font-weight: 600; } "
            "QPushButton:disabled { color: #9CA3AF; }"
        )

    def set_active(self, route: str) -> None:
        if route not in self._buttons or not self._buttons[route].isEnabled():
            return
        for key, button in self._buttons.items():
            button.setChecked(key == route)
        self.route_changed.emit(route)
