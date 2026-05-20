"""Loading state widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LoadingState(QWidget):
    def __init__(self, message: str = "正在加载只读数据..."):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        label = QLabel(message)
        label.setObjectName("loadingLabel")
        layout.addWidget(label)
        self.setStyleSheet("#loadingLabel { color: #5B6678; }")
