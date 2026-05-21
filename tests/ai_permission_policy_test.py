#!/usr/bin/env python3
"""AI permission policy static evaluator tests."""

from __future__ import annotations

import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.capability_registry import CapabilityRegistry
from knowledge_app.ai.permission_policy import PermissionPolicy


CONFIG_PATH = SOURCE_ROOT / "config" / "ai-capabilities.example.yaml"


def assert_decision_shape(decision) -> None:
    payload = decision.to_dict()
    expected = {
        "decision",
        "reason",
        "required_cards",
        "allowed_context",
        "blocked_context",
        "requires_task_queue",
        "requires_snapshot",
        "requires_approval",
    }
    if set(payload) != expected:
        raise AssertionError(f"PermissionDecision schema changed: {payload}")
    if payload["decision"] not in {"allow", "confirm", "deny"}:
        raise AssertionError(f"invalid decision value: {payload}")


def assert_unknown_denied(policy: PermissionPolicy) -> None:
    decision = policy.evaluate(None)
    assert_decision_shape(decision)
    if decision.decision != "deny":
        raise AssertionError(f"unknown capability must be denied: {decision}")


def assert_l0_allowed(registry: CapabilityRegistry, policy: PermissionPolicy) -> None:
    for capability_id in ["search_knowledge", "open_document"]:
        decision = policy.evaluate(registry.get(capability_id))
        assert_decision_shape(decision)
        if decision.decision != "allow":
            raise AssertionError(f"{capability_id} should be allowed: {decision}")


def assert_l1_summarize_context_policy(registry: CapabilityRegistry, policy: PermissionPolicy) -> None:
    summarize = registry.get("summarize_current_document")
    local_decision = policy.evaluate(summarize, {"provider": "local"})
    assert_decision_shape(local_decision)
    if local_decision.decision != "allow":
        raise AssertionError(f"L1 summarize local should be allowed: {local_decision}")

    cloud_decision = policy.evaluate(summarize, {"provider": "cloud", "context_scope": "cloud"})
    assert_decision_shape(cloud_decision)
    if cloud_decision.decision != "confirm":
        raise AssertionError(f"L1 summarize cloud should require confirmation: {cloud_decision}")
    for card in ["privacy_notice_card", "confirmation_card"]:
        if card not in cloud_decision.required_cards:
            raise AssertionError(f"L1 cloud decision missing {card}: {cloud_decision}")


def assert_l3_requires_all_gates(registry: CapabilityRegistry, policy: PermissionPolicy) -> None:
    decision = policy.evaluate(registry.get("update_category_description"))
    assert_decision_shape(decision)
    if decision.decision != "confirm":
        raise AssertionError(f"L3 update_category_description should require confirmation: {decision}")
    if not decision.requires_snapshot or not decision.requires_approval or not decision.requires_task_queue:
        raise AssertionError(f"L3 decision must require snapshot/approval/task queue: {decision}")
    if "confirmation_card" not in decision.required_cards:
        raise AssertionError(f"L3 decision must require confirmation card: {decision}")

    cloud_decision = policy.evaluate(registry.get("update_category_description"), {"provider": "cloud"})
    assert_decision_shape(cloud_decision)
    if cloud_decision.decision != "confirm":
        raise AssertionError(f"L3 cloud context should still require confirmation: {cloud_decision}")
    if not cloud_decision.requires_snapshot or not cloud_decision.requires_approval or not cloud_decision.requires_task_queue:
        raise AssertionError(f"L3 cloud context must keep all safe execute gates: {cloud_decision}")
    if "privacy_notice_card" not in cloud_decision.required_cards:
        raise AssertionError(f"L3 cloud context should require privacy notice: {cloud_decision}")


def assert_l4_denied(registry: CapabilityRegistry, policy: PermissionPolicy) -> None:
    for capability_id in ["delete_document", "promote_knowledge"]:
        decision = policy.evaluate(registry.get(capability_id))
        assert_decision_shape(decision)
        if decision.decision != "deny":
            raise AssertionError(f"{capability_id} must be denied: {decision}")
        cloud_decision = policy.evaluate(registry.get(capability_id), {"provider": "cloud"})
        assert_decision_shape(cloud_decision)
        if cloud_decision.decision != "deny":
            raise AssertionError(f"{capability_id} must remain denied with cloud context: {cloud_decision}")


def assert_sensitive_context_denied(registry: CapabilityRegistry, policy: PermissionPolicy) -> None:
    decision = policy.evaluate(
        registry.get("summarize_current_document"),
        {"provider": "local", "requested_context": ["secret"]},
    )
    assert_decision_shape(decision)
    if decision.decision != "deny":
        raise AssertionError(f"sensitive context should be denied by default: {decision}")


def main() -> int:
    registry = CapabilityRegistry.load_from_yaml(CONFIG_PATH)
    policy = PermissionPolicy()

    assert_unknown_denied(policy)
    assert_l0_allowed(registry, policy)
    assert_l1_summarize_context_policy(registry, policy)
    assert_l3_requires_all_gates(registry, policy)
    assert_l4_denied(registry, policy)
    assert_sensitive_context_denied(registry, policy)

    print("AI permission policy tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
