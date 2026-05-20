"""Knowledge library summary page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class LibraryView(QWidget):
    def __init__(self, library_vm: Any):
        super().__init__()
        self.library_vm = library_vm
        self.summary = QLabel("CategoryService 读取分类和正式层统计。")
        self.load_button = QPushButton("加载只读知识库摘要")
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["category_id", "display_name", "rules", "checklists", "snippets", "edit"])
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(QLabel("知识库"))
        root.addWidget(self.summary)
        root.addWidget(self.load_button)
        root.addWidget(self.table, 1)
        self.load_button.clicked.connect(self.load_summary)

    def load_summary(self) -> None:
        self.render_summary(self.library_vm.load_summary())

    def render_summary(self, model: Dict[str, Any]) -> None:
        data = model.get("data") or {}
        rows = data.get("categories") or []
        totals = data.get("formal_layer_totals") or {}
        self.summary.setText(
            f"{model.get('state')} | rules={totals.get('rules', 0)} "
            f"checklists={totals.get('checklists', 0)} snippets={totals.get('snippets', 0)}"
        )
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            counts = row.get("layer_counts") or {}
            values = [
                row.get("category_id", ""),
                row.get("display_name", ""),
                counts.get("rules", 0),
                counts.get("checklists", 0),
                counts.get("snippets", 0),
                "disabled",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row_index, col, QTableWidgetItem(str(value)))
