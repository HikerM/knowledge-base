#!/usr/bin/env python3
"""AssistantService mock ask/summarize flow tests."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any, Dict, Optional


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.assistant_models import AssistantRequest
from knowledge_app.ai.assistant_service import AssistantService
from knowledge_app.ai.capability_registry import CapabilityRegistry
from knowledge_app.models.operation_result import OperationResult
from knowledge_app.models.search_result import SearchResult


CONFIG_PATH = SOURCE_ROOT / "config" / "ai-capabilities.example.yaml"


class FakeSearchService:
    def __init__(self, mode: str = "results"):
        self.mode = mode
        self.calls: list[Dict[str, Any]] = []

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, top_k: int = 5, include_options: Optional[Dict[str, Any]] = None, explain_score: bool = False) -> OperationResult:
        self.calls.append({"query": query, "filters": dict(filters or {}), "top_k": top_k, "include_options": dict(include_options or {})})
        if self.mode == "index_missing":
            return OperationResult(success=False, errors=["index.sqlite missing; cannot search"])
        rows = [] if self.mode == "empty" else [
            {
                "id": 7,
                "path": "knowledge/09-ai-agent/rules/service-boundary.md",
                "title": "Service Boundary Rule",
                "category": "ai_agent",
                "layer": "rules",
                "status": "active",
                "confidence": "high",
                "source_type": "internal_practice",
                "review_required": False,
                "snippet": "GUI 和 AI 必须通过 service boundary。",
            }
        ]
        return OperationResult(success=True, data=SearchResult(query=query, top_k=top_k, allowed_layers=["rules", "checklists", "snippets"], elapsed_ms=0, results=rows))


class FakeDocumentService:
    def __init__(self):
        self.calls: list[Dict[str, Any]] = []

    def open_document(self, document_id: Optional[int] = None, path: Optional[str] = None) -> OperationResult:
        self.calls.append({"document_id": document_id, "path": path})
        return OperationResult(
            success=True,
            data={
                "path": path or "knowledge/09-ai-agent/rules/service-boundary.md",
                "metadata": {"id": document_id or 7, "title": "Service Boundary Rule", "category": "ai_agent", "layer": "rules", "status": "active", "confidence": "high", "source_type": "internal_practice"},
                "frontmatter": {"title": "Service Boundary Rule", "category": "ai_agent", "layer": "rules", "status": "active", "confidence": "high", "source_type": "internal_practice", "review_required": False},
                "body": "AI 助手只能通过 service layer 获取上下文。总结当前文档只能打开一篇明确选择的文档。",
            },
        )


def build_service(search: FakeSearchService | None = None, document: FakeDocumentService | None = None) -> AssistantService:
    registry = CapabilityRegistry.load_from_yaml(CONFIG_PATH)
    return AssistantService(
        registry=registry,
        search_service_factory=lambda workspace: search or FakeSearchService(),
        document_service_factory=lambda workspace: document or FakeDocumentService(),
    )


def card_types(response: Dict[str, Any]) -> list[str]:
    return [card["card_type"] for message in response["messages"] for card in message["cards"]]


def assert_ask_calls_search_and_returns_citations() -> None:
    search = FakeSearchService()
    response = build_service(search=search).send(AssistantRequest(message="service boundary", intent="search_knowledge")).to_dict()
    assert search.calls and search.calls[0]["filters"] == {"status": "active"}
    assert search.calls[0]["include_options"]["include_raw"] is False
    assert response["citations"]
    assert "search_result" in card_types(response)
    assert response["mutation_executed"] is False
    assert response["network_accessed"] is False


def assert_no_results_and_missing_index_are_safe() -> None:
    empty_search = FakeSearchService(mode="empty")
    empty = build_service(search=empty_search).send(AssistantRequest(message="no results", intent="search_knowledge")).to_dict()
    assert empty_search.calls
    assert "system_notice" in card_types(empty)
    assert "没有找到" in empty["messages"][0]["content"]

    missing_search = FakeSearchService(mode="index_missing")
    missing = build_service(search=missing_search).send(AssistantRequest(message="index missing", intent="search_knowledge")).to_dict()
    assert missing_search.calls
    assert "error" in card_types(missing)
    assert missing["messages"][0]["cards"][0]["metadata"]["index_missing"] is True
    assert missing["mutation_executed"] is False


def assert_summarize_requires_and_opens_one_document() -> None:
    document = FakeDocumentService()
    missing = build_service(document=document).send(AssistantRequest(message="总结", intent="summarize_document")).to_dict()
    assert not document.calls
    assert "system_notice" in card_types(missing)

    response = build_service(document=document).send(
        AssistantRequest(
            message="总结",
            intent="summarize_document",
            ui_context={"current_document_id": "7", "current_document_path": "knowledge/09-ai-agent/rules/service-boundary.md"},
        )
    ).to_dict()
    assert len(document.calls) == 1
    assert document.calls[0]["document_id"] == 7
    assert response["citations"]
    assert "document_summary" in card_types(response)
    assert response["memory_saved"] is False
    assert response["mutation_executed"] is False


def assert_risk_memory_and_boundaries() -> None:
    risk = build_service().send(AssistantRequest(message="删除这些资料")).to_dict()
    assert risk["policy_notice"]["decision"] == "deny"
    assert "risk_notice" in card_types(risk)
    assert risk["mutation_executed"] is False

    memory = build_service().send(AssistantRequest(message="请记住这个偏好")).to_dict()
    assert "memory_candidate" in card_types(memory)
    assert memory["memory_saved"] is False

    source = inspect.getsource(AssistantService)
    for token in ["subprocess", "scripts/kb.py", ".rglob(", ".glob(\"*.md", ".read_text("]:
        assert token not in source


def main() -> int:
    assert_ask_calls_search_and_returns_citations()
    assert_no_results_and_missing_index_are_safe()
    assert_summarize_requires_and_opens_one_document()
    assert_risk_memory_and_boundaries()
    print("AI assistant mock flow tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
