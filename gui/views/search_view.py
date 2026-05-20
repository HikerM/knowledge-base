"""Formal search page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSplitter, QVBoxLayout, QWidget

from gui.views.document_preview_view import DocumentPreviewView
from gui.widgets.formatters import confidence_label, layer_label, status_label


class SearchView(QWidget):
    def __init__(self, search_vm: Any, document_vm: Any):
        super().__init__()
        self.search_vm = search_vm
        self.document_vm = document_vm
        self.query = QLineEdit()
        self.query.setPlaceholderText("搜索正式知识：规则、清单、片段")
        self.button = QPushButton("搜索")
        self.results = QListWidget()
        self.preview = DocumentPreviewView()
        self.summary = QLabel("输入查询词后搜索正式层索引。")

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
        self.render_results(self.search_vm.search(self.query.text()))

    def render_results(self, model: Dict[str, Any]) -> None:
        self.results.clear()
        data = model.get("data") or {}
        rows = data.get("results") or []
        state = str(model.get("state") or "")
        index_status = str(data.get("index_status") or "")
        if not str(data.get("query") or "").strip():
            self.summary.setText("请输入查询词；空查询不会访问搜索服务。")
        elif index_status == "missing":
            self.summary.setText("索引缺失，当前没有可搜索结果。")
        elif model.get("errors"):
            self.summary.setText(self._error_text(model))
        elif not rows:
            self.summary.setText("没有搜索结果。")
        else:
            page = data.get("page") or {}
            self.summary.setText(f"状态：{status_label(state)}；本页 {page.get('count', len(rows))} 条；仅搜索正式层。")
        for row in rows:
            item = QListWidgetItem(self._row_text(row))
            item.setData(Qt.UserRole, row)
            item.setToolTip(str(row.get("path") or ""))
            self.results.addItem(item)

    def open_item(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.UserRole) or {}
        model = self.document_vm.open_document(document_id=row.get("document_id"), path=row.get("path"))
        self.preview.render_document(model)

    @staticmethod
    def _row_text(row: Dict[str, Any]) -> str:
        meta = f"{layer_label(row.get('layer'))} | {status_label(row.get('status'))} | 可信度 {confidence_label(row.get('confidence'))} | 来源 {row.get('source_type') or '未知'}"
        return f"{row.get('title') or '未命名文档'}\n{row.get('snippet') or '无摘要'}\n{meta}\n{row.get('path') or ''}"

    @staticmethod
    def _error_text(model: Dict[str, Any]) -> str:
        errors = "; ".join(item.get("message", "") for item in model.get("errors", []))
        return f"搜索失败：{errors or '服务不可用'}"
