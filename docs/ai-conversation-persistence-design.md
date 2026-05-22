# AI Conversation Persistence Design

本文定义 v2.5.0 Persistent ConversationStore 的真实持久化方案。当前阶段只做设计文档，不实现落盘写入，不创建 `workspace/ai`，不创建 conversation 文件，不接真实 AI，不下载模型，不做 RSS/vector，不执行 mutation，不修改 `knowledge/**/*.md`，不修改 SQLite schema，也不改变 `search` / `index` / `audit` 行为。

ConversationStore 的持久化目标是让未来用户可以回看、删除、导出和审计 AI 对话，同时确保对话记录不进入 formal knowledge，不污染 `SearchService` 的正式检索边界。

## 1. Scope

本阶段只设计：

- Storage layout。
- Source of truth。
- Schema versioning。
- Manifest。
- Atomic writes。
- Partial write / crash / corruption recovery。
- Retention。
- Delete / clear。
- Export。
- Backup inclusion boundary。
- Audit gates。
- Performance。
- Future tests。

本阶段不做：

- 不实现真实 `ConversationStore` 落盘。
- 不创建 `workspace_root/ai/`。
- 不写 conversation JSON / JSONL。
- 不新增或修改 SQLite schema。
- 不把 conversation 注入 formal search。
- 不接真实 AI provider。
- 不做 cloud context send。
- 不改现有 search/index/audit 行为。

## 2. Storage Layout

推荐未来布局：

```text
workspace_root/
  ai/
    manifest.json
    conversations/
      manifest.json
      active/
        YYYY/
          MM/
            conv_<conversation_id>.jsonl
      deleted/
        tombstones.jsonl
    memory/
    drafts/
      conversation-drafts.jsonl
    indexes/
      conversations.index.sqlite
      conversations.index.manifest.json
```

Rules:

- `ai/` 必须是 workspace-scoped。
- 不放 `knowledge/`，因为 conversation 不是知识卡片，不是 rules/checklists/snippets。
- 不放 `.kb/`，因为 `.kb/` 是 runtime/cache，可删除重建。
- 不放软件安装目录，避免卸载、重装或多 workspace 混杂。
- `ai/indexes/` 只允许存放 conversation 查询用 derived index；它可以删除重建，不是事实来源。
- AI data 默认不进入 knowledge formal search。
- `drafts/` 只保存未来未提交 UI 草稿、导出草稿或 pending preview；草稿有更短 retention。

## 3. Source Of Truth

推荐事实来源：

- 每个 conversation 使用一份 UTF-8 JSONL event log。
- 每一行是一个完整 JSON record。
- 每个 record 必须包含 `schema_version`、`record_type`、`record_id`、`conversation_id`、`created_at` 和 `checksum`。
- `ai/manifest.json` 和 `conversations/manifest.json` 只记录目录级 schema、capability flags、last_compacted_at、index metadata 和 storage policy。

Example record:

```json
{
  "schema_version": "conversation-record-v1",
  "record_type": "message_appended",
  "record_id": "crec_01H...",
  "conversation_id": "conv_01H...",
  "workspace_id": "workspace_01H...",
  "created_at": "2026-05-22T10:00:00+08:00",
  "payload": {
    "message_id": "msg_01H...",
    "role": "assistant",
    "type": "assistant_text",
    "content": {
      "text": "..."
    },
    "citations": [],
    "policy_decision_id": "policy_01H..."
  },
  "checksum": "sha256-of-canonical-record-without-checksum"
}
```

Allowed event types:

- `conversation_created`
- `message_appended`
- `citation_recorded`
- `policy_decision_recorded`
- `context_preview_recorded`
- `task_reference_recorded`
- `summary_updated`
- `title_updated`
- `conversation_retention_updated`
- `conversation_deleted`

Rules:

- Conversation JSONL is source of truth.
- Optional SQLite in `ai/indexes/` is a derived index only.
- Derived index can be deleted and rebuilt from JSONL records.
- Conversation records are not formal knowledge.
- Conversation summaries are not long-term memory.
- Conversation records cannot satisfy project-rule citations by themselves.

## 4. Directory Manifests

Each storage directory needs a manifest.

`ai/manifest.json` should include:

```json
{
  "schema_version": "ai-storage-manifest-v1",
  "workspace_id": "workspace_01H...",
  "created_at": "2026-05-22T10:00:00+08:00",
  "updated_at": "2026-05-22T10:00:00+08:00",
  "storage_layout_version": "ai-storage-layout-v1",
  "directories": {
    "conversations": "conversations/",
    "memory": "memory/",
    "drafts": "drafts/",
    "indexes": "indexes/"
  },
  "source_of_truth": {
    "conversation": "jsonl",
    "memory": "jsonl",
    "indexes": "derived"
  },
  "privacy_mode_default": false,
  "schema_min_reader_version": "2.5.0-design",
  "schema_writer_version": null
}
```

`conversations/manifest.json` should include:

- `schema_version`
- `record_schema_version`
- `retention_policy_id`
- `default_retention_days`
- `conversation_count_estimate`
- `last_retention_run_at`
- `last_compaction_run_at`
- `derived_index_path`
- `derived_index_rebuild_required`
- `corruption_quarantine_count`

Manifest rules:

- Manifest is metadata, not conversation body source of truth.
- Manifest writes must be atomic.
- Manifest must not include full message bodies.
- Old manifest versions must be validated before use.
- Unknown schema versions must fail closed and require migration plan.

## 5. Schema Versioning

Requirements:

- Every JSONL record has `schema_version`.
- Every manifest has `schema_version`.
- `schema_version` is an explicit string enum, not an inferred app version.
- Reader must validate known fields and strict types before returning data.
- Unknown record type is preserved but not rendered unless the reader supports it.
- Unknown schema version must produce a blocked migration plan, not silent best-effort parsing.
- Older schema can be read only through versioned validators.

Compatibility:

- Minor additive fields may be ignored if the manifest declares compatibility.
- Required-field changes require a migration plan.
- Field type changes require migration and tests.
- Enum expansion requires explicit fallback behavior.
- Redaction and sensitivity fields must never be dropped during migration.

## 6. Atomic Writes

Future writes must use a service-owned atomic writer:

1. Validate payload in memory.
2. Serialize canonical JSON with stable key ordering.
3. Calculate checksum.
4. Write to a temp file in the same directory.
5. Flush file buffers.
6. `fsync` file contents.
7. Rename temp file into place with replace semantics.
8. `fsync` parent directory where the platform supports it.
9. Re-read lightweight metadata or checksum if needed.

JSONL append rules:

- Append one complete line per record.
- Always end committed records with newline.
- Flush and fsync after append batches.
- Batch size must be bounded.
- If a crash leaves a trailing partial line, recovery truncates only the incomplete final line after checksum validation.

Windows file locking:

- Writer must open files with conservative sharing.
- Rename failures caused by antivirus/indexer locks must retry with bounded backoff.
- If retries fail, leave the temp file in a recoverable `*.pending` state and return a structured error.
- Readers must handle temporary files by ignoring `*.tmp` / `*.pending` unless running recovery.

## 7. Crash And Corruption Recovery

Recovery must be explicit and service-owned:

- Detect missing manifest.
- Detect manifest checksum mismatch where checksum is available.
- Detect invalid JSON record.
- Detect partial trailing JSONL line.
- Detect record checksum mismatch.
- Detect derived index staleness.
- Detect missing conversation file referenced by manifest.

Recovery behavior:

- Derived index corruption: delete and rebuild from JSONL.
- Partial trailing line: truncate only the incomplete line after preserving a recovery copy or snapshot.
- Invalid middle record: quarantine the affected conversation file for user-visible repair plan; do not silently drop records.
- Missing manifest: reconstruct minimal manifest by scanning only the AI storage area during an explicit repair command, not startup.
- Unknown schema: produce migration-required status.

No recovery path may read or modify `knowledge/**/*.md` or `.kb/index.sqlite`.

## 8. Retention Enforcement

Conversation retention policy:

- Default retention is configurable per workspace.
- Privacy mode conversations have no persistent write.
- Conversation summaries follow the same retention as their source conversation.
- Drafts expire faster than normal conversations.
- Retention cleanup must be a future explicit task or background service action, not startup scan.

Recommended defaults:

| Data | Default | Notes |
| --- | --- | --- |
| Active conversation | User-configurable local retention | Suggested default can be never-expire or bounded by user setting |
| Conversation summary | Same as conversation | Not long-term memory |
| Conversation draft | 7-30 days | Pending UI state only |
| Export staging file | Short-lived | Must be cleared after export |
| Privacy-mode conversation | No persistent write | RAM-only current session |

Retention rules:

- Retention must not delete Markdown knowledge.
- Retention must not delete saved memory unless the user explicitly selects memory deletion.
- Retention must record result summary without echoing sensitive message content.
- Retention cleanup must be cancellable if implemented through TaskQueue.

## 9. Delete, Clear, Disable

Required future controls:

- Delete one conversation.
- Clear all conversations in current workspace.
- Clear conversations older than retention window.
- Clear drafts.
- Disable conversation persistence for future sessions.
- Enable privacy mode for current session.

Delete semantics:

- User-facing delete should remove message content from source-of-truth storage.
- A tombstone may be retained with `conversation_id`, timestamp, reason, and checksum, but no message text.
- Tombstone retention must be configurable and privacy-sensitive.
- Hard delete must be available for privacy cleanup.
- Delete must never touch `knowledge/`, `.kb/index.sqlite`, formal search index, saved memory, or task logs.

Clear all semantics:

- Applies only to current workspace.
- Requires explicit confirmation in future UI.
- Must show whether saved memory is included. Default is conversation-only.
- Must not clear memory candidates unless explicitly selected.

Disable semantics:

- Disabling conversation persistence stops future writes.
- Existing conversations remain until deleted or retention cleanup runs.
- Privacy mode overrides persistence and prevents writes for the active session.

## 10. Export

Export modes:

- Export one conversation.
- Export selected conversations.
- Export all conversations in current workspace.

Export formats can include:

- JSON for full structured records.
- Markdown for human-readable conversation transcript.
- ZIP for multi-conversation export with manifest.

Export must include:

- Conversation metadata.
- Messages.
- Citations with document/title/layer/status/source_type/confidence where available.
- Policy decisions.
- Context preview ids or hashes where available.
- Provider kind.
- Privacy warnings.
- Redaction manifest.

Redaction rules:

- Secrets are redacted by default.
- Sensitive fields are redacted by default.
- Cloud-send-denied context remains marked denied.
- Quarantine, rejected and unconfirmed sources remain marked and must not be described as formal rules.
- Exported conversations are not formal knowledge.

## 11. Backup Boundary

Conversation backup defaults:

- `include_ai_conversations=false` by default.
- `include_ai_drafts=false` by default.
- Backup manifest must record whether conversations and drafts were included.
- Backup UI must show privacy warning before including conversation history.
- Derived indexes should be excluded by default and rebuilt after restore.

Restore implications:

- Restored conversations remain non-formal AI history.
- Restore must not inject conversations into `knowledge/`.
- Restore must not rebuild formal search from AI data.
- Restore should mark derived AI indexes stale and rebuild only on explicit AI-history use.

## 12. Audit Gates

Before any future persistent conversation write:

- User setting must allow conversation persistence where required.
- Privacy mode must be false.
- Service layer must own all file IO.
- GUI/ViewModel/provider must not write files directly.
- Record schema validation must pass.
- Secret/sensitive policy must run before cloud context or export.
- No AI data may be injected into formal `SearchService` results.
- Startup must not scan `ai/conversations/`.
- Cloud provider must not receive conversation history without context preview and user confirmation.

Denied states:

- Unknown schema version.
- Missing manifest when not in explicit repair flow.
- Corrupted record that cannot be isolated.
- Privacy mode active.
- User disabled conversation persistence.
- Attempt to store under `knowledge/`, `.kb/` or installation directory.

## 13. Performance

Large conversation count handling:

- Partition conversation files by year/month.
- Keep one conversation per JSONL file to avoid rewriting large global logs.
- Keep manifest metadata small and bounded.
- Use pagination for conversation lists.
- Lazy-load messages only when a conversation is opened.
- Use optional derived index for title, timestamp, provider kind and message snippets.
- Rebuild derived index from JSONL only on explicit repair/rebuild or when the AI history view is opened and index is stale.
- Do not scan `ai/conversations/` during app startup.

Storage growth controls:

- Configurable retention.
- Conversation compaction.
- Draft expiry.
- Export staging cleanup.
- User-visible storage usage summary.
- Hard cap warnings before large AI history grows without bound.

## 14. Future Tests

Future implementation must include tests for:

- Atomic write success.
- Atomic write failure leaves old file intact.
- Windows-style rename retry behavior.
- Partial trailing JSONL recovery.
- Middle-record corruption detection.
- Derived index delete and rebuild.
- Schema migration required for unknown schema.
- Conversation retention cleanup.
- Privacy mode no-write.
- Delete one conversation does not touch memory or Markdown.
- Clear all conversations does not touch memory by default.
- Backup inclusion flags.
- Export redaction.
- No formal search contamination.
- No startup scan of `ai/conversations/`.

## 15. Acceptance Criteria

- Storage layout is workspace-scoped under `ai/`.
- Conversation source of truth is JSONL / JSON records, not SQLite.
- Optional SQLite index is derived and rebuildable.
- Every record and manifest has `schema_version`.
- Atomic write, crash recovery and corruption detection are defined.
- Retention, delete, clear, export and backup boundaries are defined.
- Audit gates block privacy, cloud-send and formal-search contamination risks.
- Performance plan avoids startup scan and supports pagination/lazy loading.
- v2.5.0 remains design-only with no persistent write implementation.
