#!/usr/bin/env python3
"""MockAIProvider deterministic behavior tests."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.assistant_models import AssistantRequest, PolicyNotice
from knowledge_app.ai.mock_provider import MockAIProvider


def _notice(decision: str = "allow") -> PolicyNotice:
    return PolicyNotice(decision=decision, reason=f"{decision} for test")


def assert_deterministic_response(provider: MockAIProvider) -> None:
    request = AssistantRequest(
        message="搜索 service layer",
        intent="search_knowledge",
        capability_id="search_knowledge",
        context={
            "search_results": [
                {
                    "rank": 1,
                    "document_id": "fixture-rule",
                    "path": "knowledge/09-ai-agent/rules/fixture.md",
                    "title": "Fixture Rule",
                    "layer": "rules",
                    "status": "active",
                    "confidence": "high",
                    "source_type": "internal_practice",
                    "snippet": "Fixture snippet.",
                }
            ]
        },
    )
    first = provider.generate(request, _notice()).to_dict()
    second = provider.generate(request, _notice()).to_dict()
    assert first == second
    assert first["network_accessed"] is False
    assert first["mutation_executed"] is False
    assert first["model_dependency"] == "none"
    assert [card["card_type"] for card in first["messages"][0]["cards"]] == ["search_result", "citation"]


def assert_forbidden_returns_risk_notice(provider: MockAIProvider) -> None:
    request = AssistantRequest(message="删除资料", intent="delete_documents", capability_id="delete_document")
    response = provider.generate(request, _notice("deny")).to_dict()
    cards = response["messages"][0]["cards"]
    assert response["policy_notice"]["decision"] == "deny"
    assert cards[0]["card_type"] == "risk_notice"
    assert response["mutation_executed"] is False


def assert_memory_candidate_not_saved(provider: MockAIProvider) -> None:
    request = AssistantRequest(message="记住这个偏好", intent="create_memory_candidate", capability_id="create_memory_candidate")
    response = provider.generate(request, _notice("confirm")).to_dict()
    card_types = [card["card_type"] for card in response["messages"][0]["cards"]]
    assert "memory_candidate" in card_types
    assert "confirmation" in card_types
    assert response["memory_saved"] is False
    assert response["mutation_executed"] is False


def assert_plan_stays_mock(provider: MockAIProvider) -> None:
    request = AssistantRequest(message="生成清单", intent="create_checklist_draft", capability_id="create_checklist_draft")
    response = provider.generate(request, _notice()).to_dict()
    card_types = [card["card_type"] for card in response["messages"][0]["cards"]]
    assert card_types == ["plan", "task_progress"]
    assert response["mutation_executed"] is False


def assert_no_network_or_model_dependency() -> None:
    source = inspect.getsource(MockAIProvider).lower()
    for token in ["openai", "modelscope", "requests", "urllib", "socket", "sqlite3", "subprocess"]:
        assert token not in source


def main() -> int:
    provider = MockAIProvider()
    assert_deterministic_response(provider)
    assert_forbidden_returns_risk_notice(provider)
    assert_memory_candidate_not_saved(provider)
    assert_plan_stays_mock(provider)
    assert_no_network_or_model_dependency()
    print("AI mock provider tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
