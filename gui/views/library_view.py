"""Knowledge library summary page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from gui.views.document_preview_view import DocumentPreviewView
from gui.widgets.formatters import confidence_label, layer_label, source_type_label, status_label


class LibraryView(QWidget):
    def __init__(self, library_vm: Any, document_vm: Any):
        super().__init__()
        self.library_vm = library_vm
        self.document_vm = document_vm
        self._loading_filters = False
        self.limit = 25
        self.offset = 0
        self.has_more = False
        self.summary = QLabel("进入知识库后读取正式层摘要；列表分页显示。")
        self.summary.setWordWrap(True)
        self.layer_filter = QComboBox()
        self.layer_filter.addItem("全部正式层", None)
        self.layer_filter.addItem("规则", "rules")
        self.layer_filter.addItem("清单", "checklists")
        self.layer_filter.addItem("片段", "snippets")
        self.category_filter = QComboBox()
        self.refresh_button = QPushButton("刷新")
        self.open_button = QPushButton("打开所选")
        self.prev_button = QPushButton("上一页")
        self.next_button = QPushButton("下一页")
        self.preview_button = QPushButton("隐藏预览")
        self.page_label = QLabel("第 1 页")
        self.open_button.setEnabled(False)
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["标题", "层级", "状态", "可信度", "来源", "路径", "审核"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.preview = DocumentPreviewView()

        filters = QHBoxLayout()
        filters.addWidget(QLabel("层级"))
        filters.addWidget(self.layer_filter)
        filters.addWidget(QLabel("分类"))
        filters.addWidget(self.category_filter)
        filters.addWidget(self.refresh_button)
        filters.addStretch(1)
        paging = QHBoxLayout()
        paging.addWidget(self.page_label)
        paging.addStretch(1)
        paging.addWidget(self.open_button)
        paging.addWidget(self.prev_button)
        paging.addWidget(self.next_button)
        paging.addWidget(self.preview_button)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("知识库"))
        left_layout.addWidget(self.summary)
        left_layout.addLayout(filters)
        left_layout.addLayout(paging)
        left_layout.addWidget(self.table, 1)
        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(True)
        self.splitter.addWidget(left)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(self.splitter, 1)

        self.layer_filter.currentIndexChanged.connect(self.load_first_page)
        self.category_filter.currentIndexChanged.connect(self.load_first_page)
        self.refresh_button.clicked.connect(self.load_first_page)
        self.open_button.clicked.connect(self.open_selected_document)
        self.prev_button.clicked.connect(self.previous_page)
        self.next_button.clicked.connect(self.next_page)
        self.preview_button.clicked.connect(self.toggle_preview)
        self.table.itemSelectionChanged.connect(self.update_selection_state)
        self.table.itemActivated.connect(lambda item: self.open_selected_document())
        self.setTabOrder(self.layer_filter, self.category_filter)
        self.setTabOrder(self.category_filter, self.refresh_button)
        self.setTabOrder(self.refresh_button, self.table)

    def load_summary(self) -> None:
        if self._loading_filters:
            return
        layer = self.layer_filter.currentData()
        category_id = self.category_filter.currentData()
        self.summary.setText("正在读取正式层知识库摘要...")
        self.render_summary(self.library_vm.load_summary(limit=self.limit, offset=self.offset, layer=layer, category_id=category_id))

    def focus_primary(self) -> None:
        self.layer_filter.setFocus()

    def load_first_page(self) -> None:
        self.offset = 0
        self.load_summary()

    def previous_page(self) -> None:
        self.offset = max(0, self.offset - self.limit)
        self.load_summary()

    def next_page(self) -> None:
        if self.has_more:
            self.offset += self.limit
            self.load_summary()

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
                f"本页 {page.get('count', len(docs))} 条，每页最多 {page.get('limit', self.limit)} 条。"
            )
        self.limit = int(page.get("limit") or self.limit)
        self.offset = int(page.get("offset") or self.offset)
        self.has_more = bool(page.get("has_more"))
        self.page_label.setText(f"第 {self.offset // self.limit + 1} 页")
        self.prev_button.setEnabled(self.offset > 0)
        self.next_button.setEnabled(self.has_more)
        self._render_documents(docs)
        self.update_selection_state()

    def open_selected_document(self) -> None:
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].data(Qt.UserRole) or {}
        model = self.document_vm.open_document(document_id=row.get("document_id"), path=row.get("path"))
        self.preview.render_document(model)
        if not self.preview.isVisible():
            self.toggle_preview()

    def update_selection_state(self) -> None:
        self.open_button.setEnabled(bool(self.table.selectedItems()))

    def toggle_preview(self) -> None:
        visible = self.preview.isVisible()
        self.preview.setVisible(not visible)
        self.preview_button.setText("显示预览" if visible else "隐藏预览")

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
                source_type_label(row.get("source_type")),
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
