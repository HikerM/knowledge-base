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
  - view review queues under 审核, maintenance subviews under 维护, task history, and backup/snapshot status.
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
  - Search, Knowledge Library, Review, and Maintenance metadata list screens must use service-backed SQLite metadata / FTS hot paths through services.
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
| Owner / Local User | All main navigation items, workspace state, formal layers, review subviews, maintenance subviews, tasks, backup/snapshot status | Search, open document, inspect review queues, create backup/snapshot task, create plans, approve supported safe category mutation in later phases | Only service-supported safe mutations with plan + snapshot + approval + TaskQueue | Destructive future actions disabled; no direct Markdown/SQLite/Git writes |
| Reviewer | Home summary, Search, Knowledge Library, Review subviews, document preview, review metadata | Open documents, inspect source_url/source_file/review_required/validation metadata, create future promote plan when service exists | No direct promote in current GUI phases | Raw/distilled are marked unreviewed and cannot be treated as formal project rules |
| Reader | Home summary, Search, Knowledge Library formal subviews, DocumentPreview | Formal search and explicit document open | No writes | Review, Maintenance, Settings, and task execute actions hidden or read-only |
| Advanced User | Owner visibility plus Task Center, Maintenance, Settings, optional Git status when service exists | Run safe long-running tasks, inspect logs, retry failed tasks, create restore plans | Still limited to service-supported safe mutation execute | Cannot bypass plan/snapshot/approval/TaskQueue; unsupported destructive execute remains disabled |

## 3. Information Architecture

```text
App
├── 首页
├── 搜索
├── 知识库
│   ├── 全部正式知识
│   ├── Rules
│   ├── Checklists
│   └── Snippets
├── 审核
│   ├── Raw Inbox
│   ├── Distilled Review
│   └── Future Promote Plan
├── 任务中心
├── 维护
│   ├── 归档
│   ├── 整理中心
│   ├── 备份与同步
│   └── 审计中心
└── 设置
    ├── 分类设置
    ├── 模板管理
    ├── 来源管理
    └── App / Workspace 设置
```

Primary navigation is intentionally small. The left sidebar is the only main navigation surface:

- 首页
- 搜索
- 知识库
- 审核
- 任务中心
- 维护
- 设置

Merged module rules:

- 归档、整理中心、备份与同步、审计中心 belong under 维护.
- 模板管理、来源管理、分类设置 belong under 设置.
- Raw Inbox and Distilled Review are subviews under 审核.
- Rules / Checklists / Snippets are subviews under 知识库.
- The top bar must never duplicate these main navigation entries.

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

- Left sidebar is the sole main navigation system.
- TopBar is not navigation. It only exposes workspace switch, global search / command search, index status, task status, backup status, and settings/user entry.
- Main content area for screen content.
- Optional right inspector panel for selected document, plan, task, category, or metadata detail.
- Bottom status bar for workspace, index, task, backup/snapshot, and warning indicators.

## 4. Navigation Model

Desktop app shell:

```text
┌────────────────────────────────────────────────────────────┐
│ TopBar: workspace | global/command search | statuses | user  │
├──────────────┬───────────────────────────────┬─────────────┤
│ SidebarNav   │ Main Content Area             │ Inspector   │
│ collapsible  │ screen/router content         │ collapsible │
├──────────────┴───────────────────────────────┴─────────────┤
│ StatusBar: workspace | index | tasks | snapshot | warnings  │
└────────────────────────────────────────────────────────────┘
```

- Left sidebar:
  - is the only main navigation.
  - includes only 首页, 搜索, 知识库, 审核, 任务中心, 维护, 设置.
  - exposes subviews inside the active module, not as competing top-level destinations.
  - supports expanded and collapsed states.
  - displays module warning badges, blocked states, and active route.
- Top bar:
  - must not act as primary navigation.
  - includes only workspace switch, global search / command search, index status indicator, task status indicator, backup status indicator, and settings/user entry.
  - provides default formal-layer search and command search.
  - command entries must map to service actions.
  - must not shell out by building CLI command strings.
- Main content area:
  - uses screen-local scroll containers.
  - uses paginated or virtualized lists for large result sets.
  - does not render all search results or task rows at once.
- Right inspector panel:
  - optional, collapsible, and collapsed by default.
  - on 首页, defaults to a compact workspace health summary.
  - on 搜索、知识库、审核、任务中心, expands only after the user selects an item.
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
| 首页 | Provide a compact workspace health overview without exposing every feature entry | App startup / sidebar | All | Service summaries | `WorkspaceStatusService`, `IndexMetadataService`, `TaskQueueService`, `BackupService`, `SnapshotService`, `ReviewQueueService` summary | Read-only in Phase 1; recommended actions only route to existing screens or service-backed task creation in later phases | Future background task shortcuts only where service supports them | None in Phase 1 | no workspace, index missing/stale/partial, backup missing, task failed, review count unavailable | Phase 1 |
| 搜索 | Search formal knowledge and open explicit documents | Sidebar / TopBar search submit | All | SQLite FTS via service | `SearchService`, `DocumentService.open_document` | Search read-only; open one document through service | None | None | empty query, no result, index missing/stale, search error | Phase 1 |
| 知识库 | Browse indexed formal knowledge with subviews for all formal, Rules, Checklists, Snippets | Sidebar | All by role | SQLite metadata via service | `CategoryService`, `SearchService`, `DocumentService` | Read-only lists; explicit document open only | None | None | empty category, empty layer, loading page, metadata error | Phase 1 |
| 审核 | Inspect unreviewed Raw Inbox and Distilled Review subviews | Sidebar | Owner, Reviewer | Review metadata via service | `ReviewQueueService`, `DocumentService`, future promote plan service | Read-only plus future promote plan-only; no direct promote execute | Future distill/promote task disabled until service exists | Future confirmation required; current execute disabled | queue empty, raw empty, distilled empty, review_required, quarantine warning, load error | Phase 2 |
| 任务中心 | Show task progress, logs, retry, cancellation, cleanup plans | Sidebar / status indicator | Owner, Advanced User; Reader summary | Task records through service | `TaskQueueService` | Read task history; service-backed cancel/retry/cleanup-plan | All long tasks | Cancel confirmation for partial tasks | no tasks, running, failed, cancelled, log missing | Phase 3 |
| 维护 | House archive, organize center, backup/sync, and audit center subviews | Sidebar | Owner, Advanced User | Archive metadata, backup/snapshot catalog, task summaries, plan service results | `ArchiveMetadataService`, `BackupService`, `SnapshotService`, `RestorePlanService`, `TaskQueueService`, `IndexMetadataService`, future audit/archive/organize plan services | Plan-only or task-backed where service supports it; restore/archive execute disabled | backup_create, audit/index tasks where supported; future archive/restore disabled | Backup task confirmation; destructive execute disabled | archive empty, backup missing, snapshot required, audit warning, blocked plan, restore conflict | Phase 3 |
| 设置 | House category settings, template manager, source manager, and app/workspace settings | Sidebar / top settings entry | Owner, Advanced User | Category/template/source/workspace config through services | `CategoryService`, `CategoryPlanService`, `TemplatePlanService`, `WorkspacePlanService`, future SettingsService / Source service, `SafeMutationService`, `SnapshotService`, `TaskQueueService` | Phase 1: not exposed except read-only shell settings; Phase 2: plan-only; Phase 4: category display_name/description execute only | Category safe mutation execute must run through TaskQueue in Phase 4 | Snapshot + approval required for supported execute; unsupported destructive actions disabled | service unavailable, blocked plan, approval expired, validation error, unsupported execute | Phase 2 / Phase 4 |

## 6. GUI Phase 1 Read-only MVP Boundary

GUI Phase 1 is intentionally limited to read-only paths:

- Startup status read path through `WorkspaceStatusService` and `IndexMetadataService`.
- 首页 read path for index status, pending review count, backup status, task status, recent tasks, recommended actions, and quick entries.
- Search read path through `SearchService`.
- Knowledge Library read path through `CategoryService` and indexed metadata services.
- Document open read path through `DocumentService.open_document`, one explicit document at a time.
- Task status read path through `TaskQueueService` for status/progress/history visibility only.

首页 must stay compact. It must not lay out every product function as a card grid or duplicate the sidebar.

GUI Phase 1 must not expose category `display_name` / `description` execute.

GUI Phase 1 must not expose:

- full Maintenance execute workflows.
- full Settings mutation workflows.
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
4. 首页 shows only index status, pending review count, backup status, task status, recent tasks, recommended actions, and quick entries.
5. The top bar shows status indicators, but it does not expose main navigation.
6. UI does not scan `knowledge/`, read Markdown bodies, or auto-index.

### Formal Search Workflow

1. User enters query in `SearchBox`.
2. UI calls `SearchService` with default formal layers: `rules`, `checklists`, `snippets`.
3. Result list shows layer, status, confidence, source_type, snippet, and file path.
4. User opens one result.
5. UI calls `DocumentService.open_document`.
6. Document body appears in `DocumentPreview`.

### Review Visibility Workflow

1. Reviewer opens 审核.
2. Reviewer switches between Raw Inbox and Distilled Review subviews inside 审核.
3. UI calls `ReviewQueueService`.
4. Raw and distilled items show `未经审核，不能作为正式项目规则`.
5. Opening an item uses `DocumentService.open_document`.
6. Promote remains future plan-only and execute disabled until the service exists.

### Category Safe Mutation Workflow

1. User opens 设置 > 分类设置 in Phase 4 or later.
2. User edits category `display_name` or `description`.
3. UI calls `CategoryPlanService`.
4. UI shows `PlanCard`, affected config file, validation commands, blockers, and risk.
5. UI requires valid local snapshot through `SnapshotService`.
6. User approves the exact plan.
7. UI calls `SafeMutationService` execute.
8. `SafeMutationService` execute action runs through `TaskQueueService`.
9. UI shows task progress, task log, result summary, validation result, and restore-plan entry.

### Backup / Snapshot Workflow

1. User opens 维护 > 备份与同步.
2. UI calls `BackupService` or `SnapshotService` through the service boundary.
3. Long-running creation runs through `TaskQueueService`.
4. Task Center shows progress, logs, result summary, and failure recovery.

### Restore Planning Workflow

1. User selects backup or snapshot.
2. UI calls `RestorePlanService`.
3. UI shows conflicts, would-create/would-overwrite lists, validation commands, and blockers.
4. Restore execute remains disabled/future.

### Archive / Organize Workflow

1. User opens 维护 for organize/archive plans or 设置 for template plans.
2. UI calls the corresponding plan service.
3. UI shows plan-only actions.
4. Execute remains disabled unless a future service explicitly supports it with plan + snapshot + approval + TaskQueue.

## 8. Service Mapping

| UI Action | Trigger | Service | Input | Output | Loading | Success | Error | Permission |
|---|---|---|---|---|---|---|---|---|
| Load app status | App startup / 首页 | `WorkspaceStatusService`, `IndexMetadataService` | workspace context | workspace + index status | shell skeleton | 首页 health summary visible | no workspace / service error | All |
| Load home summary | 首页 | `WorkspaceStatusService`, `IndexMetadataService`, `TaskQueueService`, `BackupService`, `SnapshotService`, `ReviewQueueService` | workspace context | compact health cards, recent tasks, pending review count | card skeletons | compact MVP overview | partial service unavailable | All |
| Search formal knowledge | TopBar search submit or 搜索 screen submit | `SearchService` | query, filters, top_k, formal layers | result page | inline spinner | virtualized result list | index missing/stale/error | All |
| Open document | result click | `DocumentService.open_document` | document id/path from service result | single document body + metadata | preview loading | preview rendered | open denied/missing | Role-based |
| Browse formal library | 知识库 | `CategoryService` | category_id, formal subview, layer/status filters, page cursor | metadata list | table skeleton | paged/virtualized list | category missing/service error | All by role |
| Plan category change | 设置 > 分类设置 save | `CategoryPlanService` | category_id, new display_name/description | PlanResult | plan loading | PlanCard shown | blocked plan | Owner/Advanced |
| Execute category display_name/description | 设置 > 分类设置 approval confirm | `SafeMutationService`, `TaskQueueService` | approved plan, snapshot id, approval token | task_id + MutationResult summary | task/progress | result summary | approval expired/validation failed/task failed | Owner/Advanced |
| Load review queue | 审核 > Raw Inbox / Distilled Review | `ReviewQueueService` | layer/status/page | review items | skeleton | queue list | service/index error | Owner/Reviewer |
| Future promote plan | 审核 promote plan button | future promote plan service | distilled id + review metadata | PlanResult | disabled/loading when available | plan shown | unsupported | Owner/Reviewer |
| Load archive metadata | 维护 > 归档 | `ArchiveMetadataService` | status/page/filter | archive/trash/quarantine list | table skeleton | list rendered | metadata error | Owner/Advanced |
| Future archive plan | 维护 > 归档 plan action | future archive plan service | document ids/scope | PlanResult | disabled/loading when available | plan shown | unsupported | Owner/Advanced |
| Create backup | 维护 > 备份与同步 button | `BackupService`, `TaskQueueService` | scope, include_index flag | task_id | task indicator | backup result summary | task failed | Owner/Advanced |
| Create snapshot | 维护 > 备份与同步 snapshot button | `SnapshotService`, `TaskQueueService` | scope/reason | task_id/snapshot id | progress | snapshot ready | snapshot failed | Owner/Advanced |
| Build restore plan | 维护 > 备份与同步 restore-plan button | `RestorePlanService` | backup/snapshot id, target workspace | RestorePlan | plan loading | conflicts/validation shown | conflict/error | Owner/Advanced |
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
  "layout.topbar.height": "52px",
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

- Shell: `AppShell`, `SidebarNav`, `TopBar`, `StatusBar`.
- Data display: `DataTable`, `ResultList`, `MetadataBadge`, `LayerBadge`, `RiskBadge`.
- Document: `DocumentPreview`, `InspectorPanel`.
- Workflow: `PlanCard`, `SnapshotBanner`, `ApprovalDialog`, `ProgressPanel`.
- Feedback: `EmptyState`, `ErrorState`, `ConfirmDialog`.
- Task: `TaskActivityPanel`, `TaskRow`, `TaskLogViewer`.

## 13. Component System

| Component | Category | Purpose / Inputs | Required States | Adaptive Behavior |
|---|---|---|---|---|
| AppShell | Shell | workspace status, route, panel state | no workspace, loading, ready, degraded | sidebar/inspector collapsible; status bar fixed |
| SidebarNav | Shell | only seven main nav items, role visibility, badges | active, hover, collapsed, disabled | 260px expanded, 64px collapsed |
| TopBar | Shell | workspace switch, global search / command search, index/task/backup indicators, settings/user entry | focused, searching, status-warning, disabled | preserves search and status indicators at min width; never renders main nav links |
| StatusBar | Shell | workspace/index/task/backup indicators | ready, warning, danger, running | compact labels at 1100px |
| TaskActivityPanel | Task | task list summary, filters | running, failed, empty | drawer or full Task Center |
| SearchBox | Input | query, filters, submit | idle, focused, loading, error | min 320px, grows in TopBar or 搜索 screen |
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
| InspectorPanel | Shell/Detail | selected entity details or compact workspace health on 首页 | collapsed, empty, workspace-health, document, task, plan, category | collapsed by default; 360px when expanded; collapses to drawer |

## 14. Adaptive Desktop Layout

Target sizes:

- Minimum window: `1100x720`
- Preferred: `1440x900`
- Large: `1920x1080`
- Ultra-wide: `2560x1440`

Layout rules:

- Root grid rows: `TopBar 52px / Main 1fr / StatusBar 28px`.
- Root grid columns: `Sidebar 260px or 64px / Content minmax(0, 1fr) / Inspector 360px optional`.
- At minimum width, inspector stays collapsed by default, then sidebar may collapse to icon-only mode.
- At preferred width, show sidebar expanded; inspector remains collapsed until the active screen or selected item needs detail.
- On 首页, the inspector shows only compact workspace health when expanded.
- On 搜索、知识库、审核、任务中心, selecting an item expands the inspector with item detail.
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
| index missing | 首页/搜索 show missing index; offer background index task only through service; no auto-index |
| index ready | Search enabled; formal layers default |
| index stale | Warning badge; search allowed with stale indicator |
| index partial | Partial indicator; affected filters marked incomplete |
| search empty | EmptyState explains no indexed formal result |
| review queue empty | EmptyState with no fake review cards |
| task running | StatusBar activity + TaskActivityPanel progress |
| task failed | StatusBar danger badge; Task Center error/log/retry |
| backup missing | TopBar status and 维护 > 备份与同步 warning; safe execute blocked |
| snapshot required | SnapshotBanner blocks approval |
| approval expired | ApprovalDialog resets; user must re-approve current plan |
| blocked plan | PlanCard shows blockers; execute disabled |
| unsupported execute action | Button disabled with current-version reason |
| secret-scan warning | 首页/维护 warning; affected docs are not auto-modified |
| restore-plan conflict | RestorePlan view shows conflicts; restore execute disabled |

## 16. Implementation Phases

| Phase | Scope | Must Include | Must Not Include |
|---|---|---|---|
| GUI Phase 0: Architecture Contract | This document | IA, roles, service map, states, tokens, phases | code, packaging, framework selection |
| GUI Phase 1: Read-only MVP | AppShell + TopBar + seven-item Sidebar + 首页 + 搜索 + 知识库 + DocumentPreview + task status read path | startup/search/knowledge-library/document open/task status read path through services; compact home health summary; inspector collapsed by default | full 审核 workflows, Maintenance execute workflows, Settings mutation workflows, category display_name/description execute, SafeMutation execute, destructive execute, direct Markdown/SQLite, CLI shelling |
| GUI Phase 2: Review + Plan-only UI | 审核 plus plan-only surfaces under 维护 and 设置 | Raw Inbox / Distilled Review subviews, plan views, blocked plans, unsupported execute states | archive/delete/merge/template apply/restore execute |
| GUI Phase 3: Maintenance + Task Center | 任务中心 plus 维护 subviews for backup/snapshot, archive metadata, organize plans, audit status | `BackupService`, `SnapshotService`, `RestorePlanService`, `ArchiveMetadataService`, `TaskQueueService`, log/cancel/retry/cleanup-plan UX | restore/archive/delete/merge/template apply execute |
| GUI Phase 4: Safe category settings execute | 设置 > 分类设置 display_name/description execute | plan + snapshot + approval + `SafeMutationService` + `TaskQueueService` + result summary | path rename, category_id/path/slug edit, Markdown writes, SQLite schema changes |
| GUI Phase 5: Package as EXE | installer/runtime hardening | workspace data protection, service API integration | storing user knowledge in install dir, Git as required dependency |

## 17. Acceptance Criteria

- GUI does not directly read or write Markdown.
- GUI does not directly read or write SQLite.
- GUI does not assemble CLI command strings as its main integration mechanism.
- All data access and mutation intent go through service/core API.
- Startup only reads workspace/index metadata and does not scan `knowledge/`.
- Startup does not automatically trigger index/reindex.
- Markdown body reads only happen through `DocumentService.open_document` for one explicitly opened document.
- Search, Knowledge Library, Review, and Maintenance metadata lists use service-backed SQLite metadata / FTS hot paths.
- TopBar is not a main navigation surface.
- TopBar only contains workspace switch, global search / command search, index status indicator, task status indicator, backup status indicator, and settings/user entry.
- Sidebar is the only main navigation surface.
- Sidebar top-level navigation contains only 首页, 搜索, 知识库, 审核, 任务中心, 维护, 设置.
- 归档、整理中心、备份与同步、审计中心 are subviews under 维护.
- Template Manager, Sources, and Category Settings are subviews under 设置.
- Raw Inbox and Distilled Review are subviews under 审核.
- Rules / Checklists / Snippets are subviews under 知识库.
- 首页 stays compact and only shows index status, pending review count, backup status, task status, recent tasks, recommended actions, and quick entries.
- 首页 must not duplicate every feature entry or become a full admin dashboard.
- Inspector is collapsible and collapsed by default.
- 首页 inspector shows compact workspace health only.
- 搜索、知识库、审核、任务中心 expand inspector details only after item selection.
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
- App Shell includes sidebar, TopBar, main content, optional inspector, status bar, task activity indicator, index status indicator, and backup/snapshot status indicator.
- All main screens define loading, empty, error, permission/disabled, and long-content states.
