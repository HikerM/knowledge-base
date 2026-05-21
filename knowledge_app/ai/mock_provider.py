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
                "当前版本只提供模拟 AI 助手 flow。删除、归档、恢复、promote "
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
        service_error = request.context.get("service_error")
        if service_error:
            return self._error_response(request, policy_notice, service_error)
        if request.context.get("empty_query"):
            card = AssistantCard(
                card_type="system_notice",
                title="请输入问题",
                body="问我的资料需要一个查询词；空输入不会访问搜索服务。",
                metadata={"empty_query": True},
            )
            return self._response(request, policy_notice, "请输入要搜索的问题。", cards=[card])

        rows = list(request.context.get("search_results") or [])
        if not rows:
            card = AssistantCard(
                card_type="system_notice",
                title="没有匹配的正式知识",
                body="我没有在 rules / checklists / snippets 的正式索引中找到匹配结果。不会自动 index，也不会读取 Markdown 正文。",
                items=[f"查询：{request.context.get('search_query') or request.message}"],
                metadata={"empty_results": True},
            )
            return self._response(request, policy_notice, "没有找到匹配的正式知识。", cards=[card])

        citations = [_citation_from_search(row) for row in rows]
        cards = [
            AssistantCard(
                card_type="search_result",
                title=citation.title,
                body=rows[index - 1].get("snippet") or "该结果没有摘要。",
                citations=[citation],
                metadata={"rank": index, "query": request.context.get("search_query") or request.message},
            )
            for index, citation in enumerate(citations, start=1)
        ]
        cards.append(
            AssistantCard(
                card_type="citation",
                title="引用来源",
                body="以下引用来自 SearchService 返回的正式层 metadata；MockAIProvider 没有读取索引或正文。",
                citations=citations,
                metadata={"citation_count": len(citations)},
            )
        )
        return self._response(
            request,
            policy_notice,
            "根据正式知识搜索结果，我生成了这条模拟回答。请以 citation cards 为准。",
            cards=cards,
            citations=citations,
        )

    def _summary_response(self, request: AssistantRequest, policy_notice: PolicyNotice) -> AssistantResponse:
        service_error = request.context.get("service_error")
        if service_error:
            return self._error_response(request, policy_notice, service_error)
        if request.context.get("missing_current_document"):
            card = AssistantCard(
                card_type="system_notice",
                title="请先打开一篇文档",
                body="总结当前文档需要明确的 current_document_id，AI 助手不会猜测或批量读取 Markdown。",
                metadata={"missing_current_document": True},
            )
            return self._response(request, policy_notice, "请先打开一篇文档。", cards=[card])

        document = dict(request.context.get("document") or {})
        citation = _citation_from_document(document)
        body = str(document.get("body") or "")
        summary = _deterministic_summary(body)
        cards = [
            AssistantCard(
                card_type="document_summary",
                title=f"DocumentSummary mock: {citation.title}",
                body=summary,
                items=["通过 DocumentService.open_document 打开单篇文档", "不接真实模型", "不保存总结"],
                citations=[citation],
            ),
            AssistantCard(
                card_type="citation",
                title=citation.title,
                body="引用指向当前明确打开的单篇文档。",
                citations=[citation],
            ),
        ]
        return self._response(
            request,
            policy_notice,
            "已生成当前文档的模拟摘要。",
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

    def _error_response(self, request: AssistantRequest, policy_notice: PolicyNotice, service_error: object) -> AssistantResponse:
        payload = dict(service_error or {}) if isinstance(service_error, dict) else {"errors": [str(service_error)]}
        service = str(payload.get("service") or "AssistantService")
        errors = [str(item) for item in payload.get("errors") or ["service unavailable"]]
        title = "索引不可用" if payload.get("index_missing") else "服务不可用"
        card = AssistantCard(
            card_type="error",
            title=title,
            body="; ".join(errors),
            items=[f"service: {service}", "没有自动 index，没有执行 mutation。"],
            metadata={"service": service, "index_missing": bool(payload.get("index_missing"))},
        )
        return self._response(request, policy_notice, "当前无法完成这个 mock flow。", cards=[card])


def _citation_from_search(row: dict) -> Citation:
    return Citation(
        citation_id=f"search-{row.get('rank') or 0}",
        title=str(row.get("title") or row.get("path") or "未命名文档"),
        document_id=str(row.get("document_id") or ""),
        path=str(row.get("path") or ""),
        layer=str(row.get("layer") or ""),
        status=str(row.get("status") or ""),
        source_type=str(row.get("source_type") or ""),
        confidence=str(row.get("confidence") or ""),
        review_required=bool(row.get("review_required", False)),
        source_url=str(row.get("source_url") or ""),
    )


def _citation_from_document(document: dict) -> Citation:
    return Citation(
        citation_id="current-document",
        title=str(document.get("title") or document.get("path") or "当前文档"),
        document_id=str(document.get("document_id") or ""),
        path=str(document.get("path") or ""),
        layer=str(document.get("layer") or ""),
        status=str(document.get("status") or ""),
        source_type=str(document.get("source_type") or ""),
        confidence=str(document.get("confidence") or ""),
        review_required=bool(document.get("review_required", False)),
        source_url=str(document.get("source_url") or ""),
    )


def _deterministic_summary(body: str) -> str:
    text = " ".join(body.strip().split())
    if not text:
        return "该文档没有可总结的正文。"
    return f"模拟摘要：{text[:220]}{'...' if len(text) > 220 else ''}"
