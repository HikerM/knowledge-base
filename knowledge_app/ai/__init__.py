"""AI control-plane contracts and v2.2.0 mock assistant skeleton.

This package intentionally exposes only static registry/policy evaluation and
an offline MockAIProvider. It does not connect to real AI providers or execute
capabilities.
"""

from knowledge_app.ai.assistant_models import (
    AssistantCard,
    AssistantMessage,
    AssistantRequest,
    AssistantResponse,
    Citation,
    PolicyNotice,
    SuggestedAction,
)
from knowledge_app.ai.assistant_service import AssistantService
from knowledge_app.ai.capability_registry import CapabilityRegistry, CapabilityRegistryValidationError
from knowledge_app.ai.models import Capability, CapabilityAuditSpec, CapabilityLevel, PermissionDecision
from knowledge_app.ai.mock_provider import MockAIProvider
from knowledge_app.ai.permission_policy import PermissionPolicy
from knowledge_app.ai.provider import AIProvider

__all__ = [
    "AIProvider",
    "AssistantCard",
    "AssistantMessage",
    "AssistantRequest",
    "AssistantResponse",
    "AssistantService",
    "Capability",
    "CapabilityAuditSpec",
    "CapabilityLevel",
    "CapabilityRegistry",
    "CapabilityRegistryValidationError",
    "Citation",
    "MockAIProvider",
    "PermissionDecision",
    "PermissionPolicy",
    "PolicyNotice",
    "SuggestedAction",
]
