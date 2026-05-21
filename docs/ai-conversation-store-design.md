# AI ConversationStore Design

本文定义 v2.4.0 AI 助手 ConversationStore 设计。当前阶段只做设计文档，不实现真实持久化，不写入 conversation store，不接真实 AI，不接 OpenAI、本地模型或 ModelScope，不下载模型，不做 RSS/vector，不执行 mutation，不修改 `knowledge/**/*.md`，不修改 SQLite schema，也不改变 `search` / `index` / `audit` 行为。

ConversationStore 的目标是记录用户和 AI 助手的交互历史、引用、计划、确认、任务状态和策略判定，方便用户回看、审计和删除。它不是长期记忆，也不是正式知识层。

## 1. Core Boundary

- 对话记录不等于长期记忆。
- 对话记录不进入 formal knowledge。
- 对话记录不写入 `knowledge/`。
- 对话记录不写入 `.kb/`，因为 `.kb/` 是 runtime/cache。
- 对话记录不放安装目录。
- 对话记录不得被索引为 `rules`、`checklists` 或 `snippets`。
- 用户可以清空对话记录。
- 清空对话记录不删除长期记忆，除非用户明确选择同时删除长期记忆。
- ConversationStore 只能由未来 service 管理；GUI、AI provider、前端 bridge 或 CLI wrapper 不得直接写存储文件。

## 2. Conversation Record Schema

建议记录形态：

```json
{
  "conversation_id": "conv_01H...",
  "workspace_id": "workspace_01H...",
  "created_at": "2026-05-21T10:00:00+08:00",
  "updated_at": "2026-05-21T10:15:00+08:00",
  "title": "Ask My Knowledge: service boundary",
  "messages": [],
  "citations": [],
  "tasks": [],
  "policy_decisions": [],
  "provider_kind": "mock|local|cloud|none",
  "summary": {
    "text": "Short non-authoritative conversation summary.",
    "created_at": "2026-05-21T10:15:00+08:00",
    "source_message_ids": ["msg_1", "msg_2"],
    "not_long_term_memory": true
  },
  "metadata": {
    "schema_version": "0.1",
    "app_version": "2.4.0-design",
    "policy_version": "ai-memory-retention-0.1",
    "retention_policy_id": "default_local",
    "privacy_mode": false,
    "memory_disabled": false
  }
}
```

Required fields:

- `conversation_id`: stable identity for one conversation.
- `workspace_id`: workspace scope; conversation history is workspace-bound by default.
- `created_at`: ISO timestamp.
- `updated_at`: ISO timestamp.
- `title`: user-editable display title or generated local summary title.
- `messages`: ordered message list.
- `citations`: conversation-level citation index.
- `tasks`: task references surfaced during the conversation.
- `policy_decisions`: permission and context decisions made during the conversation.
- `provider_kind`: `mock`, `local`, `cloud` or `none`.
- `summary`: optional conversation summary; still not long-term memory.
- `metadata`: schema, version, retention and UI metadata.

## 3. Message Schema

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

Each message must support:

```json
{
  "message_id": "msg_01H...",
  "role": "user|assistant|system|tool",
  "type": "assistant_text",
  "created_at": "2026-05-21T10:01:00+08:00",
  "content": {
    "text": "Response text or structured card payload."
  },
  "citations": ["citation_1"],
  "policy_decision_id": "policy_1",
  "task_id": "task_1",
  "metadata": {
    "provider_kind": "mock",
    "context_preview_id": null,
    "unreviewed_warning": null,
    "not_formal_knowledge": true
  }
}
```

Rules:

- `role=user` can only represent user-authored input or explicit user confirmation decisions.
- `role=assistant` can represent AI output, but it cannot imply saved memory or executed mutation.
- `role=system` is for local notices, policy warnings and privacy notices.
- `role=tool` is reserved for future service-returned cards and must contain only structured service output.
- `content` should store the minimal payload needed to render the message and audit the decision; it should not duplicate full Markdown documents unless explicitly required by a future export flow.
- `citations` must reference citation records with layer/status/source_type/confidence metadata.
- `policy_decision_id` links to the permission decision that allowed, denied or required confirmation.
- `task_id` links to TaskQueue only through service-visible task ids; ConversationStore must not read `.kb/tasks/`.

## 4. Citation Records

Conversation citations preserve why an answer or card was shown:

```json
{
  "citation_id": "citation_1",
  "document_id": "12",
  "title": "Service Boundary Rule",
  "layer": "rules",
  "status": "active",
  "source_type": "internal_practice",
  "confidence": "high",
  "review_required": false,
  "chunk_id": "chunk_12_01",
  "warning": null
}
```

If a citation points to `raw`, `distilled`, `research`, archived content, or `review_required=true`, the UI must show: `未经审核，不能作为正式项目规则`. Quarantine and rejected sources are denied by default and should only appear inside a blocked/denied explanation.

## 5. Task References

Conversation task entries are references, not task storage:

```json
{
  "task_id": "task_01H...",
  "capability_id": "workspace_status",
  "status_at_last_render": "running|succeeded|failed|cancelled",
  "progress_percent_at_last_render": 60,
  "message_id": "msg_task_card",
  "metadata": {
    "read_via_service": true
  }
}
```

Rules:

- Task progress cards read through `TaskQueueService`.
- ConversationStore does not store task logs.
- ConversationStore does not read `.kb/tasks/` directly.
- ConversationStore cannot create destructive tasks.

## 6. Policy Decision Records

Every AI control-plane decision should be auditable:

```json
{
  "policy_decision_id": "policy_1",
  "created_at": "2026-05-21T10:02:00+08:00",
  "capability_id": "summarize_current_document",
  "level": "L1",
  "decision": "allow|confirm|context_preview_required|deny",
  "reason": "current document summary allowed for local mock provider",
  "provider_kind": "mock",
  "context_preview_id": null,
  "confirmation_id": null,
  "metadata": {
    "cloud_send_allowed": false,
    "mutation_allowed": false
  }
}
```

Policy records should preserve decisions without copying sensitive bodies. They should reference ids, hashes, selected source metadata and confirmation ids.

## 7. Short-term Conversation State

Short-term memory used by ConversationStore includes:

- 当前会话。
- 当前页面。
- 当前打开文档。
- 当前搜索结果。
- 最近几轮对话。
- 当前 plan。
- 当前任务。
- 当前 provider mode。
- 当前 context preview。

Rules:

- 短期记忆用于对话连贯性。
- 短期记忆不自动转为长期记忆。
- 短期记忆不作为正式知识。
- 退出会话后可以形成会话摘要，但摘要仍不是长期记忆。
- 会话摘要不得被写入 `knowledge/`，不得进入 formal search。

## 8. Storage Boundary

推荐未来位置：

```text
workspace_root/ai/conversations/
workspace_root/ai/drafts/
```

Rationale:

- 放在 workspace 下，便于 workspace-scoped privacy、export、backup 和删除策略。
- 不放 `.kb/`，因为 `.kb/` 是 runtime/cache，可删除重建。
- 不放 `knowledge/`，因为 conversation history 不是正式知识卡片。
- 不放安装目录，避免卸载或重装影响用户数据，也避免多 workspace 混杂。

Conversation drafts can hold unsaved plan previews, export staging data or pending UI state. Drafts are not memory and can expire faster than conversations.

## 9. Backup, Export And Clear

Backup design:

- Conversation history should be excluded from default knowledge backup unless the user explicitly enables `include_ai_conversations`.
- Backup manifest must clearly show whether `ai/conversations/` was included.
- Conversation backup must never include `.kb/index.sqlite` as a source of truth.
- Memory candidates should not be backed up by default if they are pending or expired.

Export design:

- User can export one conversation or selected conversations in a future flow.
- Export must include citations, policy decisions and privacy warnings.
- Export should redact secrets and sensitive markers by default.

Clear design:

- Delete one conversation.
- Clear all conversations in current workspace.
- Clear conversations older than retention window.
- Clearing conversations does not delete long-term memory unless the user explicitly selects that action.

## 10. User Controls

Future UI must provide:

- 查看对话历史。
- 搜索或过滤对话历史。
- 删除单个会话。
- 清空所有会话。
- 设置对话保留周期。
- 导出对话，可作为后续功能。
- 启用隐私模式，使当前会话不写入持久 ConversationStore。
- 查看与某条回答相关的 citations、context preview 和 policy decision。

## 11. Acceptance Criteria

- Conversation schema includes `conversation_id`, `workspace_id`, timestamps, title, messages, citations, tasks, policy decisions, provider kind, summary and metadata.
- Message schema includes `message_id`, role, type, timestamp, content, citations, policy decision id, task id and metadata.
- The design states that conversation history is not long-term memory, not formal knowledge and not stored under `knowledge/` or `.kb/`.
- The design states that clearing conversation history does not delete long-term memory by default.
- The design includes storage, backup, export, clear and user-control boundaries.
