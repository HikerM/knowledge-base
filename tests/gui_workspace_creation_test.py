#!/usr/bin/env python3
"""Qt offscreen checks for the workspace creation wizard."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


def _choose_template(gate, template_id: str) -> None:
    index = next(index for index in range(gate.template_select.count()) if gate.template_select.itemData(index) == template_id)
    gate.template_select.setCurrentIndex(index)


def _generate_plan(app, gate, target: Path, name: str, template_id: str) -> None:
    gate.target_input.setText(str(target))
    gate.next_button.click()
    app.processEvents()
    gate.name_input.setText(name)
    gate.next_button.click()
    app.processEvents()
    _choose_template(gate, template_id)
    gate.next_button.click()
    app.processEvents()
    gate.generate_button.click()
    app.processEvents()


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # noqa: BLE001
        print(f"gui workspace creation skipped: PySide6 unavailable: {exc}")
        return 0

    from gui.adapters.service_adapter import ServiceAdapter
    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    with tempfile.TemporaryDirectory(prefix="pkb-gui-create-") as tmp:
        root = Path(tmp)

        fake_target = root / "planned-kb"
        fake_adapter = FakeServiceAdapter()
        fake_window = MainWindow(creation_adapter=fake_adapter, gui_settings_path=root / "fake-settings.json")
        fake_window.show()
        app.processEvents()

        gate = fake_window.shell.workspace_gate_view
        assert fake_window.shell.current_route == "workspace_gate"
        assert "请选择一个知识库文件夹" in gate.header.title.text()
        assert "不会自动扫描或修改你的文件" in gate.header.subtitle.text()
        assert gate.select_button.text() == "打开已有知识库"
        assert gate.create_wizard_button.text() == "新建一个知识库"
        assert fake_adapter.calls == []

        gate.create_wizard_button.click()
        app.processEvents()
        assert fake_adapter.calls == [("list_workspace_templates", {})]
        assert gate.template_select.count() == 5

        _generate_plan(app, gate, fake_target, "计划知识库", "developer")
        assert fake_adapter.calls[-1][0] == "create_workspace_plan"
        assert fake_adapter.calls[-1][1]["target_path"] == str(fake_target)
        assert fake_adapter.calls[-1][1]["workspace_name"] == "计划知识库"
        assert fake_adapter.calls[-1][1]["template_id"] == "developer"
        preview = gate.plan_preview.toPlainText()
        assert "创建计划预览" in preview
        assert "模板：开发者 (developer)" in preview
        assert "将创建的文件夹" in preview
        assert "将创建的文件" in preview
        assert "将写入的配置" in preview
        assert "dry_run: True" in preview
        assert "would_modify: False" in preview
        assert "workspace.yaml" in preview
        assert "index_status" in preview and "missing" in preview
        assert "auto_index_started" in preview and "false" in preview.lower()
        assert gate.create_button.isEnabled()
        assert not fake_target.exists(), "plan generation must not create target directory"

        gate.copy_button.click()
        app.processEvents()
        assert "workspace.yaml" in QApplication.clipboard().text()

        error_target = root / "execute-error-kb"
        gate.target_input.setText(str(error_target))
        gate.name_input.setText("执行失败知识库")
        gate.generate_plan()
        app.processEvents()
        gate.create_button.click()
        app.processEvents()
        assert gate.create_confirm_label.isVisible()
        assert not error_target.exists(), "first create click only asks for confirmation"
        gate.create_button.click()
        app.processEvents()
        assert fake_adapter.calls[-1][0] == "create_workspace_from_plan"
        assert "创建失败" in gate.plan_preview.toPlainText()
        assert not error_target.exists()

        blocked_target = root / "non-empty-target"
        gate.target_input.setText(str(blocked_target))
        gate.name_input.setText("阻断知识库")
        gate.generate_plan()
        app.processEvents()
        blocked_preview = gate.plan_preview.toPlainText()
        assert "blocked: True" in blocked_preview
        assert "非空目录" in blocked_preview or "已经有内容" in blocked_preview
        assert "需要换一个位置" in gate.plan_status_chip.text()
        assert not gate.create_button.isEnabled()
        assert not blocked_target.exists()
        for raw_error, friendly in [
            ("target_path exists and is not empty; non-empty initialization is blocked in this version", "已经有内容"),
            ("target_path is inside the application install directory: D:/App", "安装目录"),
            ("target_path is inside a protected runtime/build directory: .git", "受保护目录"),
            ("target_path cannot be inspected: access denied", "权限不足"),
        ]:
            gate._show_plan_error(raw_error)
            app.processEvents()
            assert friendly in gate.plan_preview.toPlainText()
        fake_window.close()
        app.processEvents()

        created_target = root / "created-kb"
        settings_path = root / "real-settings.json"
        real_window = MainWindow(creation_adapter=ServiceAdapter(), gui_settings_path=settings_path)
        real_window.show()
        app.processEvents()
        real_gate = real_window.shell.workspace_gate_view
        real_gate.create_wizard_button.click()
        app.processEvents()
        _generate_plan(app, real_gate, created_target, "真实创建知识库", "personal")
        assert not created_target.exists()
        real_gate.create_button.click()
        app.processEvents()
        assert real_gate.create_confirm_label.isVisible()
        assert not created_target.exists()
        real_gate.create_button.click()
        app.processEvents()

        assert (created_target / "workspace.yaml").exists()
        assert (created_target / "config" / "categories.yaml").exists()
        assert (created_target / "knowledge").is_dir()
        assert (created_target / "templates").is_dir()
        assert (created_target / "reports").is_dir()
        assert not (created_target / ".kb").exists()
        assert not (created_target / ".kb" / "index.sqlite").exists()
        assert not list((created_target / "knowledge").rglob("*.md"))
        assert real_window.workspace_path == created_target.resolve()
        assert real_window.shell.current_route == "workspace_gate"
        assert real_window.shell.stack.currentWidget() is real_window.shell.workspace_gate_view
        assert real_gate.stack.currentWidget() is real_gate.success_page
        assert "知识库已创建" in real_gate.success_card.value_label.text()
        assert str(created_target.resolve()) in real_gate.success_path_label.text()
        assert "index_status=missing" in real_gate.success_status_chip.text()
        assert "添加资料" in real_gate.success_next_steps.toPlainText()
        assert "建立搜索索引" in real_gate.success_next_steps.toPlainText()
        assert "查看备份设置" in real_gate.success_next_steps.toPlainText()
        assert real_window.shell.workspace_vm.data["index_status"] == "missing"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        assert settings["last_opened_workspace"] == str(created_target.resolve())
        real_gate.success_dashboard_button.click()
        app.processEvents()
        assert real_window.shell.current_route == "dashboard"
        assert real_window.shell.workspace_vm.data["index_status"] == "missing"

        real_window.close()
        app.processEvents()

        restored_window = MainWindow(gui_settings_path=settings_path)
        restored_window.show()
        app.processEvents()
        assert restored_window.workspace_path == created_target.resolve()
        assert restored_window.shell.current_route == "dashboard"
        assert restored_window.shell.workspace_vm.data["index_status"] == "missing"
        assert not (created_target / ".kb" / "index.sqlite").exists()
        restored_window.close()
        app.processEvents()

        shutil.rmtree(created_target)
        unavailable_window = MainWindow(gui_settings_path=settings_path)
        unavailable_window.show()
        app.processEvents()
        unavailable_gate = unavailable_window.shell.workspace_gate_view
        assert unavailable_window.shell.current_route == "workspace_gate"
        assert "上次的知识库位置不可用" in unavailable_gate.card.value_label.text()
        assert "恢复文件夹" in unavailable_gate.card.caption_label.text()
        unavailable_window.close()
        app.processEvents()

    print("gui workspace creation tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
