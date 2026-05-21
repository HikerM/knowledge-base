#!/usr/bin/env python3
"""AssistantService skeleton tests."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from knowledge_app.ai.assistant_models import AssistantRequest
from knowledge_app.ai.assistant_service import AssistantService


def assert_uses_registry_and_policy(service: AssistantService) -> None:
    response = service.send(AssistantRequest(message="搜索 GUI service layer")).to_dict()
    assert response["intent"] == "search_knowledge"
    assert response["capability_id"] == "search_knowledge"
    assert response["policy_notice"]["decision"] == "allow"
    assert response["provider"] == "mock"
    assert response["network_accessed"] is False


def assert_unknown_capability_denied(service: AssistantService) -> None:
    response = service.send(AssistantRequest(message="unknown", intent="not_registered")).to_dict()
    assert response["intent"] == "not_registered"
    assert response["capability_id"] is None
    assert response["policy_notice"]["decision"] == "deny"
    assert response["messages"][0]["cards"][0]["card_type"] == "risk_notice"


def assert_high_risk_request_denied(service: AssistantService) -> None:
    response = service.send(AssistantRequest(message="请删除这些资料")).to_dict()
    assert response["intent"] == "delete_documents"
    assert response["policy_notice"]["decision"] == "deny"
    assert response["mutation_executed"] is False


def assert_memory_candidate_is_not_persisted(service: AssistantService) -> None:
    response = service.send(AssistantRequest(message="请记住我偏好正式层搜索")).to_dict()
    assert response["intent"] == "create_memory_candidate"
    assert response["policy_notice"]["decision"] == "confirm"
    assert response["memory_saved"] is False
    assert response["mutation_executed"] is False


def assert_no_markdown_sqlite_or_cli_access() -> None:
    source = inspect.getsource(AssistantService)
    for token in ["sqlite3", "subprocess", "scripts/kb.py", ".rglob(", ".glob(\"*.md", ".read_text("]:
        assert token not in source


def main() -> int:
    service = AssistantService.from_registry_path()
    assert_uses_registry_and_policy(service)
    assert_unknown_capability_denied(service)
    assert_high_risk_request_denied(service)
    assert_memory_candidate_is_not_persisted(service)
    assert_no_markdown_sqlite_or_cli_access()
    print("AI assistant service tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
