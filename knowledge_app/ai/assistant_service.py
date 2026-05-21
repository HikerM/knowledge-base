"""Assistant service skeleton for the mock floating assistant."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from knowledge_app.ai.assistant_models import AssistantRequest, AssistantResponse, PolicyNotice
from knowledge_app.ai.capability_registry import CapabilityRegistry
from knowledge_app.ai.mock_provider import MockAIProvider
from knowledge_app.ai.models import PermissionDecision
from knowledge_app.ai.permission_policy import PermissionPolicy
from knowledge_app.ai.provider import AIProvider
from knowledge_app.services.document_service import DocumentService
from knowledge_app.services.search_service import SearchService


DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "ai-capabilities.example.yaml"

RISK_INTENT_KEYWORDS = (
    ("delete_documents", ("删除", "清空", "delete", "remove")),
    ("archive_documents", ("归档", "archive")),
    ("restore_backup", ("恢复", "restore")),
    ("promote_knowledge", ("promote", "正式化", "提升为正式", "提升到正式")),
)


class AssistantService:
    """Route a user request through registry, policy, and MockAIProvider.

    Ask/summarize mock flows use SearchService and DocumentService only after
    registry/policy checks. This class does not execute mutation capabilities,
    read Markdown/SQLite directly, send cloud context, or persist memory.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        policy: Optional[PermissionPolicy] = None,
        provider: Optional[AIProvider] = None,
        workspace_path: Path | str | None = None,
        search_service_factory: Optional[Callable[[Path | None], Any]] = None,
        document_service_factory: Optional[Callable[[Path | None], Any]] = None,
    ):
        self.registry = registry
        self.policy = policy or PermissionPolicy()
        self.provider = provider or MockAIProvider()
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else None
        self.search_service_factory = search_service_factory or (lambda workspace: SearchService(workspace))
        self.document_service_factory = document_service_factory or (lambda workspace: DocumentService(workspace))

    @classmethod
    def from_registry_path(
        cls,
        path: Path | str = DEFAULT_REGISTRY_PATH,
        workspace_path: Path | str | None = None,
    ) -> "AssistantService":
        registry = CapabilityRegistry.load_from_yaml(path)
        return cls(registry=registry, workspace_path=workspace_path)

    def send(self, request: AssistantRequest | Dict[str, Any]) -> AssistantResponse:
        assistant_request = _coerce_request(request)
        resolved_intent = self._resolve_intent(assistant_request)
        capability = self._resolve_capability(assistant_request, resolved_intent)
        capability_id = capability.id if capability else assistant_request.capability_id
        context = self._policy_context(assistant_request, resolved_intent)
        decision = self.policy.evaluate(capability, context)
        policy_notice = _notice_from_decision(decision)
        if decision.decision != "deny":
            if resolved_intent == "search_knowledge":
                context = self.ask_my_knowledge(assistant_request.message, assistant_request.ui_context, context)
            elif resolved_intent == "summarize_document":
                context = self.summarize_current_document(_current_document_id(assistant_request.ui_context), assistant_request.ui_context, context)
        routed_request = replace(assistant_request, intent=resolved_intent, capability_id=capability_id, context=context)
        return self.provider.generate(routed_request, policy_notice)

    def ask_my_knowledge(self, query: str, ui_context: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Search formal knowledge through SearchService and attach mock context."""

        payload = dict(context or {})
        clean_query = query.strip()
        payload["mock_flow"] = "ask_my_knowledge"
        payload["ui_context"] = dict(ui_context)
        payload["allowed_scope"] = "formal_only"
        payload["formal_layers"] = ["rules", "checklists", "snippets"]
        if not clean_query:
            payload["empty_query"] = True
            return payload

        service = self.search_service_factory(self.workspace_path)
        result = service.search(
            clean_query,
            filters={"status": "active"},
            top_k=5,
            include_options={"include_raw": False, "include_distilled": False, "include_deprecated": False},
        )
        payload["search_service_called"] = True
        payload["search_query"] = clean_query
        payload["search_filters"] = {"layers": ["rules", "checklists", "snippets"], "status": ["active"], "review_required": False}
        if not result.success or result.data is None:
            payload["service_error"] = {
                "service": "SearchService",
                "errors": list(result.errors or ["search service unavailable"]),
                "index_missing": _looks_like_index_missing(result.errors),
            }
            payload["search_results"] = []
            return payload

        data = result.data.to_dict() if hasattr(result.data, "to_dict") else dict(result.data)
        payload["search_results"] = [_search_result_card_payload(item, index) for index, item in enumerate(data.get("results", []), start=1)]
        payload["search_elapsed_ms"] = int(data.get("elapsed_ms") or result.elapsed_ms or 0)
        return payload

    def summarize_current_document(self, document_id: str | int | None, ui_context: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Open one explicit document through DocumentService and attach mock context."""

        payload = dict(context or {})
        payload["mock_flow"] = "summarize_current_document"
        payload["ui_context"] = dict(ui_context)
        payload["allowed_scope"] = "explicit_single_document"
        document_path = str(ui_context.get("current_document_path") or "")
        if document_id in (None, "") and not document_path:
            payload["missing_current_document"] = True
            return payload

        numeric_id = int(document_id) if document_id not in (None, "") and str(document_id).isdigit() else None
        path = document_path or (str(document_id) if numeric_id is None and document_id not in (None, "") else None)
        service = self.document_service_factory(self.workspace_path)
        result = service.open_document(document_id=numeric_id, path=path)
        payload["document_service_called"] = True
        payload["document_open_request"] = {"document_id": numeric_id, "path": path}
        if not result.success or not result.data:
            payload["service_error"] = {"service": "DocumentService", "errors": list(result.errors or ["document service unavailable"])}
            return payload
        payload["document"] = _document_payload(result.data)
        return payload

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
        context["ui_context"] = dict(request.ui_context)
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
        ui_context=dict(request.get("ui_context") or request.get("uiContext") or {}),
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


def _current_document_id(ui_context: Dict[str, Any]) -> str:
    return str(ui_context.get("current_document_id") or "")


def _looks_like_index_missing(errors: list[str]) -> bool:
    text = " ".join(str(item).lower() for item in errors or [])
    return "index" in text and ("missing" in text or "not found" in text or "no such file" in text)


def _search_result_card_payload(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    path = str(item.get("path") or "")
    return {
        "rank": index,
        "document_id": str(item.get("document_id") or item.get("id") or path),
        "path": path,
        "title": str(item.get("title") or path or "未命名文档"),
        "category_id": str(item.get("category_id") or item.get("category") or ""),
        "layer": str(item.get("layer") or ""),
        "status": str(item.get("status") or ""),
        "confidence": str(item.get("confidence") or ""),
        "source_type": str(item.get("source_type") or ""),
        "review_required": bool(item.get("review_required", False)),
        "snippet": str(item.get("snippet") or ""),
        "source_url": str(item.get("source_url") or ""),
    }


def _document_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    metadata = dict(data.get("metadata") or {})
    frontmatter = dict(data.get("frontmatter") or {})
    path = str(data.get("path") or "")
    return {
        "document_id": str(metadata.get("id") or path),
        "path": path,
        "title": str(frontmatter.get("title") or metadata.get("title") or path or "未命名文档"),
        "category_id": str(frontmatter.get("category") or metadata.get("category") or ""),
        "layer": str(frontmatter.get("layer") or metadata.get("layer") or ""),
        "status": str(frontmatter.get("status") or metadata.get("status") or ""),
        "source_type": str(frontmatter.get("source_type") or metadata.get("source_type") or ""),
        "confidence": str(frontmatter.get("confidence") or metadata.get("confidence") or ""),
        "review_required": bool(frontmatter.get("review_required", metadata.get("review_required", False))),
        "source_url": str(frontmatter.get("source_url") or metadata.get("source_url") or ""),
        "last_reviewed": str(frontmatter.get("last_reviewed") or metadata.get("last_reviewed") or ""),
        "body": str(data.get("body") or ""),
    }
