"""Knowledge library summary page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QLabel, QSplitter, QStackedWidget, QTableWidgetItem, QVBoxLayout, QWidget

from gui.styles.tokens import SPACING
from gui.views.document_inspector_preview import DocumentInspectorPreview
from gui.views.document_reader_view import DocumentReaderView
from gui.widgets.controls import Select, secondary_button
from gui.widgets.empty_state import EmptyState
from gui.widgets.error_state import ErrorState
from gui.widgets.formatters import confidence_label, layer_label, source_type_label, status_label
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_chip import StatusChip, tone_for_status
from gui.widgets.table import DataTable


def _short_path(path: str, max_chars: int = 28) -> str:
    return path if len(path) <= max_chars else f"{path[:10]}...{path[-max_chars + 13:]}"


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
        self.summary.setObjectName("mutedText")
        self.summary.setWordWrap(True)
        self.empty_state = EmptyState("等待加载", "进入知识库后分页读取正式层列表。")
        self.error_state = ErrorState("知识库读取失败", "")
        self.error_state.hide()
        self.layer_filter = Select()
        self.layer_filter.addItem("全部正式层", None)
        self.layer_filter.addItem("规则", "rules")
        self.layer_filter.addItem("清单", "checklists")
        self.layer_filter.addItem("片段", "snippets")
        self.category_filter = Select()
        self.refresh_button = secondary_button("刷新")
        self.open_button = secondary_button("在主区域打开")
        self.prev_button = secondary_button("上一页")
        self.next_button = secondary_button("下一页")
        self.preview_button = secondary_button("隐藏详情面板")
        self.page_label = QLabel("第 1 页")
        self.open_button.setEnabled(False)
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.table = DataTable(0, 7)
        self.table.setHorizontalHeaderLabels(["标题", "层级", "状态", "可信度", "来源", "路径", "审核"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.preview = DocumentInspectorPreview()
        self.reader = DocumentReaderView("返回知识库")
        self.main_stack = QStackedWidget()

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
        self.library_page = QWidget()
        left_layout = QVBoxLayout(self.library_page)
        left_layout.setContentsMargins(0, 0, 12, 0)
        left_layout.setSpacing(SPACING.gap)
        left_layout.addWidget(self.summary)
        left_layout.addLayout(filters)
        left_layout.addWidget(self.empty_state)
        left_layout.addWidget(self.error_state)
        left_layout.addLayout(paging)
        left_layout.addWidget(self.table, 1)
        self.main_stack.addWidget(self.library_page)
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
        root.addWidget(SectionHeader("知识库", "只浏览规则、清单、片段；列表分页读取，不加载正文。"))
        root.addWidget(self.splitter, 1)

        self.layer_filter.currentIndexChanged.connect(self.load_first_page)
        self.category_filter.currentIndexChanged.connect(self.load_first_page)
        self.refresh_button.clicked.connect(self.load_first_page)
        self.open_button.clicked.connect(self.open_selected_document)
        self.prev_button.clicked.connect(self.previous_page)
        self.next_button.clicked.connect(self.next_page)
        self.preview_button.clicked.connect(self.toggle_preview)
        self.table.itemSelectionChanged.connect(self.inspect_selected_document)
        self.table.itemActivated.connect(lambda item: self.open_selected_document())
        self.reader.return_requested.connect(self.show_library)
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
        self.show_library()
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
            self.error_state.set_state("知识库读取失败", self._error_text(model))
            self.error_state.show()
            self.empty_state.hide()
        else:
            self.summary.setText(
                f"正式层：规则 {totals.get('rules', 0)} / 清单 {totals.get('checklists', 0)} / 片段 {totals.get('snippets', 0)}；"
                f"本页 {page.get('count', len(docs))} 条，每页最多 {page.get('limit', self.limit)} 条。"
            )
            self.error_state.hide()
            if docs:
                self.empty_state.hide()
            else:
                self.empty_state.set_state("没有正式知识", "当前筛选条件下没有规则、清单或片段。")
                self.empty_state.show()
        self.limit = int(page.get("limit") or self.limit)
        self.offset = int(page.get("offset") or self.offset)
        self.has_more = bool(page.get("has_more"))
        self.page_label.setText(f"第 {self.offset // self.limit + 1} 页")
        self.prev_button.setEnabled(self.offset > 0)
        self.next_button.setEnabled(self.has_more)
        self._render_documents(docs)
        self.update_selection_state()

    def open_selected_document(self) -> None:
        row = self._selected_row()
        if not row:
            return
        model = self.document_vm.open_document(document_id=row.get("document_id"), path=row.get("path"))
        self.reader.render_document(model)
        self.main_stack.setCurrentWidget(self.reader)

    def update_selection_state(self) -> None:
        self.open_button.setEnabled(bool(self._selected_row()))

    def inspect_selected_document(self) -> None:
        self.update_selection_state()
        row = self._selected_row()
        if not row:
            self.preview.render_empty()
            return
        model = self.document_vm.open_document(document_id=row.get("document_id"), path=row.get("path"))
        self.preview.render_document(model, row=row)

    def show_library(self) -> None:
        self.main_stack.setCurrentWidget(self.library_page)

    def toggle_preview(self) -> None:
        visible = self.preview.isVisible()
        self.preview.setVisible(not visible)
        self.preview_button.setText("显示详情面板" if visible else "隐藏详情面板")

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
                _short_path(str(row.get("path", ""))),
                "需审核" if row.get("review_required") else "已审核",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, row)
                if col == 5:
                    item.setToolTip(str(row.get("path") or ""))
                self.table.setItem(row_index, col, item)
            self.table.setCellWidget(row_index, 1, StatusChip(layer_label(row.get("layer")), "info"))
            self.table.setCellWidget(row_index, 2, StatusChip(status_label(row.get("status")), tone_for_status(row.get("status"))))

    def _selected_row(self) -> Dict[str, Any] | None:
        selected = self.table.selectedItems()
        if not selected:
            return None
        return selected[0].data(Qt.UserRole) or None

    @staticmethod
    def _error_text(model: Dict[str, Any]) -> str:
        errors = "; ".join(item.get("message", "") for item in model.get("errors", []))
        return f"知识库摘要加载失败：{errors or '服务不可用'}"
