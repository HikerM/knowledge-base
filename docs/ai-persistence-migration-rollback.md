# AI Persistence Migration And Rollback Design

本文定义 v2.5.0 AI ConversationStore / MemoryService 持久化的 migration、rollback、recovery 和验收设计。当前阶段只做设计文档，不实现迁移器，不创建 `workspace/ai`，不写 conversation 或 memory 文件，不修改 `knowledge/**/*.md`，不修改 SQLite schema，也不改变 `search` / `index` / `audit` 行为。

Migration 的目标是让未来 AI persistence schema 可以安全演进，并且每次执行前都有可审计计划、local snapshot、回滚路径和验收命令。

## 1. Scope

本阶段只设计：

- Schema versioning rules。
- Migration plan lifecycle。
- Rollback plan lifecycle。
- Snapshot and backup requirements。
- Atomic migration strategy。
- Derived index rebuild strategy。
- Corruption recovery strategy。
- Audit gates。
- Future test plan。

本阶段不做：

- 不实现迁移命令。
- 不执行迁移。
- 不创建 AI storage。
- 不读取所有 conversation/memory 文件。
- 不修改 Markdown knowledge。
- 不修改 `.kb/index.sqlite` 或 SQLite schema。

## 2. Version Model

AI persistence must version these layers separately:

| Layer | Example | Purpose |
| --- | --- | --- |
| storage layout | `ai-storage-layout-v1` | Directory and manifest structure |
| directory manifest | `ai-storage-manifest-v1` | Root AI storage metadata |
| conversation record | `conversation-record-v1` | Conversation JSONL event schema |
| memory record | `memory-record-v1` | Saved memory schema |
| candidate record | `memory-candidate-record-v1` | Pending candidate schema |
| suppression record | `memory-suppression-record-v1` | Rejected candidate suppression schema |
| derived index | `ai-derived-index-v1` | Optional query index schema |

Rules:

- App version does not replace schema version.
- Each record carries its own `schema_version`.
- Each directory has a manifest with active schema versions.
- Derived index version is independent and rebuildable.
- Unknown schema versions must fail closed.
- Old schema can be read only through explicit validators.

## 3. Migration Plan Lifecycle

Future migration must be plan-first.

Recommended lifecycle:

```text
detect schema state
  ↓
validate manifests and sample / targeted records
  ↓
build dry-run migration plan
  ↓
show impacted files, counts, risks and rollback path
  ↓
create local snapshot / backup
  ↓
require explicit user approval
  ↓
run migration through TaskQueue
  ↓
validate migrated records
  ↓
mark derived indexes stale
  ↓
emit result summary
```

Plan output must include:

- `dry_run=true`
- `would_modify=false` for plan-only mode
- `blocked`
- `blockers`
- `actions`
- `source_schema_versions`
- `target_schema_versions`
- `impacted_paths`
- `estimated_record_counts`
- `requires_snapshot`
- `rollback_plan`
- `validation_commands`
- `privacy_warnings`

Blocked plan is still a valid plan if it can be constructed. It should return success status to the caller and list blockers.

## 4. Migration Preconditions

Migration execution must be blocked unless:

- User explicitly requested migration.
- Target workspace is selected.
- AI persistence is already enabled or migration target exists.
- Source manifests validate.
- Unknown schemas have a supported migration path.
- Local snapshot / backup exists and verifies.
- User approved the exact plan hash.
- TaskQueue task is created for execution.
- Privacy warnings have been acknowledged if AI data is included in backup.

Migration must not run:

- During app startup.
- During workspace-status.
- During formal search.
- During index/audit/doctor unless a future explicit AI repair command is invoked.
- From GUI View or provider direct IO.

## 5. Atomic Migration Strategy

Future migration must avoid in-place destructive rewrites.

Recommended strategy:

1. Read source records through versioned validators.
2. Write target records to a staging directory under the same AI storage root.
3. Fsync staged files.
4. Validate staged records.
5. Write staged manifests.
6. Rename staged directory into place with an atomic swap or guarded replace.
7. Preserve previous version until migration finalization.
8. Mark derived indexes stale.
9. Rebuild derived indexes only after source-of-truth validation succeeds.

Staging example:

```text
workspace_root/ai/
  .migration/
    mig_<id>/
      plan.json
      staged/
      validation-report.json
```

Rules:

- `.migration/` is inside future `ai/` storage, not `.kb/`.
- Migration temp files are not formal knowledge.
- Failed migration must not leave mixed schema as current state.
- Derived indexes are always disposable.

## 6. Rollback Strategy

Rollback must be possible before any migration execution.

Rollback sources:

- Local snapshot / backup created before migration.
- Preserved previous AI storage version if atomic swap used.
- Migration plan and validation report.

Rollback behavior:

- Rollback restores AI persistence files only.
- Rollback must not overwrite `knowledge/`.
- Rollback must not modify `.kb/index.sqlite`.
- Rollback must mark AI derived indexes stale.
- Rollback must not enable memory or cloud-send settings silently.
- Rollback must be explicit and user-confirmed.

Rollback plan must include:

- Paths that would be restored.
- Paths that would be removed.
- Conflicts.
- Privacy impact.
- Whether backup contains AI conversations/memory/drafts.
- Validation commands after rollback.

## 7. Derived Index Migration

Derived AI indexes:

- Are not source of truth.
- Can be deleted.
- Can be rebuilt from JSONL / JSON records.
- Must live under `workspace_root/ai/indexes/` if needed.
- Must not modify `.kb/index.sqlite`.
- Must not be used by formal `SearchService`.

Index migration rule:

- Prefer rebuild over in-place migration.
- If index schema changes, mark stale and rebuild.
- If rebuild fails, AI history search can be disabled while source records remain intact.
- Startup must not rebuild AI derived index.

## 8. Corruption Recovery

Recovery modes:

- Manifest repair.
- JSONL trailing-line truncation.
- Record quarantine.
- Derived index rebuild.
- Snapshot restore.

Rules:

- Repair must be explicit, not startup scan.
- Corrupted source records must not be silently dropped.
- Invalid middle records should generate a repair plan.
- Secret/sensitive text must not be echoed in repair reports.
- Quarantined AI persistence records are not quarantine knowledge cards and must not enter `knowledge/`.
- Corruption recovery must not read or modify Markdown knowledge.

## 9. Privacy And Retention During Migration

Migration must preserve:

- `sensitivity`
- `cloud_send_allowed`
- `privacy_mode`
- `confirmed_by`
- `confirmation_id`
- `policy_decision_id`
- `context_preview_id`
- `retention_policy_id`
- `deleted` / `disabled` status
- rejection suppression fingerprints

Migration must not:

- Re-enable disabled memory.
- Restore deleted memory as active.
- Extend retention silently.
- Include AI data in backup unless user explicitly selected it.
- Send any AI data to cloud provider.

## 10. Audit Gates

Migration implementation is blocked until these gates exist:

- Plan-first migration service.
- Local snapshot / backup requirement.
- Approval bound to plan hash.
- TaskQueue execution path.
- Versioned schema validators.
- Rollback plan.
- Redaction for migration reports.
- No startup scan proof.
- No formal search contamination proof.
- No GUI/provider direct file IO proof.

Denied states:

- Missing snapshot.
- Approval absent or plan hash mismatch.
- Unknown schema without migration path.
- Attempt to store under `.kb/`, `knowledge/` or installation directory.
- Attempt to mutate Markdown or `.kb/index.sqlite`.
- Attempt to run migration from startup path.

## 11. Performance

Migration must handle large AI data:

- Paginate record scanning.
- Stream JSONL validation.
- Bound memory use.
- Report progress through TaskQueue.
- Support cooperative cancellation at file boundaries.
- Avoid loading all conversations into memory.
- Avoid scanning all workspace AI stores when switching workspaces.
- Avoid formal knowledge indexing.

Large migration should produce:

- Estimated file count.
- Estimated byte count.
- Current phase.
- Records processed.
- Error count.
- Cancellation status.

## 12. Future Tests

Future implementation must include tests for:

- Unknown schema produces blocked plan.
- Valid old schema migrates through versioned validator.
- Invalid bool/int/list/dict types are rejected.
- Migration requires snapshot.
- Approval plan hash mismatch blocks execution.
- Atomic staging failure leaves original files intact.
- Rollback restores previous AI records.
- Rollback does not touch Markdown or `.kb/index.sqlite`.
- Derived index migration uses rebuild.
- Corruption recovery handles partial trailing JSONL.
- Retention metadata preserved.
- Disabled/deleted memory stays disabled/deleted.
- No startup scan of `ai/conversations` or `ai/memory`.
- No formal search contamination.

## 13. Acceptance Commands

The v2.5.0 design-only change should continue to pass existing governance validation:

```bash
python scripts/kb.py audit
python scripts/kb.py secret-scan
python tests/smoke_test.py
python tests/governance_test.py
```

These commands validate repository governance and smoke behavior; they do not imply AI persistence is implemented.

## 14. Acceptance Criteria

- Migration and rollback are plan-first.
- Every schema layer has explicit versioning.
- Old schemas require validation before use.
- Snapshot / backup and approval are mandatory before future execution.
- Atomic staging and rollback are defined.
- Derived indexes are rebuildable and separate from `.kb/index.sqlite`.
- Migration does not touch Markdown knowledge, formal search, index or audit behavior.
- v2.5.0 remains design-only.
