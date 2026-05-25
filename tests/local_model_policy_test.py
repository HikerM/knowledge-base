#!/usr/bin/env python3
"""Local model storage/download/verification policy tests."""

from __future__ import annotations

import re
import sys
from dataclasses import replace
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.local_model_catalog import (  # noqa: E402
    LocalModelDownloadPolicy,
    LocalModelStoragePolicy,
    LocalModelVerificationPolicy,
    load_local_model_catalog,
)
from knowledge_app.ai.local_model_policy import (  # noqa: E402
    DEFAULT_WINDOWS_MODEL_DIR,
    LocalModelPolicyValidationError,
    validate_local_model_download_policy,
    validate_local_model_storage_path,
    validate_local_model_storage_policy,
    validate_local_model_verification_policy,
)


CONFIG_PATH = SOURCE_ROOT / "config" / "local-model-catalog.example.yaml"
WORKSPACE_ROOT = "D:/workspaces/pkb"
INSTALL_ROOT = "D:/Users/me/AppData/Local/Programs/PersonalKnowledgeBase"


def expect_policy_error(callback) -> None:
    try:
        callback()
    except LocalModelPolicyValidationError:
        return
    raise AssertionError("expected LocalModelPolicyValidationError")


def valid_download_policy() -> LocalModelDownloadPolicy:
    return LocalModelDownloadPolicy(
        no_auto_download=True,
        confirmation_required=True,
        task_queue_required=True,
        single_file_gguf_only=True,
        no_repository_download=True,
        no_shell_script=True,
        no_arbitrary_command=True,
        actual_download_enabled=False,
    )


def valid_storage_policy() -> LocalModelStoragePolicy:
    return LocalModelStoragePolicy(
        default_model_dir_windows=DEFAULT_WINDOWS_MODEL_DIR,
        user_custom_model_dir_allowed=True,
        user_custom_dir_requires_future_confirmation=True,
        forbidden_locations=[
            "workspace",
            "software_install_dir",
            "knowledge",
            ".kb",
            "config",
            "templates",
            "reports",
            "system_dir",
        ],
        uninstall_app_deletes_models_by_default=False,
        user_can_delete_model_files_in_settings=True,
        delete_model_requires_confirmation=True,
    )


def valid_verification_policy() -> LocalModelVerificationPolicy:
    return LocalModelVerificationPolicy(
        sha256_required_for_verified_install=True,
        sha256_pending_blocks_verified_install=True,
        expected_size_required=True,
        invalid_checksum_fails_install=True,
        license_review_required=True,
    )


def assert_example_policies_validate() -> None:
    catalog = load_local_model_catalog(CONFIG_PATH)
    validate_local_model_storage_policy(catalog.storage_policy, WORKSPACE_ROOT, INSTALL_ROOT)
    validate_local_model_download_policy(catalog.download_policy)
    validate_local_model_verification_policy(catalog.verification_policy)


def assert_storage_policy_rejects_forbidden_locations() -> None:
    policy = validate_local_model_storage_policy(valid_storage_policy(), WORKSPACE_ROOT, INSTALL_ROOT)
    if policy.default_model_dir_windows != DEFAULT_WINDOWS_MODEL_DIR:
        raise AssertionError("default model path should stay under LocalAppData PersonalKnowledgeBase models")

    validate_local_model_storage_path("D:/LocalModels/PersonalKnowledgeBase", WORKSPACE_ROOT, INSTALL_ROOT)
    expect_policy_error(
        lambda: validate_local_model_storage_path("D:/workspaces/pkb/models", WORKSPACE_ROOT, INSTALL_ROOT)
    )
    expect_policy_error(
        lambda: validate_local_model_storage_path(
            "D:/Users/me/AppData/Local/Programs/PersonalKnowledgeBase/models",
            WORKSPACE_ROOT,
            INSTALL_ROOT,
        )
    )
    expect_policy_error(
        lambda: validate_local_model_storage_path("D:/LocalModels/knowledge/models", WORKSPACE_ROOT, INSTALL_ROOT)
    )
    expect_policy_error(
        lambda: validate_local_model_storage_path("D:/LocalModels/.kb/models", WORKSPACE_ROOT, INSTALL_ROOT)
    )
    expect_policy_error(
        lambda: validate_local_model_storage_policy(
            replace(valid_storage_policy(), user_custom_dir_requires_future_confirmation=False),
            WORKSPACE_ROOT,
            INSTALL_ROOT,
        )
    )
    expect_policy_error(
        lambda: validate_local_model_storage_policy(
            replace(valid_storage_policy(), uninstall_app_deletes_models_by_default=True),
            WORKSPACE_ROOT,
            INSTALL_ROOT,
        )
    )
    expect_policy_error(
        lambda: validate_local_model_storage_policy(
            replace(valid_storage_policy(), delete_model_requires_confirmation=False),
            WORKSPACE_ROOT,
            INSTALL_ROOT,
        )
    )


def assert_download_policy_rejects_auto_download() -> None:
    validate_local_model_download_policy(valid_download_policy())
    expect_policy_error(
        lambda: validate_local_model_download_policy(
            replace(valid_download_policy(), no_auto_download=False)
        )
    )
    expect_policy_error(
        lambda: validate_local_model_download_policy(
            replace(valid_download_policy(), actual_download_enabled=True)
        )
    )


def assert_download_policy_requires_confirmation_and_task_queue() -> None:
    expect_policy_error(
        lambda: validate_local_model_download_policy(
            replace(valid_download_policy(), confirmation_required=False)
        )
    )
    expect_policy_error(
        lambda: validate_local_model_download_policy(
            replace(valid_download_policy(), task_queue_required=False)
        )
    )
    expect_policy_error(
        lambda: validate_local_model_download_policy(
            replace(valid_download_policy(), single_file_gguf_only=False)
        )
    )
    expect_policy_error(
        lambda: validate_local_model_download_policy(
            replace(valid_download_policy(), no_repository_download=False)
        )
    )


def assert_download_policy_rejects_shell_and_arbitrary_command() -> None:
    expect_policy_error(
        lambda: validate_local_model_download_policy(
            replace(valid_download_policy(), no_shell_script=False)
        )
    )
    expect_policy_error(
        lambda: validate_local_model_download_policy(
            replace(valid_download_policy(), no_arbitrary_command=False)
        )
    )


def assert_verification_policy_requires_sha256_and_size() -> None:
    validate_local_model_verification_policy(valid_verification_policy())
    expect_policy_error(
        lambda: validate_local_model_verification_policy(
            replace(valid_verification_policy(), sha256_required_for_verified_install=False)
        )
    )
    expect_policy_error(
        lambda: validate_local_model_verification_policy(
            replace(valid_verification_policy(), sha256_pending_blocks_verified_install=False)
        )
    )
    expect_policy_error(
        lambda: validate_local_model_verification_policy(
            replace(valid_verification_policy(), expected_size_required=False)
        )
    )


def assert_no_network_download_or_runtime_start() -> None:
    catalog = load_local_model_catalog(CONFIG_PATH)
    validate_local_model_download_policy(catalog.download_policy)
    if catalog.download_policy.actual_download_enabled:
        raise AssertionError("local model policy must not enable actual download")

    forbidden_imports = {"requests", "urllib", "socket", "http.client", "subprocess", "openai"}
    forbidden_tokens = {"Popen", "system(", "start_runtime", "llama_cpp", "ModelScopeClient"}
    for relative_path in [
        "knowledge_app/ai/local_model_catalog.py",
        "knowledge_app/ai/local_model_policy.py",
    ]:
        source = (SOURCE_ROOT / relative_path).read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if re.match(r"^(import|from)\s+", stripped):
                for name in forbidden_imports:
                    if re.search(rf"\b{name}\b", stripped):
                        raise AssertionError(f"{relative_path} imports forbidden dependency {name}: {stripped}")
        for token in forbidden_tokens:
            if token in source:
                raise AssertionError(f"{relative_path} contains forbidden runtime token: {token}")


def main() -> int:
    assert_example_policies_validate()
    assert_storage_policy_rejects_forbidden_locations()
    assert_download_policy_rejects_auto_download()
    assert_download_policy_requires_confirmation_and_task_queue()
    assert_download_policy_rejects_shell_and_arbitrary_command()
    assert_verification_policy_requires_sha256_and_size()
    assert_no_network_download_or_runtime_start()

    print("Local model policy tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
