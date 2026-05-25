"""Plan-only local model download service.

This service creates dry-run plans only. It does not download model files,
create directories, write registries, start runtimes, open network connections,
or enqueue real TaskQueue tasks.
"""

from __future__ import annotations

import hashlib
import time
from typing import List, Optional

from knowledge_app.ai.local_model_catalog import (
    LocalModelCatalog,
    LocalModelCatalogValidationError,
    LocalModelEntry,
    get_model,
    validate_local_model_catalog,
)
from knowledge_app.ai.local_model_download_models import (
    LOCAL_MODEL_DOWNLOAD_PLAN_SCHEMA_VERSION,
    ModelDownloadPlan,
)
from knowledge_app.ai.local_model_policy import (
    LocalModelPolicyValidationError,
    validate_local_model_download_policy,
    validate_local_model_storage_path,
    validate_local_model_storage_policy,
    validate_local_model_verification_policy,
)


ADVANCED_MODEL_SIZE_GB = 30.0


class LocalModelDownloadPlanServiceError(ValueError):
    """Raised when a download plan cannot be constructed from valid inputs."""


class ModelDownloadPlanService:
    """Create dry-run model download plans from a validated catalog."""

    def __init__(self, workspace_root: Optional[str] = None, install_root: Optional[str] = None):
        self.workspace_root = workspace_root
        self.install_root = install_root

    def create_download_plan(
        self,
        catalog: LocalModelCatalog,
        model_id: str,
        target_dir: str,
        available_disk_gb: Optional[float] = None,
    ) -> ModelDownloadPlan:
        """Create a plan-only download contract without touching the target path."""

        started = time.perf_counter()
        try:
            validated_catalog = validate_local_model_catalog(catalog)
            model = get_model(validated_catalog, model_id)
        except LocalModelCatalogValidationError as exc:
            raise LocalModelDownloadPlanServiceError(str(exc)) from exc

        blockers: List[str] = []
        warnings: List[str] = list(model.warnings)
        validation_steps = [
            "catalog schema validated",
            "model id resolved",
            "download policy validated",
            "verification policy validated",
            "storage policy validated",
            "target path checked without filesystem writes",
            "disk estimate calculated",
            "dry-run plan generated without download",
        ]

        try:
            validate_local_model_download_policy(validated_catalog.download_policy)
        except LocalModelPolicyValidationError as exc:
            blockers.append(f"download policy blocked: {exc}")
        try:
            validate_local_model_verification_policy(validated_catalog.verification_policy)
        except LocalModelPolicyValidationError as exc:
            blockers.append(f"verification policy blocked: {exc}")
        try:
            validate_local_model_storage_policy(
                validated_catalog.storage_policy,
                self.workspace_root,
                self.install_root,
                target_dir,
            )
        except LocalModelPolicyValidationError as exc:
            blockers.append(f"target_dir blocked: {exc}")

        if model.sha256 == "pending":
            blockers.append("sha256=pending blocks verified install")
        if model.verified_install_allowed and model.sha256 == "pending":
            blockers.append("verified install requires a non-pending sha256")
        if model.default and (model.expected_size >= ADVANCED_MODEL_SIZE_GB or model.install_size >= ADVANCED_MODEL_SIZE_GB):
            blockers.append("30GB+ models cannot be default")
        elif model.expected_size >= ADVANCED_MODEL_SIZE_GB or model.install_size >= ADVANCED_MODEL_SIZE_GB:
            blockers.append("30GB+ model requires an explicit advanced flow in a future release")

        estimated_disk_required = _estimate_disk_required(model)
        if available_disk_gb is not None:
            if type(available_disk_gb) not in {int, float} or available_disk_gb < 0:
                blockers.append("available_disk_gb must be a non-negative number")
            elif float(available_disk_gb) < estimated_disk_required:
                blockers.append("available_disk_gb is below estimated disk requirement")

        target_file = _join_target_file(target_dir, model.filename)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ModelDownloadPlan(
            schema_version=LOCAL_MODEL_DOWNLOAD_PLAN_SCHEMA_VERSION,
            plan_id=_plan_id(model.id, target_file),
            model_id=model.id,
            display_name=model.display_name,
            tier=model.tier.value,
            filename=model.filename,
            source_kind=model.source_kind,
            source_ref=model.source_ref,
            target_dir=target_dir,
            target_file=target_file,
            expected_size=model.expected_size,
            install_size=model.install_size,
            sha256=model.sha256,
            verified_install_allowed=model.verified_install_allowed,
            blockers=blockers,
            warnings=warnings,
            requires_confirmation=True,
            requires_task_queue=True,
            dry_run=True,
            would_modify=False,
            would_download=False,
            would_create_dirs=[target_dir],
            validation_steps=validation_steps,
            estimated_disk_required=estimated_disk_required,
            cleanup_policy=_cleanup_policy(),
            rollback_hint="No filesystem changes are made by this dry-run plan.",
            elapsed_ms=elapsed_ms,
        ).validate()


def create_download_plan(
    catalog: LocalModelCatalog,
    model_id: str,
    target_dir: str,
    available_disk_gb: Optional[float] = None,
) -> ModelDownloadPlan:
    """Convenience wrapper using default plan-only service settings."""

    return ModelDownloadPlanService().create_download_plan(catalog, model_id, target_dir, available_disk_gb)


def _estimate_disk_required(model: LocalModelEntry) -> float:
    return round(max(model.expected_size, model.install_size), 3)


def _cleanup_policy() -> dict[str, object]:
    return {
        "stage": "future_execution_only",
        "partial_download_suffix": ".partial",
        "checksum_failure": "delete_partial_file_and_keep_catalog_unchanged",
        "cancel_behavior": "cooperative_cancel_then_delete_partial_file",
        "resume_policy": "deferred",
        "writes_now": False,
    }


def _join_target_file(target_dir: str, filename: str) -> str:
    directory = str(target_dir).strip()
    if directory.endswith(("/", "\\")):
        return f"{directory}{filename}"
    separator = "\\" if "\\" in directory and "/" not in directory else "/"
    return f"{directory}{separator}{filename}"


def _plan_id(model_id: str, target_file: str) -> str:
    digest = hashlib.sha256(f"{model_id}|{target_file}".encode("utf-8")).hexdigest()[:12]
    return f"model_download_plan_{digest}"
