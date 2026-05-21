"""Static permission policy evaluator for AI capability examples."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from knowledge_app.ai.models import Capability, CapabilityLevel, PermissionDecision


class PermissionPolicy:
    """Evaluate static allow/confirm/deny decisions without executing anything."""

    def evaluate(self, capability: Optional[Capability], context: Optional[Dict[str, Any]] = None) -> PermissionDecision:
        if capability is None:
            return PermissionDecision(
                decision="deny",
                reason="unknown capability is forbidden",
                required_cards=["error_card"],
                blocked_context=["unknown_capability"],
            )

        context = dict(context or {})
        requested_context = _requested_context(context)
        allowed_context = list(capability.allowed_context)

        if capability.level == CapabilityLevel.L4:
            return PermissionDecision(
                decision="deny",
                reason="L4 forbidden/destructive capability is denied",
                required_cards=["risk_notice_card"],
                allowed_context=allowed_context,
                blocked_context=requested_context or allowed_context,
            )

        sensitive_context = _has_sensitive_context(context)
        if sensitive_context:
            if _sensitive_scope_requires_confirmation(context):
                return _confirm(
                    "sensitive metadata requires explicit confirmation",
                    allowed_context=allowed_context,
                    blocked_context=["sensitive_context"],
                    required_cards=["privacy_notice_card", "confirmation_card"],
                )
            return PermissionDecision(
                decision="deny",
                reason="sensitive context is denied by default",
                required_cards=["risk_notice_card"],
                allowed_context=allowed_context,
                blocked_context=requested_context or ["sensitive_context"],
            )

        cloud_context = _requires_cloud_confirmation(context)

        if capability.level == CapabilityLevel.L0 and capability.read_only:
            if cloud_context:
                return _confirm(
                    "cloud or expanded context requires privacy notice and confirmation",
                    allowed_context=allowed_context,
                    required_cards=["privacy_notice_card", "confirmation_card"],
                )
            return PermissionDecision(
                decision="allow",
                reason="L0 read-only capability is allowed",
                allowed_context=allowed_context,
            )

        if capability.level == CapabilityLevel.L1:
            if capability.requires_confirmation or cloud_context:
                cards = ["privacy_notice_card", "confirmation_card"] if cloud_context else ["confirmation_card"]
                return _confirm(
                    "L1 capability requires confirmation by registry or context policy",
                    allowed_context=allowed_context,
                    required_cards=cards,
                )
            return PermissionDecision(
                decision="allow",
                reason="L1 local suggestion is allowed without persistence",
                allowed_context=allowed_context,
            )

        if capability.level == CapabilityLevel.L2:
            if capability.requires_confirmation or _is_high_risk(context) or cloud_context:
                cards = ["privacy_notice_card", "confirmation_card"] if cloud_context else ["confirmation_card"]
                return _confirm(
                    "L2 plan-only capability requires confirmation and cannot execute",
                    allowed_context=allowed_context,
                    required_cards=cards,
                )
            return PermissionDecision(
                decision="allow",
                reason="L2 plan-only capability is allowed without execution",
                allowed_context=allowed_context,
            )

        if capability.level == CapabilityLevel.L3:
            cards = ["privacy_notice_card", "confirmation_card"] if cloud_context else ["confirmation_card"]
            return _confirm(
                "L3 safe execute requires confirmation, snapshot, approval, and TaskQueue",
                allowed_context=allowed_context,
                required_cards=cards,
                requires_task_queue=True,
                requires_snapshot=True,
                requires_approval=True,
            )

        return PermissionDecision(
            decision="deny",
            reason="unsupported capability level is denied",
            required_cards=["error_card"],
            allowed_context=allowed_context,
        )


def _confirm(
    reason: str,
    allowed_context: List[str],
    blocked_context: Optional[List[str]] = None,
    required_cards: Optional[List[str]] = None,
    requires_task_queue: bool = False,
    requires_snapshot: bool = False,
    requires_approval: bool = False,
) -> PermissionDecision:
    return PermissionDecision(
        decision="confirm",
        reason=reason,
        required_cards=_unique(required_cards or ["confirmation_card"]),
        allowed_context=list(allowed_context),
        blocked_context=list(blocked_context or []),
        requires_task_queue=requires_task_queue,
        requires_snapshot=requires_snapshot,
        requires_approval=requires_approval,
    )


def _requested_context(context: Dict[str, Any]) -> List[str]:
    value = context.get("requested_context") or context.get("context") or context.get("context_types") or []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _requires_cloud_confirmation(context: Dict[str, Any]) -> bool:
    provider = str(context.get("provider") or context.get("provider_kind") or "").lower()
    scope = str(context.get("scope") or context.get("context_scope") or "").lower()
    return bool(
        context.get("cloud_context")
        or context.get("expanded_context")
        or provider in {"cloud", "openai", "remote"}
        or scope in {"cloud", "expanded", "full_document_cloud"}
    )


def _has_sensitive_context(context: Dict[str, Any]) -> bool:
    if context.get("sensitive_context") or context.get("has_sensitive_context"):
        return True
    sensitive_markers = {
        "secret",
        "secrets",
        "credential",
        "credentials",
        "token",
        "private_key",
        "customer_private_data",
        "quarantine",
        "rejected",
        "unreviewed_raw",
    }
    values = set(item.lower() for item in _requested_context(context))
    layer = str(context.get("layer") or "").lower()
    status = str(context.get("status") or "").lower()
    return bool(values.intersection(sensitive_markers) or layer == "quarantine" or status in {"rejected", "quarantine"})


def _sensitive_scope_requires_confirmation(context: Dict[str, Any]) -> bool:
    scope = str(context.get("sensitive_scope") or context.get("scope") or "").lower()
    return scope in {"metadata_only", "local_metadata", "explicit_metadata"}


def _is_high_risk(context: Dict[str, Any]) -> bool:
    risk = str(context.get("risk") or context.get("risk_level") or "").lower()
    return bool(context.get("high_risk") or risk == "high")


def _unique(values: List[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
