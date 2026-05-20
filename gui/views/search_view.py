"""Formal search page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QSplitter, QStackedWidget, QVBoxLayout, QWidget

from gui.styles.tokens import SPACING
from gui.views.document_inspector_preview import DocumentInspectorPreview
from gui.views.document_reader_view import DocumentReaderView
from gui.widgets.controls import SearchInput, primary_button, secondary_button
from gui.widgets.empty_state import EmptyState
from gui.widgets.error_state import ErrorState
from gui.widgets.formatters import confidence_label, layer_label, source_type_label, status_label
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_chip import StatusChip, tone_for_status


class SearchView(QWidget):
    def __init__(self, search_vm: Any, document_vm: Any):
        super().__init__()
        self.search_vm = search_vm
        self.document_vm = document_vm
        self.limit = 25
        self.offset = 0
        self.has_more = False
        self.query = SearchInput("搜索正式知识：规则、清单、片段")
        self.button = primary_button("搜索")
        self.open_button = secondary_button("在主区域打开")
        self.prev_button = secondary_button("上一页")
        self.next_button = secondary_button("下一页")
        self.preview_button = secondary_button("隐藏详情面板")
        self.results = QListWidget()
        self.results.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results.setWordWrap(True)
        self.results.setObjectName("resultList")
        self.preview = DocumentInspectorPreview()
        self.reader = DocumentReaderView("返回搜索结果")
        self.main_stack = QStackedWidget()
        self.summary = QLabel("输入查询词后搜索正式层索引。")
        self.summary.setObjectName("mutedText")
        self.summary.setWordWrap(True)
        self.empty_state = EmptyState("等待搜索", "输入查询词后，只查询正式层索引。")
        self.error_state = ErrorState("搜索失败", "")
        self.error_state.hide()
        self.page_label = QLabel("第 1 页")
        self.page_label.setObjectName("mutedText")
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
        self.result_page = QWidget()
        left_layout = QVBoxLayout(self.result_page)
        left_layout.setContentsMargins(0, 0, 12, 0)
        left_layout.setSpacing(SPACING.gap)
        left_layout.addLayout(controls)
        left_layout.addWidget(self.summary)
        left_layout.addWidget(self.empty_state)
        left_layout.addWidget(self.error_state)
        left_layout.addLayout(paging)
        left_layout.addWidget(self.results, 1)
        self.main_stack.addWidget(self.result_page)
        self.main_stack.addWidget(self.reader)
        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(True)
        self.splitter.addWidget(self.main_stack)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING.page, SPACING.page, SPACING.page, SPACING.page)
        root.setSpacing(SPACING.gap)
        root.addWidget(SectionHeader("搜索", "检索规则、清单、片段。结果打开时才读取单篇文档。"))
        root.addWidget(self.splitter, 1)

        self.button.clicked.connect(self.run_search)
        self.open_button.clicked.connect(self.open_current_item)
        self.prev_button.clicked.connect(self.previous_page)
        self.next_button.clicked.connect(self.next_page)
        self.preview_button.clicked.connect(self.toggle_preview)
        self.query.returnPressed.connect(self.run_search)
        self.results.itemActivated.connect(self.open_item_in_reader)
        self.results.itemSelectionChanged.connect(self.inspect_current_item)
        self.reader.return_requested.connect(self.show_results)
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
        self.show_results()
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
        self.empty_state.hide()
        self.error_state.hide()
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
            self.empty_state.set_state("等待搜索", "输入查询词后，只查询正式层索引。")
            self.empty_state.show()
        elif index_status == "missing":
            self.summary.setText("索引缺失，当前没有可搜索结果。")
            self.empty_state.set_state("索引缺失", "当前工作区没有可用索引。界面不会自动创建索引。")
            self.empty_state.show()
        elif model.get("errors"):
            self.summary.setText(self._error_text(model))
            self.error_state.set_state("搜索失败", self._error_text(model))
            self.error_state.show()
        elif not rows:
            self.summary.setText("没有搜索结果。")
            self.empty_state.set_state("没有匹配结果", "请换一个查询词，或检查当前工作区索引状态。")
            self.empty_state.show()
        else:
            page = data.get("page") or {}
            self.summary.setText(f"状态：{status_label(state)}；本页 {page.get('count', len(rows))} 条；仅搜索正式层。")
            self.empty_state.hide()
            self.error_state.hide()
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
            widget = self._row_widget(row)
            item.setSizeHint(widget.sizeHint())
            self.results.setItemWidget(item, widget)
        if not rows and str(data.get("query") or "").strip() and not model.get("errors"):
            item = QListWidgetItem("没有匹配结果。请换一个查询词。")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)
        self.update_selection_state()

    def update_selection_state(self) -> None:
        item = self.results.currentItem()
        self.open_button.setEnabled(bool(item and item.data(Qt.UserRole)))

    def inspect_current_item(self) -> None:
        self.update_selection_state()
        item = self.results.currentItem()
        row = item.data(Qt.UserRole) if item is not None else None
        if not row:
            self.preview.render_empty()
            return
        model = self.document_vm.open_document(document_id=row.get("document_id"), path=row.get("path"))
        self.preview.render_document(model, row=row)

    def open_current_item(self) -> None:
        item = self.results.currentItem()
        if item is not None:
            self.open_item_in_reader(item)

    def open_item_in_reader(self, item: QListWidgetItem) -> None:
        row = item.data(Qt.UserRole) or {}
        if not row:
            return
        model = self.document_vm.open_document(document_id=row.get("document_id"), path=row.get("path"))
        self.reader.render_document(model)
        self.main_stack.setCurrentWidget(self.reader)

    def show_results(self) -> None:
        self.main_stack.setCurrentWidget(self.result_page)

    def toggle_preview(self) -> None:
        visible = self.preview.isVisible()
        self.preview.setVisible(not visible)
        self.preview_button.setText("显示详情面板" if visible else "隐藏详情面板")

    @staticmethod
    def _row_text(row: Dict[str, Any]) -> str:
        meta = f"{layer_label(row.get('layer'))} | {status_label(row.get('status'))} | 可信度 {confidence_label(row.get('confidence'))} | 来源 {source_type_label(row.get('source_type'))}"
        return f"{row.get('title') or '未命名文档'}\n{row.get('snippet') or '无摘要'}\n{meta}\n{row.get('path') or ''}"

    @staticmethod
    def _row_widget(row: Dict[str, Any]) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)
        title = QLabel(str(row.get("title") or "未命名文档"))
        title.setObjectName("cardValue")
        snippet = QLabel(str(row.get("snippet") or "无摘要"))
        snippet.setObjectName("mutedText")
        snippet.setWordWrap(True)
        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)
        for chip in [
            StatusChip(layer_label(row.get("layer")), "info"),
            StatusChip(status_label(row.get("status")), tone_for_status(row.get("status"))),
            StatusChip(f"可信度 {confidence_label(row.get('confidence'))}", "muted"),
            StatusChip(source_type_label(row.get("source_type")), "muted"),
        ]:
            chips.addWidget(chip)
        chips.addStretch(1)
        path = QLabel(str(row.get("path") or ""))
        path.setObjectName("pathLabel")
        layout.addWidget(title)
        layout.addWidget(snippet)
        layout.addLayout(chips)
        layout.addWidget(path)
        return widget

    @staticmethod
    def _error_text(model: Dict[str, Any]) -> str:
        errors = "; ".join(item.get("message", "") for item in model.get("errors", []))
        return f"搜索失败：{errors or '服务不可用'}"
