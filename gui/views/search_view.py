"""Formal search page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSplitter, QVBoxLayout, QWidget

from gui.views.document_preview_view import DocumentPreviewView
from gui.widgets.formatters import confidence_label, layer_label, source_type_label, status_label


class SearchView(QWidget):
    def __init__(self, search_vm: Any, document_vm: Any):
        super().__init__()
        self.search_vm = search_vm
        self.document_vm = document_vm
        self.limit = 25
        self.offset = 0
        self.has_more = False
        self.query = QLineEdit()
        self.query.setPlaceholderText("搜索正式知识：规则、清单、片段")
        self.button = QPushButton("搜索")
        self.open_button = QPushButton("打开所选")
        self.prev_button = QPushButton("上一页")
        self.next_button = QPushButton("下一页")
        self.preview_button = QPushButton("隐藏预览")
        self.results = QListWidget()
        self.results.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results.setWordWrap(True)
        self.preview = DocumentPreviewView()
        self.summary = QLabel("输入查询词后搜索正式层索引。")
        self.summary.setWordWrap(True)
        self.page_label = QLabel("第 1 页")
        self.open_button.setEnabled(False)
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)

        controls = QHBoxLayout()
        controls.addWidget(self.query, 1)
        controls.addWidget(self.button)
        controls.addWidget(self.open_button)
        paging = QHBoxLayout()
        paging.addWidget(self.page_label)
        paging.addStretch(1)
        paging.addWidget(self.prev_button)
        paging.addWidget(self.next_button)
        paging.addWidget(self.preview_button)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addLayout(controls)
        left_layout.addWidget(self.summary)
        left_layout.addLayout(paging)
        left_layout.addWidget(self.results, 1)
        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(True)
        self.splitter.addWidget(left)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(QLabel("搜索"))
        root.addWidget(self.splitter, 1)

        self.button.clicked.connect(self.run_search)
        self.open_button.clicked.connect(self.open_current_item)
        self.prev_button.clicked.connect(self.previous_page)
        self.next_button.clicked.connect(self.next_page)
        self.preview_button.clicked.connect(self.toggle_preview)
        self.query.returnPressed.connect(self.run_search)
        self.results.itemActivated.connect(self.open_item)
        self.results.itemClicked.connect(self.open_item)
        self.results.itemSelectionChanged.connect(self.update_selection_state)
        self.setTabOrder(self.query, self.button)
        self.setTabOrder(self.button, self.open_button)
        self.setTabOrder(self.open_button, self.results)

    def set_query_and_run(self, query: str) -> None:
        self.query.setText(query)
        self.run_search()

    def focus_primary(self) -> None:
        self.query.setFocus()
        self.query.selectAll()

    def run_search(self) -> None:
        self.offset = 0
        self._load_page()

    def previous_page(self) -> None:
        self.offset = max(0, self.offset - self.limit)
        self._load_page()

    def next_page(self) -> None:
        if self.has_more:
            self.offset += self.limit
            self._load_page()

    def _load_page(self) -> None:
        self.summary.setText("正在搜索正式层索引...")
        self.open_button.setEnabled(False)
        self.render_results(self.search_vm.search(self.query.text(), limit=self.limit, offset=self.offset))

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
        page = data.get("page") or {}
        self.limit = int(page.get("limit") or self.limit)
        self.offset = int(page.get("offset") or self.offset)
        self.has_more = bool(page.get("has_more"))
        self.page_label.setText(f"第 {self.offset // self.limit + 1} 页，每页最多 {self.limit} 条")
        self.prev_button.setEnabled(self.offset > 0)
        self.next_button.setEnabled(self.has_more)
        for row in rows:
            item = QListWidgetItem(self._row_text(row))
            item.setData(Qt.UserRole, row)
            item.setToolTip(str(row.get("path") or ""))
            self.results.addItem(item)
        if not rows and str(data.get("query") or "").strip() and not model.get("errors"):
            item = QListWidgetItem("没有匹配结果。请换一个查询词。")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)
        self.update_selection_state()

    def update_selection_state(self) -> None:
        item = self.results.currentItem()
        self.open_button.setEnabled(bool(item and item.data(Qt.UserRole)))

    def open_current_item(self) -> None:
        item = self.results.currentItem()
        if item is not None:
            self.open_item(item)

    def open_item(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.UserRole) or {}
        if not row:
            return
        model = self.document_vm.open_document(document_id=row.get("document_id"), path=row.get("path"))
        self.preview.render_document(model)
        if not self.preview.isVisible():
            self.toggle_preview()

    def toggle_preview(self) -> None:
        visible = self.preview.isVisible()
        self.preview.setVisible(not visible)
        self.preview_button.setText("显示预览" if visible else "隐藏预览")

    @staticmethod
    def _row_text(row: Dict[str, Any]) -> str:
        meta = f"{layer_label(row.get('layer'))} | {status_label(row.get('status'))} | 可信度 {confidence_label(row.get('confidence'))} | 来源 {source_type_label(row.get('source_type'))}"
        return f"{row.get('title') or '未命名文档'}\n{row.get('snippet') or '无摘要'}\n{meta}\n{row.get('path') or ''}"

    @staticmethod
    def _error_text(model: Dict[str, Any]) -> str:
        errors = "; ".join(item.get("message", "") for item in model.get("errors", []))
        return f"搜索失败：{errors or '服务不可用'}"
