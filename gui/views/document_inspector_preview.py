"""Right-side document inspector with metadata and a short preview only."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from gui.styles.tokens import SPACING
from gui.widgets.card import Card
from gui.widgets.formatters import bool_label, confidence_label, layer_label, source_type_label, status_label
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_chip import StatusChip, tone_for_status


def _short_path(path: str, max_chars: int = 58) -> str:
    return path if len(path) <= max_chars else f"...{path[-max_chars + 3:]}"


class DocumentInspectorPreview(QWidget):
    """Lightweight inspector. It intentionally does not render full document body."""

    def __init__(self):
        super().__init__()
        self.header = SectionHeader("快速预览", "选择一条结果后，在这里查看文档摘要和元数据。")
        self.title = QLabel("未选择文档")
        self.title.setObjectName("cardValue")
        self.path = QLabel("")
        self.path.setObjectName("pathLabel")
        self.path.setWordWrap(True)
        self.layer_chip = StatusChip("层级：未知", "muted")
        self.status_chip = StatusChip("状态：未知", "muted")
        self.confidence_chip = StatusChip("可信度：未知", "muted")
        self.source_chip = StatusChip("来源：未知", "muted")
        self.summary_card = Card("摘要", "未打开", "完整内容请在主区域打开")
        self.metadata = QTextEdit()
        self.metadata.setReadOnly(True)
        self.metadata.setMaximumHeight(150)
        self.metadata.setLineWrapMode(QTextEdit.WidgetWidth)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.compact)
        layout.addWidget(self.header)
        layout.addWidget(self.title)
        layout.addWidget(self.path)
        for chip in [self.layer_chip, self.status_chip, self.confidence_chip, self.source_chip]:
            layout.addWidget(chip)
        layout.addWidget(self.summary_card)
        meta_title = QLabel("元数据")
        meta_title.setObjectName("cardTitle")
        layout.addWidget(meta_title)
        layout.addWidget(self.metadata)
        layout.addStretch(1)
        self.render_empty()

    def render_empty(self) -> None:
        self.header.set_subtitle("选择一条结果后，在这里查看文档摘要和元数据。")
        self.title.setText("未选择文档")
        self.path.setText("")
        self.layer_chip.set_chip("层级：未知", "muted")
        self.status_chip.set_chip("状态：未知", "muted")
        self.confidence_chip.set_chip("可信度：未知", "muted")
        self.source_chip.set_chip("来源：未知", "muted")
        self.summary_card.set_content("摘要", "未打开", "完整内容请在主区域打开")
        self.metadata.setPlainText("")

    def render_document(self, model: Dict[str, Any], row: Dict[str, Any] | None = None) -> None:
        if model.get("state") == "error":
            message = "; ".join(item.get("message", "") for item in model.get("errors", []))
            self.title.setText("文档打开失败")
            self.path.setText("")
            self.status_chip.set_chip("状态：错误", "danger")
            self.summary_card.set_content("错误", message or "服务不可用", "请回到列表重新选择文档")
            self.metadata.setPlainText("")
            return
        data = model.get("data") or {}
        path = str(data.get("path") or (row or {}).get("path") or "")
        self.title.setText(str(data.get("title") or (row or {}).get("title") or "未命名文档"))
        self.path.setText(f"路径：{_short_path(path)}")
        self.path.setToolTip(path)
        self.layer_chip.set_chip(f"层级：{layer_label(data.get('layer'))}", "info")
        self.status_chip.set_chip(f"状态：{status_label(data.get('status'))}", tone_for_status(data.get("status")))
        self.confidence_chip.set_chip(f"可信度：{confidence_label(data.get('confidence'))}", "muted")
        self.source_chip.set_chip(f"来源：{source_type_label(data.get('source_type'))}", "muted")
        snippet = str((row or {}).get("snippet") or "已加载元数据。完整文档内容请在主区域打开。")
        self.summary_card.set_content("摘要", snippet, "右侧仅显示快速预览")
        self.metadata.setPlainText(_metadata_text(data))


def _metadata_text(data: Dict[str, Any]) -> str:
    rows: list[tuple[str, Any]] = [
        ("标题", data.get("title")),
        ("层级", layer_label(data.get("layer"))),
        ("状态", status_label(data.get("status"))),
        ("可信度", confidence_label(data.get("confidence"))),
        ("来源类型", source_type_label(data.get("source_type"))),
        ("来源链接", data.get("source_url") or "无"),
        ("需审核", bool_label(data.get("review_required"))),
        ("最近审核", data.get("last_reviewed") or "未知"),
    ]
    return "\n".join(f"{label}：{value or '未知'}" for label, value in rows)

