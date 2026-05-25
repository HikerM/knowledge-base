#!/usr/bin/env python3
"""Local model download plan-only service tests."""

from __future__ import annotations

import re
import sys
import tempfile
from dataclasses import replace
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.local_model_catalog import (  # noqa: E402
    DEFAULT_MODEL_ID,
    LocalModelCatalog,
    get_default_model,
    get_model,
    load_local_model_catalog,
)
from knowledge_app.ai.local_model_download_models import (  # noqa: E402
    LOCAL_MODEL_DOWNLOAD_PLAN_SCHEMA_VERSION,
    ModelDownloadPlan,
)
from knowledge_app.ai.local_model_download_plan_service import (  # noqa: E402
    LocalModelDownloadPlanServiceError,
    ModelDownloadPlanService,
)


CONFIG_PATH = SOURCE_ROOT / "config" / "local-model-catalog.example.yaml"
WORKSPACE_ROOT = "D:/workspaces/pkb"
INSTALL_ROOT = "D:/Users/me/AppData/Local/Programs/PersonalKnowledgeBase"


def load_catalog() -> LocalModelCatalog:
    return load_local_model_catalog(CONFIG_PATH)


def service() -> ModelDownloadPlanService:
    return ModelDownloadPlanService(workspace_root=WORKSPACE_ROOT, install_root=INSTALL_ROOT)


def expect_service_error(callback) -> None:
    try:
        callback()
    except LocalModelDownloadPlanServiceError:
        return
    raise AssertionError("expected LocalModelDownloadPlanServiceError")


def assert_valid_model_creates_dry_run_plan() -> ModelDownloadPlan:
    catalog = load_catalog()
    plan = service().create_download_plan(
        catalog,
        DEFAULT_MODEL_ID,
        "D:/LocalModels/PersonalKnowledgeBase",
        available_disk_gb=10.0,
    )
    if plan.schema_version != LOCAL_MODEL_DOWNLOAD_PLAN_SCHEMA_VERSION:
        raise AssertionError("unexpected plan schema version")
    if plan.model_id != DEFAULT_MODEL_ID:
        raise AssertionError("plan should use requested model id")
    if plan.dry_run is not True:
        raise AssertionError("plan must be dry_run=true")
    if plan.would_modify is not False:
        raise AssertionError("plan must not modify")
    if plan.would_download is not False:
        raise AssertionError("plan must not download")
    if plan.requires_task_queue is not True:
        raise AssertionError("plan must require TaskQueue")
    if plan.requires_confirmation is not True:
        raise AssertionError("plan must require confirmation")
    if not plan.target_file.endswith(".gguf"):
        raise AssertionError("target file must be .gguf")
    if not plan.would_create_dirs:
        raise AssertionError("plan should list future directories without creating them")
    return plan


def assert_plan_does_not_write_target_dir() -> None:
    catalog = load_catalog()
    with tempfile.TemporaryDirectory() as temp_root:
        target_dir = Path(temp_root) / "models-not-created"
        if target_dir.exists():
            raise AssertionError("test setup target should not exist")
        plan = service().create_download_plan(catalog, DEFAULT_MODEL_ID, str(target_dir), available_disk_gb=10.0)
        if plan.would_modify or plan.would_download:
            raise AssertionError("plan-only service must not modify or download")
        if target_dir.exists():
            raise AssertionError("plan-only service created target directory")


def assert_sha256_pending_creates_blocker() -> None:
    plan = service().create_download_plan(
        load_catalog(),
        DEFAULT_MODEL_ID,
        "D:/LocalModels/PersonalKnowledgeBase",
        available_disk_gb=10.0,
    )
    if "sha256=pending blocks verified install" not in plan.blockers:
        raise AssertionError(f"expected sha256 blocker, got {plan.blockers}")


def assert_invalid_model_rejected() -> None:
    expect_service_error(
        lambda: service().create_download_plan(
            load_catalog(),
            "missing_model",
            "D:/LocalModels/PersonalKnowledgeBase",
        )
    )


def assert_target_workspace_path_blocked() -> None:
    plan = service().create_download_plan(load_catalog(), DEFAULT_MODEL_ID, "D:/workspaces/pkb/models")
    if not any("workspace" in blocker for blocker in plan.blockers):
        raise AssertionError(f"expected workspace path blocker, got {plan.blockers}")


def assert_target_install_dir_blocked() -> None:
    plan = service().create_download_plan(
        load_catalog(),
        DEFAULT_MODEL_ID,
        "D:/Users/me/AppData/Local/Programs/PersonalKnowledgeBase/models",
    )
    if not any("install dir" in blocker for blocker in plan.blockers):
        raise AssertionError(f"expected install dir blocker, got {plan.blockers}")


def assert_target_knowledge_path_blocked() -> None:
    plan = service().create_download_plan(load_catalog(), DEFAULT_MODEL_ID, "D:/LocalModels/knowledge/models")
    if not any("knowledge" in blocker for blocker in plan.blockers):
        raise AssertionError(f"expected knowledge path blocker, got {plan.blockers}")


def assert_target_kb_path_blocked() -> None:
    plan = service().create_download_plan(load_catalog(), DEFAULT_MODEL_ID, "D:/LocalModels/.kb/models")
    if not any(".kb" in blocker for blocker in plan.blockers):
        raise AssertionError(f"expected .kb path blocker, got {plan.blockers}")


def assert_insufficient_disk_blocked() -> None:
    plan = service().create_download_plan(
        load_catalog(),
        DEFAULT_MODEL_ID,
        "D:/LocalModels/PersonalKnowledgeBase",
        available_disk_gb=0.1,
    )
    if not any("disk" in blocker for blocker in plan.blockers):
        raise AssertionError(f"expected disk blocker, got {plan.blockers}")


def assert_default_model_plan_is_ultra_light() -> None:
    catalog = load_catalog()
    default = get_default_model(catalog)
    plan = service().create_download_plan(catalog, default.id, "D:/LocalModels/PersonalKnowledgeBase")
    if plan.tier != "ultra_light":
        raise AssertionError(f"default plan tier must be ultra_light, got {plan.tier}")


def assert_30gb_model_cannot_be_default() -> None:
    catalog = load_catalog()
    default = get_default_model(catalog)
    inflated_default = replace(default, expected_size=31.0, install_size=32.0)
    mutated_models = [inflated_default if model.id == default.id else model for model in catalog.models]
    mutated_catalog = replace(catalog, models=mutated_models)
    expect_service_error(
        lambda: service().create_download_plan(
            mutated_catalog,
            default.id,
            "D:/LocalModels/PersonalKnowledgeBase",
        )
    )


def assert_30gb_non_default_requires_future_advanced_flow() -> None:
    catalog = load_catalog()
    model = get_model(catalog, "qwen3_8b_gguf_q4")
    large_model = replace(model, expected_size=31.0, install_size=32.0)
    mutated_models = [large_model if item.id == model.id else item for item in catalog.models]
    mutated_catalog = replace(catalog, models=mutated_models)
    plan = service().create_download_plan(
        mutated_catalog,
        model.id,
        "D:/LocalModels/PersonalKnowledgeBase",
        available_disk_gb=100.0,
    )
    if not any("30GB+" in blocker for blocker in plan.blockers):
        raise AssertionError(f"expected 30GB advanced-flow blocker, got {plan.blockers}")


def assert_no_network_download_or_runtime_imports() -> None:
    forbidden_imports = {
        "requests",
        "urllib",
        "socket",
        "http.client",
        "subprocess",
        "openai",
        "llama_cpp",
    }
    forbidden_tokens = {
        "Popen",
        "os.system",
        "start_runtime",
        "start_server",
        "ModelScopeClient",
        "AIProvider",
        "ContextBuilder",
        "download(",
    }
    for relative_path in [
        "knowledge_app/ai/local_model_download_models.py",
        "knowledge_app/ai/local_model_download_plan_service.py",
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
    assert_valid_model_creates_dry_run_plan()
    assert_plan_does_not_write_target_dir()
    assert_sha256_pending_creates_blocker()
    assert_invalid_model_rejected()
    assert_target_workspace_path_blocked()
    assert_target_install_dir_blocked()
    assert_target_knowledge_path_blocked()
    assert_target_kb_path_blocked()
    assert_insufficient_disk_blocked()
    assert_default_model_plan_is_ultra_light()
    assert_30gb_model_cannot_be_default()
    assert_30gb_non_default_requires_future_advanced_flow()
    assert_no_network_download_or_runtime_imports()

    print("Local model download plan tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
