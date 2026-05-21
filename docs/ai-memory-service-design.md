# AI MemoryService Design

本文定义 v2.4.0 AI 助手 MemoryService 设计。当前阶段只做设计，不实现真实持久化，不保存真实长期记忆，不实现 ConversationStore 写入，不接真实 AI，不接 OpenAI、本地模型或 ModelScope，不下载模型，不做 RSS/vector，不执行 mutation，不修改 `knowledge/**/*.md`，不修改 SQLite schema，也不改变 `search` / `index` / `audit` 行为。

MemoryService 的目标是让未来 AI 助手在用户明确确认后保存少量有用偏好，同时保证记忆可查看、可删除、可禁用、可导出、可排除备份，并且不能污染 formal knowledge。

## 1. Memory Model Boundary

Memory has three different scopes:

| Scope | Meaning | Persistence | Formal knowledge |
| --- | --- | --- | --- |
| Short-term memory | 当前会话和 UI 状态 | current session / optional conversation summary | no |
| MemoryCandidate | 待用户确认的候选记忆 | draft / pending only | no |
| Long-term memory | 用户确认保存的偏好或工作方式 | future MemoryService storage | no |

Core rules:

- AI 不得自动保存长期记忆。
- 长期记忆必须用户确认。
- MemoryCandidate 不是 saved memory。
- Memory 不得写入 `knowledge/`。
- Memory 不得放入 `.kb/`。
- Memory 不得作为 formal knowledge。
- Memory 不得绕过 `SearchService` 的 formal 层边界。
- Memory 不得用于 promote、archive、delete、restore 或 mutation 决策。
- 用户必须能查看 AI 记住了什么。

## 2. Short-term Memory

Short-term memory is the active state used for conversation continuity:

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

- 短期记忆只用于对话连贯性。
- 短期记忆不自动转为长期记忆。
- 短期记忆不作为正式知识。
- 短期记忆不得被 SearchService 当作 `rules`、`checklists` 或 `snippets`。
- 退出会话后可以形成会话摘要，但仍不是长期记忆。
- 会话摘要如果用于后续对话，只能作为 conversation context，不得作为项目规则依据。

## 3. Long-term Memory Types

Allowed saved memory types:

- `preference`: 用户确认的偏好，例如“默认用中文回复”。
- `format`: 用户确认的输出格式，例如“验收结果按命令列出”。
- `workflow`: 用户确认的常用流程，例如“文档变更后先跑 audit 和 secret-scan”。
- `personal_rule`: 用户确认的个人工作规则，例如“提交前先展示风险摘要”。
- `long_term_goal`: 用户确认的长期目标，例如“优先把 GUI 保持 read-only service boundary”。

Forbidden memory:

- 未经用户确认保存个人信息。
- 保存密钥、凭据、token、private key。
- 保存客户隐私数据。
- 保存未审核 raw 原文。
- 保存 quarantine / rejected / sensitive 摘要。
- 保存 AI 自己推断出的敏感偏好。
- 保存来自 cloud provider 的推断画像。
- 保存绕过 service layer 获得的上下文。

## 4. MemoryCandidate Schema

MemoryCandidate is a user-review draft. It is not saved memory.

```json
{
  "candidate_id": "memcand_01H...",
  "conversation_id": "conv_01H...",
  "workspace_id": "workspace_01H...",
  "type": "preference|format|workflow|personal_rule|long_term_goal",
  "proposed_text": "用户希望验收结果按命令列出。",
  "source_message_ids": ["msg_1", "msg_2"],
  "sensitivity": "low|medium|high|blocked",
  "requires_confirmation": true,
  "status": "pending|accepted|rejected|expired",
  "metadata": {
    "created_at": "2026-05-21T10:05:00+08:00",
    "expires_at": "2026-06-20T10:05:00+08:00",
    "rejection_fingerprint": "hash-of-normalized-proposal",
    "blocked_reason": null
  }
}
```

Required fields:

- `candidate_id`
- `conversation_id`
- `workspace_id`
- `type`
- `proposed_text`
- `source_message_ids`
- `sensitivity`
- `requires_confirmation=true`
- `status=pending|accepted|rejected|expired`

Rules:

- Candidate must be shown as `MemoryCandidateCard`.
- Candidate cannot be silently accepted.
- Candidate cannot be saved without explicit user confirmation.
- User can edit proposed text before accepting.
- Rejected candidate should not repeatedly bother the user; store a rejection fingerprint or equivalent suppression record.
- Expired candidate should not be saved without regenerating and re-confirming it.
- High sensitivity candidate requires stronger warning; blocked sensitivity cannot be accepted.

## 5. Saved Memory Schema

Future saved memory should be small, explicit and user-visible:

```json
{
  "memory_id": "mem_01H...",
  "workspace_id": "workspace_01H...",
  "type": "preference",
  "text": "用户希望默认使用中文回复。",
  "created_at": "2026-05-21T10:06:00+08:00",
  "updated_at": "2026-05-21T10:06:00+08:00",
  "source": {
    "candidate_id": "memcand_01H...",
    "conversation_id": "conv_01H...",
    "source_message_ids": ["msg_1"]
  },
  "sensitivity": "low",
  "status": "active|disabled|deleted",
  "metadata": {
    "confirmed_by": "user",
    "confirmation_id": "confirm_01H...",
    "retention_policy_id": "until_user_deletes",
    "cloud_send_allowed": false
  }
}
```

Rules:

- `status=deleted` should be a local audit state or tombstone only if needed; the user-facing behavior is deletion.
- Disabled memory stays visible in memory settings but is not used for context.
- Active memory can be included in local context only through future MemoryService.
- Cloud provider cannot receive memory unless context preview explicitly includes it and the user confirms.

## 6. MemoryService Responsibilities

Future MemoryService should own:

- Create memory candidate.
- Render candidate payload for `MemoryCandidateCard`.
- Accept candidate after user confirmation.
- Reject candidate and suppress repeated prompts.
- Expire stale candidates.
- List saved memory.
- Delete one memory.
- Disable / enable one memory.
- Disable all long-term memory for a workspace.
- Clear all memory after explicit confirmation.
- Export memory after explicit confirmation.
- Enforce retention, sensitivity and cloud context policy.

MemoryService must not:

- Read or write `knowledge/**/*.md`.
- Read or write `.kb/index.sqlite`.
- Query SQLite directly to bypass services.
- Read `.kb/tasks/`.
- Save secrets or customer data.
- Promote memory to rules/checklists/snippets.
- Execute mutation.

## 7. Storage Boundary

推荐未来位置：

```text
workspace_root/ai/memory/
workspace_root/ai/drafts/
```

Suggested layout:

```text
workspace_root/
  ai/
    memory/
      memories.jsonl
      disabled.json
      rejection-suppressions.jsonl
    drafts/
      memory-candidates.jsonl
```

This is a design suggestion only. v2.4.0 does not create these paths.

Storage rules:

- Memory is workspace-bound by default.
- Memory does not live under `.kb/`, because `.kb/` is runtime/cache and can be deleted.
- Memory does not live under `knowledge/`, because it is not formal knowledge.
- Memory does not live in the installation directory.
- Memory storage must be owned by future service/core API, not GUI widgets or AI providers.
- Sensitive memory records should support local encryption or OS credential storage as a future hardening option, but this is not part of v2.4.0.

## 8. Backup, Export And Clear

Backup:

- Long-term memory should be excluded from default backup until the user explicitly enables `include_ai_memory`.
- If included, backup manifest must mark `include_ai_memory=true`.
- Pending candidates should be excluded from default backup.
- Rejection suppressions can be excluded or included only as privacy settings, not knowledge.

Export:

- User can export saved memory in a future flow.
- Export must show type, text, created_at, source conversation id and sensitivity.
- Export should redact sensitive entries by default and require explicit inclusion for higher sensitivity.

Clear:

- Delete one memory.
- Clear all saved memory in current workspace.
- Disable memory without deleting it.
- Clear pending candidates.
- Clear rejection suppressions only after user confirmation.
- Clearing conversation history does not clear saved memory unless explicitly selected.

## 9. User Controls

Future UI must support:

- 查看长期记忆。
- 删除单条记忆。
- 禁用单条记忆。
- 禁用长期记忆。
- 拒绝 memory candidate。
- 编辑并确认 memory candidate。
- 查看候选来源消息。
- 查看 sensitivity 和 cloud-send 状态。
- 隐私模式：当前会话不创建候选、不保存 conversation history。
- 导出记忆，可作为后续功能。

## 10. Context Use Rules

Memory can help personalize answers, but it cannot replace knowledge search:

- Ask My Knowledge still uses `SearchService.search` for formal `rules` / `checklists` / `snippets`.
- Memory cannot make raw/distilled/research formal.
- Memory cannot decide project rules without citations.
- Memory cannot authorize mutation.
- Memory cannot satisfy required citations for knowledge-backed answers.
- Memory can only appear as a separate context source with explicit metadata.

## 11. Acceptance Criteria

- Long-term memory types are limited to `preference`, `format`, `workflow`, `personal_rule` and `long_term_goal`.
- Forbidden memory categories include secrets, credentials, tokens, customer privacy data, unreviewed raw content, quarantine/rejected/sensitive summaries and sensitive inferred preferences.
- MemoryCandidate schema includes all required fields and states.
- Candidate is not saved memory and must be confirmed via `MemoryCandidateCard`.
- Storage boundary recommends `workspace_root/ai/memory/` and `workspace_root/ai/drafts/`, not `.kb/`, not `knowledge/`, not installation directory.
- User controls include view, delete, disable, reject candidate, export and privacy mode.
- The design remains implementation-free for v2.4.0.
