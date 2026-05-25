"""Plan-only local model download models.

These models describe future download tasks. They do not download files, create
directories, start runtimes, register providers, or write model metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


LOCAL_MODEL_DOWNLOAD_PLAN_SCHEMA_VERSION = "local-model-download-plan-v0.1"


class LocalModelDownloadPlanValidationError(ValueError):
    """Raised when a model download plan violates the plan-only contract."""


@dataclass(frozen=True)
class ModelDownloadPlan:
    """Dry-run plan for a future single-file GGUF model download."""

    schema_version: str
    plan_id: str
    model_id: str
    display_name: str
    tier: str
    filename: str
    source_kind: str
    source_ref: str
    target_dir: str
    target_file: str
    expected_size: float
    install_size: float
    sha256: str
    verified_install_allowed: bool
    blockers: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    requires_confirmation: bool = True
    requires_task_queue: bool = True
    dry_run: bool = True
    would_modify: bool = False
    would_download: bool = False
    would_create_dirs: List[str] = field(default_factory=list)
    validation_steps: List[str] = field(default_factory=list)
    estimated_disk_required: float = 0.0
    cleanup_policy: Dict[str, Any] = field(default_factory=dict)
    rollback_hint: str = ""
    elapsed_ms: int = 0

    def validate(self) -> "ModelDownloadPlan":
        _require_text(self.schema_version, "schema_version")
        _require_text(self.plan_id, "plan_id")
        _require_text(self.model_id, "model_id")
        _require_text(self.display_name, "display_name")
        _require_text(self.tier, "tier")
        _require_text(self.filename, "filename")
        _require_text(self.source_kind, "source_kind")
        _require_text(self.source_ref, "source_ref")
        _require_text(self.target_dir, "target_dir")
        _require_text(self.target_file, "target_file")
        _require_positive_number(self.expected_size, "expected_size")
        _require_positive_number(self.install_size, "install_size")
        _require_text(self.sha256, "sha256")
        _require_bool(self.verified_install_allowed, "verified_install_allowed")
        _require_text_list(self.blockers, "blockers")
        _require_text_list(self.warnings, "warnings")
        _require_bool(self.requires_confirmation, "requires_confirmation")
        _require_bool(self.requires_task_queue, "requires_task_queue")
        _require_bool(self.dry_run, "dry_run")
        _require_bool(self.would_modify, "would_modify")
        _require_bool(self.would_download, "would_download")
        _require_text_list(self.would_create_dirs, "would_create_dirs")
        _require_text_list(self.validation_steps, "validation_steps")
        _require_positive_number(self.estimated_disk_required, "estimated_disk_required")
        _require_dict(self.cleanup_policy, "cleanup_policy")
        _require_text(self.rollback_hint, "rollback_hint")
        _require_non_negative_int(self.elapsed_ms, "elapsed_ms")

        if self.schema_version != LOCAL_MODEL_DOWNLOAD_PLAN_SCHEMA_VERSION:
            raise LocalModelDownloadPlanValidationError("unsupported model download plan schema_version")
        if self.requires_confirmation is not True:
            raise LocalModelDownloadPlanValidationError("model download plan must require confirmation")
        if self.requires_task_queue is not True:
            raise LocalModelDownloadPlanValidationError("model download plan must require TaskQueue")
        if self.dry_run is not True:
            raise LocalModelDownloadPlanValidationError("model download plan must remain dry_run=true")
        if self.would_modify is not False:
            raise LocalModelDownloadPlanValidationError("model download plan must set would_modify=false")
        if self.would_download is not False:
            raise LocalModelDownloadPlanValidationError("model download plan must set would_download=false")
        if not self.filename.lower().endswith(".gguf"):
            raise LocalModelDownloadPlanValidationError("model download plan filename must be .gguf")
        if not self.target_file.lower().endswith(".gguf"):
            raise LocalModelDownloadPlanValidationError("model download plan target_file must be .gguf")
        return self

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "tier": self.tier,
            "filename": self.filename,
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "target_dir": self.target_dir,
            "target_file": self.target_file,
            "expected_size": self.expected_size,
            "install_size": self.install_size,
            "sha256": self.sha256,
            "verified_install_allowed": self.verified_install_allowed,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "requires_confirmation": self.requires_confirmation,
            "requires_task_queue": self.requires_task_queue,
            "dry_run": self.dry_run,
            "would_modify": self.would_modify,
            "would_download": self.would_download,
            "would_create_dirs": list(self.would_create_dirs),
            "validation_steps": list(self.validation_steps),
            "estimated_disk_required": self.estimated_disk_required,
            "cleanup_policy": dict(self.cleanup_policy),
            "rollback_hint": self.rollback_hint,
            "elapsed_ms": self.elapsed_ms,
        }


def _require_text(value: Any, field_name: str) -> str:
    if value is None or not isinstance(value, str) or not value.strip():
        raise LocalModelDownloadPlanValidationError(f"{field_name} is required")
    return value.strip()


def _require_bool(value: Any, field_name: str) -> bool:
    if type(value) is not bool:
        raise LocalModelDownloadPlanValidationError(f"{field_name} must be a boolean")
    return value


def _require_positive_number(value: Any, field_name: str) -> float:
    if type(value) not in {int, float} or value <= 0:
        raise LocalModelDownloadPlanValidationError(f"{field_name} must be a positive number")
    return float(value)


def _require_non_negative_int(value: Any, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise LocalModelDownloadPlanValidationError(f"{field_name} must be a non-negative integer")
    return value


def _require_text_list(values: Any, field_name: str) -> List[str]:
    if not isinstance(values, list):
        raise LocalModelDownloadPlanValidationError(f"{field_name} must be a list")
    result: List[str] = []
    for index, value in enumerate(values):
        result.append(_require_text(value, f"{field_name}[{index}]"))
    return result


def _require_dict(value: Any, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise LocalModelDownloadPlanValidationError(f"{field_name} must be a dictionary")
    return value
