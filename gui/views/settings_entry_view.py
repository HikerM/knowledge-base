"""Read-only settings entry page."""

from __future__ import annotations

from typing import Any, Callable, Dict

from PySide6.QtWidgets import QLabel, QListWidget, QMessageBox, QVBoxLayout, QWidget

from gui.styles.tokens import SPACING
from gui.widgets.card import Card
from gui.widgets.controls import secondary_button
from gui.widgets.formatters import bool_label, status_label
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_chip import StatusChip, tone_for_status


def _short_path(path: str, max_chars: int = 72) -> str:
    if len(path) <= max_chars:
        return path
    return f"...{path[-max_chars + 3:]}"


class SettingsEntryView(QWidget):
    def __init__(self, settings_vm: Any, gui_settings_provider: Callable[[], Dict[str, Any]] | None = None, reset_window_layout: Callable[[], None] | None = None):
        super().__init__()
        self.settings_vm = settings_vm
        self.gui_settings_provider = gui_settings_provider
        self.reset_window_layout = reset_window_layout
        self.workspace_card = Card("工作区", "未知", "")
        self.window_card = Card("窗口布局", "未加载", "")
        self.reset_window_button = secondary_button("重置窗口布局")
        self.reset_window_button.clicked.connect(self._confirm_reset_window_layout)
        self.window_card.add_body_widget(self.reset_window_button)
        self.local_card = Card("本地文件", "当前用户目录", "")
        self.service_card = Card("只读状态", "未加载", "")
        self.service_chip = StatusChip("服务：未知", "muted")
        self.index_chip = StatusChip("索引：未知", "muted")
        self.mutation_chip = StatusChip("写入能力：未开放", "muted")
        self.service_card.add_body_widget(self.service_chip)
        self.service_card.add_body_widget(self.index_chip)
        self.service_card.add_body_widget(self.mutation_chip)
        self.notice = QLabel("知识库设置保持只读；窗口布局只保存到当前用户目录，不写入工作区。")
        self.notice.setObjectName("mutedText")
        self.notice.setWordWrap(True)
        self.sections = QListWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING.page, SPACING.page, SPACING.page, SPACING.page)
        root.setSpacing(SPACING.gap)
        root.addWidget(SectionHeader("设置", "查看工作区和只读能力边界。"))
        root.addWidget(self.workspace_card)
        root.addWidget(self.window_card)
        root.addWidget(self.local_card)
        root.addWidget(self.service_card)
        root.addWidget(self.notice)
        section_title = QLabel("功能区域")
        section_title.setObjectName("cardValue")
        root.addWidget(section_title)
        root.addWidget(self.sections, 1)

    def load_settings(self) -> None:
        self.render_settings(self.settings_vm.load_entry())

    def focus_primary(self) -> None:
        self.sections.setFocus()

    def render_settings(self, model: Dict[str, Any]) -> None:
        data = model.get("data") or {}
        workspace_path = str(data.get("workspace_path") or "")
        snapshot = self.gui_settings_provider() if self.gui_settings_provider else {}
        current_workspace = str(snapshot.get("current_workspace") or workspace_path)
        last_workspace = str(snapshot.get("last_opened_workspace") or "")
        self.workspace_card.set_content("工作区", _short_path(current_workspace) or "未选择", f"上次打开：{_short_path(last_workspace, 48) or '无'}")
        self.workspace_card.setToolTip(workspace_path)
        self._render_gui_settings(snapshot)
        self._render_local_paths(snapshot)
        service_status = data.get("service_status")
        index_status = data.get("index_status")
        self.service_card.set_content("只读状态", "服务边界正常", f"文档 {data.get('document_count', 0)} / 分块 {data.get('chunk_count', 0)}")
        self.service_chip.set_chip(f"服务：{status_label(service_status)}", tone_for_status(service_status))
        self.index_chip.set_chip(f"索引：{status_label(index_status)}", tone_for_status(index_status))
        self.mutation_chip.set_chip("写入能力：未开放", "muted")
        rows = data.get("sections") or []
        self.sections.clear()
        for row in rows:
            values = [row.get("label", ""), self._phase_label(row.get("phase")), bool_label(row.get("read_only")), bool_label(row.get("editable")), bool_label(row.get("execute_available"))]
            self.sections.addItem(f"{values[0]} · {values[1]} · 只读 {values[2]} · 可编辑 {values[3]} · 可执行 {values[4]}")
        if not rows:
            self.sections.addItem("没有可展示的设置区域。")

    def _render_gui_settings(self, snapshot: Dict[str, Any]) -> None:
        size_text = f"{snapshot.get('window_width', 0)} x {snapshot.get('window_height', 0)}"
        if snapshot.get("maximized"):
            size_text = f"{size_text}（最大化）"
        path = str(snapshot.get("settings_path") or "")
        caption = f"保存位置：{_short_path(path, 64)}" if path else "保存位置：当前用户目录"
        self.window_card.set_content("窗口布局", size_text, caption)
        self.window_card.setToolTip(path)

    def _render_local_paths(self, snapshot: Dict[str, Any]) -> None:
        settings_path = str(snapshot.get("settings_path") or "")
        log_path = str(snapshot.get("log_path") or "")
        caption = f"设置：{_short_path(settings_path, 56)}"
        self.local_card.set_content("本地文件", "仅保存到当前用户目录", f"{caption} · 日志：{_short_path(log_path, 44) or '未配置'}")
        self.local_card.setToolTip(f"GUI 设置：{settings_path}\n日志：{log_path}")

    def _confirm_reset_window_layout(self) -> None:
        if self.reset_window_layout is None:
            return
        result = QMessageBox.question(self, "重置窗口布局", "重置后将使用默认窗口大小和居中位置，只影响当前用户的本地界面设置。是否继续？")
        if result == QMessageBox.StandardButton.Yes:
            self.reset_window_layout()

    @staticmethod
    def _phase_label(value: str) -> str:
        if value == "future":
            return "未来阶段"
        if value == "phase_1_read_only":
            return "第一阶段只读"
        return value or "未知"
