# AI Memory Privacy And Retention Policy

本文定义 v2.4.0 AI 助手 conversation 和 memory 的隐私、保留周期、安全和备份边界。当前阶段只做设计文档和策略草案，不实现真实持久化，不保存真实长期记忆，不实现 ConversationStore 写入，不接真实 AI，不接 OpenAI、本地模型或 ModelScope，不下载模型，不做 RSS/vector，不执行 mutation，不修改 `knowledge/**/*.md`，不修改 SQLite schema，也不改变 `search` / `index` / `audit` 行为。

## 1. Privacy Principles

- 用户必须能查看 AI 记住了什么。
- AI 不得自动保存长期记忆。
- AI 不得把 memory 当 formal knowledge。
- AI 不得用 memory 绕过 `SearchService` formal 层边界。
- AI 不得向云端发送 memory，除非 context preview 明确列出 memory 内容并获得用户确认。
- Secret-scan / sensitive 标记应阻止云端发送。
- 对话记录不等于长期记忆。
- 清空对话历史不清空长期记忆，除非用户明确选择。
- Memory 和 conversation 不得写入 `knowledge/`。
- Memory 和 conversation 不得放入 `.kb/`。
- Memory 和 conversation 不得放入安装目录。

## 2. Retention Defaults

Recommended defaults:

| Data | Default retention | Configurable | Notes |
| --- | --- | --- | --- |
| Short-term memory | Current session | limited | Used only for continuity |
| Conversation history | Local retention, configurable | yes | Workspace-bound by default |
| Conversation summary | Same as conversation | yes | Not long-term memory |
| Memory candidates | Expire, recommended 30 days | yes | Pending candidates are not saved memory |
| Rejected candidates | Suppression record, recommended 180 days | yes | Prevent repeated prompts |
| Long-term memory | Until user deletes | yes for disable, not auto-expire by default | Must be user-confirmed |
| Privacy-mode conversation | No persistent write | yes | May keep in RAM for current session |

Rules:

- Conversation retention 默认本地保留，可配置。
- Memory candidates 可过期。
- Long-term memory 保留直到用户删除。
- Cloud provider 不得收到 memory，除非 context preview 明确确认。
- 清空对话历史不清空长期记忆。
- Retention must be enforced by future service layer, not UI-only logic.

## 3. Workspace Binding

Recommended future storage boundary:

```text
workspace_root/ai/conversations/
workspace_root/ai/memory/
workspace_root/ai/drafts/
```

Workspace rules:

- AI data is bound to one workspace by default.
- Workspace switching must not scan all workspace AI data.
- Startup must not scan `ai/conversations/` or `ai/memory/`.
- Startup may only read lightweight settings or metadata needed to know whether AI data exists.
- AI data must not be stored in software installation directory.
- AI data must not be stored in `.kb/`, because `.kb/` is runtime/cache.
- AI data must not be stored in `knowledge/`, because it is not formal knowledge.

## 4. Backup Policy

Privacy-first backup defaults:

- Default backup excludes `workspace_root/ai/conversations/`.
- Default backup excludes `workspace_root/ai/memory/`.
- Default backup excludes `workspace_root/ai/drafts/`.
- User can explicitly enable `include_ai_conversations`.
- User can explicitly enable `include_ai_memory`.
- Pending candidates should remain excluded unless the user explicitly chooses to include drafts.
- Backup manifest must record `include_ai_conversations`, `include_ai_memory` and `include_ai_drafts`.
- Backup UI must warn that AI memory and conversation history may contain personal preferences, private project context or sensitive text.

Rationale:

- Knowledge backup protects Markdown source data.
- AI conversation and memory can contain private interaction history.
- Users need explicit control over whether this data leaves the live workspace.

## 5. Export Policy

Future export controls:

- Export one conversation.
- Export all conversations in current workspace.
- Export long-term memory list.
- Export must include citations, policy decisions and context preview ids where available.
- Export should redact secrets and sensitive markers by default.
- Export should include a visible warning that exported conversation and memory are not formal knowledge.
- Export should not include `.kb/index.sqlite`.
- Export should not include task logs unless a separate task-log export is explicitly selected.

## 6. Delete And Clear Policy

Required user controls:

- 查看对话历史。
- 删除单个会话。
- 清空所有会话。
- 查看长期记忆。
- 删除单条记忆。
- 禁用长期记忆。
- 拒绝 memory candidate。
- 清空 pending / expired candidates.
- 导出对话，可选后续。
- 隐私模式。

Deletion rules:

- Delete one conversation removes that conversation record only.
- Clear all conversations removes conversation history in current workspace only.
- Clear conversations does not delete saved long-term memory unless the user explicitly selects that option.
- Delete one memory removes or tombstones that memory and prevents future use.
- Disable memory preserves user-visible records but prevents context use.
- Reject candidate marks it rejected and should suppress repeated prompts.
- Expired candidate cannot be saved without re-confirmation.

## 7. Cloud Provider Policy

Cloud provider rules:

- Memory is denied by default for cloud context.
- Conversation history is denied by default for cloud context unless the user explicitly selects it.
- Cloud context preview must show every memory item that would be sent.
- Cloud context preview must show selected conversation messages or summaries that would be sent.
- User confirmation must bind to a preview hash or equivalent immutable snapshot.
- If context changes, confirmation expires.
- Secret-scan / sensitive flags block cloud send.
- Quarantine, rejected and unconfirmed sources are denied by default.
- Raw, distilled, research and `review_required=true` sources require explicit warning and still cannot be treated as formal rules.

## 8. Sensitive Data Rules

Never save as memory:

- API keys.
- Passwords.
- Tokens.
- Private keys.
- Customer privacy data.
- Sensitive personal information inferred by AI.
- Quarantine or rejected content summaries.
- Sensitive document summaries.
- Unreviewed raw source text.

Sensitive handling:

- MemoryCandidate with secret-like content must be blocked.
- `sensitivity=blocked` candidates cannot be accepted.
- Secret-scan or sensitive marker should prevent cloud send and backup inclusion unless a future explicit high-risk override exists.
- Error cards should explain that sensitive data was excluded without echoing the sensitive text.

## 9. Security Policy

- AI 不得自动保存长期记忆。
- AI 不得把 memory 当 formal knowledge。
- AI 不得用 memory 绕过 `SearchService` formal 层边界。
- AI 不得向云端发送 memory，除非用户确认。
- Secret-scan / sensitive 标记应阻止云端发送。
- 用户必须能查看 AI 记住了什么。
- Memory and conversation storage must be controlled by service/core API.
- GUI View must not write memory files.
- AI provider must not write memory files.
- Memory cannot authorize or execute mutations.
- Memory cannot be used as approval, snapshot, plan hash or reviewer identity.

## 10. Workspace Deletion Future Policy

Deleting a workspace is future work and must be plan-first. The future policy must specify:

- Whether `workspace_root/ai/` will be deleted with the workspace.
- Whether backups containing AI data should be listed before deletion.
- Whether exported AI data should be mentioned.
- Whether AI data can be preserved separately.
- Whether deletion has a local snapshot.
- How the UI distinguishes clearing workspace AI data from deleting formal knowledge.

Default recommendation:

- If a workspace folder is deleted, AI data inside that folder is deleted with it.
- If backups or exports exist outside the workspace, they are not deleted automatically.
- Future delete plan must list AI data impact explicitly.

## 11. Implementation Gates

Before any persistent memory implementation, the project must have:

- Deletion policy.
- Retention policy.
- Backup inclusion policy.
- Export policy.
- Privacy mode behavior.
- Secret/sensitive blocking behavior.
- User-visible memory list.
- User-visible conversation clear controls.
- Service-layer storage boundary.
- Tests proving memory does not enter `knowledge/`, `.kb/`, SQLite schema, formal search or startup scan.

## 12. Acceptance Criteria

- Retention policy defines local configurable conversation retention, candidate expiry and long-term memory until user deletion.
- Cloud provider cannot receive memory without context preview confirmation.
- Clearing conversations does not clear long-term memory by default.
- User controls cover view/delete conversations, clear conversations, view/delete/disable memory, reject candidates, export and privacy mode.
- Security policy states memory cannot be formal knowledge, cannot bypass SearchService and cannot authorize mutation.
- Backup policy explains explicit inclusion and why AI data is not default knowledge backup content.
