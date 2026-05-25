"""AI memory settings page for explicit in-memory management."""

from __future__ import annotations

import json
from typing import Any, Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.styles.tokens import SPACING
from gui.widgets.card import Card
from gui.widgets.controls import danger_button, ghost_button, secondary_button
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_chip import StatusChip


class MemorySettingsView(QWidget):
    """Render AI memory settings without loading memory at startup."""

    back_requested = Signal()

    def __init__(self, memory_vm: Any):
        super().__init__()
        self.setObjectName("memorySettingsView")
        self.memory_vm = memory_vm
        self.current_candidate_id = ""
        self.current_memory_id = ""

        self.back_button = ghost_button("返回设置")
        self.back_button.setObjectName("memoryBackButton")
        self.mode_chip = StatusChip("内存模拟模式", "info")
        self.state_label = QLabel("")
        self.state_label.setObjectName("memoryStateLabel")
        self.state_label.setWordWrap(True)
        self.mode_notice = QLabel("AI 记忆当前为内存模拟模式，关闭应用后不会保留。")
        self.mode_notice.setObjectName("memoryModeNotice")
        self.mode_notice.setWordWrap(True)
        self.safety_notice = QLabel(
            "长期记忆必须由你确认后才会保存。\n"
            "AI 记忆不会作为正式知识，也不会进入搜索规则。\n"
            "当前不会发送到云端。\n"
            "删除为删除记录，不是正式知识删除。"
        )
        self.safety_notice.setObjectName("memorySafetyNotice")
        self.safety_notice.setWordWrap(True)

        self.status_filter = QComboBox()
        self.status_filter.setObjectName("memoryCandidateStatusFilter")
        for label, value in [("全部", ""), ("待确认", "pending"), ("已接受", "accepted"), ("已拒绝", "rejected"), ("已过期", "expired")]:
            self.status_filter.addItem(label, value)
        self.load_candidates_button = secondary_button("加载候选")
        self.load_candidates_button.setObjectName("memoryLoadCandidatesButton")
        self.accept_button = secondary_button("接受")
        self.accept_button.setObjectName("memoryAcceptCandidateButton")
        self.reject_button = secondary_button("拒绝")
        self.reject_button.setObjectName("memoryRejectCandidateButton")
        self.expire_button = secondary_button("标记过期")
        self.expire_button.setObjectName("memoryExpireCandidateButton")
        self.candidates_list = QListWidget()
        self.candidates_list.setObjectName("memoryCandidatesList")
        self.candidates_list.setMaximumHeight(160)

        self.memory_status_filter = QComboBox()
        self.memory_status_filter.setObjectName("memoryStatusFilter")
        for label, value in [("全部", ""), ("启用", "active"), ("已禁用", "disabled"), ("已删除", "deleted")]:
            self.memory_status_filter.addItem(label, value)
        self.load_memories_button = secondary_button("加载已保存记忆")
        self.load_memories_button.setObjectName("memoryLoadMemoriesButton")
        self.disable_button = secondary_button("禁用")
        self.disable_button.setObjectName("memoryDisableButton")
        self.delete_button = danger_button("删除")
        self.delete_button.setObjectName("memoryDeleteButton")
        self.clear_button = danger_button("清空内存记忆")
        self.clear_button.setObjectName("memoryClearButton")
        self.memories_list = QListWidget()
        self.memories_list.setObjectName("memorySavedList")
        self.memories_list.setMaximumHeight(170)

        self.refresh_previews_button = secondary_button("刷新预览")
        self.refresh_previews_button.setObjectName("memoryRefreshPreviewsButton")
        self.copy_export_button = secondary_button("复制 export JSON")
        self.copy_export_button.setObjectName("memoryCopyExportPreviewButton")
        self.backup_preview = QPlainTextEdit()
        self.backup_preview.setObjectName("memoryBackupPreview")
        self.backup_preview.setReadOnly(True)
        self.backup_preview.setMaximumHeight(88)
        self.export_preview = QPlainTextEdit()
        self.export_preview.setObjectName("memoryExportPreview")
        self.export_preview.setReadOnly(True)
        self.export_preview.setMaximumHeight(100)
        self.privacy_status = QPlainTextEdit()
        self.privacy_status.setObjectName("memoryPrivacyStatus")
        self.privacy_status.setReadOnly(True)
        self.privacy_status.setMaximumHeight(86)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("memorySettingsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(SPACING.page, SPACING.page, SPACING.page, SPACING.page)
        content_layout.setSpacing(SPACING.gap)
        content_layout.addLayout(self._top_row())
        content_layout.addWidget(SectionHeader("AI 记忆", "只管理当前进程中的内存模拟数据。"))
        content_layout.addWidget(self.mode_notice)
        content_layout.addWidget(self.safety_notice)
        content_layout.addWidget(self._candidate_card())
        content_layout.addWidget(self._memory_card())
        content_layout.addWidget(self._preview_card())
        content_layout.addStretch(1)
        self.scroll.setWidget(content)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.scroll)

        self.back_button.clicked.connect(self.back_requested.emit)
        self.load_candidates_button.clicked.connect(self.load_candidates)
        self.accept_button.clicked.connect(self.accept_selected_candidate)
        self.reject_button.clicked.connect(self.reject_selected_candidate)
        self.expire_button.clicked.connect(self.expire_selected_candidate)
        self.load_memories_button.clicked.connect(self.load_memories)
        self.disable_button.clicked.connect(self.disable_selected_memory)
        self.delete_button.clicked.connect(self.delete_selected_memory)
        self.clear_button.clicked.connect(self.clear_memory)
        self.refresh_previews_button.clicked.connect(self.refresh_previews)
        self.copy_export_button.clicked.connect(self.copy_export_preview_json)
        self.candidates_list.itemSelectionChanged.connect(self.update_candidate_actions)
        self.memories_list.itemSelectionChanged.connect(self.update_memory_actions)
        self.render(self.memory_vm.snapshot())

    def render(self, model: Dict[str, Any]) -> None:
        self.state_label.setText(str(model.get("message") or ""))
        self._render_candidates(model.get("candidates") or [], model)
        self._render_memories(model.get("memories") or [], model)
        self.backup_preview.setPlainText(self._backup_text(model.get("backup_preview") or {}))
        self.export_preview.setPlainText(self._export_text(model.get("export_preview") or {}))
        self.privacy_status.setPlainText(self._privacy_text(model.get("privacy_status") or {}, model))
        self.update_candidate_actions()
        self.update_memory_actions()

    def focus_primary(self) -> None:
        self.load_candidates_button.setFocus()

    def load_candidates(self) -> None:
        status = self.status_filter.currentData() or None
        self.render(self.memory_vm.load_candidates(status=status))

    def accept_selected_candidate(self) -> None:
        if not self.current_candidate_id:
            return
        answer = QMessageBox.question(
            self,
            "接受 MemoryCandidate",
            "长期记忆必须由你确认后才会保存。确认保存到当前内存模拟服务？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        self.render(self.memory_vm.accept_candidate(self.current_candidate_id, confirmed=answer == QMessageBox.StandardButton.Yes))

    def reject_selected_candidate(self) -> None:
        if self.current_candidate_id:
            self.render(self.memory_vm.reject_candidate(self.current_candidate_id))

    def expire_selected_candidate(self) -> None:
        if not self.current_candidate_id:
            return
        answer = QMessageBox.question(
            self,
            "标记过期 MemoryCandidate",
            "标记过期只会把当前候选改为 expired，不会保存 SavedMemory。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        self.render(self.memory_vm.expire_candidate(self.current_candidate_id, confirmed=answer == QMessageBox.StandardButton.Yes))

    def load_memories(self) -> None:
        status = self.memory_status_filter.currentData() or None
        self.render(self.memory_vm.load_memories(status=status))

    def disable_selected_memory(self) -> None:
        if self.current_memory_id:
            self.render(self.memory_vm.disable_memory(self.current_memory_id))

    def delete_selected_memory(self) -> None:
        if not self.current_memory_id:
            return
        answer = QMessageBox.question(
            self,
            "删除 SavedMemory",
            "删除为删除记录，不是正式知识删除。确认删除这个内存记忆？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        self.render(self.memory_vm.delete_memory(self.current_memory_id, confirmed=answer == QMessageBox.StandardButton.Yes))

    def clear_memory(self) -> None:
        answer = QMessageBox.question(
            self,
            "清空内存记忆",
            "清空只影响当前工作区的内存模拟记忆，不会删除正式知识。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        self.render(self.memory_vm.clear_memory(confirmed=answer == QMessageBox.StandardButton.Yes))

    def refresh_previews(self) -> None:
        self.render(self.memory_vm.refresh_previews())

    def copy_export_preview_json(self) -> None:
        preview = dict(self.memory_vm.export_preview or {})
        if not preview:
            self.state_label.setText("请先刷新 export preview。")
            return
        try:
            text = json.dumps(preview, ensure_ascii=False, indent=2, sort_keys=True)
            self._copy_text_to_clipboard(text)
        except Exception as exc:  # noqa: BLE001
            self.state_label.setText(f"复制 export preview 失败：{exc}")
            return
        self.state_label.setText("已复制 export preview JSON；不会写入文件或发送云端。")

    @staticmethod
    def _copy_text_to_clipboard(text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is None:
            raise RuntimeError("clipboard unavailable")
        clipboard.setText(text)

    def update_candidate_actions(self) -> None:
        item = self.candidates_list.currentItem()
        row = dict(item.data(Qt.ItemDataRole.UserRole) or {}) if item is not None else {}
        self.current_candidate_id = str(row.get("candidate_id") or "")
        pending = str(row.get("status") or "") == "pending"
        self.accept_button.setEnabled(bool(self.current_candidate_id and pending))
        self.reject_button.setEnabled(bool(self.current_candidate_id and pending))
        self.expire_button.setEnabled(bool(self.current_candidate_id and pending))

    def update_memory_actions(self) -> None:
        item = self.memories_list.currentItem()
        row = dict(item.data(Qt.ItemDataRole.UserRole) or {}) if item is not None else {}
        self.current_memory_id = str(row.get("memory_id") or "")
        status = str(row.get("status") or "")
        self.disable_button.setEnabled(bool(self.current_memory_id and status == "active"))
        self.delete_button.setEnabled(bool(self.current_memory_id and status != "deleted"))

    def _top_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACING.compact)
        row.addWidget(self.back_button)
        row.addWidget(self.mode_chip)
        row.addWidget(self.state_label, 1)
        return row

    def _candidate_card(self) -> Card:
        card = Card("MemoryCandidate", "未加载", "点击加载候选后读取 pending / accepted / rejected / expired。")
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(SPACING.compact)
        controls.addWidget(QLabel("状态"))
        controls.addWidget(self.status_filter)
        controls.addWidget(self.load_candidates_button)
        controls.addWidget(self.accept_button)
        controls.addWidget(self.reject_button)
        controls.addWidget(self.expire_button)
        controls.addStretch(1)
        wrapper = QWidget()
        wrapper.setLayout(controls)
        card.add_body_widget(wrapper)
        card.add_body_widget(self.candidates_list)
        return card

    def _memory_card(self) -> Card:
        card = Card("SavedMemory", "未加载", "deleted tombstone 显示“已删除，仅保留删除记录”。")
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(SPACING.compact)
        controls.addWidget(QLabel("状态"))
        controls.addWidget(self.memory_status_filter)
        controls.addWidget(self.load_memories_button)
        controls.addWidget(self.disable_button)
        controls.addWidget(self.delete_button)
        controls.addWidget(self.clear_button)
        controls.addStretch(1)
        wrapper = QWidget()
        wrapper.setLayout(controls)
        card.add_body_widget(wrapper)
        card.add_body_widget(self.memories_list)
        return card

    def _preview_card(self) -> Card:
        card = Card("Preview", "未刷新", "backup/export/privacy 只做预览，不写文件、不发云端、不进入正式搜索。")
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(SPACING.compact)
        controls.addWidget(self.refresh_previews_button)
        controls.addWidget(self.copy_export_button)
        controls.addStretch(1)
        wrapper = QWidget()
        wrapper.setLayout(controls)
        card.add_body_widget(wrapper)
        card.add_body_widget(QLabel("Backup preview"))
        card.add_body_widget(self.backup_preview)
        card.add_body_widget(QLabel("Export preview"))
        card.add_body_widget(self.export_preview)
        card.add_body_widget(QLabel("Privacy status"))
        card.add_body_widget(self.privacy_status)
        return card

    def _render_candidates(self, rows: list[Dict[str, Any]], model: Dict[str, Any]) -> None:
        selected = self.current_candidate_id
        selected_item = None
        self.candidates_list.clear()
        for row in rows:
            item = QListWidgetItem(self._candidate_text(row))
            item.setData(Qt.ItemDataRole.UserRole, dict(row))
            self.candidates_list.addItem(item)
            if selected and row.get("candidate_id") == selected:
                selected_item = item
        if selected_item is not None:
            self.candidates_list.setCurrentItem(selected_item)
        if not rows:
            self.candidates_list.addItem(self._empty_candidate_text(model))

    def _render_memories(self, rows: list[Dict[str, Any]], model: Dict[str, Any]) -> None:
        selected = self.current_memory_id
        selected_item = None
        self.memories_list.clear()
        for row in rows:
            item = QListWidgetItem(self._memory_text(row))
            item.setData(Qt.ItemDataRole.UserRole, dict(row))
            self.memories_list.addItem(item)
            if selected and row.get("memory_id") == selected:
                selected_item = item
        if selected_item is not None:
            self.memories_list.setCurrentItem(selected_item)
        if not rows:
            self.memories_list.addItem(self._empty_memory_text(model))

    @staticmethod
    def _candidate_text(row: Dict[str, Any]) -> str:
        return "\n".join(
            [
                f"{row.get('status', '')} | {row.get('type', '')} | sensitivity={row.get('sensitivity', '')}",
                str(row.get("proposed_text") or ""),
                f"source_message_ids={', '.join(row.get('source_message_ids') or [])}",
            ]
        )

    @staticmethod
    def _memory_text(row: Dict[str, Any]) -> str:
        status = str(row.get("status") or "")
        tombstone = str(row.get("tombstone_label") or "")
        text = str(row.get("text") or "")
        if bool(row.get("text_redacted")):
            text = "内容已删除"
        return "\n".join(
            part
            for part in [
                f"{status} | {row.get('type', '')} | sensitivity={row.get('sensitivity', '')}",
                tombstone,
                text,
                f"source_message_ids={', '.join(row.get('source_message_ids') or [])}",
            ]
            if part
        )

    @staticmethod
    def _empty_candidate_text(model: Dict[str, Any]) -> str:
        if str(model.get("state") or "") == "idle":
            return "尚未加载 MemoryCandidate。点击加载候选后才读取内存。"
        status_filter = str(model.get("status_filter") or "")
        labels = {"pending": "待确认", "accepted": "已接受", "rejected": "已拒绝", "expired": "已过期"}
        if status_filter:
            return f"没有{labels.get(status_filter, status_filter)}的 MemoryCandidate。"
        return "没有 MemoryCandidate；记忆候选不会自动创建或自动保存。"

    @staticmethod
    def _empty_memory_text(model: Dict[str, Any]) -> str:
        if str(model.get("state") or "") == "idle":
            return "尚未加载 SavedMemory。点击加载已保存记忆后才读取内存。"
        status_filter = str(model.get("memory_status_filter") or "")
        labels = {"active": "启用", "disabled": "已禁用", "deleted": "已删除"}
        if status_filter:
            return f"没有{labels.get(status_filter, status_filter)}的 SavedMemory。"
        return "无已保存记忆；长期记忆必须由你确认后才会保存。"

    @staticmethod
    def _backup_text(preview: Dict[str, Any]) -> str:
        if not preview:
            return "点击刷新预览。"
        backup = dict(preview.get("default_backup") or {})
        return "\n".join(
            [
                f"include_ai_memory={str(backup.get('include_ai_memory', False)).lower()}",
                f"include_ai_drafts={str(backup.get('include_ai_drafts', False)).lower()}",
                f"include_ai_conversations={str(backup.get('include_ai_conversations', False)).lower()}",
                f"writes_file={str(preview.get('writes_file', False)).lower()}",
                f"not_formal_knowledge={str(preview.get('not_formal_knowledge', True)).lower()}",
            ]
        )

    @staticmethod
    def _export_text(preview: Dict[str, Any]) -> str:
        if not preview:
            return "点击刷新预览。"
        includes = dict(preview.get("includes") or {})
        return "\n".join(
            [
                f"writes_file={str(preview.get('writes_file', False)).lower()}",
                f"cloud_send_allowed={str(preview.get('cloud_send_allowed', False)).lower()}",
                f"formal_search_records={str(includes.get('formal_search_records', False)).lower()}",
                f"memory_count={int(preview.get('memory_count') or 0)}",
                json.dumps({"includes": includes}, ensure_ascii=False, sort_keys=True),
            ]
        )

    @staticmethod
    def _privacy_text(status: Dict[str, Any], model: Dict[str, Any]) -> str:
        if not status:
            return "点击刷新预览。"
        privacy = dict(status.get("privacy") or {})
        lines = [
            f"privacy_mode={str(privacy.get('privacy_mode', False)).lower()}",
            f"memory_candidate_creation_allowed={str(status.get('memory_candidate_creation_allowed', False)).lower()}",
            f"memory_save_allowed={str(status.get('memory_save_allowed', False)).lower()}",
            f"cloud_send_allowed={str(status.get('cloud_send_allowed', False)).lower()}",
            f"formal_search_records={str(status.get('formal_search_records', False)).lower()}",
        ]
        reason = str(model.get("save_blocked_reason") or status.get("save_blocked_reason") or "")
        if reason:
            lines.append(reason)
        return "\n".join(lines)
