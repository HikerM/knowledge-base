"""Explicitly opened AI conversation history viewer."""

from __future__ import annotations

from typing import Any, Dict, Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.styles.tokens import SPACING
from gui.widgets.controls import danger_button, ghost_button, secondary_button


class ConversationHistoryView(QWidget):
    """Render paginated conversation history from a ViewModel snapshot."""

    load_requested = Signal()
    previous_page_requested = Signal()
    next_page_requested = Signal()
    back_requested = Signal()
    open_requested = Signal(str)
    delete_requested = Signal(str)
    export_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("conversationHistoryView")
        self.current_conversation_id = ""
        self.current_detail: Dict[str, Any] = {}
        self.detail_filter = "all"

        self.back_button = ghost_button("返回对话")
        self.back_button.setObjectName("conversationHistoryBackButton")
        self.refresh_button = secondary_button("刷新")
        self.refresh_button.setObjectName("conversationHistoryRefreshButton")
        self.previous_button = ghost_button("上一页")
        self.previous_button.setObjectName("conversationHistoryPreviousButton")
        self.next_button = ghost_button("下一页")
        self.next_button.setObjectName("conversationHistoryNextButton")
        self.delete_button = danger_button("删除对话")
        self.delete_button.setObjectName("conversationHistoryDeleteButton")
        self.export_button = secondary_button("导出预览")
        self.export_button.setObjectName("conversationHistoryExportButton")
        self.copy_export_button = secondary_button("复制 JSON")
        self.copy_export_button.setObjectName("conversationHistoryCopyJsonButton")
        self.copy_export_button.setToolTip("复制当前导出预览 JSON，不写入文件。")
        self.copy_export_button.setEnabled(False)

        self.state_label = QLabel("")
        self.state_label.setObjectName("conversationHistoryState")
        self.state_label.setWordWrap(True)
        self.page_label = QLabel("")
        self.page_label.setObjectName("mutedText")

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("conversationHistoryList")
        self.list_widget.setMaximumHeight(150)

        self.detail_area = QScrollArea()
        self.detail_area.setObjectName("conversationHistoryDetailArea")
        self.detail_area.setWidgetResizable(True)
        self.detail_container = QWidget()
        self.detail_container.setObjectName("conversationHistoryDetail")
        self.detail_layout = QVBoxLayout(self.detail_container)
        self.detail_layout.setContentsMargins(8, 8, 8, 8)
        self.detail_layout.setSpacing(SPACING.compact)
        self.detail_area.setWidget(self.detail_container)

        self.export_preview = QPlainTextEdit()
        self.export_preview.setObjectName("conversationExportPreview")
        self.export_preview.setReadOnly(True)
        self.export_preview.setMaximumHeight(120)
        self.export_preview.hide()

        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        self.filter_buttons = self._create_filter_buttons()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(SPACING.compact)
        root.addLayout(self._top_row())
        root.addWidget(self.state_label)
        root.addWidget(self.list_widget)
        root.addWidget(self.page_label)
        root.addLayout(self._action_row())
        root.addLayout(self._filter_row())
        root.addWidget(self.detail_area, 1)
        root.addWidget(self.export_preview)

        self.back_button.clicked.connect(self.back_requested.emit)
        self.refresh_button.clicked.connect(self.load_requested.emit)
        self.previous_button.clicked.connect(self.previous_page_requested.emit)
        self.next_button.clicked.connect(self.next_page_requested.emit)
        self.list_widget.itemClicked.connect(self._open_item)
        self.delete_button.clicked.connect(self._delete_current)
        self.export_button.clicked.connect(self._export_current)
        self.copy_export_button.clicked.connect(self._copy_export_json)
        self._set_action_enabled(False)
        self._set_filter_enabled(False)

    def render(self, model: Dict[str, Any]) -> None:
        state = str(model.get("state") or "idle")
        self.state_label.setText(str(model.get("message") or ""))
        page = dict(model.get("page") or {})
        self.page_label.setText(str(page.get("label") or self._page_label(page)))
        self.previous_button.setEnabled(bool(page.get("can_previous", int(page.get("offset") or 0) > 0)))
        self.next_button.setEnabled(bool(page.get("can_next", page.get("has_more", False))))
        self._render_list(model.get("conversations") or [])
        self._render_detail(dict(model.get("selected_conversation") or {}))
        export_text = str(model.get("export_preview") or "")
        self.export_preview.setPlainText(export_text)
        self.export_preview.setVisible(bool(export_text))
        self.copy_export_button.setEnabled(bool(export_text))
        if state in {"idle", "not_bootstrapped", "empty", "error"}:
            self._set_action_enabled(False)

    def _top_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACING.compact)
        row.addWidget(self.back_button)
        row.addStretch(1)
        row.addWidget(self.refresh_button)
        row.addWidget(self.previous_button)
        row.addWidget(self.next_button)
        return row

    def _action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACING.compact)
        row.addWidget(self.export_button)
        row.addWidget(self.copy_export_button)
        row.addWidget(self.delete_button)
        row.addStretch(1)
        return row

    def _filter_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACING.compact)
        row.addWidget(self._muted("详情筛选"))
        for key in ["all", "messages", "citations", "policies", "tasks"]:
            row.addWidget(self.filter_buttons[key])
        row.addStretch(1)
        return row

    def _render_list(self, conversations: Iterable[Dict[str, Any]]) -> None:
        selected_id = self.current_conversation_id
        self.list_widget.clear()
        for conversation in conversations:
            item = QListWidgetItem(self._summary_text(conversation))
            item.setData(Qt.ItemDataRole.UserRole, str(conversation.get("conversation_id") or ""))
            self.list_widget.addItem(item)
            if selected_id and item.data(Qt.ItemDataRole.UserRole) == selected_id:
                item.setSelected(True)

    def _render_detail(self, conversation: Dict[str, Any]) -> None:
        self._clear_detail()
        self.current_detail = dict(conversation)
        self.current_conversation_id = str(conversation.get("conversation_id") or "")
        self._set_action_enabled(bool(self.current_conversation_id))
        self._set_filter_enabled(bool(self.current_conversation_id))
        if not conversation:
            self.detail_layout.addWidget(self._muted("选择一个对话查看详情。"))
            self.detail_layout.addStretch(1)
            return
        self.detail_layout.addWidget(self._title(conversation.get("title") or "Conversation"))
        self.detail_layout.addWidget(
            self._muted(
                f"{conversation.get('updated_at', '')} | provider={conversation.get('provider_kind', '')} | "
                f"messages={conversation.get('message_count', 0)} | citations={conversation.get('citation_count', 0)}"
            )
        )
        summary = str(conversation.get("summary_preview") or "")
        if summary:
            self.detail_layout.addWidget(self._muted(summary))
        rendered_sections = 0
        if self.detail_filter in {"all", "messages"}:
            for message in conversation.get("messages") or []:
                self.detail_layout.addWidget(self._message_widget(dict(message)))
                rendered_sections += 1
            if self.detail_filter == "messages" and not conversation.get("messages"):
                self.detail_layout.addWidget(self._muted("暂无消息。"))
        if self.detail_filter in {"all", "citations"}:
            self.detail_layout.addWidget(self._details_group("引用", self._citation_lines(conversation.get("citations") or []), "conversationHistoryCitationsGroup"))
            rendered_sections += 1
        if self.detail_filter in {"all", "policies"}:
            self.detail_layout.addWidget(
                self._details_group("策略", self._policy_lines(conversation.get("policy_decisions") or []), "conversationHistoryPoliciesGroup")
            )
            rendered_sections += 1
        if self.detail_filter in {"all", "tasks"}:
            self.detail_layout.addWidget(self._details_group("任务", self._task_lines(conversation.get("tasks") or []), "conversationHistoryTasksGroup"))
            rendered_sections += 1
        if rendered_sections == 0:
            self.detail_layout.addWidget(self._muted("当前筛选没有内容。"))
        self.detail_layout.addStretch(1)

    @staticmethod
    def _summary_text(conversation: Dict[str, Any]) -> str:
        title = str(conversation.get("title") or "Conversation")
        updated_at = str(conversation.get("updated_at") or "")
        provider = str(conversation.get("provider_kind") or "")
        status = str(conversation.get("status") or "")
        summary = str(conversation.get("summary_preview") or "")
        stats = f"messages {conversation.get('message_count', 0)} | citations {conversation.get('citation_count', 0)}"
        return "\n".join(part for part in [title, f"{updated_at} | {provider} | {stats} | {status}", summary] if part)

    @staticmethod
    def _message_widget(message: Dict[str, Any]) -> QFrame:
        frame = QFrame()
        role = str(message.get("role") or "assistant")
        frame.setObjectName("historyMessageBubble")
        frame.setProperty("messageRole", role)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(SPACING.compact, SPACING.compact, SPACING.compact, SPACING.compact)
        role_label = QLabel(f"{role} | {message.get('type', '')} | {message.get('created_at', '')}")
        role_label.setObjectName("messageAuthor")
        body = QLabel(str(message.get("content_text") or ""))
        body.setObjectName("historyMessageContent")
        body.setWordWrap(True)
        layout.addWidget(role_label)
        layout.addWidget(body)
        refs = []
        if message.get("citations"):
            refs.append(f"citations={', '.join(message.get('citations') or [])}")
        if message.get("policy_decision_id"):
            refs.append(f"policy={message.get('policy_decision_id')}")
        if message.get("task_id"):
            refs.append(f"task={message.get('task_id')}")
        if refs:
            ref_label = QLabel(" | ".join(refs))
            ref_label.setObjectName("mutedText")
            ref_label.setWordWrap(True)
            layout.addWidget(ref_label)
        return frame

    def _details_group(self, title: str, lines: list[str], object_name: str) -> QGroupBox:
        group = QGroupBox(title)
        group.setObjectName(object_name)
        group.setCheckable(True)
        group.setChecked(self.detail_filter != "all")
        content = QWidget()
        content.setObjectName("conversationHistoryDetailsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 4, 0, 0)
        if lines:
            for line in lines:
                content_layout.addWidget(self._muted(line))
        else:
            content_layout.addWidget(self._muted("无"))
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(8, 8, 8, 8)
        group_layout.addWidget(content)
        content.setVisible(self.detail_filter != "all")
        group.toggled.connect(content.setVisible)
        return group

    @staticmethod
    def _citation_lines(citations: Iterable[Dict[str, Any]]) -> list[str]:
        return [
            f"{item.get('citation_id', '')} | {item.get('title', '')} | {item.get('layer', '')}/{item.get('status', '')} | {item.get('source_type', '')} | {item.get('confidence', '')}"
            for item in citations
        ]

    @staticmethod
    def _policy_lines(decisions: Iterable[Dict[str, Any]]) -> list[str]:
        return [
            f"{item.get('policy_decision_id', '')} | {item.get('level', '')} | {item.get('decision', '')} | {item.get('capability_id', '')} | {item.get('reason', '')}"
            for item in decisions
        ]

    @staticmethod
    def _task_lines(tasks: Iterable[Dict[str, Any]]) -> list[str]:
        return [
            f"{item.get('task_id', '')} | {item.get('capability_id', '')} | {item.get('status_at_last_render', '')} | {item.get('progress_percent_at_last_render', 0)}%"
            for item in tasks
        ]

    @staticmethod
    def _title(text: Any) -> QLabel:
        label = QLabel(str(text))
        label.setObjectName("assistantCardTitle")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _muted(text: Any) -> QLabel:
        label = QLabel(str(text))
        label.setObjectName("mutedText")
        label.setWordWrap(True)
        return label

    def _open_item(self, item: QListWidgetItem) -> None:
        conversation_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if conversation_id:
            self.open_requested.emit(conversation_id)

    def _delete_current(self) -> None:
        if self.current_conversation_id:
            self.delete_requested.emit(self.current_conversation_id)

    def _export_current(self) -> None:
        if self.current_conversation_id:
            self.export_requested.emit(self.current_conversation_id)

    def _copy_export_json(self) -> None:
        text = self.export_preview.toPlainText()
        if not text:
            self.state_label.setText("请先生成导出预览。")
            return
        try:
            clipboard = QApplication.clipboard()
            if clipboard is None:
                raise RuntimeError("clipboard unavailable")
            clipboard.setText(text)
        except Exception as exc:  # noqa: BLE001
            self.state_label.setText(f"复制 JSON 失败：{exc}")
            return
        self.state_label.setText("已复制 JSON；对话记录不是正式知识。")

    def _set_action_enabled(self, enabled: bool) -> None:
        self.delete_button.setEnabled(enabled)
        self.export_button.setEnabled(enabled)

    def _set_filter_enabled(self, enabled: bool) -> None:
        for button in self.filter_buttons.values():
            button.setEnabled(enabled)

    def _clear_detail(self) -> None:
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_detail_filter(self, filter_key: str) -> None:
        self.detail_filter = filter_key
        self._render_detail(self.current_detail)

    def _create_filter_buttons(self) -> Dict[str, Any]:
        labels = {
            "all": ("全部", "conversationHistoryFilterAllButton"),
            "messages": ("消息", "conversationHistoryFilterMessagesButton"),
            "citations": ("引用", "conversationHistoryFilterCitationsButton"),
            "policies": ("策略", "conversationHistoryFilterPoliciesButton"),
            "tasks": ("任务", "conversationHistoryFilterTasksButton"),
        }
        buttons: Dict[str, Any] = {}
        for key, (label, object_name) in labels.items():
            button = ghost_button(label)
            button.setObjectName(object_name)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, selected=key: self._set_detail_filter(selected))
            self.filter_group.addButton(button)
            buttons[key] = button
        buttons["all"].setChecked(True)
        return buttons

    @staticmethod
    def _page_label(page: Dict[str, Any]) -> str:
        limit = int(page.get("limit") or 0)
        offset = int(page.get("offset") or 0)
        count = int(page.get("count") or 0)
        current_page = offset // limit + 1 if limit else 1
        return f"第 {current_page} 页 | 本页 {count} 条 | 每页最多 {limit} 条"
