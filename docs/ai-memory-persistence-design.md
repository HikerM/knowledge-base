# AI Memory Persistence Design

本文定义 v2.5.0 Persistent MemoryService 的真实持久化方案。当前阶段只做设计文档，不实现落盘写入，不创建 `workspace/ai`，不创建 memory 文件，不保存长期记忆到磁盘，不接真实 AI，不下载模型，不做 RSS/vector，不执行 mutation，不修改 `knowledge/**/*.md`，不修改 SQLite schema，也不改变 `search` / `index` / `audit` 行为。

MemoryService 的持久化目标是让未来 AI 助手只在用户确认后保存少量、可见、可删除、可禁用、可导出的长期偏好，同时保证 memory 不是 formal knowledge，不能绕过 `SearchService`。

## 1. Scope

本阶段只设计：

- Memory storage layout。
- Saved memory / candidate / rejection suppression source of truth。
- Schema versioning and manifests。
- Atomic writes。
- Retention。
- Delete / disable / clear。
- Export。
- Backup boundary。
- Privacy mode。
- Audit gates。
- Performance。
- Future tests。

本阶段不做：

- 不实现真实 MemoryService 持久化。
- 不创建 `workspace_root/ai/`。
- 不保存长期记忆到磁盘。
- 不写 memory candidate 文件。
- 不接真实 AI provider。
- 不新增 SQLite schema。
- 不把 memory 注入 formal search。
- 不改变现有 search/index/audit 行为。

## 2. Storage Layout

推荐未来布局：

```text
workspace_root/
  ai/
    manifest.json
    memory/
      manifest.json
      memories.jsonl
      disabled.jsonl
      deletion-tombstones.jsonl
      rejection-suppressions.jsonl
    drafts/
      memory-candidates.jsonl
    indexes/
      memory.index.sqlite
      memory.index.manifest.json
```

Rules:

- `ai/memory/` is workspace-scoped.
- Memory 不放 `knowledge/`。
- Memory 不放 `.kb/`。
- Memory 不放安装目录。
- `ai/indexes/memory.index.sqlite` 如存在，只是 derived index，可删除重建。
- AI memory 默认不进入 knowledge formal search。
- `drafts/memory-candidates.jsonl` 存放待确认候选；candidate 不是 saved memory。

## 3. Source Of Truth

推荐事实来源：

- Saved memory: `ai/memory/memories.jsonl`
- Disabled state history: `ai/memory/disabled.jsonl`
- Deletion tombstones: `ai/memory/deletion-tombstones.jsonl`
- Rejection suppressions: `ai/memory/rejection-suppressions.jsonl`
- Pending candidates: `ai/drafts/memory-candidates.jsonl`

Each JSONL record must include:

- `schema_version`
- `record_type`
- `record_id`
- `workspace_id`
- `created_at`
- `payload`
- `checksum`

SQLite use:

- SQLite can be used only as optional derived index under `ai/indexes/`.
- It cannot be `.kb/index.sqlite`.
- It cannot be queried by `SearchService` formal search.
- It can be rebuilt from JSONL source records.

Memory is never formal knowledge:

- Memory cannot satisfy project rule citations.
- Memory cannot promote raw/distilled/research into formal layers.
- Memory cannot authorize mutation.
- Memory cannot become reviewer identity, approval id, plan hash or snapshot.

## 4. Record Schemas

### Saved Memory

```json
{
  "schema_version": "memory-record-v1",
  "record_type": "memory_saved",
  "record_id": "mrec_01H...",
  "workspace_id": "workspace_01H...",
  "created_at": "2026-05-22T10:00:00+08:00",
  "payload": {
    "memory_id": "mem_01H...",
    "type": "preference",
    "text": "用户希望默认使用中文回复。",
    "sensitivity": "low",
    "status": "active",
    "source": {
      "candidate_id": "memcand_01H...",
      "conversation_id": "conv_01H...",
      "source_message_ids": ["msg_01H..."]
    },
    "confirmed_by": "user",
    "confirmation_id": "confirm_01H...",
    "retention_policy_id": "until_user_deletes",
    "cloud_send_allowed": false
  },
  "checksum": "sha256-of-canonical-record-without-checksum"
}
```

Allowed memory types:

- `preference`
- `format`
- `workflow`
- `personal_rule`
- `long_term_goal`

Forbidden memory:

- Secrets, credentials, private keys or tokens.
- Customer privacy data.
- Sensitive personal data inferred by AI.
- Quarantine or rejected content.
- Unreviewed raw content.
- Sensitive document summaries.
- Cloud-inferred profile data.
- Any context obtained outside service layer.

### Memory Candidate

```json
{
  "schema_version": "memory-candidate-record-v1",
  "record_type": "memory_candidate_created",
  "record_id": "mcandrec_01H...",
  "workspace_id": "workspace_01H...",
  "created_at": "2026-05-22T10:00:00+08:00",
  "payload": {
    "candidate_id": "memcand_01H...",
    "conversation_id": "conv_01H...",
    "type": "workflow",
    "proposed_text": "用户希望文档变更后先跑 audit 和 secret-scan。",
    "source_message_ids": ["msg_01H..."],
    "sensitivity": "low",
    "requires_confirmation": true,
    "status": "pending",
    "expires_at": "2026-06-21T10:00:00+08:00",
    "rejection_fingerprint": "sha256-normalized-proposal"
  },
  "checksum": "sha256-of-canonical-record-without-checksum"
}
```

Candidate rules:

- Candidate is not saved memory.
- Candidate must be shown to the user.
- Candidate cannot be accepted silently.
- Candidate can expire.
- `sensitivity=blocked` cannot be accepted.
- Rejected candidate creates a suppression record.

### Rejection Suppression

```json
{
  "schema_version": "memory-suppression-record-v1",
  "record_type": "memory_candidate_rejected",
  "record_id": "msup_01H...",
  "workspace_id": "workspace_01H...",
  "created_at": "2026-05-22T10:00:00+08:00",
  "payload": {
    "rejection_fingerprint": "sha256-normalized-proposal",
    "candidate_type": "workflow",
    "suppressed_until": "2026-11-18T10:00:00+08:00",
    "reason": "user_rejected"
  },
  "checksum": "sha256-of-canonical-record-without-checksum"
}
```

## 5. Directory Manifest

`ai/memory/manifest.json` should include:

```json
{
  "schema_version": "memory-manifest-v1",
  "workspace_id": "workspace_01H...",
  "record_schema_versions": {
    "saved_memory": "memory-record-v1",
    "candidate": "memory-candidate-record-v1",
    "suppression": "memory-suppression-record-v1"
  },
  "retention": {
    "candidate_expiry_days": 30,
    "rejected_suppression_days": 180,
    "saved_memory_policy": "until_user_deletes"
  },
  "privacy": {
    "memory_enabled": false,
    "cloud_send_default": false
  },
  "derived_index": {
    "path": "../indexes/memory.index.sqlite",
    "rebuild_required": true
  }
}
```

Manifest rules:

- Manifest has `schema_version`.
- Manifest must not include full memory text if a smaller metadata summary is enough.
- Unknown manifest version must require migration plan.
- Manifest cannot be used as a substitute for JSONL source records.

## 6. Schema Versioning

Requirements:

- Every record must carry `schema_version`.
- Every directory must carry a manifest.
- Schema validators must enforce strict bool/int/list/dict/string types.
- String `"true"` / `"false"` cannot replace bool.
- Integer `0` / `1` cannot replace bool.
- `type`, `status`, `sensitivity` and `record_type` must be strict enums.
- Old schema records must be validated by version-specific loaders before being returned.
- Unknown schema must fail closed and require migration plan.

Migration-sensitive fields:

- `sensitivity`
- `cloud_send_allowed`
- `confirmed_by`
- `confirmation_id`
- `source`
- `retention_policy_id`
- `status`
- `rejection_fingerprint`

These fields cannot be dropped or defaulted silently.

## 7. Atomic Writes

Future writes must be service-owned and atomic:

- Validate record before serialization.
- Canonicalize JSON.
- Add checksum.
- Write temp file in the same directory for new compacted files.
- Flush and fsync file.
- Rename atomically.
- Fsync parent directory where supported.
- For JSONL append, append complete newline-terminated records and fsync bounded batches.

Windows handling:

- Rename must retry on sharing violations.
- Antivirus/indexer locks must produce bounded retry, then structured failure.
- Pending temp files must be recoverable.
- Readers must ignore temp/pending files unless explicitly repairing.

Partial write recovery:

- Incomplete trailing JSONL line can be truncated only after checksum verification of previous records.
- Invalid middle records require quarantine/repair plan.
- Derived index can be deleted and rebuilt.

## 8. Retention Enforcement

Recommended defaults:

| Data | Default retention | Notes |
| --- | --- | --- |
| Memory candidate | 30 days | Pending candidate only |
| Rejected suppression | 180 days | Prevent repeated prompts |
| Saved memory | Until user deletion | User-confirmed long-term memory |
| Disabled memory | Until user deletion | Visible but not used |
| Privacy-mode candidate | No persistent write | RAM-only current session |

Rules:

- Long-term memory does not auto-expire by default.
- Candidate expiry cannot turn a candidate into memory.
- Expired candidate must be regenerated and reconfirmed.
- Rejected suppression prevents repeated prompts but does not create memory.
- Privacy mode creates no persistent candidate or saved memory record.
- Retention cleanup must be service-owned and not run as startup scan.

## 9. Delete, Disable, Clear

Required future controls:

- Delete one memory.
- Disable one memory.
- Enable one disabled memory.
- Disable all memory for a workspace.
- Clear all saved memory.
- Clear pending candidates.
- Clear expired candidates.
- Clear rejection suppressions.

Delete semantics:

- User-facing delete prevents future context use.
- Hard delete must be available for privacy cleanup.
- Tombstone may retain `memory_id`, deletion timestamp, and reason, but no memory text.
- Delete memory must not delete conversations unless explicitly selected.
- Delete memory must not modify Markdown knowledge or formal search indexes.

Disable semantics:

- Disabled memory remains visible in settings.
- Disabled memory is excluded from ContextBuilder.
- Disabled memory is excluded from cloud context preview.
- Disabled memory can be re-enabled only by explicit user action.

Clear semantics:

- Clear all memory requires explicit confirmation in future UI.
- Clear candidates does not delete saved memory.
- Clear conversations does not delete saved memory by default.
- Clear suppressions can make future similar candidates appear again.

## 10. Privacy Mode

Privacy mode rules:

- No persistent memory candidate writes.
- No saved memory writes.
- No rejection suppression writes unless the user explicitly confirms after leaving privacy mode.
- No conversation persistence writes.
- In-memory context can exist only for current session.
- Privacy mode must be visible in UI.
- Provider cannot override privacy mode.

Privacy mode audit:

- Service should return `write_skipped_privacy_mode` or equivalent structured status.
- It should not write a local audit file that reveals sensitive content from privacy mode.

## 11. Export

Export modes:

- Export saved memory.
- Export disabled memory.
- Export selected memory.
- Export candidates only with explicit user choice.
- Export suppressions only with explicit advanced choice.

Export must include:

- `memory_id`
- type
- text unless redacted
- status
- sensitivity
- created_at / updated_at
- source candidate / conversation ids
- confirmation id
- cloud send decision
- redaction manifest

Redaction:

- Secrets are redacted by default.
- `sensitivity=high` requires warning or default redaction.
- `sensitivity=blocked` cannot be exported as plain text by default.
- Export must say memory is not formal knowledge.

## 12. Backup Boundary

Backup defaults:

- `include_ai_memory=false` by default.
- `include_ai_drafts=false` by default.
- `include_ai_conversations=false` remains independent.
- Pending candidates are excluded unless `include_ai_drafts=true`.
- Derived memory indexes are excluded by default.

Backup manifest flags:

- `include_ai_memory`
- `include_ai_drafts`
- `include_ai_conversations`
- `include_ai_indexes`
- `ai_data_privacy_warning_acknowledged`

Restore implications:

- Restored memory remains non-formal.
- Restored memory must respect disabled/deleted statuses.
- Derived AI index is stale after restore.
- Restore must not write memory into `knowledge/` or `.kb/`.
- Restore must not enable cloud-send settings silently.

## 13. Audit Gates

Before any future memory write:

- User setting must enable memory where required.
- Privacy mode must be false.
- Candidate must pass sensitivity/secret blocking.
- Candidate must be explicitly confirmed before save.
- Schema validation must pass.
- Service layer must own IO.
- GUI/ViewModel/provider must not write files directly.
- Memory must not enter `SearchService` formal results.
- Startup must not scan `ai/memory/`.
- Cloud context must require preview and confirmation before including memory.

Denied states:

- Attempt to save without confirmation.
- Attempt to save blocked sensitivity.
- Attempt to store under `knowledge/`, `.kb/` or installation directory.
- Attempt to use memory as approval/snapshot/reviewer identity.
- Attempt to send memory to cloud without preview.
- Unknown schema version without migration plan.

## 14. Performance

Large memory handling:

- Saved memory should stay small by product design.
- List memory with pagination.
- Lazy-load full source conversation only when user opens source details.
- Keep candidate and suppression scans bounded.
- Use derived index for filtering by type/status/sensitivity if needed.
- Do not scan `ai/memory/` during startup.

Storage growth limits:

- Candidate expiry.
- Suppression retention.
- User-visible count and storage summary.
- Warnings if memory grows beyond expected personal preference scale.
- Compaction plan for JSONL after many updates/deletes.

## 15. Future Tests

Future implementation must include tests for:

- Atomic memory write success.
- Atomic memory write failure leaves previous data intact.
- Partial candidate JSONL recovery.
- Corruption recovery.
- Schema migration.
- Candidate expiry.
- Rejected suppression retention.
- Privacy mode no-write.
- Save memory requires explicit confirmation.
- Blocked sensitivity cannot be saved.
- Delete memory does not touch Markdown or conversations.
- Disable memory excludes it from context.
- Backup inclusion flags.
- Export redaction.
- No formal search contamination.
- No startup scan of `ai/memory/`.

## 16. Acceptance Criteria

- Memory storage layout is workspace-scoped under `ai/memory/` and `ai/drafts/`.
- JSONL / JSON records are source of truth.
- SQLite is only an optional derived index under `ai/indexes/`.
- Every record and manifest has `schema_version`.
- Candidate, saved memory, suppression, delete and disable semantics are defined.
- Retention, privacy mode, backup, export and audit gates are defined.
- Performance plan avoids startup scan and supports pagination/lazy loading.
- v2.5.0 remains design-only with no persistent write implementation.
