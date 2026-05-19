# GUI Product UI Architecture Contract

This document is the Phase 0 Product UI Architecture Contract for the future Windows desktop GUI of `personal-knowledge-base`.

It is not a GUI implementation, packaging plan, or framework selection. Do not implement screens, choose Tauri/Electron/PySide/WinUI, or package an EXE from this document alone.

## 1. Product Understanding

- Project type: local-first personal developer knowledge base desktop application for knowledge governance, search, review, backup, task execution, and safe mutation workflows.
- Project scale: Large Product Interface / Complex Desktop Knowledge Base App.
- Platform: future Windows desktop EXE.
- UI technology / engine: not selected in Phase 0.
- Target users:
  - developers maintaining long-lived personal engineering knowledge.
  - reviewers validating raw/distilled knowledge before formal promotion.
  - readers searching formal rules, checklists, and snippets.
  - advanced users managing backup, task logs, audit, and future safe maintenance operations.
- Main usage scenarios:
  - view workspace, index, backup, snapshot, and task status at startup.
  - search formal knowledge from `rules`, `checklists`, and `snippets`.
  - open one explicit Markdown document through `DocumentService.open_document`.
  - inspect raw and distilled content with clear unreviewed warnings.
  - view review queues, archive metadata, task history, and backup/snapshot status.
  - create plan-only category/template/workspace/archive/restore plans.
  - execute only currently supported category config-only safe mutations in later GUI phases.
- Core constraints:
  - Markdown is the source of truth.
  - SQLite is the runtime hot index, not the source of truth.
  - GUI must not directly read or write Markdown.
  - GUI must not directly read or write SQLite.
  - GUI must not assemble CLI command strings as its main integration mechanism.
  - GUI must call service/core API boundaries.
  - App startup must not scan `knowledge/`, read Markdown bodies, or automatically trigger index/reindex.
  - Markdown body reads are allowed only through `DocumentService.open_document` when the user explicitly opens one document.
  - Search, Category, Review Queue, and Archive list screens must use service-backed SQLite metadata / FTS hot paths.
  - Long-running tasks must run through `TaskQueueService`; the UI main thread must not run index, audit, backup, restore, archive, template apply, secret-scan, benchmark, or maintenance.
  - Local Backup/Snapshot is the default recovery mechanism.
  - Git is optional and must not be required for backup, restore, promote, audit, index, archive, or GUI usage.
- Current service boundary:
  - `WorkspaceStatusService`
  - `IndexMetadataService`
  - `SearchService`
  - `CategoryService`
  - `ReviewQueueService`
  - `ArchiveMetadataService`
  - `DocumentService`
  - `CategoryPlanService`
  - `TemplatePlanService`
  - `WorkspacePlanService`
  - `BackupService`
  - `SnapshotService`
  - `RestorePlanService`
  - `TaskQueueService`
  - `SafeMutationService`
- Current safe mutation boundary:
  - `SafeMutationService` execute actions must run through `TaskQueueService`.
  - Current execute support is limited to category `display_name` and `description` config-only mutations.
  - Supported category execute actions may only modify the target field in `config/categories.yaml`.
  - Supported category execute actions must not rename paths, modify `category_id`, modify `path`, modify slug, modify Markdown, or modify SQLite schema.
  - Archive, delete, merge, template apply, restore, destructive maintenance, and workspace upgrade execute actions are future work and must be disabled or plan-only in the GUI.

## 2. User Roles

| Role | Can See | Can Operate | Write / Execute | Guardrails |
|---|---|---|---|---|
| Owner / Local User | All modules, workspace state, formal layers, raw, distilled, archive metadata, tasks, backup/snapshot status | Search, open document, create backup/snapshot task, create plans, approve supported safe category mutation in later phases | Only service-supported safe mutations with plan + snapshot + approval + TaskQueue | Destructive future actions disabled; no direct Markdown/SQLite/Git writes |
| Reviewer | Raw Inbox, Distilled Review, formal knowledge, document preview, review metadata | Open documents, inspect source_url/source_file/review_required/validation metadata, create future promote plan when service exists | No direct promote in current GUI phases | Raw/distilled are marked unreviewed and cannot be treated as formal project rules |
| Reader | Dashboard summary, Search, Rules / Checklists / Snippets, DocumentPreview | Formal search and explicit document open | No writes | Raw/distilled/archive/settings/task execute hidden or read-only |
| Advanced User | Owner visibility plus Task logs, Audit Center, Backup & Sync, Settings, optional Git status when service exists | Run safe long-running tasks, inspect logs, retry failed tasks, create restore plans | Still limited to service-supported safe mutation execute | Cannot bypass plan/snapshot/approval/TaskQueue; unsupported destructive execute remains disabled |

## 3. Information Architecture

```text
App
├── Dashboard
├── Search
├── Knowledge Library
│   ├── Raw Inbox
│   ├── Distilled Review
│   └── Rules / Checklists / Snippets
├── Category Settings
├── Template Manager
├── Sources
├── Organize Center
├── Archive Manager
├── Backup & Sync
├── Task Center
├── Audit Center
└── Settings
```

Core entities:

- Workspace: current knowledge-base root, workspace metadata, index status, backup status, task status.
- Document: Markdown source document. Body reads must go through `DocumentService.open_document`.
- IndexedDocument: service-backed SQLite metadata / FTS representation.
- Layer: `rules`, `checklists`, `snippets`, `distilled`, `raw`.
- Lifecycle status: `active`, `deprecated`, `rejected`, `quarantine`, `archived`.
- Category: stable `category_id`, `path`, and UI-only `display_name`.
- Plan: plan-only service result. `actions` are planned actions, not executed actions.
- Task: `task_id`, `status`, `progress_percent`, `cancel_requested`, `error`, `log_path`, `result_summary`, `elapsed_ms`, and retry lineage.
- Snapshot / Backup: default local recovery mechanism.
- RestorePlan: read-only recovery plan; it must not restore, overwrite, move, or delete files.

Primary navigation:

- Left sidebar for module-level navigation.
- Top command/search bar for workspace context, global formal search, and service-backed command entry.
- Main content area for screen content.
- Optional right inspector panel for selected document, plan, task, category, or metadata detail.
- Bottom status bar for workspace, index, task, backup/snapshot, and warning indicators.

## 4. Navigation Model

Desktop app shell:

```text
┌────────────────────────────────────────────────────────────┐
│ CommandBar: workspace switch | global search | safe actions │
├──────────────┬───────────────────────────────┬─────────────┤
│ SidebarNav   │ Main Content Area             │ Inspector   │
│ collapsible  │ screen/router content         │ collapsible │
├──────────────┴───────────────────────────────┴─────────────┤
│ StatusBar: workspace | index | tasks | snapshot | warnings  │
└────────────────────────────────────────────────────────────┘
```

- Left sidebar:
  - includes Dashboard, Search, Knowledge Library, Raw Inbox, Distilled Review, Rules / Checklists / Snippets, Category Settings, Template Manager, Sources, Organize Center, Archive Manager, Backup & Sync, Task Center, Audit Center, Settings.
  - supports expanded and collapsed states.
  - displays module warning badges, blocked states, and active route.
- Top command/search bar:
  - provides default formal-layer search.
  - command entries must map to service actions.
  - must not shell out by building CLI command strings.
- Main content area:
  - uses screen-local scroll containers.
  - uses paginated or virtualized lists for large result sets.
  - does not render all search results or task rows at once.
- Right inspector panel:
  - optional and collapsible.
  - default width: 360px.
  - collapses to drawer at minimum window width.
- Bottom status bar:
  - shows workspace selected/missing.
  - shows index status: `missing`, `ready`, `stale`, `partial`, `running`.
  - shows task activity: pending/running/failed counts.
  - shows backup/snapshot status: `missing`, `recent`, `required`, `failed`.
  - shows secret-scan and audit warning indicators.

## 5. Screen Inventory

| Screen | Purpose | Entry Point | User Role | Data Source | Service Dependency | Read / Write Behavior | Long-running Tasks | Destructive Confirmation | Empty / Loading / Error States | Implementation Phase |
|---|---|---|---|---|---|---|---|---|---|---|
| Workspace Gate | Show no-workspace or unavailable-workspace entry state | App startup | All | Workspace metadata through service | `WorkspaceStatusService` | Read-only; future workspace selection through service | None | None | no workspace, invalid workspace, loading status, service error | Phase 1 |
| Dashboard | Summarize workspace, index, backup, snapshot, task, and review status | Startup / sidebar | All | Service summaries | `WorkspaceStatusService`, `IndexMetadataService`, `TaskQueueService`, `BackupService`, `SnapshotService` | Read-only in Phase 1; later shortcuts must use services | Future background task shortcuts | Required before task creation when action supports execute | index missing, backup missing, task failed, partial index | Phase 1 |
| Search | Search formal knowledge and open explicit documents | CommandBar / sidebar | All | SQLite FTS via service | `SearchService`, `DocumentService.open_document` | Search read-only; open one document through service | None | None | empty query, no result, index missing/stale, search error | Phase 1 |
| Knowledge Library | Browse indexed knowledge by layer/category/status | Sidebar | All by role | SQLite metadata via service | `CategoryService`, `SearchService`, `DocumentService` | Read-only lists; explicit document open only | None | None | empty category, loading page, metadata error | Phase 1 |
| Raw Inbox | Inspect raw content with unreviewed warning | Sidebar / Knowledge Library | Owner, Reviewer | Review metadata via service | `ReviewQueueService`, `DocumentService` | Read-only in current architecture; future distill plan only when service exists | Future distill task disabled until service exists | Future confirmation required | raw empty, review_required, quarantine warning, load error | Phase 2 |
| Distilled Review | Inspect distilled drafts without treating them as formal rules | Sidebar / Knowledge Library | Owner, Reviewer | Review metadata via service | `ReviewQueueService`, `DocumentService`, future promote plan service | Read-only plus future promote plan-only | Future promote planning | Promote execute disabled until service exists | queue empty, blocked promote, review_required, error | Phase 2 |
| Rules / Checklists / Snippets | Browse formal executable knowledge | Sidebar / Knowledge Library | All | Formal indexed metadata | `SearchService`, `CategoryService`, `DocumentService` | Read-only; explicit document open only | None | None | empty formal layer, index missing, document open error | Phase 1 |
| Category Settings | Manage category metadata safely | Sidebar / Settings | Owner, Advanced User | Category config through service | `CategoryService`, `CategoryPlanService`, `SafeMutationService`, `SnapshotService`, `TaskQueueService` | Phase 1: not exposed; Phase 4: plan + approved safe execute for display_name/description only | Category safe mutation execute must run through TaskQueue | Snapshot + approval required | blocked plan, approval expired, validation error | Phase 4 |
| Template Manager | View templates and create template plans | Sidebar | Owner, Advanced User | Template metadata through service | `TemplatePlanService`, future template metadata service | Plan-only; execute disabled | Future template apply task disabled | Template apply execute disabled | no templates, conflict plan, unsupported execute | Phase 2 |
| Sources | View external source policy and import boundaries | Sidebar | Owner, Advanced User, Reviewer read-only | Future source metadata service | Future SourceMetadata/Plan service | Read-only/disabled until service exists | Future import task | Source removal disabled | service missing, empty source list, unsupported action | Phase 5 or future |
| Organize Center | Create organize/archive/merge/category/template plans | Sidebar | Owner, Advanced User | Plan service results | `CategoryPlanService`, `WorkspacePlanService`, `TemplatePlanService`, future archive/organize plan service | Plan-only; no move/delete/write | Future organize tasks disabled | Destructive execute disabled | blocked plan, conflict plan, no candidate | Phase 2 |
| Archive Manager | Browse archive/trash/quarantine metadata | Sidebar | Owner, Advanced User, limited Reviewer | SQLite metadata via service | `ArchiveMetadataService`, future archive plan service | Read-only plus future plan-only | Future archive/restore tasks disabled | Restore/archive execute disabled | archive empty, quarantine warning, metadata error | Phase 2 |
| Backup & Sync | Manage local backups/snapshots and optional sync status | Sidebar / StatusBar | Owner, Advanced User | Backup/snapshot catalog through service | `BackupService`, `SnapshotService`, `RestorePlanService`, `TaskQueueService`, future OptionalGitService | Backup/snapshot task creation; restore-plan read-only | `backup_create`; future restore execute disabled | Backup create confirmation; restore execute disabled | backup missing, snapshot required, restore conflict | Phase 3 |
| Task Center | Show task progress, logs, retry, cancellation, cleanup plans | Sidebar / StatusBar | Owner, Advanced User; Reader summary | Task records through service | `TaskQueueService` | Read task history; service-backed cancel/retry/cleanup-plan | All long tasks | Cancel confirmation for partial tasks | no tasks, running, failed, cancelled, log missing | Phase 3 |
| Audit Center | Show governance risks and audit/index task status | Sidebar | Owner, Advanced User | Task summaries and future audit reports | `TaskQueueService`, `IndexMetadataService`, future AuditReportService | Current: task/result read through service; task creation only where supported | audit, index, future secret-scan | Task confirmation by action type | no report, running audit, failed audit, warning found | Phase 3 |
| Settings | App/workspace preferences and future service-backed config | Sidebar | Owner, Advanced User | Settings through service | `WorkspaceStatusService`, `WorkspacePlanService`, future SettingsService | Read and plan-only unless service supports safe execute | Future workspace upgrade disabled | Workspace mutation disabled | invalid setting, blocked plan, service unavailable | Phase 2 |

## 6. GUI Phase 1 Read-only MVP Boundary

GUI Phase 1 is intentionally limited to read-only paths:

- Startup status read path through `WorkspaceStatusService` and `IndexMetadataService`.
- Search read path through `SearchService`.
- Category and library read path through `CategoryService` and indexed metadata services.
- Document open read path through `DocumentService.open_document`, one explicit document at a time.
- Task status read path through `TaskQueueService` for status/progress/history visibility only.

GUI Phase 1 must not expose category `display_name` / `description` execute.

GUI Phase 1 must not expose:

- `SafeMutationService` execute actions.
- category update approval or execute UI.
- archive/delete/merge/template apply/restore execute.
- destructive task creation.
- direct Markdown edit.
- direct SQLite access.
- direct CLI command construction.

## 7. Workflow Map

### Startup Status Workflow

1. App starts.
2. UI calls `WorkspaceStatusService`.
3. UI calls `IndexMetadataService`.
4. App shell shows workspace selected/missing, index missing/ready/stale/partial, and recent task/backup indicators.
5. UI does not scan `knowledge/`, read Markdown bodies, or auto-index.

### Formal Search Workflow

1. User enters query in `SearchBox`.
2. UI calls `SearchService` with default formal layers: `rules`, `checklists`, `snippets`.
3. Result list shows layer, status, confidence, source_type, snippet, and file path.
4. User opens one result.
5. UI calls `DocumentService.open_document`.
6. Document body appears in `DocumentPreview`.

### Review Visibility Workflow

1. Reviewer opens Raw Inbox or Distilled Review.
2. UI calls `ReviewQueueService`.
3. Raw and distilled items show `未经审核，不能作为正式项目规则`.
4. Opening an item uses `DocumentService.open_document`.
5. Promote remains future plan-only and execute disabled until the service exists.

### Category Safe Mutation Workflow

1. User edits category `display_name` or `description` in Phase 4 or later.
2. UI calls `CategoryPlanService`.
3. UI shows `PlanCard`, affected config file, validation commands, blockers, and risk.
4. UI requires valid local snapshot through `SnapshotService`.
5. User approves the exact plan.
6. UI calls `SafeMutationService` execute.
7. `SafeMutationService` execute action runs through `TaskQueueService`.
8. UI shows task progress, task log, result summary, validation result, and restore-plan entry.

### Backup / Snapshot Workflow

1. User creates backup or snapshot from Backup & Sync.
2. UI calls `BackupService` or `SnapshotService` through the service boundary.
3. Long-running creation runs through `TaskQueueService`.
4. Task Center shows progress, logs, result summary, and failure recovery.

### Restore Planning Workflow

1. User selects backup or snapshot.
2. UI calls `RestorePlanService`.
3. UI shows conflicts, would-create/would-overwrite lists, validation commands, and blockers.
4. Restore execute remains disabled/future.

### Archive / Organize Workflow

1. User requests organize/archive/merge/template plan.
2. UI calls the corresponding plan service.
3. UI shows plan-only actions.
4. Execute remains disabled unless a future service explicitly supports it with plan + snapshot + approval + TaskQueue.

## 8. Service Mapping

| UI Action | Trigger | Service | Input | Output | Loading | Success | Error | Permission |
|---|---|---|---|---|---|---|---|---|
| Load app status | App startup | `WorkspaceStatusService`, `IndexMetadataService` | workspace context | workspace + index status | shell skeleton | dashboard status visible | no workspace / service error | All |
| Search formal knowledge | Search submit | `SearchService` | query, filters, top_k, formal layers | result page | inline spinner | virtualized result list | index missing/stale/error | All |
| Open document | result click | `DocumentService.open_document` | document id/path from service result | single document body + metadata | preview loading | preview rendered | open denied/missing | Role-based |
| Browse categories | Knowledge Library | `CategoryService` | category_id, layer/status filters, page cursor | metadata list | table skeleton | paged/virtualized list | category missing/service error | All by role |
| Plan category change | Category Settings save | `CategoryPlanService` | category_id, new display_name/description | PlanResult | plan loading | PlanCard shown | blocked plan | Owner/Advanced |
| Execute category display_name/description | Approval confirm | `SafeMutationService`, `TaskQueueService` | approved plan, snapshot id, approval token | task_id + MutationResult summary | task/progress | result summary | approval expired/validation failed/task failed | Owner/Advanced |
| Load review queue | Raw/Distilled Review | `ReviewQueueService` | layer/status/page | review items | skeleton | queue list | service/index error | Owner/Reviewer |
| Future promote plan | Promote plan button | future promote plan service | distilled id + review metadata | PlanResult | disabled/loading when available | plan shown | unsupported | Owner/Reviewer |
| Load archive metadata | Archive Manager | `ArchiveMetadataService` | status/page/filter | archive/trash/quarantine list | table skeleton | list rendered | metadata error | Owner/Advanced |
| Future archive plan | Archive plan action | future archive plan service | document ids/scope | PlanResult | disabled/loading when available | plan shown | unsupported | Owner/Advanced |
| Create backup | Backup button | `BackupService`, `TaskQueueService` | scope, include_index flag | task_id | task indicator | backup result summary | task failed | Owner/Advanced |
| Create snapshot | Snapshot button | `SnapshotService`, `TaskQueueService` | scope/reason | task_id/snapshot id | progress | snapshot ready | snapshot failed | Owner/Advanced |
| Build restore plan | Restore Plan button | `RestorePlanService` | backup/snapshot id, target workspace | RestorePlan | plan loading | conflicts/validation shown | conflict/error | Owner/Advanced |
| View task log | Task row click | `TaskQueueService` | task_id | task detail/log | log loading | log panel | log unavailable | Owner/Advanced |
| Cancel task | Cancel button | `TaskQueueService` | task_id | cancel_requested=true | cancelling | cancelled at checkpoint | cannot cancel | Owner/Advanced |
| Retry task | Retry button | `TaskQueueService` | failed/cancelled task_id | new task_id with lineage | retry pending | running | retry blocked | Owner/Advanced |
| Cleanup plan | Cleanup action | `TaskQueueService` | task history scope | cleanup PlanResult | plan loading | cleanup candidates shown | blocked plan | Owner/Advanced |

## 9. Long-running Task UX

Long-running operations include:

- index
- reindex
- audit
- backup_create
- secret-scan
- dedupe
- conflicts
- benchmark
- maintenance
- future restore
- future archive
- future template apply
- future destructive maintenance

Task creation:

- Every long-running action returns a `task_id` immediately.
- UI remains interactive after task creation.
- StatusBar shows a task activity indicator.
- Task Center receives the task in `pending` or `running`.

Task progress:

- Show `status`, `progress_percent`, current step, elapsed time, and cancel availability.
- Progress events must be read from `TaskQueueService`.
- Progress event ordering must respect monotonic `sequence`.
- Navigation away from a task screen must not cancel the task.

Task logs:

- Task detail opens a read-only log panel through `TaskQueueService`.
- GUI must not read `.kb/tasks/` directly.
- Logs support tail mode, error summary, and copyable diagnostics.

Cancellation:

- Cancellation is cooperative.
- Cancelling a running task only sets `cancel_requested=true`.
- The task stops at safe checkpoints.
- Cancelling a partial or mutation-adjacent task requires confirmation.

Retry:

- Retry is available only for `failed` or `cancelled` tasks.
- Retry must preserve `retry_of`, `retry_root`, or equivalent lineage.
- Retry must not bypass future task blocked rules.

Cleanup-plan:

- Cleanup is plan-first.
- `task-cleanup-plan` shows candidates and validation.
- Cleanup execute remains disabled unless a future safe execute service supports it.

Failed state:

- Show failed step, service error, log entry point, retry availability, and partial result if present.
- Partial success must be explicit and must not be shown as full success.

Task history:

- Task history is paginated and filterable.
- Large task history must use pagination or virtualized rows.
- Required columns: task_id, type, status, progress, started_at, elapsed_ms, result_summary, retry lineage.

## 10. Safe Mutation UX

Current supported execute:

- category `display_name`
- category `description`
- config-only mutation in `config/categories.yaml`

Plan view:

- `PlanCard` shows plan id/type, `dry_run`, `would_modify`, `blocked`, blockers, affected files, config diff, validation commands, rollback/restore recommendation, and unsupported actions.
- Blocked plan is a successful plan result with execute disabled.

Snapshot required banner:

- Any execute-capable mutation requires a valid local snapshot.
- If missing or stale, the UI blocks approval and offers snapshot creation through `SnapshotService` and `TaskQueueService`.

Approval gate:

- User must explicitly approve the exact plan.
- Approval binds to the plan hash and snapshot id.
- Approval expires after plan changes, navigation reset, or configured timeout.

Task execution state:

- `SafeMutationService` execute actions must run through `TaskQueueService`.
- The screen shows non-blocking progress.
- Task Center remains the source of truth for task state.

Result summary:

- Show changed config key, task id, validation result, log link, and restore-plan entry.
- Rollback is not direct. The UI offers a restore-plan entry through `RestorePlanService`.

Unsupported destructive actions:

- archive execute: disabled/future.
- delete execute: disabled/future.
- merge execute: disabled/future.
- template apply execute: disabled/future.
- restore execute: disabled/future.
- workspace upgrade execute: disabled/future.
- Disabled actions must explain: `Execute not supported in current version`.

## 11. Data Safety UX

All write-capable GUI flows must use this chain:

1. Plan first:
   - UI calls plan-only service.
   - UI renders `PlanResult`.
   - `actions` are planned actions, not executed actions.
   - Blocked plans are shown as valid but non-executable.
2. Snapshot first:
   - UI checks `SnapshotService`.
   - Missing or stale snapshot blocks approval.
   - Snapshot creation runs through `TaskQueueService`.
3. Approval:
   - User reviews affected files, risk level, validation commands, reversibility, and unsupported actions.
   - Approval binds to exact plan hash and snapshot id.
4. Task queue execute:
   - Execute-capable actions run through `TaskQueueService`.
   - UI stays interactive.
5. Validation result:
   - Service result and validation output are summarized.
   - Validation failure prevents success state.
6. Restore-plan option:
   - UI offers `RestorePlanService`.
   - Restore execute remains disabled/future.

## 12. Design System Strategy

Semantic color tokens:

```json
{
  "color.surface.app": "#F6F7F9",
  "color.surface.panel": "#FFFFFF",
  "color.surface.subtle": "#EEF1F5",
  "color.border.default": "#D8DEE8",
  "color.text.primary": "#1F2937",
  "color.text.secondary": "#5B6678",
  "color.text.muted": "#7A8494",
  "color.action.primary.bg": "#2563EB",
  "color.action.primary.text": "#FFFFFF",
  "color.status.ready": "#15803D",
  "color.status.warning": "#B45309",
  "color.status.danger": "#B91C1C",
  "color.status.info": "#0369A1",
  "color.status.disabled": "#9CA3AF",
  "color.risk.quarantine": "#7F1D1D",
  "color.layer.formal": "#166534",
  "color.layer.distilled": "#854D0E",
  "color.layer.raw": "#475569"
}
```

App shell layout tokens:

```json
{
  "layout.window.min.width": "1100px",
  "layout.window.min.height": "720px",
  "layout.window.preferred.width": "1440px",
  "layout.window.preferred.height": "900px",
  "layout.sidebar.width": "260px",
  "layout.sidebar.collapsed.width": "64px",
  "layout.inspector.width": "360px",
  "layout.commandbar.height": "52px",
  "layout.statusbar.height": "28px",
  "layout.content.maxWidth": "1680px"
}
```

Density and spacing rules:

```json
{
  "space.1": "4px",
  "space.2": "8px",
  "space.3": "12px",
  "space.4": "16px",
  "space.5": "20px",
  "space.6": "24px",
  "space.panel": "16px",
  "space.screen": "20px",
  "space.table.row.compact": "32px",
  "space.table.row.default": "40px"
}
```

Typography hierarchy:

```json
{
  "font.family.ui": "Segoe UI, Inter, system-ui, sans-serif",
  "font.size.caption": "12px",
  "font.size.body": "14px",
  "font.size.bodyLarge": "16px",
  "font.size.title": "20px",
  "font.size.screenTitle": "24px",
  "font.weight.regular": "400",
  "font.weight.medium": "500",
  "font.weight.semibold": "600",
  "lineHeight.body": "1.45"
}
```

Component categories:

- Shell: `AppShell`, `SidebarNav`, `CommandBar`, `StatusBar`.
- Data display: `DataTable`, `ResultList`, `MetadataBadge`, `LayerBadge`, `RiskBadge`.
- Document: `DocumentPreview`, `InspectorPanel`.
- Workflow: `PlanCard`, `SnapshotBanner`, `ApprovalDialog`, `ProgressPanel`.
- Feedback: `EmptyState`, `ErrorState`, `ConfirmDialog`.
- Task: `TaskActivityPanel`, `TaskRow`, `TaskLogViewer`.

## 13. Component System

| Component | Category | Purpose / Inputs | Required States | Adaptive Behavior |
|---|---|---|---|---|
| AppShell | Shell | workspace status, route, panel state | no workspace, loading, ready, degraded | sidebar/inspector collapsible; status bar fixed |
| SidebarNav | Shell | nav items, role visibility, badges | active, hover, collapsed, disabled | 260px expanded, 64px collapsed |
| CommandBar | Shell | workspace switch, global search, commands | focused, searching, disabled | preserves search at min width |
| StatusBar | Shell | workspace/index/task/backup indicators | ready, warning, danger, running | compact labels at 1100px |
| TaskActivityPanel | Task | task list summary, filters | running, failed, empty | drawer or full Task Center |
| SearchBox | Input | query, filters, submit | idle, focused, loading, error | min 320px, grows in CommandBar |
| ResultList | Data | virtualized result items | loading, empty, selected, error | virtual rows; no render-all |
| DocumentPreview | Document | document id/body/metadata from service | loading, opened, error, restricted | scrollable content; long lines wrap |
| MetadataBadge | Data | status/confidence/source_type | default, warning, danger | fixed height; text truncates with tooltip |
| LayerBadge | Data | layer value | formal, raw, distilled, quarantine | semantic colors; raw/distilled warning |
| RiskBadge | Data | risk level/blocker count | low, medium, high, blocked | used in plan/review/archive |
| PlanCard | Workflow | PlanResult, actions, blockers | clean, blocked, warning, invalid | actions list scrolls internally |
| SnapshotBanner | Workflow | snapshot status, required flag | missing, stale, ready, creating | pins above approval area |
| ApprovalDialog | Workflow | plan hash, snapshot id, risk summary | pending, expired, approved, denied | modal max-height with internal scroll |
| ProgressPanel | Task | task_id, progress, current step | pending, running, failed, cancelled | embeds in screen and Task Center |
| EmptyState | Feedback | title, reason, primary service action | neutral, blocked, permission | no fake content; action optional |
| ErrorState | Feedback | error code, message, retry action | recoverable, fatal, permission | includes service source |
| ConfirmDialog | Feedback | action summary, affected scope | confirm, disabled, destructive | explicit confirmation for risk |
| DataTable | Data | columns, rows, sorting, filters | loading, empty, selected, error | pagination + virtualized body |
| InspectorPanel | Shell/Detail | selected entity details | empty, document, task, plan, category | 360px; collapses to drawer |

## 14. Adaptive Desktop Layout

Target sizes:

- Minimum window: `1100x720`
- Preferred: `1440x900`
- Large: `1920x1080`
- Ultra-wide: `2560x1440`

Layout rules:

- Root grid rows: `CommandBar 52px / Main 1fr / StatusBar 28px`.
- Root grid columns: `Sidebar 260px or 64px / Content minmax(0, 1fr) / Inspector 360px optional`.
- At minimum width, collapse inspector first, then allow sidebar icon-only mode.
- At preferred width, show sidebar expanded and inspector available.
- At large and ultra-wide sizes, cap main content at `1680px` and use additional table columns instead of stretching text lines.
- On small-height screens, keep command/status bars visible and scroll the screen content region.
- Modals use `max-height: calc(100vh - 96px)` with internal scrolling.
- Lists must use pagination or virtual scrolling.
- Search results must not render all rows at once.
- Task history must not render all rows at once.
- UI main thread must not run index/audit/backup/restore/archive/template/secret-scan tasks.

## 15. State Coverage

| State | Required UI Behavior |
|---|---|
| no workspace selected | Workspace Gate; navigation disabled except settings/help-safe entries |
| index missing | Dashboard/Search show missing index; offer background index task only through service; no auto-index |
| index ready | Search enabled; formal layers default |
| index stale | Warning badge; search allowed with stale indicator |
| index partial | Partial indicator; affected filters marked incomplete |
| search empty | EmptyState explains no indexed formal result |
| review queue empty | EmptyState with no fake review cards |
| task running | StatusBar activity + TaskActivityPanel progress |
| task failed | StatusBar danger badge; Task Center error/log/retry |
| backup missing | Backup & Sync warning; safe execute blocked |
| snapshot required | SnapshotBanner blocks approval |
| approval expired | ApprovalDialog resets; user must re-approve current plan |
| blocked plan | PlanCard shows blockers; execute disabled |
| unsupported execute action | Button disabled with current-version reason |
| secret-scan warning | Dashboard/Audit warning; affected docs are not auto-modified |
| restore-plan conflict | RestorePlan view shows conflicts; restore execute disabled |

## 16. Implementation Phases

| Phase | Scope | Must Include | Must Not Include |
|---|---|---|---|
| GUI Phase 0: Architecture Contract | This document | IA, roles, service map, states, tokens, phases | code, packaging, framework selection |
| GUI Phase 1: Read-only MVP | Shell + Dashboard + Search + Library + DocumentPreview + task status read path | startup/search/category/library/document open/task status read path through services | category display_name/description execute, SafeMutation execute, destructive execute, direct Markdown/SQLite, CLI shelling |
| GUI Phase 2: Plan-only mutation UI | Review, Archive, Organize, Template, Settings plans | plan views, blocked plans, unsupported execute states | archive/delete/merge/template apply/restore execute |
| GUI Phase 3: Backup/Snapshot + Task Center | backup, snapshot, task history/log/cancel/retry/cleanup-plan | `BackupService`, `SnapshotService`, `RestorePlanService`, `TaskQueueService` | restore execute |
| GUI Phase 4: Safe category settings execute | category display_name/description execute | plan + snapshot + approval + `SafeMutationService` + `TaskQueueService` + result summary | path rename, category_id/path/slug edit, Markdown writes, SQLite schema changes |
| GUI Phase 5: Package as EXE | installer/runtime hardening | workspace data protection, service API integration | storing user knowledge in install dir, Git as required dependency |

## 17. Acceptance Criteria

- GUI does not directly read or write Markdown.
- GUI does not directly read or write SQLite.
- GUI does not assemble CLI command strings as its main integration mechanism.
- All data access and mutation intent go through service/core API.
- Startup only reads workspace/index metadata and does not scan `knowledge/`.
- Startup does not automatically trigger index/reindex.
- Markdown body reads only happen through `DocumentService.open_document` for one explicitly opened document.
- Search, Category, Review, and Archive lists use service-backed SQLite metadata / FTS hot paths.
- Long-running tasks run through `TaskQueueService`.
- The UI main thread does not run index, audit, backup, restore, secret-scan, archive, template apply, benchmark, or maintenance.
- Destructive actions are disabled unless a service explicitly supports them.
- Current supported execute mutation is limited to category `display_name` and `description` config-only actions.
- `SafeMutationService` execute actions must run through `TaskQueueService`.
- Archive/delete/merge/template apply/restore execute actions are future/disabled.
- Plan, snapshot, approval, task, validation, and restore-plan chain is visible for supported safe mutations.
- 10K+ result/task/archive/review lists use pagination or virtual scrolling.
- Raw and distilled content visibly states `未经审核，不能作为正式项目规则`.
- `review_required=true`, quarantine, rejected, and deprecated content must not be treated as formal project decision material.
- Backup/Snapshot is the default recovery mechanism.
- Git remains optional.
- App Shell includes sidebar, command/search bar, main content, optional inspector, status bar, task activity indicator, index status indicator, and backup/snapshot status indicator.
- All main screens define loading, empty, error, permission/disabled, and long-content states.
