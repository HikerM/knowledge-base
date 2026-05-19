"""Safe execute mutation service.

v1.8.x intentionally exposes only low-risk category config mutations in
config/categories.yaml. Destructive operations remain unsupported.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from knowledge_app.models.mutation_models import MutationApproval, MutationResult
from knowledge_app.models.plan_result import PlanResult
from knowledge_app.services.category_plan_service import CategoryPlanService
from knowledge_app.services.mutation_plan_helpers import elapsed_ms, load_categories_for_workspace, resolve_workspace_path


CATEGORY_UPDATE_DISPLAY_NAME_PLAN_TYPE = "category_update_display_name"
CATEGORY_UPDATE_DESCRIPTION_PLAN_TYPE = "category_update_description"
CATEGORY_UPDATE_DISPLAY_NAME_TASK_TYPE = "category_update_display_name_execute"
CATEGORY_UPDATE_DESCRIPTION_TASK_TYPE = "category_update_description_execute"
SUPPORTED_MUTATION_PLAN_TYPES = {
    CATEGORY_UPDATE_DISPLAY_NAME_PLAN_TYPE,
    CATEGORY_UPDATE_DESCRIPTION_PLAN_TYPE,
}
MUTATION_PLAN_TO_TASK_TYPE = {
    CATEGORY_UPDATE_DISPLAY_NAME_PLAN_TYPE: CATEGORY_UPDATE_DISPLAY_NAME_TASK_TYPE,
    CATEGORY_UPDATE_DESCRIPTION_PLAN_TYPE: CATEGORY_UPDATE_DESCRIPTION_TASK_TYPE,
}
APPROVAL_TTL_HOURS = 24


class SafeMutationError(Exception):
    """Controlled safe mutation rejection."""

    def __init__(self, message: str, code: str = "safe_mutation_rejected"):
        super().__init__(message)
        self.code = code


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    if not value:
        raise ValueError("timestamp must not be empty")
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    return datetime.fromisoformat(value)


class SafeMutationService:
    """Validate approvals and execute the v1.8.x safe mutation subset."""

    def __init__(self, workspace_path: Path | str | None = None):
        self.workspace_path = resolve_workspace_path(workspace_path)
        self.categories_path = self.workspace_path / "config" / "categories.yaml"
        self.approvals_root = self.workspace_path / ".kb" / "mutation-approvals"

    def create_approval(
        self,
        plan_result: PlanResult,
        approved_by: str,
        snapshot_path: Path | str,
    ) -> MutationApproval:
        if not isinstance(plan_result, PlanResult):
            raise SafeMutationError("plan_result must be a PlanResult", code="invalid_plan")
        if plan_result.plan_type not in SUPPORTED_MUTATION_PLAN_TYPES:
            raise SafeMutationError(
                f"unsupported mutation plan_type: {plan_result.plan_type}",
                code="unsupported_mutation",
            )
        if plan_result.blocked:
            raise SafeMutationError(
                "; ".join(plan_result.blockers) or "cannot approve blocked plan",
                code="blocked_plan",
            )
        approved_by = approved_by.strip()
        if not approved_by:
            raise SafeMutationError("approved_by must not be empty", code="missing_approver")
        snapshot_text = str(snapshot_path).strip()
        if not snapshot_text:
            raise SafeMutationError("snapshot_path must not be empty", code="missing_snapshot")
        snapshot = Path(snapshot_text)
        if not snapshot.exists():
            raise SafeMutationError(f"snapshot_path does not exist: {snapshot}", code="missing_snapshot")
        if not snapshot.is_file():
            raise SafeMutationError(f"snapshot_path is not a file: {snapshot}", code="missing_snapshot")

        approved_at = datetime.now(timezone.utc)
        approval = MutationApproval(
            approval_id=f"{approved_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:12]}",
            plan_type=plan_result.plan_type,
            target=dict(plan_result.target),
            approved_at=approved_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            approved_by=approved_by,
            plan_hash=self.plan_hash(plan_result),
            snapshot_path=str(snapshot.resolve()),
            expires_at=(approved_at + timedelta(hours=APPROVAL_TTL_HOURS))
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            warnings=list(plan_result.warnings),
            metadata={
                "workspace_path": str(self.workspace_path),
                "approval_ttl_hours": APPROVAL_TTL_HOURS,
                "requires_snapshot": True,
                "requires_task_queue": True,
                "task_type": MUTATION_PLAN_TO_TASK_TYPE[plan_result.plan_type],
                "git_required": False,
            },
        )
        self._write_approval(approval)
        return approval

    def validate_approval(self, approval_id: str, plan_result: PlanResult) -> MutationApproval:
        if not isinstance(plan_result, PlanResult):
            raise SafeMutationError("plan_result must be a PlanResult", code="invalid_plan")
        if plan_result.plan_type not in SUPPORTED_MUTATION_PLAN_TYPES:
            raise SafeMutationError(
                f"unsupported mutation plan_type: {plan_result.plan_type}",
                code="unsupported_mutation",
            )
        if plan_result.blocked:
            raise SafeMutationError(
                "; ".join(plan_result.blockers) or "plan is blocked",
                code="blocked_plan",
            )

        approval = self._load_approval(approval_id)
        if approval.plan_type != plan_result.plan_type:
            raise SafeMutationError(
                f"approval plan_type mismatch: expected {approval.plan_type}, got {plan_result.plan_type}",
                code="approval_plan_type_mismatch",
            )
        if approval.plan_hash != self.plan_hash(plan_result):
            raise SafeMutationError("approval plan_hash does not match current plan", code="approval_plan_hash_mismatch")
        try:
            expires_at = parse_iso(approval.expires_at)
        except ValueError as exc:
            raise SafeMutationError(f"approval expires_at is invalid: {exc}", code="approval_expired") from exc
        if expires_at <= datetime.now(timezone.utc):
            raise SafeMutationError("approval has expired", code="approval_expired")
        snapshot = Path(approval.snapshot_path)
        if not approval.snapshot_path.strip() or not snapshot.exists() or not snapshot.is_file():
            raise SafeMutationError(f"approval snapshot_path does not exist: {approval.snapshot_path}", code="missing_snapshot")
        return approval

    def execute_category_display_name_update(
        self,
        category_id: str,
        new_display_name: str,
        approval_id: str,
    ) -> MutationResult:
        start = time.perf_counter()
        category_id = category_id.strip()
        new_display_name = new_display_name.strip()
        if not category_id:
            raise SafeMutationError("category_id must not be empty", code="invalid_target")
        if not new_display_name:
            raise SafeMutationError("new_display_name must not be empty", code="invalid_target")
        if "\n" in new_display_name or "\r" in new_display_name:
            raise SafeMutationError("new_display_name must be a single line", code="invalid_target")

        plan = CategoryPlanService(self.workspace_path).update_display_name_plan(category_id, new_display_name)
        approval = self.validate_approval(approval_id, plan)
        before_categories = load_categories_for_workspace(self.workspace_path)
        old_display_name = str(before_categories.get(category_id, {}).get("display_name") or category_id)
        before_content = self._read_categories_text()
        after_content = self._updated_categories_field_text(category_id, "display_name", new_display_name, before_content)

        changed_configs: List[str] = []
        if after_content != before_content:
            self._atomic_write_categories(after_content)
            changed_configs.append("config/categories.yaml")

        return MutationResult(
            success=True,
            mutation_type=CATEGORY_UPDATE_DISPLAY_NAME_TASK_TYPE,
            target={
                "category_id": category_id,
                "old_display_name": old_display_name,
                "new_display_name": new_display_name,
                "workspace_path": str(self.workspace_path),
            },
            changed_files=[],
            changed_configs=changed_configs,
            snapshot_path=approval.snapshot_path,
            validation_results=[
                {
                    "status": "recommended",
                    "commands": list(plan.validation_commands),
                }
            ],
            rollback_hint=(
                f"Restore {category_id}.display_name to {old_display_name!r} in config/categories.yaml "
                f"or restore from snapshot {approval.snapshot_path}."
            ),
            warnings=list(dict.fromkeys([*plan.warnings, *approval.warnings])),
            errors=[],
            elapsed_ms=elapsed_ms(start),
        )

    def execute_category_description_update(
        self,
        category_id: str,
        new_description: str,
        approval_id: str,
    ) -> MutationResult:
        start = time.perf_counter()
        category_id = category_id.strip()
        new_description = new_description.strip()
        if not category_id:
            raise SafeMutationError("category_id must not be empty", code="invalid_target")
        if "\n" in new_description or "\r" in new_description:
            raise SafeMutationError("new_description must be a single line", code="invalid_target")

        stored_approval = self._load_approval(approval_id)
        allow_empty_description = bool(stored_approval.target.get("allow_empty_description", False))
        plan = CategoryPlanService(self.workspace_path).update_description_plan(
            category_id,
            new_description,
            allow_empty_description=allow_empty_description,
        )
        approval = self.validate_approval(approval_id, plan)
        before_categories = load_categories_for_workspace(self.workspace_path)
        category = before_categories.get(category_id, {})
        old_description = str(category.get("description") or "")
        display_name = str(category.get("display_name") or category_id)
        category_path = str(category.get("path") or "")
        before_content = self._read_categories_text()
        after_content = self._updated_categories_field_text(category_id, "description", new_description, before_content)

        changed_configs: List[str] = []
        if after_content != before_content:
            self._atomic_write_categories(after_content)
            changed_configs.append("config/categories.yaml")

        return MutationResult(
            success=True,
            mutation_type=CATEGORY_UPDATE_DESCRIPTION_TASK_TYPE,
            target={
                "category_id": category_id,
                "display_name": display_name,
                "path": category_path,
                "old_description": old_description,
                "new_description": new_description,
                "allow_empty_description": allow_empty_description,
                "workspace_path": str(self.workspace_path),
            },
            changed_files=[],
            changed_configs=changed_configs,
            snapshot_path=approval.snapshot_path,
            validation_results=[
                {
                    "status": "recommended",
                    "commands": list(plan.validation_commands),
                }
            ],
            rollback_hint=(
                f"Restore {category_id}.description to {old_description!r} in config/categories.yaml "
                f"or restore from snapshot {approval.snapshot_path}."
            ),
            warnings=list(dict.fromkeys([*plan.warnings, *approval.warnings])),
            errors=[],
            elapsed_ms=elapsed_ms(start),
        )

    @staticmethod
    def plan_hash(plan_result: PlanResult) -> str:
        payload = plan_result.to_dict()
        payload["elapsed_ms"] = 0
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _approval_path(self, approval_id: str) -> Path:
        approval_id = approval_id.strip()
        if not approval_id or any(part in approval_id for part in ["/", "\\", ".."]):
            raise SafeMutationError(f"invalid approval_id: {approval_id}", code="invalid_approval_id")
        return self.approvals_root / f"{approval_id}.json"

    def _write_approval(self, approval: MutationApproval) -> None:
        self.approvals_root.mkdir(parents=True, exist_ok=True)
        path = self._approval_path(approval.approval_id)
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(approval.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
        temp_path.replace(path)

    def _load_approval(self, approval_id: str) -> MutationApproval:
        path = self._approval_path(approval_id)
        if not path.exists():
            raise SafeMutationError(f"approval not found: {approval_id}", code="missing_approval")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SafeMutationError(f"could not read approval {approval_id}: {exc}", code="invalid_approval") from exc
        if not isinstance(payload, dict):
            raise SafeMutationError(f"approval must be a JSON object: {approval_id}", code="invalid_approval")
        return MutationApproval.from_dict(payload)

    def _read_categories_text(self) -> str:
        if not self.categories_path.exists():
            raise SafeMutationError("config/categories.yaml does not exist", code="missing_config")
        return self.categories_path.read_text(encoding="utf-8")

    def _updated_categories_field_text(self, category_id: str, field_name: str, field_value: str, content: str) -> str:
        if field_name not in {"display_name", "description"}:
            raise SafeMutationError(f"unsupported category config field: {field_name}", code="unsupported_mutation")
        lines = content.splitlines(keepends=True)
        newline = "\r\n" if "\r\n" in content else "\n"
        category_index = self._find_category_line(lines, category_id)
        field_indent = self._field_indent(lines[category_index])
        category_indent = len(lines[category_index]) - len(lines[category_index].lstrip(" "))
        end_index = len(lines)
        for index in range(category_index + 1, len(lines)):
            line = lines[index]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent <= category_indent and stripped.endswith(":"):
                end_index = index
                break

        replacement = f"{' ' * field_indent}{field_name}: {self._yaml_string(field_value)}{newline}"
        for index in range(category_index + 1, end_index):
            line = lines[index]
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))
            if indent == field_indent and stripped.startswith(f"{field_name}:"):
                lines[index] = replacement
                return "".join(lines)

        insert_index = category_index + 1
        lines.insert(insert_index, replacement)
        return "".join(lines)

    @staticmethod
    def _find_category_line(lines: List[str], category_id: str) -> int:
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped == f"{category_id}:":
                return index
        raise SafeMutationError(f"category_id not found in config/categories.yaml: {category_id}", code="unknown_category")

    @staticmethod
    def _field_indent(category_line: str) -> int:
        category_indent = len(category_line) - len(category_line.lstrip(" "))
        return category_indent + 2

    @staticmethod
    def _yaml_string(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _atomic_write_categories(self, content: str) -> None:
        self.categories_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.categories_path.with_suffix(".yaml.tmp")
        temp_path.write_text(content, encoding="utf-8", newline="")
        temp_path.replace(self.categories_path)
