"""Plan-only workspace creation service."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Dict, Iterable, List

from knowledge_core.paths import ROOT_RESOLVED
from knowledge_app.models.operation_result import OperationResult
from knowledge_app.models.workspace_creation_models import (
    WorkspaceCreationPlan,
    WorkspaceCreationRequest,
    WorkspaceTemplateSummary,
)


UNSAFE_PATH_SEGMENTS = {".git", "build", "dist", "tmp", "exports", "backups"}


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


class WorkspaceCreationPlanService:
    """Build dry-run plans for new workspaces without writing anything."""

    def __init__(self, install_root: Path | str | None = None):
        self.install_root = Path(install_root).resolve() if install_root else ROOT_RESOLVED

    def list_workspace_templates(self) -> OperationResult:
        start = time.perf_counter()
        templates = [template.to_dict() for template in self._templates().values()]
        payload = {"templates": templates, "count": len(templates), "elapsed_ms": elapsed_ms(start)}
        return OperationResult(success=True, data=payload, elapsed_ms=payload["elapsed_ms"])

    def create_workspace_plan(self, request: WorkspaceCreationRequest | Dict[str, object]) -> WorkspaceCreationPlan:
        start = time.perf_counter()
        request = self._coerce_request(request)
        templates = self._templates()
        blockers: List[str] = []
        warnings: List[str] = []

        workspace_name = request.workspace_name.strip()
        if not workspace_name:
            blockers.append("workspace_name must not be empty")

        template = templates.get(request.template_id)
        if template is None:
            blockers.append(f"unknown template_id: {request.template_id}")

        target_path_text = str(request.target_path or "").strip()
        if not target_path_text:
            blockers.append("target_path must not be empty")
            target_path = Path()
        else:
            target_path = Path(target_path_text).expanduser()
            if not target_path.is_absolute():
                target_path = Path.cwd() / target_path
            target_path = target_path.resolve()
            blockers.extend(self._path_blockers(target_path))
            warnings.extend(self._path_warnings(target_path))

        plan_id = self._plan_id(request, str(target_path), blockers)
        dirs = self._planned_dirs(target_path, bool(request.create_backups_directory), template)
        files = ["workspace.yaml"]
        configs = list((template.default_configs if template else self._base_configs()))
        validation_commands = [f"python scripts/kb.py workspace-status --workspace \"{target_path}\""]
        estimated_result = {
            "index_status": "missing",
            "auto_index_started": False,
            "created_formal_knowledge": False,
            "imported_existing_files": False,
            "created_runtime_index": False,
            "git_required": False,
            "create_execute_available": False,
            "message": "plan-only; execution will be supported in a later version",
        }

        return WorkspaceCreationPlan(
            plan_id=plan_id,
            workspace_name=workspace_name,
            target_path=str(target_path),
            template_id=request.template_id,
            would_create_dirs=dirs,
            would_create_files=files,
            would_write_configs=configs,
            blockers=blockers,
            warnings=warnings,
            requires_confirmation=True,
            reversible=True,
            validation_commands=validation_commands,
            estimated_result=estimated_result,
            elapsed_ms=elapsed_ms(start),
        )

    def _path_blockers(self, target_path: Path) -> List[str]:
        blockers: List[str] = []
        if self._is_relative_to(target_path, self.install_root):
            blockers.append(f"target_path is inside the application install directory: {self.install_root}")
        lower_parts = {part.lower() for part in target_path.parts}
        unsafe = sorted(lower_parts.intersection(UNSAFE_PATH_SEGMENTS))
        if unsafe:
            blockers.append(f"target_path is inside a protected runtime/build directory: {', '.join(unsafe)}")
        try:
            if target_path.exists():
                if not target_path.is_dir():
                    blockers.append("target_path exists and is not a directory")
                elif any(target_path.iterdir()):
                    blockers.append("target_path exists and is not empty; non-empty initialization is blocked in this version")
        except OSError as exc:
            blockers.append(f"target_path cannot be inspected: {exc}")
        return blockers

    @staticmethod
    def _path_warnings(target_path: Path) -> List[str]:
        warnings: List[str] = []
        if not target_path.exists():
            warnings.append("target_path does not exist; the future create step would create it")
        return warnings

    @staticmethod
    def _planned_dirs(target_path: Path, create_backups_directory: bool, template: WorkspaceTemplateSummary | None) -> List[str]:
        dirs: List[str] = []
        if not target_path.exists():
            dirs.append(str(target_path))
        dirs.extend(template.default_dirs if template else ["knowledge", "config", "templates", "reports"])
        if create_backups_directory and "backups" not in dirs:
            dirs.append("backups")
        return dirs

    @staticmethod
    def _plan_id(request: WorkspaceCreationRequest, resolved_target: str, blockers: Iterable[str]) -> str:
        payload = "|".join(
            [
                resolved_target,
                request.workspace_name.strip(),
                request.template_id,
                request.default_language,
                str(bool(request.create_backups_directory)),
                "|".join(blockers),
            ]
        )
        return "workspace-create-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _coerce_request(request: WorkspaceCreationRequest | Dict[str, object]) -> WorkspaceCreationRequest:
        if isinstance(request, WorkspaceCreationRequest):
            return request
        return WorkspaceCreationRequest(
            target_path=str(request.get("target_path") or ""),
            workspace_name=str(request.get("workspace_name") or ""),
            template_id=str(request.get("template_id") or ""),
            description=str(request.get("description") or ""),
            default_language=str(request.get("default_language") or "zh-CN"),
            create_backups_directory=bool(request.get("create_backups_directory", True)),
        )

    @staticmethod
    def _is_relative_to(path: Path, parent: Path) -> bool:
        try:
            path.resolve().relative_to(parent.resolve())
            return True
        except ValueError:
            return False

    @staticmethod
    def _base_configs() -> List[str]:
        return ["config/categories.yaml", "config/sources.yaml", "config/quality-rules.yaml", "config/extract-rules.yaml"]

    @classmethod
    def _templates(cls) -> Dict[str, WorkspaceTemplateSummary]:
        base_dirs = ["knowledge", "config", "templates", "reports"]
        base_files = ["workspace.yaml"]
        base_configs = cls._base_configs()
        return {
            "personal": WorkspaceTemplateSummary(
                template_id="personal",
                display_name="个人资料",
                description="私人笔记、生活资料、长期收藏和手动整理。",
                intended_use=["私人笔记", "生活资料", "长期收藏"],
                not_intended_for=["自动导入浏览器收藏", "自动同步网盘资料"],
                default_dirs=base_dirs,
                default_files=base_files,
                default_configs=base_configs,
            ),
            "learning": WorkspaceTemplateSummary(
                template_id="learning",
                display_name="学习",
                description="课程、读书、论文、主题学习和复盘。",
                intended_use=["课程笔记", "主题学习", "读书复盘"],
                not_intended_for=["未经审核内容直接进入正式规则"],
                default_dirs=base_dirs,
                default_files=base_files,
                default_configs=base_configs,
            ),
            "work": WorkspaceTemplateSummary(
                template_id="work",
                display_name="工作",
                description="项目经验、会议结论、流程和交付检查清单。",
                intended_use=["项目经验", "流程记录", "交付检查"],
                not_intended_for=["客户隐私", "真实密钥", "公司敏感数据"],
                default_dirs=base_dirs,
                default_files=base_files,
                default_configs=base_configs,
            ),
            "developer": WorkspaceTemplateSummary(
                template_id="developer",
                display_name="开发者",
                description="工程规则、代码片段、检查清单和 Agent 上下文。",
                intended_use=["工程规则", "代码片段", "Agent 上下文"],
                not_intended_for=["把 raw 或 research 当作正式项目规则"],
                default_dirs=base_dirs,
                default_files=base_files,
                default_configs=base_configs,
            ),
            "custom": WorkspaceTemplateSummary(
                template_id="custom",
                display_name="自定义",
                description="最小结构，后续由用户配置分类和模板。",
                intended_use=["自定义分类", "最小结构"],
                not_intended_for=["自动生成完整分类", "迁移旧 workspace"],
                default_dirs=base_dirs,
                default_files=base_files,
                default_configs=["config/categories.yaml"],
            ),
        }
