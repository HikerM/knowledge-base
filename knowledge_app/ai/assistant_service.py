"""Assistant service skeleton for the v2.2.0 mock floating assistant."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Optional

from knowledge_app.ai.assistant_models import AssistantRequest, AssistantResponse, PolicyNotice
from knowledge_app.ai.capability_registry import CapabilityRegistry
from knowledge_app.ai.mock_provider import MockAIProvider
from knowledge_app.ai.models import PermissionDecision
from knowledge_app.ai.permission_policy import PermissionPolicy
from knowledge_app.ai.provider import AIProvider


DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "ai-capabilities.example.yaml"

RISK_INTENT_KEYWORDS = (
    ("delete_documents", ("删除", "清空", "delete", "remove")),
    ("archive_documents", ("归档", "archive")),
    ("restore_backup", ("恢复", "restore")),
    ("promote_knowledge", ("promote", "正式化", "提升为正式", "提升到正式")),
)


class AssistantService:
    """Route a user request through registry, policy, and MockAIProvider.

    This skeleton does not execute capabilities, does not call SearchService,
    does not read Markdown or SQLite, and does not persist memory.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        policy: Optional[PermissionPolicy] = None,
        provider: Optional[AIProvider] = None,
    ):
        self.registry = registry
        self.policy = policy or PermissionPolicy()
        self.provider = provider or MockAIProvider()

    @classmethod
    def from_registry_path(cls, path: Path | str = DEFAULT_REGISTRY_PATH) -> "AssistantService":
        registry = CapabilityRegistry.load_from_yaml(path)
        return cls(registry=registry)

    def send(self, request: AssistantRequest | Dict[str, Any]) -> AssistantResponse:
        assistant_request = _coerce_request(request)
        resolved_intent = self._resolve_intent(assistant_request)
        capability = self._resolve_capability(assistant_request, resolved_intent)
        capability_id = capability.id if capability else assistant_request.capability_id
        context = self._policy_context(assistant_request, resolved_intent)
        decision = self.policy.evaluate(capability, context)
        policy_notice = _notice_from_decision(decision)
        routed_request = replace(assistant_request, intent=resolved_intent, capability_id=capability_id, context=context)
        return self.provider.generate(routed_request, policy_notice)

    def _resolve_capability(self, request: AssistantRequest, intent: str):
        if request.capability_id:
            return self.registry.get(request.capability_id)
        return self.registry.get_by_intent(intent)

    @staticmethod
    def _resolve_intent(request: AssistantRequest) -> str:
        explicit = (request.intent or "").strip()
        if explicit and explicit != "auto":
            return explicit
        text = request.message.lower()
        for intent, keywords in RISK_INTENT_KEYWORDS:
            if any(keyword.lower() in text for keyword in keywords):
                return intent
        if "记住" in request.message or "remember" in text or "memory" in text:
            return "create_memory_candidate"
        if "总结" in request.message or "summary" in text or "summarize" in text:
            return "summarize_document"
        if "搜索" in request.message or "找" in request.message or "search" in text or "find" in text:
            return "search_knowledge"
        if "计划" in request.message or "整理" in request.message or "plan" in text:
            return "create_checklist_draft"
        return "explain_document"

    @staticmethod
    def _policy_context(request: AssistantRequest, intent: str) -> Dict[str, Any]:
        context = dict(request.context)
        context.setdefault("provider", "local")
        context.setdefault("provider_kind", "mock")
        context.setdefault("cloud_context", False)
        context.setdefault("expanded_context", False)
        if intent in {item[0] for item in RISK_INTENT_KEYWORDS}:
            context["high_risk"] = True
            context["risk_level"] = "high"
        return context


def _coerce_request(request: AssistantRequest | Dict[str, Any]) -> AssistantRequest:
    if isinstance(request, AssistantRequest):
        return request
    return AssistantRequest(
        message=str(request.get("message") or ""),
        intent=str(request.get("intent") or "auto"),
        conversation_id=str(request.get("conversation_id") or "mock-conversation"),
        capability_id=request.get("capability_id"),
        context=dict(request.get("context") or {}),
    )


def _notice_from_decision(decision: PermissionDecision) -> PolicyNotice:
    severity = "danger" if decision.decision == "deny" else ("warning" if decision.decision == "confirm" else "info")
    return PolicyNotice(
        decision=decision.decision,
        reason=decision.reason,
        severity=severity,
        required_cards=list(decision.required_cards),
        blocked_context=list(decision.blocked_context),
        allowed_context=list(decision.allowed_context),
        requires_task_queue=decision.requires_task_queue,
        requires_snapshot=decision.requires_snapshot,
        requires_approval=decision.requires_approval,
    )
