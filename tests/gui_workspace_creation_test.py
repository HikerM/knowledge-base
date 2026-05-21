#!/usr/bin/env python3
"""Qt offscreen checks for the workspace creation plan wizard."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # noqa: BLE001
        print(f"gui workspace creation skipped: PySide6 unavailable: {exc}")
        return 0

    from gui.fixtures.fake_service_adapter import FakeServiceAdapter
    from gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    with tempfile.TemporaryDirectory(prefix="pkb-gui-create-") as tmp:
        root = Path(tmp)
        target = root / "planned-kb"
        adapter = FakeServiceAdapter()
        window = MainWindow(creation_adapter=adapter, gui_settings_path=root / "gui-settings.json")
        window.show()
        app.processEvents()

        gate = window.shell.workspace_gate_view
        assert window.shell.current_route == "workspace_gate"
        assert gate.create_wizard_button.text() == "新建知识库"
        assert adapter.calls == []

        gate.create_wizard_button.click()
        app.processEvents()
        assert adapter.calls == [("list_workspace_templates", {})]
        assert gate.template_select.count() == 5

        gate.target_input.setText(str(target))
        gate.next_button.click()
        app.processEvents()
        gate.name_input.setText("计划知识库")
        gate.next_button.click()
        app.processEvents()
        developer_index = next(index for index in range(gate.template_select.count()) if gate.template_select.itemData(index) == "developer")
        gate.template_select.setCurrentIndex(developer_index)
        gate.next_button.click()
        app.processEvents()
        gate.generate_button.click()
        app.processEvents()

        assert adapter.calls[-1][0] == "create_workspace_plan"
        assert adapter.calls[-1][1]["target_path"] == str(target)
        assert adapter.calls[-1][1]["workspace_name"] == "计划知识库"
        assert adapter.calls[-1][1]["template_id"] == "developer"
        preview = gate.plan_preview.toPlainText()
        assert "dry_run: True" in preview
        assert "would_modify: False" in preview
        assert "workspace.yaml" in preview
        assert "index_status" in preview and "missing" in preview
        assert "auto_index_started" in preview and "false" in preview.lower()
        assert not gate.create_disabled_button.isEnabled()
        assert not target.exists(), "GUI wizard must not create target directory"
        assert not (target / ".kb").exists()
        assert not (target / ".kb" / "index.sqlite").exists()

        gate.copy_button.click()
        app.processEvents()
        assert "workspace.yaml" in QApplication.clipboard().text()

        blocked_target = root / "non-empty-target"
        gate.target_input.setText(str(blocked_target))
        gate.name_input.setText("阻断知识库")
        gate.generate_plan()
        app.processEvents()
        blocked_preview = gate.plan_preview.toPlainText()
        assert "blocked: True" in blocked_preview
        assert "not empty" in blocked_preview
        assert "计划被阻断" in gate.plan_status_chip.text()
        assert not blocked_target.exists()
        assert not (blocked_target / ".kb").exists()

        window.close()
        app.processEvents()

    print("gui workspace creation tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
