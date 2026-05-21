"""Conversation models for the mock AI assistant control plane."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Citation:
    """Source metadata shown by assistant citation cards."""

    citation_id: str
    title: str
    document_id: str = ""
    path: str = ""
    layer: str = ""
    status: str = ""
    source_type: str = ""
    confidence: str = ""
    review_required: bool = False
    source_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "title": self.title,
            "document_id": self.document_id,
            "path": self.path,
            "layer": self.layer,
            "status": self.status,
            "source_type": self.source_type,
            "confidence": self.confidence,
            "review_required": self.review_required,
            "source_url": self.source_url,
        }


@dataclass(frozen=True)
class SuggestedAction:
    """Non-executing action metadata rendered as disabled guidance in v2.2.0."""

    action_id: str
    label: str
    kind: str = "mock"
    enabled: bool = False
    requires_confirmation: bool = True
    mutation: bool = False
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "label": self.label,
            "kind": self.kind,
            "enabled": self.enabled,
            "requires_confirmation": self.requires_confirmation,
            "mutation": self.mutation,
            "description": self.description,
        }


@dataclass(frozen=True)
class PolicyNotice:
    """Permission policy decision summary attached to a mock response."""

    decision: str
    reason: str
    severity: str = "info"
    title: str = "权限策略"
    required_cards: List[str] = field(default_factory=list)
    blocked_context: List[str] = field(default_factory=list)
    allowed_context: List[str] = field(default_factory=list)
    requires_task_queue: bool = False
    requires_snapshot: bool = False
    requires_approval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "severity": self.severity,
            "title": self.title,
            "required_cards": list(self.required_cards),
            "blocked_context": list(self.blocked_context),
            "allowed_context": list(self.allowed_context),
            "requires_task_queue": self.requires_task_queue,
            "requires_snapshot": self.requires_snapshot,
            "requires_approval": self.requires_approval,
        }


@dataclass(frozen=True)
class AssistantCard:
    """Renderable assistant card payload."""

    card_type: str
    title: str
    body: str = ""
    items: List[str] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    actions: List[SuggestedAction] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_type": self.card_type,
            "title": self.title,
            "body": self.body,
            "items": list(self.items),
            "citations": [citation.to_dict() for citation in self.citations],
            "actions": [action.to_dict() for action in self.actions],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AssistantMessage:
    """One conversation message rendered by the floating assistant."""

    message_id: str
    role: str
    author: str
    content: str
    alignment: str = "left"
    cards: List[AssistantCard] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "role": self.role,
            "author": self.author,
            "content": self.content,
            "alignment": self.alignment,
            "cards": [card.to_dict() for card in self.cards],
        }


@dataclass(frozen=True)
class AssistantRequest:
    """Input accepted by AssistantService and AIProvider."""

    message: str
    intent: str = "auto"
    conversation_id: str = "mock-conversation"
    capability_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    ui_context: Dict[str, Any] = field(default_factory=dict)
    history: List[AssistantMessage] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": self.message,
            "intent": self.intent,
            "conversation_id": self.conversation_id,
            "capability_id": self.capability_id,
            "context": dict(self.context),
            "ui_context": dict(self.ui_context),
            "history": [message.to_dict() for message in self.history],
        }


@dataclass(frozen=True)
class AssistantResponse:
    """Deterministic response returned by the mock assistant provider."""

    response_id: str
    provider: str
    provider_mode: str
    intent: str
    capability_id: Optional[str]
    policy_notice: PolicyNotice
    messages: List[AssistantMessage]
    citations: List[Citation] = field(default_factory=list)
    suggested_actions: List[SuggestedAction] = field(default_factory=list)
    memory_saved: bool = False
    mutation_executed: bool = False
    network_accessed: bool = False
    model_dependency: str = "none"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_id": self.response_id,
            "provider": self.provider,
            "provider_mode": self.provider_mode,
            "intent": self.intent,
            "capability_id": self.capability_id,
            "policy_notice": self.policy_notice.to_dict(),
            "messages": [message.to_dict() for message in self.messages],
            "citations": [citation.to_dict() for citation in self.citations],
            "suggested_actions": [action.to_dict() for action in self.suggested_actions],
            "memory_saved": self.memory_saved,
            "mutation_executed": self.mutation_executed,
            "network_accessed": self.network_accessed,
            "model_dependency": self.model_dependency,
        }
