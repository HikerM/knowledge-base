#!/usr/bin/env python3
"""Minimal workspace creation execution tests."""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.models.workspace_creation_models import WorkspaceCreationRequest
from knowledge_app.services.workspace_creation_plan_service import WorkspaceCreationPlanService
from knowledge_app.services.workspace_creation_service import WorkspaceCreationService
from knowledge_app.services.workspace_status_service import WorkspaceStatusService


def hash_markdown_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*.md")):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(item.read_bytes())
    return digest.hexdigest()


def assert_minimal_workspace(target: Path) -> None:
    assert (target / "workspace.yaml").exists()
    assert (target / "config" / "categories.yaml").exists()
    assert (target / "knowledge").is_dir()
    assert (target / "config").is_dir()
    assert (target / "templates").is_dir()
    assert (target / "reports").is_dir()
    assert not (target / ".kb").exists()
    assert not (target / ".kb" / "index.sqlite").exists()
    assert not (target / ".git").exists()
    assert not list((target / "knowledge").rglob("*.md")), "minimal creation must not create sample knowledge"
    workspace_yaml = (target / "workspace.yaml").read_text(encoding="utf-8")
    assert "workspace_name:" in workspace_yaml
    assert "template_id:" in workspace_yaml
    assert "app_version: \"v2.0.0\"" in workspace_yaml
    assert "local_only: true" in workspace_yaml
    assert "git_required: false" in workspace_yaml
    assert "auto_index: false" in workspace_yaml
    categories_yaml = (target / "config" / "categories.yaml").read_text(encoding="utf-8")
    assert "display_name:" in categories_yaml
    assert "path:" in categories_yaml


def main() -> int:
    plan_service = WorkspaceCreationPlanService()
    create_service = WorkspaceCreationService()
    knowledge_hash_before = hash_markdown_tree(SOURCE_ROOT / "knowledge")

    with tempfile.TemporaryDirectory(prefix="pkb-workspace-create-") as tmp:
        root = Path(tmp)

        target = root / "new-kb"
        plan = plan_service.create_workspace_plan(
            WorkspaceCreationRequest(target_path=str(target), workspace_name="Created KB", template_id="developer")
        )
        result = create_service.create_workspace_from_plan(plan, confirmed=True)
        assert result.success, result.to_dict()
        assert result.plan_id == plan.plan_id
        assert result.workspace_path == str(target.resolve())
        assert "workspace.yaml" in result.created_files
        assert "config/categories.yaml" in result.created_files
        assert_minimal_workspace(target)
        status = WorkspaceStatusService(target).get_status()
        assert status.success and status.data.index_status == "missing"
        assert status.data.index_exists is False

        unconfirmed_target = root / "unconfirmed-kb"
        unconfirmed_plan = plan_service.create_workspace_plan(
            WorkspaceCreationRequest(target_path=str(unconfirmed_target), workspace_name="Unconfirmed", template_id="personal")
        )
        unconfirmed = create_service.create_workspace_from_plan(unconfirmed_plan, confirmed=False)
        assert not unconfirmed.success
        assert any("confirmed=true" in item for item in unconfirmed.errors)
        assert not unconfirmed_target.exists()

        blocked_target = root / "blocked-kb"
        blocked_target.mkdir()
        (blocked_target / "existing.txt").write_text("user data", encoding="utf-8")
        blocked_plan = plan_service.create_workspace_plan(
            WorkspaceCreationRequest(target_path=str(blocked_target), workspace_name="Blocked", template_id="personal")
        )
        blocked = create_service.create_workspace_from_plan(blocked_plan, confirmed=True)
        assert blocked_plan.blocked is True
        assert not blocked.success
        assert any("blocked" in item for item in blocked.errors)
        assert not (blocked_target / "workspace.yaml").exists()

        changed_target = root / "changed-after-plan"
        changed_plan = plan_service.create_workspace_plan(
            WorkspaceCreationRequest(target_path=str(changed_target), workspace_name="Changed", template_id="learning")
        )
        changed_target.mkdir()
        (changed_target / "surprise.txt").write_text("created after plan", encoding="utf-8")
        changed = create_service.create_workspace_from_plan(changed_plan, confirmed=True)
        assert not changed.success
        assert any("not empty" in item for item in changed.errors)
        assert not (changed_target / "workspace.yaml").exists()
        assert (changed_target / "surprise.txt").exists()

        invalid_target = root / "invalid-plan"
        invalid_plan = plan.to_dict()
        invalid_plan["target_path"] = str(invalid_target)
        invalid_plan["dry_run"] = False
        invalid = create_service.create_workspace_from_plan(invalid_plan, confirmed=True)
        assert not invalid.success
        assert any("dry_run=true" in item for item in invalid.errors)
        assert not invalid_target.exists()

        assert set(item.name for item in root.iterdir()) == {"new-kb", "blocked-kb", "changed-after-plan"}

    knowledge_hash_after = hash_markdown_tree(SOURCE_ROOT / "knowledge")
    assert knowledge_hash_before == knowledge_hash_after, "existing repo knowledge/ must not be modified"
    print("workspace creation execute tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
