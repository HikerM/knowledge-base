#!/usr/bin/env python3
"""Plan-only mutation service and CLI contract tests."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable


SOURCE_ROOT = Path(__file__).resolve().parents[1]

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.models.plan_result import PlanResult
from knowledge_app.services.category_plan_service import CategoryPlanService


EXPECTED_PLAN_KEYS = [
    "schema_version",
    "dry_run",
    "would_modify",
    "blocked",
    "elapsed_ms",
    "plan_type",
    "summary",
    "target",
    "affected_files",
    "affected_configs",
    "affected_categories",
    "affected_sources",
    "risks",
    "blockers",
    "warnings",
    "requires_snapshot",
    "requires_confirmation",
    "reversible",
    "rollback_plan",
    "validation_commands",
    "actions",
]


def run(cmd: list[str], cwd: Path, expect: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)
    if proc.returncode != expect:
        raise AssertionError(
            f"Command failed: {' '.join(cmd)}\n"
            f"Expected: {expect}, got: {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    return proc


def run_json(cmd: list[str], cwd: Path, expect: int = 0) -> Dict[str, Any]:
    proc = run(cmd, cwd, expect=expect)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"Command did not return JSON: {' '.join(cmd)}\n{proc.stdout}") from exc


def copy_project(dst: Path) -> None:
    ignore = shutil.ignore_patterns(".git", ".kb", "__pycache__", "*.pyc", "reports", "knowledge")
    shutil.copytree(SOURCE_ROOT, dst, ignore=ignore)


def write_ai_agent_rule(project: Path) -> Path:
    path = project / "knowledge" / "09-ai-agent" / "rules" / "fixture-ai-agent-rule.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """---
title: Fixture AI Agent Rule
category: ai_agent
type: rule
status: active
confidence: high
source_type: internal_practice
source_url: "https://example.com/plan-only-fixture"
created_at: "2026-05-19T00:00:00"
last_reviewed: "2026-05-19"
reviewed_by: "test"
valid_for: ["plan-only-test"]
not_valid_for: []
project_scope: "tests"
topic_id: "ai-agent.plan-only"
canonical_id: ""
source_hash: ""
content_hash: ""
supersedes: []
superseded_by: ""
deprecated_reason: ""
rejected_reason: ""
quarantined_reason: ""
risk_level: medium
verification_method: "fixture"
review_required: false
review_cycle_days: 180
---

# Fixture AI Agent Rule

Plan-only mutation tests need one indexed non-empty category.
""",
        encoding="utf-8",
        newline="\n",
    )
    return path


def hash_tree(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for root in sorted(paths):
        if not root.exists():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(str(path.relative_to(root)).replace("\\", "/").encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def assert_plan_contract(payload: Dict[str, Any]) -> None:
    if list(payload.keys()) != EXPECTED_PLAN_KEYS:
        raise AssertionError(f"PlanResult schema keys changed: {list(payload.keys())}")
    if payload["schema_version"] != 1:
        raise AssertionError(f"schema_version missing or changed: {payload}")
    if payload["dry_run"] is not True:
        raise AssertionError(f"dry_run must always be true: {payload}")
    if payload["would_modify"] is not False:
        raise AssertionError(f"would_modify must always be false: {payload}")
    if payload["blocked"] is not bool(payload["blockers"]):
        raise AssertionError(f"blocked must match blockers presence: {payload}")
    for key in ("affected_files", "affected_configs", "affected_categories", "affected_sources", "risks", "blockers", "warnings", "rollback_plan", "validation_commands", "actions"):
        if key not in payload or not isinstance(payload[key], list):
            raise AssertionError(f"{key} must be a stable list field: {payload}")
    for key in ("requires_snapshot", "requires_confirmation", "reversible", "blocked", "dry_run", "would_modify"):
        if not isinstance(payload[key], bool):
            raise AssertionError(f"{key} must be a stable bool field: {payload}")
    if not isinstance(payload["elapsed_ms"], int):
        raise AssertionError(f"elapsed_ms must be int: {payload}")


def assert_plan_commands_do_not_mutate(project: Path, commands: list[list[str]]) -> list[Dict[str, Any]]:
    before = hash_tree([project / "knowledge", project / "config"])
    results: list[Dict[str, Any]] = []
    for command in commands:
        payload = run_json([sys.executable, "scripts/kb.py", *command], project, expect=0)
        assert_plan_contract(payload)
        results.append(payload)
    after = hash_tree([project / "knowledge", project / "config"])
    if before != after:
        raise AssertionError("plan-only commands modified knowledge/ or config/")
    return results


def main() -> int:
    sample = PlanResult(plan_type="schema_check", summary="schema stability check").to_dict()
    assert_plan_contract(sample)

    with tempfile.TemporaryDirectory(prefix="pkb-plan-only-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)
        run_json([sys.executable, "scripts/kb.py", "init"], project)
        write_ai_agent_rule(project)
        indexed = run_json([sys.executable, "scripts/kb.py", "index"], project)
        if indexed["indexed"] != 1:
            raise AssertionError(f"expected one indexed fixture: {indexed}")

        before_direct = hash_tree([project / "knowledge", project / "config"])
        direct_plan = CategoryPlanService(project).update_display_name_plan("frontend", "Frontend Engineering")
        assert_plan_contract(direct_plan.to_dict())
        after_direct = hash_tree([project / "knowledge", project / "config"])
        if before_direct != after_direct:
            raise AssertionError("category display_name plan modified files")

        commands = [
            ["category-update-display-name-plan", "--category", "frontend", "--display-name", "Frontend Engineering"],
            ["category-archive-plan", "--category", "ai_agent"],
            ["category-merge-plan", "--source", "ai_agent", "--target", "frontend"],
            ["category-delete-plan", "--category", "ai_agent"],
            ["template-apply-plan", "--template", "developer"],
            ["workspace-upgrade-plan"],
            ["workspace-archive-plan"],
            ["workspace-delete-plan"],
        ]
        results = assert_plan_commands_do_not_mutate(project, commands)
        by_type = {item["plan_type"]: item for item in results}

        delete_plan = by_type["category_delete"]
        if delete_plan["blocked"] is not True or not delete_plan["blockers"]:
            raise AssertionError(f"non-empty category delete must be blocked: {delete_plan}")

        merge_plan = by_type["category_merge"]
        if merge_plan["requires_snapshot"] is not True:
            raise AssertionError(f"category merge must require snapshot: {merge_plan}")

        template_plan = by_type["template_apply"]
        if template_plan["requires_confirmation"] is not True or template_plan["requires_snapshot"] is not True:
            raise AssertionError(f"template apply must require confirmation and snapshot: {template_plan}")
        if any(item.get("would_overwrite") for item in template_plan["affected_configs"]):
            raise AssertionError(f"template apply plan must not overwrite config: {template_plan}")

        workspace_delete = by_type["workspace_delete"]
        if workspace_delete["blocked"] is not True or not workspace_delete["blockers"]:
            raise AssertionError(f"non-empty workspace delete must be blocked: {workspace_delete}")

        blocked_proc = run([sys.executable, "scripts/kb.py", "category-delete-plan", "--category", "ai_agent"], project, expect=0)
        blocked_payload = json.loads(blocked_proc.stdout)
        if blocked_payload["blocked"] is not True:
            raise AssertionError(f"blocked plan should return exit code 0 with blocked=true: {blocked_payload}")

    print("plan-only service tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
