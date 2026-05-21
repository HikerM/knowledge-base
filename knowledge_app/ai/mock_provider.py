"""Deterministic offline mock provider for the floating assistant skeleton."""

from __future__ import annotations

from knowledge_app.ai.assistant_models import (
    AssistantCard,
    AssistantMessage,
    AssistantRequest,
    AssistantResponse,
    Citation,
    PolicyNotice,
    SuggestedAction,
)
from knowledge_app.ai.provider import AIProvider


FORBIDDEN_INTENTS = {
    "delete_documents",
    "promote_knowledge",
    "archive_documents",
    "restore_backup",
}


class MockAIProvider(AIProvider):
    """Offline deterministic provider used only for UI and policy validation."""

    provider_name = "mock"
    provider_mode = "mock"

    def generate(self, request: AssistantRequest, policy_notice: PolicyNotice) -> AssistantResponse:
        intent = request.intent or "auto"
        if policy_notice.decision == "deny" or intent in FORBIDDEN_INTENTS:
            return self._risk_response(request, policy_notice)
        if intent == "search_knowledge":
            return self._search_response(request, policy_notice)
        if intent == "summarize_document":
            return self._summary_response(request, policy_notice)
        if intent == "create_memory_candidate":
            return self._memory_response(request, policy_notice)
        if intent in {"create_checklist_draft", "suggest_category"}:
            return self._plan_response(request, policy_notice)
        return self._default_response(request, policy_notice)

    def _response(
        self,
        request: AssistantRequest,
        policy_notice: PolicyNotice,
        content: str,
        cards: list[AssistantCard] | None = None,
        citations: list[Citation] | None = None,
        suggested_actions: list[SuggestedAction] | None = None,
        memory_saved: bool = False,
    ) -> AssistantResponse:
        message = AssistantMessage(
            message_id=f"mock-{request.intent}-assistant",
            role="assistant",
            author="AI 助手",
            content=content,
            alignment="left",
            cards=list(cards or []),
        )
        return AssistantResponse(
            response_id=f"mock-{request.intent}-response",
            provider=self.provider_name,
            provider_mode=self.provider_mode,
            intent=request.intent,
            capability_id=request.capability_id,
            policy_notice=policy_notice,
            messages=[message],
            citations=list(citations or []),
            suggested_actions=list(suggested_actions or []),
            memory_saved=memory_saved,
            mutation_executed=False,
            network_accessed=False,
            model_dependency="none",
        )

    def _risk_response(self, request: AssistantRequest, policy_notice: PolicyNotice) -> AssistantResponse:
        card = AssistantCard(
            card_type="risk_notice",
            title="当前请求不能执行",
            body=(
                "v2.2.0 只提供模拟 AI 助手 UI skeleton。删除、归档、恢复、promote "
                "或任何 mutation 都不会执行。"
            ),
            items=[
                f"Policy: {policy_notice.decision}",
                policy_notice.reason,
                "没有写入 Markdown、SQLite、配置或任务队列。",
            ],
            metadata={"blocked": True, "intent": request.intent},
        )
        return self._response(
            request,
            policy_notice,
            "我不能执行这个请求；当前阶段只返回风险提示。",
            cards=[card],
        )

    def _search_response(self, request: AssistantRequest, policy_notice: PolicyNotice) -> AssistantResponse:
        citations = [
            Citation(
                citation_id="mock-search-1",
                title="正式规则：GUI 不得绕过 service layer",
                document_id="mock-rule-service-boundary",
                path="knowledge/09-ai-agent/rules/mock-service-boundary.md",
                layer="rules",
                status="active",
                source_type="internal_practice",
                confidence="high",
                review_required=False,
            ),
            Citation(
                citation_id="mock-search-2",
                title="正式清单：AI capability 必须先过 policy",
                document_id="mock-checklist-policy",
                path="knowledge/09-ai-agent/checklists/mock-policy-checklist.md",
                layer="checklists",
                status="active",
                source_type="internal_practice",
                confidence="medium",
                review_required=False,
            ),
        ]
        cards = [
            AssistantCard(
                card_type="search_result",
                title=citation.title,
                body="模拟搜索结果卡片。真实搜索仍必须通过 SearchService，当前 provider 不读取索引。",
                citations=[citation],
                metadata={"rank": index, "query": request.message},
            )
            for index, citation in enumerate(citations, start=1)
        ]
        return self._response(
            request,
            policy_notice,
            "这是模拟搜索结果，用于验证消息卡片形态。",
            cards=cards,
            citations=citations,
        )

    def _summary_response(self, request: AssistantRequest, policy_notice: PolicyNotice) -> AssistantResponse:
        citation = Citation(
            citation_id="mock-summary-1",
            title="当前文档（模拟）",
            document_id="mock-current-document",
            path="current-document://mock",
            layer="rules",
            status="active",
            source_type="mock_context",
            confidence="medium",
            review_required=False,
        )
        cards = [
            AssistantCard(
                card_type="document_summary",
                title="DocumentSummary mock",
                body="这是一段固定摘要：当前阶段只验证总结卡片，不读取 Markdown 正文。",
                items=["边界：不接真实模型", "边界：不发送云端", "边界：不保存结果"],
                citations=[citation],
            ),
            AssistantCard(
                card_type="citation",
                title=citation.title,
                body="模拟引用元数据；不是从知识库正文读取。",
                citations=[citation],
            ),
        ]
        return self._response(
            request,
            policy_notice,
            "已生成模拟摘要。",
            cards=cards,
            citations=[citation],
        )

    def _memory_response(self, request: AssistantRequest, policy_notice: PolicyNotice) -> AssistantResponse:
        candidate = AssistantCard(
            card_type="memory_candidate",
            title="MemoryCandidateCard mock",
            body="检测到“记住”请求，但 v2.2.0 不保存长期记忆。",
            items=[
                "候选内容仅留在当前响应中。",
                "没有写入 conversation store 或 knowledge card。",
                "未来保存必须经过用户确认。",
            ],
            metadata={"saved": False, "requires_confirmation": True},
        )
        confirmation = AssistantCard(
            card_type="confirmation",
            title="ConfirmationCard mock",
            body="这里仅展示未来确认卡片形态；本阶段不提供保存按钮。",
            items=["需要确认：是", "执行状态：未执行", "持久化：未发生"],
            metadata={"mock_only": True, "buttons_exposed": False},
        )
        return self._response(
            request,
            policy_notice,
            "我可以生成记忆候选卡片，但不会保存它。",
            cards=[candidate, confirmation],
            memory_saved=False,
        )

    def _plan_response(self, request: AssistantRequest, policy_notice: PolicyNotice) -> AssistantResponse:
        cards = [
            AssistantCard(
                card_type="plan",
                title="PlanCard mock",
                body="这是只读模拟计划，用于验证 UI；不代表已执行动作。",
                items=[
                    "检查 capability registry",
                    "展示 permission policy 结果",
                    "等待未来人工确认流程",
                ],
                metadata={"blocked": False, "would_modify": False},
            ),
            AssistantCard(
                card_type="task_progress",
                title="TaskProgressCard mock",
                body="没有创建 TaskQueue 任务。该卡片只展示未来进度形态。",
                items=["task_id: mock-task-preview", "status: not_created", "progress: 0%"],
                metadata={"task_created": False, "progress_percent": 0},
            ),
        ]
        return self._response(
            request,
            policy_notice,
            "这是模拟计划和任务进度卡片。",
            cards=cards,
        )

    def _default_response(self, request: AssistantRequest, policy_notice: PolicyNotice) -> AssistantResponse:
        card = AssistantCard(
            card_type="system_notice",
            title="模拟模式",
            body="当前 AI 助手不会访问网络、不会读取资料正文、不会调用真实模型。",
            items=[
                f"识别 intent: {request.intent}",
                f"Policy: {policy_notice.decision}",
                "Provider: MockAIProvider",
            ],
        )
        return self._response(
            request,
            policy_notice,
            "我现在处于模拟模式，可以展示搜索、总结、风险和记忆候选卡片。",
            cards=[card],
        )
