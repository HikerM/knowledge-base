#!/usr/bin/env python3
"""AI capability registry loader and validation tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.capability_registry import CapabilityRegistry, CapabilityRegistryValidationError


CONFIG_PATH = SOURCE_ROOT / "config" / "ai-capabilities.example.yaml"
REQUIRED_CAPABILITY_KEYS = {
    "id",
    "intent",
    "level",
    "service",
    "provider",
    "read_only",
    "requires_ai",
    "requires_confirmation",
    "requires_cloud_context_preview",
    "allowed_context",
    "audit",
    "current_version",
    "default_filters",
    "output_policy",
    "execution_contract",
}
REQUIRED_AUDIT_KEYS = {
    "record_intent",
    "record_citations",
    "record_context_ids",
    "record_task_id",
}


def write_temp_config(text: str) -> Path:
    temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".yaml", delete=False)
    with temp:
        temp.write(text)
    return Path(temp.name)


def expect_validation_error(text: str) -> None:
    path = write_temp_config(text)
    try:
        try:
            CapabilityRegistry.load_from_yaml(path)
        except CapabilityRegistryValidationError:
            return
        raise AssertionError("expected CapabilityRegistryValidationError")
    finally:
        path.unlink(missing_ok=True)


def assert_example_loads_and_validates() -> CapabilityRegistry:
    registry = CapabilityRegistry.load_from_yaml(CONFIG_PATH)
    registry.validate()
    capabilities = registry.list_capabilities()
    if len(capabilities) != 14:
        raise AssertionError(f"expected 14 capabilities, got {len(capabilities)}")
    if registry.get("search_knowledge") is None:
        raise AssertionError("search_knowledge should be registered")
    if registry.get_by_intent("search_knowledge") is None:
        raise AssertionError("search_knowledge intent lookup should resolve")
    if registry.get("not_registered") is not None:
        raise AssertionError("unknown capability lookup should return None")
    return registry


def assert_required_fields_present(registry: CapabilityRegistry) -> None:
    for capability in registry.list_capabilities():
        payload = capability.to_dict()
        missing = REQUIRED_CAPABILITY_KEYS.difference(payload)
        if missing:
            raise AssertionError(f"{capability.id} missing serialized fields: {sorted(missing)}")
        audit_missing = REQUIRED_AUDIT_KEYS.difference(payload["audit"])
        if audit_missing:
            raise AssertionError(f"{capability.id} missing audit fields: {sorted(audit_missing)}")
        if capability.level != "L4" and not (capability.service or capability.provider):
            raise AssertionError(f"{capability.id} must declare a service or provider")


def assert_policy_shape_fields(registry: CapabilityRegistry) -> None:
    description = registry.get("update_category_description")
    if description is None:
        raise AssertionError("update_category_description should be registered")
    if description.level != "L3":
        raise AssertionError("update_category_description must remain L3")
    if not description.requires_confirmation:
        raise AssertionError("L3 update_category_description must require confirmation")
    for key in ["requires_plan", "requires_snapshot", "requires_approval", "requires_task_queue"]:
        if description.execution_contract.get(key) is not True:
            raise AssertionError(f"L3 execution_contract.{key} must be true")


def assert_service_strings_block_cli() -> None:
    original = CONFIG_PATH.read_text(encoding="utf-8")
    malformed = original.replace(
        'service: "knowledge_app.services.search_service.SearchService.search"',
        'service: "subprocess.run"',
        1,
    )
    expect_validation_error(malformed)


def assert_malformed_yaml_rejected() -> None:
    original = CONFIG_PATH.read_text(encoding="utf-8")
    missing_field = original.replace('    intent: "search_knowledge"\n', "", 1)
    expect_validation_error(missing_field)

    invalid_level = original.replace('    level: "L0"\n', '    level: "L9"\n', 1)
    expect_validation_error(invalid_level)


def main() -> int:
    registry = assert_example_loads_and_validates()
    assert_required_fields_present(registry)
    assert_policy_shape_fields(registry)
    assert_service_strings_block_cli()
    assert_malformed_yaml_rejected()

    print("AI capability registry tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
