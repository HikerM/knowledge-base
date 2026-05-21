# AI Memory Design

本文定义 AI 助手记忆和会话记录设计。当前阶段只做设计，不实现 memory service，不保存真实长期记忆，不接真实 AI。

## 1. Principles

- 对话记录不等于长期记忆。
- 长期记忆必须用户确认后保存。
- 用户可以查看、删除、关闭记忆。
- 不得自动保存敏感信息。
- 记忆不得作为正式知识层。
- 记忆不得绕过 `rules` / `checklists` / `snippets` 的正式搜索边界。
- 记忆读写必须由未来 service 管理；AI 或 GUI 不得直接写文件。

## 2. Short-term Memory

短期记忆只存在于当前会话或当前 UI 状态中。

Allowed short-term state:

- 当前会话。
- 当前页面。
- 当前打开文档。
- 当前选中搜索结果。
- 最近几轮对话。
- 当前 plan。
- 当前任务。
- 当前 provider mode。
- 当前 permission decision。
- 当前 context preview。

短期记忆规则：

- 可以用于当前对话连贯性。
- 不自动持久化为长期记忆。
- 会话结束后可以进入 conversation store，但仍不等于长期偏好。
- 不得被当作正式项目规则。

## 3. Long-term Memory

长期记忆只保存用户确认的偏好和工作方式。

Allowed long-term memory categories:

- 用户确认保存的偏好。
- 常用输出格式。
- 工作流程。
- 个人规则。
- 长期目标。

Forbidden memory:

- 未经用户确认的个人信息。
- 密钥、凭据、token 或 private key。
- 客户隐私数据。
- 未审核 raw 原文。
- quarantine、rejected 或敏感资料摘要。
- AI 自己推断出的偏好。

长期记忆保存流程：

```text
AI suggests memory candidate
  ↓
MemoryCandidateCard
  ↓
User confirms / edits / rejects
  ↓
Future AIMemoryService saves scoped memory
  ↓
Memory appears in user-viewable memory list
```

## 4. Memory Candidate

Memory candidate is not saved memory.

Suggested shape:

```json
{
  "candidate_id": "string",
  "conversation_id": "string",
  "workspace_id": "string",
  "type": "preference|format|workflow|personal_rule|long_term_goal",
  "proposed_text": "string",
  "source_message_ids": ["string"],
  "sensitivity": "low|medium|high",
  "requires_confirmation": true,
  "status": "pending|accepted|rejected|expired"
}
```

Rules:

- Candidate defaults to `pending`.
- Candidate must be shown as `MemoryCandidateCard`.
- Accepted candidate can be saved only through future memory service.
- Rejected candidate must not be resurfaced repeatedly without new evidence.

## 5. Conversation Store

Conversation store is runtime/user interaction history, not formal knowledge.

Suggested record:

```json
{
  "conversation_id": "string",
  "created_at": "string",
  "updated_at": "string",
  "workspace_id": "string",
  "messages": [],
  "summary": "string",
  "citations": [],
  "memory_candidates": [],
  "tasks": [],
  "metadata": {
    "provider_kind": "mock|local|cloud|none",
    "policy_version": "string",
    "app_version": "string"
  }
}
```

Storage boundary:

- Conversation store must be owned by a future service.
- It must not live under `knowledge/`.
- It must not be indexed as formal knowledge.
- It must not be used to rebuild `rules`, `checklists` or `snippets`.
- User should be able to clear conversation history without deleting knowledge.

## 6. Message Types

Allowed message types:

- `user_text`
- `assistant_text`
- `system_notice`
- `citation_list`
- `search_result_cards`
- `document_summary`
- `plan_card`
- `confirmation_card`
- `task_progress_card`
- `error_card`
- `memory_candidate_card`
- `privacy_notice_card`

Message shape:

```json
{
  "message_id": "string",
  "type": "assistant_text",
  "created_at": "string",
  "author": "user|assistant|system",
  "content": {},
  "citations": [],
  "policy_decision_id": "string|null",
  "task_id": "string|null",
  "metadata": {}
}
```

## 7. Citations In Conversation

Conversation-level citations must preserve:

- citation id.
- document id.
- title.
- layer.
- status.
- source type.
- confidence.
- chunk id or result id.
- whether the source was confirmed formal knowledge.

If a message uses unconfirmed context, the message must include a warning in metadata and visible UI.

## 8. User Controls

Future UI must support:

- View saved long-term memory.
- Search saved memory by type.
- Delete one memory item.
- Disable memory globally.
- Disable memory for current workspace.
- Reject pending memory candidate.
- Export or clear conversation history if implemented.

Deleting memory must not delete Markdown knowledge. Clearing conversation history must not delete long-term memory unless explicitly selected.

## 9. Privacy And Retention

Recommended defaults:

- Short-term memory: current session.
- Conversation history: local-only, retention configurable.
- Memory candidates: expire if not confirmed.
- Long-term memory: local-only unless user explicitly enables sync later.
- Cloud provider never receives long-term memory without context preview.

No automatic memory migration into knowledge cards is allowed.
