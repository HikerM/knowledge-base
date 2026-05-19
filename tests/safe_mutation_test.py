#!/usr/bin/env python3
"""Safe execute mutation framework tests."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable


SOURCE_ROOT = Path(__file__).resolve().parents[1]

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.models.mutation_models import MutationApproval, MutationResult
from knowledge_app.services.category_plan_service import CategoryPlanService
from knowledge_app.services.mutation_plan_helpers import load_categories_for_workspace
from knowledge_app.services.safe_mutation_service import SafeMutationError, SafeMutationService


APPROVAL_KEYS = {
    "schema_version",
    "approval_id",
    "plan_type",
    "target",
    "approved_at",
    "approved_by",
    "plan_hash",
    "snapshot_path",
    "expires_at",
    "warnings",
    "metadata",
}

MUTATION_RESULT_KEYS = {
    "schema_version",
    "success",
    "mutation_type",
    "target",
    "changed_files",
    "changed_configs",
    "snapshot_path",
    "validation_results",
    "rollback_hint",
    "warnings",
    "errors",
    "elapsed_ms",
}


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
    ignore = shutil.ignore_patterns(".git", ".kb", "backups", "__pycache__", "*.pyc", "reports", "knowledge")
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
source_url: "https://example.com/safe-mutation-fixture"
created_at: "2026-05-19T00:00:00"
last_reviewed: "2026-05-19"
reviewed_by: "test"
valid_for: ["safe-mutation-test"]
not_valid_for: []
project_scope: "tests"
topic_id: "ai-agent.safe-mutation"
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

Safe mutation tests need one indexed category document.
""",
        encoding="utf-8",
        newline="\n",
    )
    return path


def hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def hash_files(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        if not path.exists():
            continue
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def sqlite_schema(project: Path) -> list[tuple[str, str, str]]:
    db_path = project / ".kb" / "index.sqlite"
    with sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            """
            SELECT type, name, COALESCE(sql, '')
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        ).fetchall()
    return [(str(row[0]), str(row[1]), str(row[2])) for row in rows]


def approval_json_path(project: Path, approval_id: str) -> Path:
    return project / ".kb" / "mutation-approvals" / f"{approval_id}.json"


def assert_model_schemas() -> None:
    approval = MutationApproval(approval_id="schema").to_dict()
    result = MutationResult(success=True, mutation_type="schema").to_dict()
    if set(approval) != APPROVAL_KEYS:
        raise AssertionError(f"MutationApproval schema changed: {approval}")
    if set(result) != MUTATION_RESULT_KEYS:
        raise AssertionError(f"MutationResult schema changed: {result}")


def approve_display_name(project: Path, display_name: str) -> Dict[str, Any]:
    payload = run_json(
        [
            sys.executable,
            "scripts/kb.py",
            "category-update-display-name-approve",
            "--category",
            "ai_agent",
            "--new-display-name",
            display_name,
            "--approved-by",
            "safe-mutation-test",
        ],
        project,
    )
    if not payload["success"]:
        raise AssertionError(f"approval failed: {payload}")
    if set(payload["approval"]) != APPROVAL_KEYS:
        raise AssertionError(f"approval schema changed: {payload}")
    if not Path(payload["snapshot_path"]).exists():
        raise AssertionError(f"approval snapshot missing: {payload}")
    return payload


def approve_description(project: Path, description: str, allow_empty_description: bool = False) -> Dict[str, Any]:
    command = [
        sys.executable,
        "scripts/kb.py",
        "category-update-description-approve",
        "--category",
        "ai_agent",
        "--new-description",
        description,
        "--approved-by",
        "safe-mutation-test",
    ]
    if allow_empty_description:
        command.append("--allow-empty-description")
    payload = run_json(command, project)
    if not payload["success"]:
        raise AssertionError(f"description approval failed: {payload}")
    if set(payload["approval"]) != APPROVAL_KEYS:
        raise AssertionError(f"description approval schema changed: {payload}")
    if not Path(payload["snapshot_path"]).exists():
        raise AssertionError(f"description approval snapshot missing: {payload}")
    return payload


def assert_rejected_display_name_execute(project: Path, approval_id: str, display_name: str) -> Dict[str, Any]:
    payload = run_json(
        [
            sys.executable,
            "scripts/kb.py",
            "category-update-display-name-execute",
            "--category",
            "ai_agent",
            "--new-display-name",
            display_name,
            "--approval-id",
            approval_id,
        ],
        project,
        expect=1,
    )
    if payload["success"] is not False or payload["status"] != "failed":
        raise AssertionError(f"execute rejection should fail via TaskQueue: {payload}")
    return payload


def assert_rejected_description_execute(
    project: Path,
    approval_id: str,
    description: str,
    allow_empty_description: bool = False,
) -> Dict[str, Any]:
    command = [
        sys.executable,
        "scripts/kb.py",
        "category-update-description-execute",
        "--category",
        "ai_agent",
        "--new-description",
        description,
        "--approval-id",
        approval_id,
    ]
    if allow_empty_description:
        command.append("--allow-empty-description")
    payload = run_json(command, project, expect=1)
    if payload["success"] is not False or payload["status"] != "failed":
        raise AssertionError(f"description execute rejection should fail via TaskQueue: {payload}")
    return payload


def main() -> int:
    assert_model_schemas()

    with tempfile.TemporaryDirectory(prefix="pkb-safe-mutation-") as temp:
        project = Path(temp) / "personal-knowledge-base"
        copy_project(project)
        run_json([sys.executable, "scripts/kb.py", "init"], project)
        write_ai_agent_rule(project)
        indexed = run_json([sys.executable, "scripts/kb.py", "index"], project)
        if indexed["indexed"] != 1:
            raise AssertionError(f"expected one indexed fixture: {indexed}")

        categories_path = project / "config" / "categories.yaml"
        other_config_hash = hash_files(path for path in (project / "config").glob("*.yaml") if path.name != "categories.yaml")
        knowledge_hash = hash_tree(project / "knowledge")
        schema_before = sqlite_schema(project)
        categories_before = categories_path.read_text(encoding="utf-8")

        no_approval = assert_rejected_display_name_execute(project, "missing-approval", "AI Agent")
        if "approval not found" not in " ".join(no_approval["errors"]):
            raise AssertionError(f"missing approval should reject execution: {no_approval}")
        if categories_path.read_text(encoding="utf-8") != categories_before:
            raise AssertionError("execute without approval modified categories.yaml")

        service = SafeMutationService(project)
        target_display_name = "AI Agent Safe Mutation"
        plan = CategoryPlanService(project).update_display_name_plan("ai_agent", target_display_name)
        try:
            service.create_approval(plan, "safe-mutation-test", project / "missing-snapshot.zip")
        except SafeMutationError as exc:
            if exc.code != "missing_snapshot":
                raise AssertionError(f"missing snapshot should be rejected with missing_snapshot: {exc.code}")
        else:
            raise AssertionError("create_approval accepted a missing snapshot")

        mismatch = approve_display_name(project, target_display_name)
        mismatch_payload = assert_rejected_display_name_execute(project, mismatch["approval_id"], "AI Agent Two")
        if "plan_hash" not in " ".join(mismatch_payload["errors"]):
            raise AssertionError(f"plan hash mismatch should reject execution: {mismatch_payload}")
        if categories_path.read_text(encoding="utf-8") != categories_before:
            raise AssertionError("plan hash mismatch modified categories.yaml")

        expired = approve_display_name(project, target_display_name)
        expired_path = approval_json_path(project, expired["approval_id"])
        expired_payload = json.loads(expired_path.read_text(encoding="utf-8"))
        expired_payload["expires_at"] = "2000-01-01T00:00:00Z"
        expired_path.write_text(json.dumps(expired_payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        expired_result = assert_rejected_display_name_execute(project, expired["approval_id"], target_display_name)
        if "expired" not in " ".join(expired_result["errors"]):
            raise AssertionError(f"expired approval should reject execution: {expired_result}")
        if categories_path.read_text(encoding="utf-8") != categories_before:
            raise AssertionError("expired approval modified categories.yaml")

        approved = approve_display_name(project, target_display_name)
        executed = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "category-update-display-name-execute",
                "--category",
                "ai_agent",
                "--new-display-name",
                target_display_name,
                "--approval-id",
                approved["approval_id"],
            ],
            project,
        )
        if not executed["success"] or executed["status"] != "succeeded":
            raise AssertionError(f"safe mutation execute failed: {executed}")
        mutation_result = executed["result"].get("mutation_result")
        if not mutation_result or set(mutation_result) != MUTATION_RESULT_KEYS:
            raise AssertionError(f"task result_summary must contain MutationResult: {executed}")
        if mutation_result["changed_files"] != []:
            raise AssertionError(f"safe display_name execute must not report Markdown changes: {mutation_result}")
        if mutation_result["changed_configs"] != ["config/categories.yaml"]:
            raise AssertionError(f"safe display_name execute should only change categories.yaml: {mutation_result}")
        if not mutation_result["snapshot_path"] or not Path(mutation_result["snapshot_path"]).exists():
            raise AssertionError(f"MutationResult must retain snapshot_path: {mutation_result}")

        summary = run_json([sys.executable, "scripts/kb.py", "category-summary", "--category", "ai_agent"], project)
        if summary["display_name"] != target_display_name:
            raise AssertionError(f"category display_name was not updated: {summary}")

        description_target = "AI Agent knowledge and Codex governance test"
        categories_before_description = load_categories_for_workspace(project)
        ai_agent_before_description = dict(categories_before_description["ai_agent"])
        config_before_description_plan = categories_path.read_text(encoding="utf-8")
        description_plan = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "category-update-description-plan",
                "--category",
                "ai_agent",
                "--new-description",
                description_target,
            ],
            project,
        )
        if description_plan["plan_type"] != "category_update_description" or description_plan["requires_snapshot"] is not True:
            raise AssertionError(f"description plan contract unexpected: {description_plan}")
        if categories_path.read_text(encoding="utf-8") != config_before_description_plan:
            raise AssertionError("description plan modified categories.yaml")

        empty_description_plan = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "category-update-description-plan",
                "--category",
                "ai_agent",
                "--new-description",
                "",
            ],
            project,
        )
        if empty_description_plan["blocked"] is not True or not empty_description_plan["blockers"]:
            raise AssertionError(f"empty description plan should be blocked without explicit allow flag: {empty_description_plan}")

        description_no_approval = assert_rejected_description_execute(project, "missing-approval", description_target)
        if "approval not found" not in " ".join(description_no_approval["errors"]):
            raise AssertionError(f"missing description approval should reject execution: {description_no_approval}")
        if categories_path.read_text(encoding="utf-8") != config_before_description_plan:
            raise AssertionError("description execute without approval modified categories.yaml")

        description_plan_obj = CategoryPlanService(project).update_description_plan("ai_agent", description_target)
        try:
            service.create_approval(description_plan_obj, "safe-mutation-test", project / "missing-description-snapshot.zip")
        except SafeMutationError as exc:
            if exc.code != "missing_snapshot":
                raise AssertionError(f"missing description snapshot should be rejected with missing_snapshot: {exc.code}")
        else:
            raise AssertionError("create_approval accepted a missing description snapshot")

        description_mismatch = approve_description(project, description_target)
        description_mismatch_payload = assert_rejected_description_execute(
            project,
            description_mismatch["approval_id"],
            f"{description_target} changed",
        )
        if "plan_hash" not in " ".join(description_mismatch_payload["errors"]):
            raise AssertionError(f"description plan hash mismatch should reject execution: {description_mismatch_payload}")
        if categories_path.read_text(encoding="utf-8") != config_before_description_plan:
            raise AssertionError("description plan hash mismatch modified categories.yaml")

        missing_snapshot_approval = approve_description(project, description_target)
        missing_snapshot_path = approval_json_path(project, missing_snapshot_approval["approval_id"])
        missing_snapshot_payload = json.loads(missing_snapshot_path.read_text(encoding="utf-8"))
        missing_snapshot_payload["snapshot_path"] = str(project / "backups" / "missing-description-snapshot.zip")
        missing_snapshot_path.write_text(
            json.dumps(missing_snapshot_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
        missing_snapshot_result = assert_rejected_description_execute(
            project,
            missing_snapshot_approval["approval_id"],
            description_target,
        )
        if "snapshot" not in " ".join(missing_snapshot_result["errors"]):
            raise AssertionError(f"missing approval snapshot should reject description execution: {missing_snapshot_result}")
        if categories_path.read_text(encoding="utf-8") != config_before_description_plan:
            raise AssertionError("description missing snapshot modified categories.yaml")

        description_approved = approve_description(project, description_target)
        description_executed = run_json(
            [
                sys.executable,
                "scripts/kb.py",
                "category-update-description-execute",
                "--category",
                "ai_agent",
                "--new-description",
                description_target,
                "--approval-id",
                description_approved["approval_id"],
            ],
            project,
        )
        if not description_executed["success"] or description_executed["status"] != "succeeded":
            raise AssertionError(f"safe description mutation execute failed: {description_executed}")
        description_mutation_result = description_executed["result"].get("mutation_result")
        if not description_mutation_result or set(description_mutation_result) != MUTATION_RESULT_KEYS:
            raise AssertionError(f"description task result_summary must contain MutationResult: {description_executed}")
        if description_mutation_result["changed_files"] != []:
            raise AssertionError(f"safe description execute must not report Markdown changes: {description_mutation_result}")
        if description_mutation_result["changed_configs"] != ["config/categories.yaml"]:
            raise AssertionError(f"safe description execute should only change categories.yaml: {description_mutation_result}")

        categories_after_description = load_categories_for_workspace(project)
        ai_agent_after_description = categories_after_description["ai_agent"]
        if ai_agent_after_description.get("description") != description_target:
            raise AssertionError(f"category description was not updated: {ai_agent_after_description}")
        for stable_field in ["path", "display_name", "slug"]:
            if ai_agent_after_description.get(stable_field) != ai_agent_before_description.get(stable_field):
                raise AssertionError(
                    f"description execute changed stable field {stable_field}: "
                    f"before={ai_agent_before_description} after={ai_agent_after_description}"
                )
        if set(categories_after_description) != set(categories_before_description):
            raise AssertionError("description execute changed category ids")

        if hash_tree(project / "knowledge") != knowledge_hash:
            raise AssertionError("safe mutation modified knowledge/**/*.md")
        if hash_files(path for path in (project / "config").glob("*.yaml") if path.name != "categories.yaml") != other_config_hash:
            raise AssertionError("safe mutation modified config files other than categories.yaml")
        if sqlite_schema(project) != schema_before:
            raise AssertionError("safe mutation modified SQLite schema")

        audit = run_json([sys.executable, "scripts/kb.py", "audit"], project)
        if "elapsed_ms" not in audit:
            raise AssertionError(f"audit did not complete: {audit}")
        secret_scan = run_json([sys.executable, "scripts/kb.py", "secret-scan"], project)
        if secret_scan["high_risk_count"] != 0:
            raise AssertionError(f"secret-scan found high-risk findings after safe mutation: {secret_scan}")

        log = run_json([sys.executable, "scripts/kb.py", "task-log", "--task-id", description_executed["task_id"]], project)
        messages = [item["message"] for item in log["results"]]
        for required in ["plan validated", "snapshot verified", "config updated", "validation commands recommended"]:
            if required not in messages:
                raise AssertionError(f"task log missing {required!r}: {log}")

        unsupported_commands = [
            ["category-delete-execute", "--category", "ai_agent"],
            ["category-archive-execute", "--category", "ai_agent"],
            ["category-merge-execute", "--source", "ai_agent", "--target", "frontend"],
            ["template-apply-execute", "--template", "developer"],
            ["restore-execute", "--backup", approved["snapshot_path"], "--target", str(project)],
        ]
        for command in unsupported_commands:
            run([sys.executable, "scripts/kb.py", *command], project, expect=1)

    print("safe mutation tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
