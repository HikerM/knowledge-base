#!/usr/bin/env python3
"""Workspace creation plan-only service tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.models.workspace_creation_models import WorkspaceCreationRequest
from knowledge_app.services.workspace_creation_plan_service import WorkspaceCreationPlanService


def assert_no_runtime_index(path: Path) -> None:
    assert not (path / ".kb").exists(), ".kb must not be created by plan-only service"
    assert not (path / ".kb" / "index.sqlite").exists(), "index.sqlite must not be created by plan-only service"


def main() -> int:
    service = WorkspaceCreationPlanService()
    templates = service.list_workspace_templates()
    assert templates.success, templates
    ids = {item["template_id"] for item in templates.data["templates"]}
    assert ids == {"personal", "learning", "work", "developer", "custom"}

    with tempfile.TemporaryDirectory(prefix="pkb-workspace-plan-") as tmp:
        root = Path(tmp)
        target = root / "new-kb"
        plan = service.create_workspace_plan(
            WorkspaceCreationRequest(target_path=str(target), workspace_name="My KB", template_id="developer")
        )

        assert plan.dry_run is True
        assert plan.would_modify is False
        assert plan.blocked is False
        assert plan.blockers == []
        assert str(target.resolve()) in plan.would_create_dirs
        assert "knowledge" in plan.would_create_dirs
        assert "config" in plan.would_create_dirs
        assert "templates" in plan.would_create_dirs
        assert "reports" in plan.would_create_dirs
        assert "workspace.yaml" in plan.would_create_files
        assert "config/categories.yaml" in plan.would_write_configs
        assert plan.estimated_result["index_status"] == "missing"
        assert plan.estimated_result["auto_index_started"] is False
        assert plan.estimated_result["created_formal_knowledge"] is False
        assert not target.exists(), "plan-only service must not create a missing target"
        assert_no_runtime_index(target)

        empty_target = root / "empty-kb"
        empty_target.mkdir()
        empty_plan = service.create_workspace_plan(
            WorkspaceCreationRequest(target_path=str(empty_target), workspace_name="Empty KB", template_id="personal")
        )
        assert empty_plan.blocked is False
        assert str(empty_target) not in empty_plan.would_create_dirs
        assert list(empty_target.iterdir()) == []
        assert_no_runtime_index(empty_target)

        non_empty_target = root / "non-empty-kb"
        non_empty_target.mkdir()
        (non_empty_target / "note.txt").write_text("existing user data", encoding="utf-8")
        blocked_plan = service.create_workspace_plan(
            WorkspaceCreationRequest(target_path=str(non_empty_target), workspace_name="Blocked KB", template_id="personal")
        )
        assert blocked_plan.blocked is True
        assert blocked_plan.dry_run is True
        assert blocked_plan.would_modify is False
        assert any("not empty" in item for item in blocked_plan.blockers)
        assert not (non_empty_target / "workspace.yaml").exists()
        assert_no_runtime_index(non_empty_target)

        invalid_template = service.create_workspace_plan(
            WorkspaceCreationRequest(target_path=str(root / "invalid-template"), workspace_name="Invalid Template", template_id="unknown")
        )
        assert invalid_template.blocked is True
        assert any("unknown template_id" in item for item in invalid_template.blockers)

        empty_name = service.create_workspace_plan(
            WorkspaceCreationRequest(target_path=str(root / "empty-name"), workspace_name=" ", template_id="personal")
        )
        assert empty_name.blocked is True
        assert any("workspace_name" in item for item in empty_name.blockers)

        install_dir_plan = service.create_workspace_plan(
            WorkspaceCreationRequest(target_path=str(SOURCE_ROOT / "new-workspace"), workspace_name="Install Dir", template_id="personal")
        )
        assert install_dir_plan.blocked is True
        assert any("install directory" in item for item in install_dir_plan.blockers)

        protected_plan = service.create_workspace_plan(
            WorkspaceCreationRequest(target_path=str(root / "backups" / "new-kb"), workspace_name="Backups Dir", template_id="personal")
        )
        assert protected_plan.blocked is True
        assert any("protected runtime/build directory" in item for item in protected_plan.blockers)

    print("workspace creation plan tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
