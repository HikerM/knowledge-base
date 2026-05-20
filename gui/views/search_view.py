"""Formal search page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSplitter, QVBoxLayout, QWidget

from gui.views.document_preview_view import DocumentPreviewView


class SearchView(QWidget):
    def __init__(self, search_vm: Any, document_vm: Any):
        super().__init__()
        self.search_vm = search_vm
        self.document_vm = document_vm
        self.query = QLineEdit()
        self.query.setPlaceholderText("默认只搜索 rules / checklists / snippets")
        self.button = QPushButton("搜索")
        self.results = QListWidget()
        self.preview = DocumentPreviewView()
        self.summary = QLabel("输入查询后读取 SearchService。")

        controls = QHBoxLayout()
        controls.addWidget(self.query, 1)
        controls.addWidget(self.button)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addLayout(controls)
        left_layout.addWidget(self.summary)
        left_layout.addWidget(self.results, 1)
        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(QLabel("搜索"))
        root.addWidget(splitter, 1)

        self.button.clicked.connect(self.run_search)
        self.query.returnPressed.connect(self.run_search)
        self.results.itemActivated.connect(self.open_item)
        self.results.itemClicked.connect(self.open_item)

    def set_query_and_run(self, query: str) -> None:
        self.query.setText(query)
        self.run_search()

    def run_search(self) -> None:
        model = self.search_vm.search(self.query.text())
        self.render_results(model)

    def render_results(self, model: Dict[str, Any]) -> None:
        self.results.clear()
        data = model.get("data") or {}
        rows = data.get("results") or []
        self.summary.setText(f"{model.get('state')} | {len(rows)} result(s) | formal layers only")
        for row in rows:
            item = QListWidgetItem(f"{row.get('title')} [{row.get('layer')} / {row.get('status')}] - {row.get('snippet')}")
            item.setData(Qt.UserRole, row)
            self.results.addItem(item)

    def open_item(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.UserRole) or {}
        model = self.document_vm.open_document(document_id=row.get("document_id"), path=row.get("path"))
        self.preview.render_document(model)
