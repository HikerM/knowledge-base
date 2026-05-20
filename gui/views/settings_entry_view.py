"""Read-only settings entry page."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget

from gui.styles.tokens import SPACING
from gui.widgets.card import Card
from gui.widgets.formatters import bool_label, status_label
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_chip import StatusChip, tone_for_status


def _short_path(path: str, max_chars: int = 72) -> str:
    if len(path) <= max_chars:
        return path
    return f"...{path[-max_chars + 3:]}"


class SettingsEntryView(QWidget):
    def __init__(self, settings_vm: Any):
        super().__init__()
        self.settings_vm = settings_vm
        self.workspace_card = Card("工作区", "未知", "")
        self.service_card = Card("只读状态", "未加载", "")
        self.service_chip = StatusChip("服务：未知", "muted")
        self.index_chip = StatusChip("索引：未知", "muted")
        self.mutation_chip = StatusChip("写入能力：未开放", "muted")
        self.service_card.add_body_widget(self.service_chip)
        self.service_card.add_body_widget(self.index_chip)
        self.service_card.add_body_widget(self.mutation_chip)
        self.notice = QLabel("当前设置入口仅展示只读信息，不提供编辑、保存、应用或执行操作。")
        self.notice.setObjectName("mutedText")
        self.notice.setWordWrap(True)
        self.sections = QListWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING.page, SPACING.page, SPACING.page, SPACING.page)
        root.setSpacing(SPACING.gap)
        root.addWidget(SectionHeader("设置", "查看工作区和只读能力边界。"))
        root.addWidget(self.workspace_card)
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
        self.workspace_card.set_content("工作区", _short_path(workspace_path) or "未知", "完整路径见提示")
        self.workspace_card.setToolTip(workspace_path)
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

    @staticmethod
    def _phase_label(value: str) -> str:
        if value == "future":
            return "未来阶段"
        if value == "phase_1_read_only":
            return "第一阶段只读"
        return value or "未知"
