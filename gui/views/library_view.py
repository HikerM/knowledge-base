"""Knowledge library summary page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from gui.views.document_preview_view import DocumentPreviewView
from gui.widgets.formatters import confidence_label, layer_label, status_label


class LibraryView(QWidget):
    def __init__(self, library_vm: Any, document_vm: Any):
        super().__init__()
        self.library_vm = library_vm
        self.document_vm = document_vm
        self._loading_filters = False
        self.summary = QLabel("正在读取正式层知识库摘要。")
        self.layer_filter = QComboBox()
        self.layer_filter.addItem("全部正式层", None)
        self.layer_filter.addItem("规则", "rules")
        self.layer_filter.addItem("清单", "checklists")
        self.layer_filter.addItem("片段", "snippets")
        self.category_filter = QComboBox()
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["标题", "层级", "状态", "可信度", "来源", "路径", "审核"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.preview = DocumentPreviewView()

        filters = QHBoxLayout()
        filters.addWidget(QLabel("层级"))
        filters.addWidget(self.layer_filter)
        filters.addWidget(QLabel("分类"))
        filters.addWidget(self.category_filter)
        filters.addStretch(1)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("知识库"))
        left_layout.addWidget(self.summary)
        left_layout.addLayout(filters)
        left_layout.addWidget(self.table, 1)
        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(splitter, 1)

        self.layer_filter.currentIndexChanged.connect(self.load_summary)
        self.category_filter.currentIndexChanged.connect(self.load_summary)
        self.table.itemSelectionChanged.connect(self.open_selected_document)

    def load_summary(self) -> None:
        if self._loading_filters:
            return
        layer = self.layer_filter.currentData()
        category_id = self.category_filter.currentData()
        self.render_summary(self.library_vm.load_summary(limit=50, offset=0, layer=layer, category_id=category_id))

    def render_summary(self, model: Dict[str, Any]) -> None:
        data = model.get("data") or {}
        self._render_category_filter(data.get("categories") or [], data.get("active_category_id"))
        totals = data.get("formal_layer_totals") or {}
        docs = data.get("documents") or []
        page = data.get("page") or {}
        if model.get("errors"):
            self.summary.setText(self._error_text(model))
        else:
            self.summary.setText(
                f"正式层：规则 {totals.get('rules', 0)} / 清单 {totals.get('checklists', 0)} / 片段 {totals.get('snippets', 0)}；"
                f"本页 {page.get('count', len(docs))} 条，最多 50 条。"
            )
        self._render_documents(docs)

    def open_selected_document(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].data(Qt.UserRole) or {}
        model = self.document_vm.open_document(document_id=row.get("document_id"), path=row.get("path"))
        self.preview.render_document(model)

    def _render_category_filter(self, categories: list[Dict[str, Any]], active: str | None) -> None:
        self._loading_filters = True
        self.category_filter.clear()
        self.category_filter.addItem("全部分类", None)
        for category in categories:
            label = category.get("display_name") or category.get("category_id") or ""
            self.category_filter.addItem(label, category.get("category_id"))
        if active:
            index = self.category_filter.findData(active)
            if index >= 0:
                self.category_filter.setCurrentIndex(index)
        self._loading_filters = False

    def _render_documents(self, rows: list[Dict[str, Any]]) -> None:
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("title", ""),
                layer_label(row.get("layer")),
                status_label(row.get("status")),
                confidence_label(row.get("confidence")),
                row.get("source_type", "") or "未知",
                row.get("path", ""),
                "需审核" if row.get("review_required") else "已审核",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, row)
                self.table.setItem(row_index, col, item)

    @staticmethod
    def _error_text(model: Dict[str, Any]) -> str:
        errors = "; ".join(item.get("message", "") for item in model.get("errors", []))
        return f"知识库摘要加载失败：{errors or '服务不可用'}"
