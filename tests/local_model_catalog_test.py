#!/usr/bin/env python3
"""Local model catalog static loader and validation tests."""

from __future__ import annotations

import copy
import re
import sys
import tempfile
from pathlib import Path

import yaml


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.local_model_catalog import (  # noqa: E402
    DEFAULT_MODEL_DISPLAY_NAME,
    DEFAULT_MODEL_ID,
    LocalModelCatalog,
    LocalModelCatalogValidationError,
    LocalModelTier,
    get_default_model,
    get_model,
    list_models_by_tier,
    load_local_model_catalog,
    validate_local_model_catalog,
)


CONFIG_PATH = SOURCE_ROOT / "config" / "local-model-catalog.example.yaml"


def example_payload() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def write_temp_catalog(payload: dict) -> Path:
    temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".yaml", delete=False)
    with temp:
        yaml.safe_dump(payload, temp, allow_unicode=True, sort_keys=False)
    return Path(temp.name)


def expect_catalog_error(payload: dict) -> None:
    path = write_temp_catalog(payload)
    try:
        try:
            load_local_model_catalog(path)
        except LocalModelCatalogValidationError:
            return
        raise AssertionError("expected LocalModelCatalogValidationError")
    finally:
        path.unlink(missing_ok=True)


def assert_example_catalog_loads() -> LocalModelCatalog:
    catalog = load_local_model_catalog(CONFIG_PATH)
    validate_local_model_catalog(catalog)
    if len(catalog.models) != 4:
        raise AssertionError(f"expected 4 models, got {len(catalog.models)}")
    if get_model(catalog, DEFAULT_MODEL_ID).display_name != DEFAULT_MODEL_DISPLAY_NAME:
        raise AssertionError("default model id should resolve to Qwen3-0.6B-GGUF Q4_K_M")
    return catalog


def assert_tiers_present(catalog: LocalModelCatalog) -> None:
    tiers = {tier.value for tier in catalog.tiers}
    expected = {tier.value for tier in LocalModelTier}
    if tiers != expected:
        raise AssertionError(f"expected tiers {sorted(expected)}, got {sorted(tiers)}")
    for tier in LocalModelTier:
        models = list_models_by_tier(catalog, tier)
        if not models:
            raise AssertionError(f"expected at least one model for tier {tier.value}")


def assert_default_model_contract(catalog: LocalModelCatalog) -> None:
    default = get_default_model(catalog)
    if default.id != DEFAULT_MODEL_ID:
        raise AssertionError(f"default model should be {DEFAULT_MODEL_ID}, got {default.id}")
    if default.display_name != DEFAULT_MODEL_DISPLAY_NAME:
        raise AssertionError("default display name must stay Qwen3-0.6B-GGUF Q4_K_M")
    if default.tier is not LocalModelTier.ULTRA_LIGHT:
        raise AssertionError("default tier must be ultra_light")
    default_count = sum(1 for model in catalog.models if model.default)
    if default_count != 1:
        raise AssertionError(f"expected exactly one default, got {default_count}")


def assert_model_file_and_provider_contract(catalog: LocalModelCatalog) -> None:
    for model in catalog.models:
        if model.provider_kind != "local":
            raise AssertionError(f"{model.id} provider_kind must be local")
        if not model.filename.endswith(".gguf"):
            raise AssertionError(f"{model.id} filename must be .gguf")
        if model.source_kind not in {"modelscope_reference", "manual_reference"}:
            raise AssertionError(f"{model.id} source_kind must be reference-only")
        if model.expected_size <= 0 or model.install_size <= 0:
            raise AssertionError(f"{model.id} sizes must be positive")


def assert_unknown_tier_rejected() -> None:
    payload = example_payload()
    payload["models"][0]["tier"] = "desktop_replacement"
    expect_catalog_error(payload)


def assert_30gb_default_rejected() -> None:
    payload = example_payload()
    payload["models"][0]["expected_size_gb"] = 31.0
    payload["models"][0]["install_size_gb"] = 31.0
    expect_catalog_error(payload)


def assert_sha256_pending_blocks_verified_install() -> None:
    catalog = load_local_model_catalog(CONFIG_PATH)
    for model in catalog.models:
        if model.sha256 == "pending" and model.verified_install_allowed is not False:
            raise AssertionError(f"{model.id} sha256=pending must block verified install")

    payload = example_payload()
    payload["models"][0]["sha256"] = "pending"
    payload["models"][0]["verified_install_allowed"] = True
    expect_catalog_error(payload)


def assert_verified_install_requires_sha256() -> None:
    payload = example_payload()
    payload["models"][0]["sha256"] = ""
    payload["models"][0]["verified_install_allowed"] = True
    expect_catalog_error(payload)


def assert_malformed_catalog_rejected() -> None:
    payload = example_payload()
    del payload["models"][0]["display_name"]
    expect_catalog_error(payload)

    payload = example_payload()
    payload["default_model"] = "missing_model"
    expect_catalog_error(payload)

    payload = example_payload()
    payload["models"][1]["is_default"] = True
    expect_catalog_error(payload)

    payload = example_payload()
    payload["models"][0]["provider_kind"] = "openai"
    expect_catalog_error(payload)

    payload = example_payload()
    payload["models"][0]["filename"] = "qwen3.bin"
    expect_catalog_error(payload)


def assert_loader_accepts_payload_validation() -> None:
    payload = copy.deepcopy(example_payload())
    catalog = validate_local_model_catalog(payload)
    if not isinstance(catalog, LocalModelCatalog):
        raise AssertionError("validate_local_model_catalog should return LocalModelCatalog")


def assert_no_network_download_or_runtime_dependencies() -> None:
    forbidden_imports = {"requests", "urllib", "socket", "http.client", "subprocess", "openai"}
    forbidden_tokens = {"Popen", "run_server", "llama.cpp", "llama_cpp", "ModelScopeClient"}
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

    catalog = load_local_model_catalog(CONFIG_PATH)
    if catalog.download_policy.actual_download_enabled is not False:
        raise AssertionError("catalog must not enable actual model downloads")
    if catalog.download_policy.no_auto_download is not True:
        raise AssertionError("catalog must keep no_auto_download=true")


def main() -> int:
    catalog = assert_example_catalog_loads()
    assert_tiers_present(catalog)
    assert_default_model_contract(catalog)
    assert_model_file_and_provider_contract(catalog)
    assert_unknown_tier_rejected()
    assert_30gb_default_rejected()
    assert_sha256_pending_blocks_verified_install()
    assert_verified_install_requires_sha256()
    assert_malformed_catalog_rejected()
    assert_loader_accepts_payload_validation()
    assert_no_network_download_or_runtime_dependencies()

    print("Local model catalog tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
