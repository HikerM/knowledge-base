"""Minimal confirmed workspace creation service."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from knowledge_app.models.workspace_creation_models import WorkspaceCreationPlan, WorkspaceCreationResult
from knowledge_app.services.workspace_creation_plan_service import WorkspaceCreationPlanService


APP_VERSION = "v2.0.0-beta.8"
VALID_TEMPLATE_IDS = {"personal", "learning", "work", "developer", "custom"}
FORBIDDEN_CREATED_PARTS = {".git", ".kb"}


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


class WorkspaceCreationService:
    """Execute the smallest safe workspace creation from a confirmed plan."""

    def __init__(self, install_root: Path | str | None = None):
        self.plan_service = WorkspaceCreationPlanService(install_root=install_root)

    def create_workspace_from_plan(self, plan: WorkspaceCreationPlan | Dict[str, Any], confirmed: bool) -> WorkspaceCreationResult:
        start = time.perf_counter()
        raw_plan = dict(plan) if isinstance(plan, dict) else plan.to_dict()
        early_errors = self._raw_plan_errors(raw_plan, confirmed)
        if early_errors:
            return self._result(raw_plan, start, errors=early_errors)

        creation_plan = self._coerce_plan(raw_plan)
        errors = self._plan_errors(creation_plan)
        if errors:
            return self._result(creation_plan, start, errors=errors)

        target_path = self._resolve_target(creation_plan.target_path)
        path_errors = self.plan_service._path_blockers(target_path)  # revalidate immediately before writes
        if path_errors:
            return self._result(creation_plan, start, errors=path_errors)

        created_dirs: List[Path] = []
        created_files: List[Path] = []
        skipped_existing: List[Path] = []
        warnings: List[str] = []
        try:
            planned_dirs = self._resolve_planned_paths(target_path, creation_plan.would_create_dirs, allow_target=True)
            planned_files = self._resolve_planned_paths(
                target_path,
                [*creation_plan.would_create_files, *creation_plan.would_write_configs],
                allow_target=False,
            )

            self._validate_no_forbidden_paths(target_path, [*planned_dirs, *planned_files])
            for directory in planned_dirs:
                if directory.exists():
                    if not directory.is_dir():
                        raise WorkspaceCreationError(f"planned directory exists and is not a directory: {self._display_path(target_path, directory)}")
                    skipped_existing.append(directory)
                    continue
                directory.mkdir(parents=True, exist_ok=False)
                created_dirs.append(directory)

            for file_path in planned_files:
                if file_path.exists():
                    skipped_existing.append(file_path)
                    continue
                if not file_path.parent.exists() or not file_path.parent.is_dir():
                    raise WorkspaceCreationError(
                        f"planned file parent directory was not created by the plan: {self._display_path(target_path, file_path.parent)}"
                    )
                content = self._file_content(creation_plan, file_path.relative_to(target_path).as_posix())
                self._atomic_write_text(file_path, content, creation_plan.plan_id)
                created_files.append(file_path)
        except Exception as exc:  # noqa: BLE001
            warnings.extend(self._cleanup_created(target_path, created_files, created_dirs))
            return self._result(
                creation_plan,
                start,
                created_dirs=created_dirs,
                created_files=created_files,
                skipped_existing=skipped_existing,
                warnings=warnings,
                errors=[str(exc)],
            )

        return self._result(
            creation_plan,
            start,
            created_dirs=created_dirs,
            created_files=created_files,
            skipped_existing=skipped_existing,
            warnings=warnings,
            success=True,
            next_steps=[
                "打开 workspace status，确认 index_status=missing",
                "需要搜索时由用户显式启动 index/reindex",
                "按需补充资料；不会自动导入或创建正式知识",
            ],
        )

    @staticmethod
    def _raw_plan_errors(raw_plan: Dict[str, Any], confirmed: bool) -> List[str]:
        errors: List[str] = []
        if not confirmed:
            errors.append("workspace creation requires confirmed=true")
        if raw_plan.get("dry_run") is not True:
            errors.append("workspace creation requires a dry_run=true plan")
        if raw_plan.get("would_modify") is not False:
            errors.append("workspace creation requires a would_modify=false plan")
        return errors

    @staticmethod
    def _plan_errors(plan: WorkspaceCreationPlan) -> List[str]:
        errors: List[str] = []
        if plan.blocked:
            errors.append("blocked workspace creation plans cannot be executed")
            errors.extend(plan.blockers)
        if plan.template_id not in VALID_TEMPLATE_IDS:
            errors.append(f"unknown template_id: {plan.template_id}")
        if not plan.workspace_name.strip():
            errors.append("workspace_name must not be empty")
        if not plan.target_path.strip():
            errors.append("target_path must not be empty")
        return errors

    @staticmethod
    def _coerce_plan(raw_plan: Dict[str, Any]) -> WorkspaceCreationPlan:
        return WorkspaceCreationPlan(
            plan_id=str(raw_plan.get("plan_id") or ""),
            workspace_name=str(raw_plan.get("workspace_name") or ""),
            target_path=str(raw_plan.get("target_path") or ""),
            template_id=str(raw_plan.get("template_id") or ""),
            would_create_dirs=[str(item) for item in raw_plan.get("would_create_dirs", []) or []],
            would_create_files=[str(item) for item in raw_plan.get("would_create_files", []) or []],
            would_write_configs=[str(item) for item in raw_plan.get("would_write_configs", []) or []],
            blockers=[str(item) for item in raw_plan.get("blockers", []) or []],
            warnings=[str(item) for item in raw_plan.get("warnings", []) or []],
            requires_confirmation=bool(raw_plan.get("requires_confirmation", True)),
            reversible=bool(raw_plan.get("reversible", True)),
            validation_commands=[str(item) for item in raw_plan.get("validation_commands", []) or []],
            estimated_result=dict(raw_plan.get("estimated_result", {})),
            elapsed_ms=int(raw_plan.get("elapsed_ms") or 0),
        )

    @staticmethod
    def _resolve_target(target_path: str) -> Path:
        path = Path(target_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    def _resolve_planned_paths(self, target_path: Path, items: Iterable[str], allow_target: bool) -> List[Path]:
        paths: List[Path] = []
        for item in items:
            if not item:
                raise WorkspaceCreationError("planned path must not be empty")
            candidate = Path(item).expanduser()
            if not candidate.is_absolute():
                candidate = target_path / candidate
            candidate = candidate.resolve()
            if candidate == target_path:
                if not allow_target:
                    raise WorkspaceCreationError("planned file path cannot be the workspace root")
            elif not self.plan_service._is_relative_to(candidate, target_path):
                raise WorkspaceCreationError(f"planned path is outside target workspace: {candidate}")
            paths.append(candidate)
        return paths

    def _validate_no_forbidden_paths(self, target_path: Path, paths: Iterable[Path]) -> None:
        for path in paths:
            rel = path.relative_to(target_path)
            parts = {part.lower() for part in rel.parts}
            if parts.intersection(FORBIDDEN_CREATED_PARTS):
                raise WorkspaceCreationError(f"workspace creation must not create runtime or Git paths: {rel.as_posix()}")
            if path.name.lower() == "index.sqlite":
                raise WorkspaceCreationError("workspace creation must not create index.sqlite")
            if rel.parts and rel.parts[0].lower() == "knowledge" and path.suffix.lower() in {".md", ".markdown"}:
                raise WorkspaceCreationError(f"workspace creation must not create sample knowledge files: {rel.as_posix()}")

    def _file_content(self, plan: WorkspaceCreationPlan, relative_path: str) -> str:
        if relative_path == "workspace.yaml":
            return self._workspace_yaml(plan)
        if relative_path == "config/categories.yaml":
            return self._categories_yaml(plan.template_id)
        if relative_path == "config/sources.yaml":
            return "sources: []\n"
        if relative_path == "config/quality-rules.yaml":
            return self._quality_rules_yaml()
        if relative_path == "config/extract-rules.yaml":
            return self._extract_rules_yaml()
        if relative_path == "config/workspace.yaml":
            return self._workspace_config_yaml(plan)
        raise WorkspaceCreationError(f"no writer registered for planned file: {relative_path}")

    @staticmethod
    def _workspace_yaml(plan: WorkspaceCreationPlan) -> str:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        return "\n".join(
            [
                "schema_version: 1",
                f"workspace_name: {yaml_string(plan.workspace_name)}",
                f"template_id: {yaml_string(plan.template_id)}",
                f"created_at: {yaml_string(created_at)}",
                f"app_version: {yaml_string(APP_VERSION)}",
                "local_only: true",
                "git_required: false",
                "auto_index: false",
                "auto_import: false",
                "creates_formal_knowledge: false",
                "",
            ]
        )

    @staticmethod
    def _workspace_config_yaml(plan: WorkspaceCreationPlan) -> str:
        return "\n".join(
            [
                "workspace:",
                f"  name: {yaml_string(plan.workspace_name)}",
                f"  template_id: {yaml_string(plan.template_id)}",
                "  local_only: true",
                "  git_required: false",
                "",
            ]
        )

    @staticmethod
    def _categories_yaml(template_id: str) -> str:
        categories = CATEGORY_TEMPLATES.get(template_id, CATEGORY_TEMPLATES["custom"])
        lines: List[str] = []
        for category_id, meta in categories.items():
            lines.extend(
                [
                    f"{category_id}:",
                    f"  display_name: {yaml_string(meta['display_name'])}",
                    f"  path: {yaml_string(meta['path'])}",
                    f"  description: {yaml_string(meta['description'])}",
                    "  status: active",
                    "",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _quality_rules_yaml() -> str:
        return "\n".join(
            [
                "policy:",
                "  - raw 和 distilled 默认不能作为正式知识。",
                "  - 新资料必须人工审核后才能进入 rules、snippets、checklists。",
                "  - 不存储真实密钥、密码、token 或客户隐私数据。",
                "",
            ]
        )

    @staticmethod
    def _extract_rules_yaml() -> str:
        return "\n".join(
            [
                "best_practice:",
                "  description: 从资料提炼规则时默认进入 distilled，并要求人工审核。",
                "  output_layer: distilled",
                "  review_required: true",
                "",
            ]
        )

    @staticmethod
    def _atomic_write_text(path: Path, content: str, plan_id: str) -> None:
        temp_path = path.with_name(f".{path.name}.{plan_id}.tmp")
        temp_path.write_text(content, encoding="utf-8", newline="\n")
        temp_path.replace(path)

    def _cleanup_created(self, target_path: Path, created_files: List[Path], created_dirs: List[Path]) -> List[str]:
        warnings: List[str] = []
        for file_path in reversed(created_files):
            try:
                if file_path.exists():
                    file_path.unlink()
            except OSError as exc:
                warnings.append(f"cleanup could not remove {self._display_path(target_path, file_path)}: {exc}")
        for directory in sorted(created_dirs, key=lambda item: len(item.parts), reverse=True):
            try:
                if directory.exists():
                    directory.rmdir()
            except OSError:
                pass
        return warnings

    def _result(
        self,
        plan: WorkspaceCreationPlan | Dict[str, Any],
        start: float,
        *,
        created_dirs: List[Path] | None = None,
        created_files: List[Path] | None = None,
        skipped_existing: List[Path] | None = None,
        warnings: List[str] | None = None,
        errors: List[str] | None = None,
        success: bool = False,
        next_steps: List[str] | None = None,
    ) -> WorkspaceCreationResult:
        raw = plan if isinstance(plan, dict) else plan.to_dict()
        target_path = self._resolve_target(str(raw.get("target_path") or ".")) if raw.get("target_path") else Path()
        return WorkspaceCreationResult(
            success=success,
            plan_id=str(raw.get("plan_id") or ""),
            workspace_path=str(target_path) if raw.get("target_path") else "",
            created_dirs=[self._display_path(target_path, item) for item in created_dirs or []],
            created_files=[self._display_path(target_path, item) for item in created_files or []],
            skipped_existing=[self._display_path(target_path, item) for item in skipped_existing or []],
            warnings=list(warnings or []),
            errors=list(errors or []),
            elapsed_ms=elapsed_ms(start),
            next_steps=list(next_steps or []),
        )

    @staticmethod
    def _display_path(target_path: Path, path: Path) -> str:
        try:
            if path.resolve() == target_path.resolve():
                return str(target_path)
            return path.resolve().relative_to(target_path.resolve()).as_posix()
        except ValueError:
            return str(path)


class WorkspaceCreationError(RuntimeError):
    """Raised internally for safe, user-facing creation failures."""


def yaml_string(value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


CATEGORY_TEMPLATES: Dict[str, Dict[str, Dict[str, str]]] = {
    "personal": {
        "personal_notes": {
            "display_name": "个人笔记",
            "path": "knowledge/personal-notes",
            "description": "私人笔记、长期收藏和手动整理资料。",
        },
        "life": {
            "display_name": "生活资料",
            "path": "knowledge/life",
            "description": "生活记录、清单和本地资料索引。",
        },
        "reference": {
            "display_name": "参考资料",
            "path": "knowledge/reference",
            "description": "待整理的参考主题，不自动导入资料。",
        },
    },
    "learning": {
        "courses": {
            "display_name": "课程",
            "path": "knowledge/courses",
            "description": "课程笔记和学习路线。",
        },
        "books": {
            "display_name": "读书",
            "path": "knowledge/books",
            "description": "读书摘要、摘录索引和复盘。",
        },
        "research_notes": {
            "display_name": "研究笔记",
            "path": "knowledge/research-notes",
            "description": "主题学习资料，默认需要人工审核。",
        },
    },
    "work": {
        "projects": {
            "display_name": "项目",
            "path": "knowledge/projects",
            "description": "项目经验、决策和交付记录。",
        },
        "meetings": {
            "display_name": "会议",
            "path": "knowledge/meetings",
            "description": "会议结论和后续行动。",
        },
        "processes": {
            "display_name": "流程",
            "path": "knowledge/processes",
            "description": "工作流程、检查清单和团队约定。",
        },
    },
    "developer": {
        "frontend": {
            "display_name": "前端",
            "path": "knowledge/frontend",
            "description": "前端工程规则、组件和测试经验。",
        },
        "backend": {
            "display_name": "后端",
            "path": "knowledge/backend",
            "description": "服务分层、API、数据和部署经验。",
        },
        "ai_agent": {
            "display_name": "AI Agent",
            "path": "knowledge/ai-agent",
            "description": "Agent 工作流、提示词和工具边界。",
        },
    },
    "custom": {
        "general": {
            "display_name": "通用",
            "path": "knowledge/general",
            "description": "自定义知识分类入口。",
        },
    },
}
