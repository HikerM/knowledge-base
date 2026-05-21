"""First-run workspace selection and minimal creation wizard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.styles.tokens import SPACING
from gui.widgets.card import Card
from gui.widgets.controls import Select, primary_button, secondary_button
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_chip import StatusChip


class WorkspaceGateView(QWidget):
    """Friendly first-run gate before a workspace is selected."""

    workspace_selected = Signal(str)
    workspace_created = Signal(str)

    def __init__(self, creation_vm: Any | None = None):
        super().__init__()
        self.creation_vm = creation_vm
        self.setObjectName("workspaceGate")
        self.header = SectionHeader("请选择一个知识库文件夹", "不会自动扫描或修改你的文件。")
        self.status_chip = StatusChip("未选择知识库", "warning")
        self._last_path = ""
        self._step_index = 0
        self._templates_loaded = False
        self._create_confirmation_pending = False

        self.stack = QStackedWidget()
        self.entry_page = QWidget()
        self.wizard_page = QWidget()
        self.success_page = QWidget()
        self.stack.addWidget(self.entry_page)
        self.stack.addWidget(self.wizard_page)
        self.stack.addWidget(self.success_page)

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING.page, SPACING.page, SPACING.page, SPACING.page)
        root.setSpacing(SPACING.gap)
        root.addWidget(self.header)
        root.addWidget(self.stack, 1)

        self._build_entry_page()
        self._build_wizard_page()
        self._build_success_page()
        self.select_button.clicked.connect(self.choose_workspace)
        self.retry_button.clicked.connect(self._retry_last)
        self.create_wizard_button.clicked.connect(self.start_creation_wizard)
        self.back_to_gate_button.clicked.connect(self.show_unselected)
        self.success_dashboard_button.clicked.connect(self._open_created_workspace_status)
        self.browse_button.clicked.connect(self.choose_target_path)
        self.next_button.clicked.connect(self.next_step)
        self.back_button.clicked.connect(self.previous_step)
        self.generate_button.clicked.connect(self.generate_plan)
        self.copy_button.clicked.connect(self.copy_plan_summary)
        self.create_button.clicked.connect(self.handle_create_click)

    def _build_entry_page(self) -> None:
        self.message = QLabel("打开已有知识库或新建一个知识库。应用不会自动扫描或修改你的文件。")
        self.message.setObjectName("mutedText")
        self.message.setWordWrap(True)
        self.card = Card("首次使用", "请选择一个知识库文件夹", "搜索索引尚未建立时，只会显示状态提示，不会自动 index。")
        self.select_button = primary_button("打开已有知识库")
        self.select_button.setObjectName("selectExistingWorkspaceButton")
        self.create_wizard_button = secondary_button("新建一个知识库")
        self.create_wizard_button.setObjectName("createWorkspaceWizardButton")
        self.retry_button = secondary_button("重新检测")
        self.retry_button.setVisible(False)
        self.card.add_body_widget(self.status_chip)
        self.card.add_body_widget(self.select_button)
        self.card.add_body_widget(self.create_wizard_button)
        self.card.add_body_widget(self.retry_button)
        layout = QVBoxLayout(self.entry_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.gap)
        layout.addWidget(self.message)
        layout.addWidget(self.card)
        layout.addStretch(1)

    def _build_wizard_page(self) -> None:
        self.wizard_step_label = QLabel("")
        self.wizard_step_label.setObjectName("mutedText")
        self.wizard_stack = QStackedWidget()

        self.target_input = QLineEdit()
        self.target_input.setObjectName("wizardTargetInput")
        self.target_input.setPlaceholderText("例如 D:\\Knowledge\\PersonalKB")
        self.browse_button = secondary_button("选择目录")
        location = QWidget()
        location_layout = QVBoxLayout(location)
        location_layout.setContentsMargins(0, 0, 0, 0)
        location_layout.setSpacing(SPACING.gap)
        location_layout.addWidget(Card("Step 1", "选择创建位置", "建议选择 Documents 或其他用户数据目录。不会写安装目录。"))
        row = QHBoxLayout()
        row.addWidget(self.target_input, 1)
        row.addWidget(self.browse_button)
        location_layout.addLayout(row)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("wizardNameInput")
        self.name_input.setPlaceholderText("我的知识库")
        name = QWidget()
        name_layout = QVBoxLayout(name)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(SPACING.gap)
        name_layout.addWidget(Card("Step 2", "输入知识库名称", "名称只用于显示，不作为稳定 workspace_id。"))
        name_layout.addWidget(self.name_input)

        self.template_select = Select()
        self.template_select.setObjectName("wizardTemplateSelect")
        template = QWidget()
        template_layout = QVBoxLayout(template)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.setSpacing(SPACING.gap)
        template_layout.addWidget(Card("Step 3", "选择模板", "模板只影响初始结构和配置，不创建正式知识。"))
        template_layout.addWidget(self.template_select)

        generate = QWidget()
        generate_layout = QVBoxLayout(generate)
        generate_layout.setContentsMargins(0, 0, 0, 0)
        generate_layout.setSpacing(SPACING.gap)
        generate_layout.addWidget(Card("Step 4", "生成创建计划", "先预览将创建的文件夹、文件和配置；被阻断时不会写入。"))
        self.generate_button = primary_button("生成创建计划")
        self.generate_button.setObjectName("wizardGenerateButton")
        generate_layout.addWidget(self.generate_button)

        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(SPACING.gap)
        self.plan_status_chip = StatusChip("尚未生成计划", "muted")
        self.plan_preview = QTextEdit()
        self.plan_preview.setObjectName("wizardPlanPreview")
        self.plan_preview.setReadOnly(True)
        self.plan_preview.setMinimumHeight(260)
        self.copy_button = secondary_button("复制计划摘要")
        self.copy_button.setObjectName("wizardCopyPlanButton")
        self.create_confirm_label = QLabel("创建前请确认：只会写入预览中的最小目录、workspace.yaml 和 config，不会创建 .kb/index.sqlite，也不会自动 index 或导入资料。")
        self.create_confirm_label.setObjectName("mutedText")
        self.create_confirm_label.setWordWrap(True)
        self.create_confirm_label.setVisible(False)
        self.create_button = primary_button("创建知识库")
        self.create_button.setObjectName("wizardCreateButton")
        self.create_button.setEnabled(False)
        preview_layout.addWidget(Card("Step 5", "计划预览", "确认后只执行最小创建，不会自动 index。"))
        preview_layout.addWidget(self.plan_status_chip)
        preview_layout.addWidget(self.plan_preview, 1)
        preview_layout.addWidget(self.copy_button)
        preview_layout.addWidget(self.create_confirm_label)
        preview_layout.addWidget(self.create_button)

        for page in [location, name, template, generate, preview]:
            self.wizard_stack.addWidget(page)

        controls = QHBoxLayout()
        self.back_button = secondary_button("返回")
        self.next_button = primary_button("下一步")
        self.back_to_gate_button = secondary_button("取消")
        controls.addWidget(self.back_to_gate_button)
        controls.addStretch(1)
        controls.addWidget(self.back_button)
        controls.addWidget(self.next_button)

        layout = QVBoxLayout(self.wizard_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.gap)
        layout.addWidget(self.wizard_step_label)
        layout.addWidget(self.wizard_stack, 1)
        layout.addLayout(controls)

    def _build_success_page(self) -> None:
        self.success_card = Card("创建成功", "知识库已创建", "搜索索引尚未建立；本次没有自动 index、导入资料或创建正式知识。")
        self.success_status_chip = StatusChip("index_status=missing", "warning")
        self.success_path_label = QLabel("")
        self.success_path_label.setObjectName("mutedText")
        self.success_path_label.setWordWrap(True)
        self.success_next_steps = QTextEdit()
        self.success_next_steps.setObjectName("workspaceCreationSuccessText")
        self.success_next_steps.setReadOnly(True)
        self.success_next_steps.setMinimumHeight(160)
        self.success_dashboard_button = primary_button("查看工作区状态")
        self.success_dashboard_button.setObjectName("workspaceCreationStatusButton")
        self.success_card.add_body_widget(self.success_status_chip)
        self.success_card.add_body_widget(self.success_path_label)
        self.success_card.add_body_widget(self.success_next_steps)
        self.success_card.add_body_widget(self.success_dashboard_button)

        layout = QVBoxLayout(self.success_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING.gap)
        layout.addWidget(self.success_card)
        layout.addStretch(1)

    def choose_workspace(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "请选择一个知识库文件夹")
        if path:
            self.submit_workspace(path)

    def choose_target_path(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "请选择新知识库位置")
        if path:
            self.target_input.setText(path)

    def start_creation_wizard(self) -> None:
        self.stack.setCurrentWidget(self.wizard_page)
        self._step_index = 0
        self._load_templates()
        self._show_step(0)

    def next_step(self) -> None:
        if self._step_index < self.wizard_stack.count() - 1:
            self._show_step(self._step_index + 1)

    def previous_step(self) -> None:
        if self._step_index > 0:
            self._show_step(self._step_index - 1)
        else:
            self.show_unselected()

    def generate_plan(self) -> None:
        if self.creation_vm is None:
            self._show_plan_error("当前环境暂不支持创建计划。")
            return
        plan = self.creation_vm.create_plan(
            target_path=self.target_input.text().strip(),
            workspace_name=self.name_input.text().strip(),
            template_id=str(self.template_select.currentData() or ""),
        )
        data = dict(plan.get("data") or {})
        if plan.get("state") == "error":
            self._show_plan_error(_format_errors(plan))
        else:
            self._render_plan(data)
        self._show_step(4)

    def copy_plan_summary(self) -> None:
        QApplication.clipboard().setText(self.plan_preview.toPlainText())

    def handle_create_click(self) -> None:
        if self.creation_vm is None:
            self._show_create_error("当前环境暂不支持创建知识库。")
            return
        plan_data = self.creation_vm.plan_data
        if not plan_data:
            self._show_create_error("请先生成创建计划。")
            return
        if plan_data.get("blocked"):
            self._show_create_error("计划被阻断，不能执行创建。")
            return
        if not self._create_confirmation_pending:
            self._create_confirmation_pending = True
            self.create_confirm_label.setVisible(True)
            self.create_button.setText("确认创建知识库")
            self.plan_status_chip.set_chip("等待创建确认", "warning")
            return

        result = self.creation_vm.create_workspace_from_current_plan(confirmed=True)
        data = dict(result.get("data") or {})
        if result.get("state") == "ready" and data.get("success"):
            workspace_path = str(data.get("workspace_path") or plan_data.get("target_path") or "")
            self.show_creation_success(workspace_path, index_status="missing")
            self.create_button.setEnabled(False)
            self.create_button.setText("已创建")
            self.plan_preview.setPlainText(f"{self.plan_preview.toPlainText()}\n\ncreate_result:\n{_format_result(data)}")
            self.workspace_created.emit(workspace_path)
            return
        self._show_create_error(_format_errors(result) or "\n".join(data.get("errors", [])) or "创建失败。")

    def submit_workspace(self, path: str | Path) -> None:
        self._last_path = str(path)
        self.workspace_selected.emit(str(path))

    def show_unselected(self) -> None:
        self.stack.setCurrentWidget(self.entry_page)
        self.status_chip.set_chip("未选择知识库", "warning")
        self.card.set_content("首次使用", "请选择一个知识库文件夹", "不会自动扫描或修改你的文件。")
        self.retry_button.setVisible(False)

    def show_unavailable_last_workspace(self, path: str) -> None:
        self.stack.setCurrentWidget(self.entry_page)
        self._last_path = path
        self.status_chip.set_chip("上次的知识库位置不可用", "warning")
        self.card.set_content("需要重新选择", "上次的知识库位置不可用", f"{_short_path(path)} · 请连接磁盘、恢复文件夹，或打开其他知识库。")
        self.retry_button.setVisible(False)

    def show_error(self, message: str, path: str = "") -> None:
        self.stack.setCurrentWidget(self.entry_page)
        self._last_path = path
        self.status_chip.set_chip("文件夹不可用", "danger")
        self.card.set_content("请选择其他文件夹", _friendly_error(message), _short_path(path))
        self.retry_button.setVisible(bool(path))

    def show_index_missing(self, path: str) -> None:
        self.stack.setCurrentWidget(self.entry_page)
        self.status_chip.set_chip("搜索索引尚未建立", "warning")
        self.card.set_content("已选择知识库", "搜索索引尚未建立", f"{_short_path(path)} · 不会自动 index，你可以稍后从任务入口建立索引。")
        self.retry_button.setVisible(False)

    def show_creation_success(self, path: str, index_status: str = "missing") -> None:
        self._last_path = path
        self.stack.setCurrentWidget(self.success_page)
        self.success_status_chip.set_chip(f"index_status={index_status}", "warning" if index_status == "missing" else "ready")
        self.success_path_label.setText(f"workspace 路径：{path}")
        self.success_next_steps.setPlainText(
            "\n".join(
                [
                    "下一步建议：",
                    "- 添加资料：后续版本会提供安全入口；当前不会自动导入。",
                    "- 建立搜索索引：后续从任务入口显式启动；当前不会自动 index。",
                    "- 查看备份设置：进入设置或维护页面确认本地备份策略。",
                ]
            )
        )
        self.status_chip.set_chip("知识库已创建", "ready")

    def focus_primary(self) -> None:
        if self.stack.currentWidget() is self.entry_page:
            self.select_button.setFocus()
        elif self._step_index == 0:
            self.target_input.setFocus()
        elif self._step_index == 1:
            self.name_input.setFocus()

    def _load_templates(self) -> None:
        if self._templates_loaded or self.creation_vm is None:
            return
        result = self.creation_vm.list_templates()
        self.template_select.clear()
        rows = list(((result.get("data") or {}).get("templates")) or [])
        for item in rows:
            self.template_select.addItem(f"{item.get('display_name')} · {item.get('description')}", item.get("template_id"))
        self._templates_loaded = bool(rows)
        if not rows:
            self.template_select.addItem("模板不可用", "")

    def _show_step(self, index: int) -> None:
        self._step_index = max(0, min(index, self.wizard_stack.count() - 1))
        self.wizard_stack.setCurrentIndex(self._step_index)
        labels = ["Step 1 / 5", "Step 2 / 5", "Step 3 / 5", "Step 4 / 5", "Step 5 / 5"]
        self.wizard_step_label.setText(labels[self._step_index])
        self.back_button.setVisible(True)
        self.next_button.setVisible(self._step_index < 3)
        self.generate_button.setVisible(self._step_index == 3)
        if self._step_index == 4:
            self.next_button.setVisible(False)

    def _render_plan(self, data: Dict[str, Any]) -> None:
        blocked = bool(data.get("blocked"))
        self.plan_status_chip.set_chip("需要换一个位置" if blocked else "计划可确认", "danger" if blocked else "ready")
        self.plan_preview.setPlainText(_format_plan(data))
        self._create_confirmation_pending = False
        self.create_confirm_label.setVisible(False)
        self.create_button.setText("创建知识库")
        self.create_button.setEnabled(not blocked)

    def _show_plan_error(self, message: str) -> None:
        self.plan_status_chip.set_chip("计划生成失败", "danger")
        self.plan_preview.setPlainText(_friendly_error(message))
        self._create_confirmation_pending = False
        self.create_confirm_label.setVisible(False)
        self.create_button.setText("创建知识库")
        self.create_button.setEnabled(False)

    def _show_create_error(self, message: str) -> None:
        self.plan_status_chip.set_chip("创建失败", "danger")
        self.create_button.setText("创建知识库")
        self.create_button.setEnabled(True)
        self._create_confirmation_pending = False
        self.create_confirm_label.setVisible(False)
        self.plan_preview.setPlainText(f"{self.plan_preview.toPlainText()}\n\n创建失败：\n{_friendly_error(message)}")

    def _retry_last(self) -> None:
        if self._last_path:
            self.submit_workspace(self._last_path)

    def _open_created_workspace_status(self) -> None:
        if self._last_path:
            self.workspace_selected.emit(self._last_path)


def _format_plan(data: Dict[str, Any]) -> str:
    template_id = str(data.get("template_id") or "")
    blocked = bool(data.get("blocked"))
    lines = [
        "创建计划预览",
        f"计划编号：{data.get('plan_id', '')}",
        f"知识库名称：{data.get('workspace_name', '')}",
        f"创建位置：{data.get('target_path', '')}",
        f"模板：{_template_label(template_id)}",
        "执行方式：用户确认后只执行最小创建",
        f"安全状态：{'被阻断，需要换一个位置' if blocked else '可创建'}",
        f"dry_run: {data.get('dry_run')}",
        f"would_modify: {data.get('would_modify')}",
        f"blocked: {data.get('blocked')}",
        "",
        "将创建的文件夹：",
        *[f"- {_path_label(item)}" for item in data.get("would_create_dirs", [])],
        "",
        "将创建的文件：",
        *[f"- {_path_label(item)}" for item in data.get("would_create_files", [])],
        "",
        "将写入的配置：",
        *[f"- {_path_label(item)}" for item in data.get("would_write_configs", [])],
        "",
        "阻断原因：",
        *([f"- {_friendly_error(item)}" for item in data.get("blockers", [])] or ["- 无"]),
        "",
        "提示：",
        *([f"- {_friendly_warning(item)}" for item in data.get("warnings", [])] or ["- 无"]),
        "",
        "验收命令：",
        *[f"- {item}" for item in data.get("validation_commands", [])],
        "",
        "预计结果：",
        json.dumps(data.get("estimated_result", {}), ensure_ascii=False, indent=2),
    ]
    return "\n".join(lines)


def _format_errors(model: Dict[str, Any]) -> str:
    errors = model.get("errors") or []
    return "\n".join(_friendly_error(str(item.get("message") if isinstance(item, dict) else item)) for item in errors) or "创建计划不可用。请检查路径、名称和模板后重试。"


def _format_result(data: Dict[str, Any]) -> str:
    lines = [
        f"创建成功：{data.get('success')}",
        f"workspace 路径：{data.get('workspace_path', '')}",
        "index_status=missing",
        "",
        "已创建的文件夹：",
        *([f"- {_path_label(item)}" for item in data.get("created_dirs", [])] or ["- 无"]),
        "",
        "已创建的文件：",
        *([f"- {_path_label(item)}" for item in data.get("created_files", [])] or ["- 无"]),
        "",
        "已存在并跳过：",
        *([f"- {_path_label(item)}" for item in data.get("skipped_existing", [])] or ["- 无"]),
        "",
        "错误：",
        *([f"- {_friendly_error(item)}" for item in data.get("errors", [])] or ["- 无"]),
        "",
        "下一步：",
        *([f"- {item}" for item in data.get("next_steps", [])] or ["- 无"]),
    ]
    return "\n".join(lines)


def _template_label(template_id: str) -> str:
    labels = {
        "personal": "个人资料",
        "learning": "学习",
        "work": "工作",
        "developer": "开发者",
        "custom": "自定义",
    }
    return f"{labels.get(template_id, template_id or '未知模板')} ({template_id})" if template_id else "未知模板"


def _friendly_error(message: str) -> str:
    text = str(message or "").strip()
    lowered = text.lower()
    if "does not exist" in lowered or "不可用" in text:
        return "路径不存在或不可访问。请选择一个已经存在的知识库文件夹，或使用“新建一个知识库”。"
    if "not empty" in lowered:
        return "这个文件夹里已经有内容。本版本不会在非空目录中初始化；请选择空文件夹或输入一个新文件夹名称。"
    if "install directory" in lowered:
        return "不能把软件安装目录作为知识库。请选择 Documents、桌面以外的资料目录，或其他用户数据目录。"
    if "protected runtime/build directory" in lowered or ".git" in lowered or "build" in lowered or "dist" in lowered or "tmp" in lowered or "exports" in lowered or "backups" in lowered:
        return "目标位置在受保护目录中（.git/build/dist/tmp/exports/backups）。请选择普通用户资料目录。"
    if "permission" in lowered or "access" in lowered or "denied" in lowered or "cannot be inspected" in lowered:
        return "权限不足，无法检查或写入该位置。请选择有读写权限的目录，或调整目录权限后重试。"
    if "workspace_name" in lowered:
        return "知识库名称不能为空。请输入一个容易识别的名称。"
    if "template_id" in lowered or "unknown template" in lowered:
        return "模板不可用。请重新选择个人资料、学习、工作、开发者或自定义模板。"
    if "confirmed=true" in lowered:
        return "创建前需要用户确认。请再次点击“确认创建知识库”。"
    if "dry_run=true" in lowered or "would_modify=false" in lowered:
        return "创建计划已失效。请重新生成创建计划后再确认。"
    if "blocked" in lowered:
        return "当前计划被阻断，不能执行创建。请按阻断原因调整路径或输入后重新生成计划。"
    return text or "操作失败。请检查输入后重试。"


def _friendly_warning(message: str) -> str:
    text = str(message or "").strip()
    if "does not exist" in text.lower():
        return "目标文件夹还不存在；确认创建后会创建该文件夹。"
    return text


def _path_label(value: Any) -> str:
    text = str(value)
    return text or "未指定"


def _short_path(path: str, max_chars: int = 72) -> str:
    if len(path) <= max_chars:
        return path
    return f"...{path[-max_chars + 3:]}"
