# AI Backup, Export And Clear Policy

本文定义 v2.5.0 AI conversation / memory / drafts 的 backup、export、delete、clear、disable、privacy mode 和 audit gate 策略。当前阶段只做设计文档，不实现备份选项，不创建 `workspace/ai`，不创建 conversation 或 memory 文件，不保存长期记忆，不接真实 AI，不做 RSS/vector，不执行 mutation，不修改 `knowledge/**/*.md`，不修改 SQLite schema，也不改变 `search` / `index` / `audit` 行为。

AI data 可能包含私人偏好、项目上下文、对话历史和未发送云端前的 context preview。因此它不能默认进入知识库备份，也不能默认进入 formal search。

## 1. Data Classes

AI persistence data classes:

| Data | Future path | Source of truth | Default backup |
| --- | --- | --- | --- |
| Conversations | `workspace_root/ai/conversations/` | JSONL / JSON records | false |
| Saved memory | `workspace_root/ai/memory/` | JSONL / JSON records | false |
| Memory candidates | `workspace_root/ai/drafts/` | JSONL / JSON records | false |
| Conversation drafts | `workspace_root/ai/drafts/` | JSONL / JSON records | false |
| AI derived indexes | `workspace_root/ai/indexes/` | rebuildable derived index | false |

Rules:

- AI data does not live under `knowledge/`.
- AI data does not live under `.kb/`.
- AI data does not live in the installation directory.
- AI data is workspace-scoped.
- AI data is not formal knowledge.
- AI data is not indexed by formal `SearchService`.

## 2. Backup Policy

Backup flags:

- `include_ai_conversations=false` by default.
- `include_ai_memory=false` by default.
- `include_ai_drafts=false` by default.
- `include_ai_indexes=false` by default.

Default backup remains focused on:

- `knowledge/`
- `config/`
- `templates/`
- `reports/`
- `docs/`
- `README.md`
- `AGENTS.md`

AI data inclusion requires explicit user selection because it may contain private conversation history and personal preferences.

## 3. Backup Manifest

Backup manifest must include explicit flags:

```json
{
  "schema_version": "backup-manifest-vNext",
  "include_index": false,
  "include_ai_conversations": false,
  "include_ai_memory": false,
  "include_ai_drafts": false,
  "include_ai_indexes": false,
  "ai_data_privacy_warning_acknowledged": false,
  "ai_data_included_paths": [],
  "ai_data_excluded_paths": [
    "ai/conversations/",
    "ai/memory/",
    "ai/drafts/",
    "ai/indexes/"
  ]
}
```

Rules:

- Empty lists and bool fields must not be omitted.
- Manifest must distinguish source records from derived indexes.
- If AI data is included, manifest must record the exact selected classes.
- If AI data is excluded, manifest should still record that exclusion.
- Backup reports must warn that AI data may contain personal or sensitive context.

## 4. Restore Implications

Restore policy:

- Restored conversations remain AI history, not formal knowledge.
- Restored memory remains memory, not rules/checklists/snippets.
- Restored drafts remain drafts and may be expired before use.
- Restored derived indexes should be treated as stale or excluded by default.
- Restore must not inject AI data into `knowledge/`.
- Restore must not rebuild `.kb/index.sqlite` from AI data.
- Restore must not enable memory or cloud-send settings silently.
- Restore plan must list AI data impact if the backup contains AI data.

Future restore must remain plan-first and snapshot-aware. Real restore execution is outside v2.5.0.

## 5. Export Policy

Supported future exports:

- Export one conversation.
- Export selected conversations.
- Export all conversations in current workspace.
- Export saved memory.
- Export disabled memory.
- Export memory candidates only with explicit choice.

Export formats:

- JSON for structured audit records.
- Markdown for readable transcript.
- ZIP for multi-object export with manifest.

Export manifest must include:

- Export type.
- Source workspace id.
- Source ids.
- Included data classes.
- Redaction settings.
- Generated timestamp.
- Warning that exported AI data is not formal knowledge.

## 6. Export Redaction

Redaction default:

- Secrets redacted by default.
- Sensitive fields redacted by default.
- Context preview bodies redacted unless explicitly included.
- Cloud-send-denied data remains marked denied.
- Quarantine/rejected/unconfirmed references remain marked and cannot be relabeled as formal.

Export should include:

- Citations with layer/status/source_type/confidence metadata.
- Policy decisions.
- Context preview ids or hashes.
- Provider kind.
- Confirmation ids where relevant.
- Redaction manifest.

Export should not include:

- `.kb/index.sqlite`.
- `.kb/tasks/` logs unless a separate task-log export is explicitly selected.
- Derived AI indexes unless explicitly requested for debugging.
- Hidden memory suppressions unless advanced export is selected.

## 7. Delete One Conversation

Future delete-one-conversation behavior:

- Requires explicit user action.
- Deletes conversation message content.
- May leave a tombstone with id, timestamp and reason only.
- Must remove derived index entries or mark index stale.
- Must not delete saved memory by default.
- Must not delete Markdown knowledge.
- Must not delete `.kb/tasks/` logs.

Tombstone vs hard delete:

- Tombstone supports local audit and duplicate prevention without retaining message text.
- Hard delete must be available for privacy cleanup.
- Tombstone retention must be configurable.

## 8. Clear Conversations

Future clear-all-conversations behavior:

- Current workspace only.
- Explicit confirmation required.
- Default scope is conversation history only.
- Saved memory excluded by default.
- Drafts excluded unless selected.
- Derived conversation index removed or marked stale.
- Result summary must avoid echoing sensitive text.

Privacy warning must state:

- Clearing conversations does not clear long-term memory unless selected.
- Clearing conversations does not modify Markdown knowledge.
- Clearing conversations may affect assistant continuity.

## 9. Delete, Disable And Clear Memory

Delete memory:

- Removes or tombstones one saved memory.
- Prevents future context use.
- Does not delete source conversation by default.
- Does not modify Markdown knowledge.

Disable memory:

- Keeps memory visible.
- Excludes it from future context.
- Excludes it from cloud context preview.
- Can be reversed by explicit user action.

Clear all memory:

- Requires explicit confirmation.
- Current workspace only.
- Must show that conversation history is separate.
- Must mark derived memory index stale.

Clear candidates:

- Pending/expired candidates can be cleared without touching saved memory.
- Rejected suppressions require separate confirmation because clearing them can allow repeated prompts.

## 10. Disable Memory And Privacy Mode

Workspace memory disabled:

- No new saved memory.
- No memory context injection.
- Existing memory remains visible unless deleted.
- Candidates may be suppressed or not created based on setting.

Privacy mode:

- No persistent conversation writes.
- No persistent memory candidate writes.
- No saved memory writes.
- No cloud context from current session without explicit preview after privacy mode ends.
- In-memory session context can exist only for current session.

No provider, GUI view, ViewModel, adapter or CLI wrapper may bypass these settings with direct file IO.

## 11. Audit Gates

Future backup/export/delete/clear operations must enforce:

- Service layer owns all IO.
- User setting enables AI persistence where required.
- Privacy mode blocks persistent writes.
- Export requires redaction defaults.
- Cloud context requires preview and confirmation.
- Backup inclusion flags default false.
- Restore plan lists AI data impact.
- Delete/clear never touches Markdown knowledge unless a separate future formal knowledge operation is explicitly requested.
- Derived indexes are rebuildable and not source of truth.
- Startup must not scan `ai/conversations/` or `ai/memory/`.
- AI data must not enter formal search.

Denied states:

- Attempt to include AI data in backup without explicit flag.
- Attempt to export secrets without redaction or explicit high-risk confirmation.
- Attempt to delete Markdown through AI clear controls.
- Attempt to store AI data under `knowledge/`, `.kb/` or installation directory.
- Attempt to send memory to cloud without context preview.

## 12. Performance

Backup/export/delete/clear must scale:

- List objects with pagination.
- Stream JSONL export.
- Avoid loading all conversations into memory.
- Support cancellation for large operations.
- Mark derived indexes stale instead of synchronously rebuilding.
- Do not run on app startup.
- Do not scan all workspaces.
- Provide progress events if implemented through TaskQueue.

Storage growth controls:

- Conversation retention.
- Candidate expiry.
- Rejected suppression retention.
- Draft cleanup.
- Export staging cleanup.
- User-visible AI data size summary.

## 13. Future Tests

Future implementation must include tests for:

- Default backup excludes AI conversations.
- Default backup excludes AI memory.
- Default backup excludes AI drafts.
- Backup manifest flags are always present.
- Backup with AI data requires explicit flags.
- Restore plan reports AI data implications.
- Export redacts secrets by default.
- Export includes citations and policy decisions.
- Delete one conversation does not delete memory or Markdown.
- Clear conversations does not clear memory by default.
- Delete memory does not delete conversations or Markdown.
- Disable memory excludes it from context.
- Privacy mode prevents persistent writes.
- No formal search contamination.
- No startup scan of AI storage.

## 14. Acceptance Commands

The v2.5.0 policy documentation should keep existing validation passing:

```bash
python scripts/kb.py audit
python scripts/kb.py secret-scan
python tests/smoke_test.py
python tests/governance_test.py
```

These commands do not implement or exercise persistent AI storage.

## 15. Acceptance Criteria

- Backup defaults exclude AI conversations, memory, drafts and derived indexes.
- Backup manifest flags are explicit.
- Restore implications are clear.
- Export includes redaction, citations and policy decisions.
- Delete/clear/disable semantics are defined separately for conversations, memory, candidates and suppressions.
- Privacy mode no-write behavior is defined.
- Audit gates prevent direct IO, formal search injection, startup scan and cloud context leakage.
- v2.5.0 remains design-only.
