#!/usr/bin/env python3
"""Qt offscreen checks for the workspace creation wizard."""

from __future__ import annotations

import json
import os
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
        assert gate.create_wizard_button.text() == "新建知识库"
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
        assert "create_error" in gate.plan_preview.toPlainText()
        assert not error_target.exists()

        blocked_target = root / "non-empty-target"
        gate.target_input.setText(str(blocked_target))
        gate.name_input.setText("阻断知识库")
        gate.generate_plan()
        app.processEvents()
        blocked_preview = gate.plan_preview.toPlainText()
        assert "blocked: True" in blocked_preview
        assert "not empty" in blocked_preview
        assert "计划被阻断" in gate.plan_status_chip.text()
        assert not gate.create_button.isEnabled()
        assert not blocked_target.exists()
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
        assert real_window.shell.current_route == "dashboard"
        assert real_window.shell.workspace_vm.data["index_status"] == "missing"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        assert settings["last_opened_workspace"] == str(created_target.resolve())

        real_window.close()
        app.processEvents()

    print("gui workspace creation tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
