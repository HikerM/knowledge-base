"""Static policy validators for local model installer boundaries.

The validators in this module only inspect in-memory policy objects and path
strings. They do not download models, execute shell commands, start runtimes,
or contact ModelScope.
"""

from __future__ import annotations

from typing import Optional

from knowledge_app.ai.local_model_catalog import (
    LocalModelDownloadPolicy,
    LocalModelStoragePolicy,
    LocalModelVerificationPolicy,
)


DEFAULT_WINDOWS_MODEL_DIR = "%LOCALAPPDATA%\\PersonalKnowledgeBase\\models\\"
REQUIRED_FORBIDDEN_LOCATIONS = {"workspace", "software_install_dir", "knowledge", ".kb"}


class LocalModelPolicyValidationError(ValueError):
    """Raised when a local model policy violates static safety rules."""


def validate_local_model_storage_policy(
    policy: LocalModelStoragePolicy,
    workspace_root: Optional[str] = None,
    install_root: Optional[str] = None,
    candidate_dir: Optional[str] = None,
) -> LocalModelStoragePolicy:
    """Validate storage defaults and optional custom path boundaries."""

    try:
        policy.validate()
    except ValueError as exc:
        raise LocalModelPolicyValidationError(str(exc)) from exc

    if _normalize_path(policy.default_model_dir_windows) != _normalize_path(DEFAULT_WINDOWS_MODEL_DIR):
        raise LocalModelPolicyValidationError(
            "default model directory must be %LOCALAPPDATA%\\PersonalKnowledgeBase\\models\\"
        )
    missing_forbidden = REQUIRED_FORBIDDEN_LOCATIONS.difference(set(policy.forbidden_locations))
    if missing_forbidden:
        missing = ", ".join(sorted(missing_forbidden))
        raise LocalModelPolicyValidationError(f"storage_policy.forbidden_locations missing: {missing}")
    if policy.user_custom_model_dir_allowed and policy.user_custom_dir_requires_future_confirmation is not True:
        raise LocalModelPolicyValidationError("custom model directory requires future confirmation gate")
    if policy.uninstall_app_deletes_models_by_default is not False:
        raise LocalModelPolicyValidationError("uninstall must not delete model files by default")
    if policy.user_can_delete_model_files_in_settings is not True:
        raise LocalModelPolicyValidationError("user must be able to delete model files in settings")
    if policy.delete_model_requires_confirmation is not True:
        raise LocalModelPolicyValidationError("delete model must require user confirmation")
    if candidate_dir is not None:
        validate_local_model_storage_path(candidate_dir, workspace_root, install_root)
    return policy


def validate_local_model_storage_path(
    model_dir: str,
    workspace_root: Optional[str] = None,
    install_root: Optional[str] = None,
) -> str:
    """Reject workspace, install-dir, knowledge/, and .kb/ model locations."""

    normalized = _normalize_path(model_dir)
    if not normalized:
        raise LocalModelPolicyValidationError("model directory is required")

    normalized_workspace = _normalize_path(workspace_root)
    normalized_install = _normalize_path(install_root)

    if normalized_workspace and _is_under_or_equal(normalized, normalized_workspace):
        raise LocalModelPolicyValidationError("model directory must not be inside workspace")
    if normalized_install and _is_under_or_equal(normalized, normalized_install):
        raise LocalModelPolicyValidationError("model directory must not be inside install dir")
    if _contains_path_segment(normalized, "knowledge"):
        raise LocalModelPolicyValidationError("model directory must not be inside knowledge/")
    if _contains_path_segment(normalized, ".kb"):
        raise LocalModelPolicyValidationError("model directory must not be inside .kb/")
    if "/program files/" in f"/{normalized}/" or "/programs/personalknowledgebase/" in f"/{normalized}/":
        raise LocalModelPolicyValidationError("model directory must not be inside install dir")
    return model_dir


def validate_local_model_download_policy(policy: LocalModelDownloadPolicy) -> LocalModelDownloadPolicy:
    """Validate future download gates stay disabled and explicit."""

    try:
        policy.validate()
    except ValueError as exc:
        raise LocalModelPolicyValidationError(str(exc)) from exc

    if policy.actual_download_enabled:
        raise LocalModelPolicyValidationError("actual model download must remain disabled")
    if policy.no_auto_download is not True:
        raise LocalModelPolicyValidationError("no_auto_download must be true")
    if policy.confirmation_required is not True:
        raise LocalModelPolicyValidationError("download must require user confirmation")
    if policy.task_queue_required is not True:
        raise LocalModelPolicyValidationError("download must require TaskQueue")
    if policy.single_file_gguf_only is not True:
        raise LocalModelPolicyValidationError("download policy must be single-file GGUF only")
    if policy.no_repository_download is not True:
        raise LocalModelPolicyValidationError("repository download must be forbidden")
    if policy.no_shell_script is not True:
        raise LocalModelPolicyValidationError("shell download scripts must be forbidden")
    if policy.no_arbitrary_command is not True:
        raise LocalModelPolicyValidationError("arbitrary commands must be forbidden")
    return policy


def validate_local_model_verification_policy(
    policy: LocalModelVerificationPolicy,
) -> LocalModelVerificationPolicy:
    """Validate verification gates for future verified installs."""

    try:
        policy.validate()
    except ValueError as exc:
        raise LocalModelPolicyValidationError(str(exc)) from exc

    if policy.sha256_required_for_verified_install is not True:
        raise LocalModelPolicyValidationError("verified install must require sha256")
    if policy.sha256_pending_blocks_verified_install is not True:
        raise LocalModelPolicyValidationError("sha256=pending must block verified install")
    if policy.expected_size_required is not True:
        raise LocalModelPolicyValidationError("expected size must be required")
    if policy.invalid_checksum_fails_install is not True:
        raise LocalModelPolicyValidationError("invalid checksum must fail install")
    if policy.license_review_required is not True:
        raise LocalModelPolicyValidationError("license review must be required")
    return policy


def _normalize_path(value: Optional[str]) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    return text.rstrip("/").lower()


def _is_under_or_equal(child: str, parent: str) -> bool:
    if not parent:
        return False
    return child == parent or child.startswith(parent.rstrip("/") + "/")


def _contains_path_segment(path: str, segment: str) -> bool:
    parts = [part for part in path.split("/") if part]
    return segment.lower() in parts
