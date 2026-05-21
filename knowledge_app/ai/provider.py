"""AIProvider interface for assistant control-plane providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from knowledge_app.ai.assistant_models import AssistantRequest, AssistantResponse, PolicyNotice


class AIProvider(ABC):
    """Provider interface used by AssistantService.

    Current releases ship only MockAIProvider. Implementations must not be called
    directly from GUI views.
    """

    provider_name = "abstract"
    provider_mode = "none"

    @abstractmethod
    def generate(self, request: AssistantRequest, policy_notice: PolicyNotice) -> AssistantResponse:
        """Generate a response for a routed request and policy decision."""
