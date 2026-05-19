# GUI Phase 1 Read-only MVP Screen Contract

This document is the Phase 1 Read-only MVP Screen Contract for the future Windows desktop GUI of `personal-knowledge-base`.

It narrows the Phase 0 Product UI Architecture Contract into an implementable read-only screen contract. It is not a GUI implementation, packaging plan, or framework selection. Do not implement screens, choose Tauri/Electron/PySide/WinUI, or package an EXE from this document alone.

Phase 1 must stay read-only. It must prove the service boundary, startup path, hot-index read path, document-open path, task-status visibility, and adaptive desktop shell without introducing mutation risk.

## 1. Phase 1 Scope

Phase 1 includes only:

- 工作区入口
- 首页
- 搜索
- 知识库
- 文档预览
- 任务中心摘要
- 设置入口

Phase 1 must exclude:

- category `display_name` / `description` execute.
- archive/delete/merge/template apply/restore execute.
- RSS.
- vector search.
- real mutation UI.
- destructive actions.
- editable settings forms.
- cleanup execute.
- direct Markdown read/write.
- direct SQLite read/write.
- CLI command string construction as the GUI integration mechanism.

Phase 1 allowed service paths:

- Startup: `WorkspaceStatusService`, `IndexMetadataService`.
- 首页 summary: `WorkspaceStatusService`, `IndexMetadataService`, `TaskQueueService`, `BackupService`, `SnapshotService`, `ReviewQueueService` summary.
- 搜索: `SearchService`.
- 知识库: `CategoryService`, indexed metadata returned by services.
- 文档预览: `DocumentService.open_document`, one explicit document at a time.
- 任务中心摘要: `TaskQueueService` read-only status/progress/log path.
- 设置入口: read-only service-backed entry metadata only.

Phase 1 forbidden service exposure:

- Do not expose `SafeMutationService` execute actions.
- Do not expose `CategoryPlanService` write approval or execute flows.
- Do not expose category `display_name` / `description` execute even though those actions exist in the backend.
- Do not expose archive/delete/merge/template apply/restore execute.
- Do not expose promote execute.
- Do not expose future RSS/vector capabilities.

## 2. Shared App Shell

Phase 1 keeps the simplified Phase 0 desktop shell.

```text
┌────────────────────────────────────────────────────────────┐
│ TopBar: workspace | global search | index/task/backup | user │
├──────────────┬───────────────────────────────┬─────────────┤
│ SidebarNav   │ Main Content Area             │ Inspector   │
│ collapsible  │ screen content                │ collapsed   │
├──────────────┴───────────────────────────────┴─────────────┤
│ StatusBar: workspace | index | tasks | backup | warnings     │
└────────────────────────────────────────────────────────────┘
```

TopBar is not main navigation. It contains only:

- workspace switch.
- global search / command search.
- index status indicator.
- task status indicator.
- backup status indicator.
- settings/user entry.

SidebarNav is the only main navigation. Phase 1 visible entries:

- 首页
- 搜索
- 知识库
- 任务中心
- 设置

Phase 1 may show disabled future entries only if the product needs continuity with Phase 0:

- 审核: disabled or hidden, because full review workflows are outside Phase 1.
- 维护: disabled or hidden, because backup/restore/archive/audit screens are outside Phase 1.

InspectorPanel rules:

- Collapsed by default.
- On 首页, it may show compact workspace health when expanded.
- On 搜索 and 知识库, selecting a row opens 文档预览 in the inspector or in the main split preview.
- On 任务中心摘要, selecting a task opens read-only task detail/log in the inspector.
- At minimum width, inspector becomes a drawer.

StatusBar rules:

- Always visible.
- Shows workspace, index, task, backup/snapshot, and warning indicators.
- Must not expose execute actions directly.

## 3. Shared Data Rules

Phase 1 must use service-provided data only.

- GUI must not read Markdown files directly.
- GUI must not write Markdown files.
- GUI must not query SQLite directly.
- GUI must not mutate SQLite schema.
- GUI must not build CLI command strings for integration.
- Startup must not scan `knowledge/`, read Markdown bodies, compute hashes, or automatically trigger index/reindex.
- Search and list screens must use SQLite metadata / FTS through services.
- Markdown body is read only when the user explicitly opens one document through `DocumentService.open_document`.
- Lists must use pagination or virtual scrolling and must not render all rows at once.
- UI main thread must not run index, audit, backup, restore, archive, template apply, secret-scan, benchmark, or maintenance.

## 4. Screen Contracts

### 4.1 工作区入口

Purpose:

- Provide a safe first screen when no workspace is selected, the workspace is unavailable, or index metadata cannot be loaded.
- Confirm that startup can load workspace and index status without scanning Markdown or triggering index.

Service mapping:

- `WorkspaceStatusService`: workspace identity, selected workspace path, startup readiness, warnings.
- `IndexMetadataService`: index existence and lightweight status.

Data contract:

```json
{
  "workspace": {
    "selected": true,
    "path": "string",
    "display_name": "string",
    "config_status": "ready|missing|invalid",
    "warnings": ["string"]
  },
  "index": {
    "status": "missing|ready|stale|partial|unavailable",
    "document_count": 0,
    "last_updated_at": "string|null"
  },
  "startup": {
    "markdown_scan_performed": false,
    "auto_index_started": false
  }
}
```

Component tree:

```text
AppShell
└── MainContent
    └── WorkspaceGateScreen
        ├── WorkspaceStatusPanel
        ├── IndexStatusPanel
        ├── ReadOnlyBoundaryNotice
        └── PrimaryEntryActions
            ├── GoToHomeButton
            └── GoToSearchButton
```

Loading / empty / error states:

- Loading: shell skeleton, status indicators in pending state.
- Empty: no workspace selected.
- Error: invalid workspace config, index metadata unavailable, service unavailable.
- Missing index: show `index_status=missing` and a non-executing recommendation to create index later; do not auto-index.

Keyboard interactions:

- `Enter`: continue to 首页 when workspace is ready.
- `Ctrl+K`: focus global search.
- `Esc`: dismiss transient error detail.
- `Tab` / `Shift+Tab`: move through focusable controls.

Adaptive layout behavior:

- Minimum 1100x720: single-column status panels.
- Preferred 1440x900: two-column workspace/index panels.
- Large and ultra-wide: constrain content width to avoid stretched status cards.

Virtual list / pagination rules:

- No list is rendered on this screen.

Acceptance criteria:

- Startup calls only status/index services.
- Startup does not scan `knowledge/`.
- Startup does not read Markdown bodies.
- Startup does not start index/reindex.
- Missing index is displayed as a state, not repaired automatically.

Implementation phase:

- GUI Phase 1A.

### 4.2 首页

Purpose:

- Provide a compact workspace health overview.
- Keep the MVP home screen low density and operationally useful.
- Avoid turning the homepage into a full feature directory.

Home content is limited to:

- 索引状态
- 待审核数量
- 备份状态
- 任务状态
- 最近任务
- 推荐操作
- 快速入口

Service mapping:

- `WorkspaceStatusService`: workspace health.
- `IndexMetadataService`: index status and indexed document count.
- `ReviewQueueService`: pending review count summary only.
- `BackupService`: latest backup summary.
- `SnapshotService`: latest snapshot / snapshot-required summary.
- `TaskQueueService`: task count and recent task summary.

Data contract:

```json
{
  "workspace_status": {
    "display_name": "string",
    "path": "string",
    "health": "ready|warning|blocked"
  },
  "index_status": {
    "status": "missing|ready|stale|partial|running|unavailable",
    "document_count": 0,
    "last_updated_at": "string|null"
  },
  "review_summary": {
    "pending_count": 0,
    "raw_count": 0,
    "distilled_count": 0
  },
  "backup_summary": {
    "status": "missing|recent|required|failed|unknown",
    "latest_backup_at": "string|null",
    "latest_snapshot_at": "string|null"
  },
  "task_summary": {
    "running": 0,
    "pending": 0,
    "failed": 0,
    "recent": []
  },
  "recommended_actions": [
    {
      "label": "string",
      "target": "route|disabled",
      "reason": "string",
      "execute": false
    }
  ]
}
```

Component tree:

```text
AppShell
├── TopBar
├── SidebarNav
├── MainContent
│   └── HomeScreen
│       ├── HealthSummaryGrid
│       │   ├── IndexStatusCard
│       │   ├── ReviewCountCard
│       │   ├── BackupStatusCard
│       │   └── TaskStatusCard
│       ├── RecentTasksList
│       ├── RecommendedActionsPanel
│       └── QuickEntryPanel
└── InspectorPanel
    └── CompactWorkspaceHealth
```

Loading / empty / error states:

- Loading: card skeletons, recent task skeleton rows.
- Empty: no recent tasks, no recommended actions.
- Warning: index missing/stale/partial, backup missing, failed task count.
- Error: partial service unavailable; render remaining cards with service-specific error badges.

Keyboard interactions:

- `Ctrl+K`: focus global search.
- `Ctrl+F`: navigate to 搜索 and focus query input.
- Arrow keys: move between recent task rows after list focus.
- `Enter`: open focused route-only quick entry.
- `Esc`: collapse inspector.

Adaptive layout behavior:

- Minimum 1100x720: 2-column health grid, recent tasks below.
- Preferred 1440x900: 4-card health row, recent tasks and actions in two columns.
- Large 1920x1080: same density with wider recent task table.
- Ultra-wide 2560x1440: content max width 1680px; inspector may remain expanded without stretching cards.
- Small-height windows must scroll main content, not compress cards into unreadable rows.

Virtual list / pagination rules:

- Recent tasks capped at 5.
- Recommended actions capped at 3.
- Quick entries capped at 3.
- No all-feature card grid.

Acceptance criteria:

- 首页 does not duplicate all sidebar modules.
- 首页 remains read-only.
- Recommended actions route to allowed Phase 1 screens or display disabled future state.
- No task execution is started from 首页 in Phase 1.

Implementation phase:

- GUI Phase 1B.

### 4.3 搜索

Purpose:

- Search formal knowledge through service-backed SQLite FTS.
- Preserve default knowledge trust: `rules`, `checklists`, `snippets`.
- Open only one explicit document into 文档预览.

Service mapping:

- `SearchService`: query formal knowledge.
- `DocumentService.open_document`: open selected result.

Data contract:

```json
{
  "query": "string",
  "filters": {
    "layers": ["rules", "checklists", "snippets"],
    "status": ["active"],
    "category_id": "string|null",
    "source_type": "string|null",
    "confidence": "high|medium|low|null"
  },
  "page": {
    "limit": 25,
    "offset": 0,
    "has_more": true
  },
  "results": [
    {
      "document_id": "string",
      "title": "string",
      "category_id": "string",
      "layer": "rules|checklists|snippets",
      "status": "active|deprecated|rejected",
      "confidence": "high|medium|low",
      "source_type": "string",
      "review_required": false,
      "snippet": "string",
      "score": 0.0,
      "updated_at": "string|null"
    }
  ]
}
```

Component tree:

```text
AppShell
├── TopBar
│   └── GlobalSearchBox
├── SidebarNav
├── MainContent
│   └── SearchScreen
│       ├── SearchBox
│       ├── SearchFilterBar
│       ├── ResultCountSummary
│       └── ResultList
│           └── SearchResultRow
└── InspectorPanel
    └── DocumentPreview
```

Loading / empty / error states:

- Empty query: show recent allowed search hints from local UI state only; do not run search.
- Loading: keep previous results visible with inline progress when possible.
- No results: show query, filters, and reset-filter action.
- Index missing: show read-only missing-index state; do not auto-index.
- Index stale/partial: show warning badge while allowing service-backed results.
- Error: service error with retry search button.

Keyboard interactions:

- `Ctrl+F`: focus screen search box.
- `Ctrl+K`: focus global search / command search.
- `Enter`: run search from query box.
- `ArrowUp` / `ArrowDown`: move result focus.
- `Enter` on focused result: open 文档预览 through `DocumentService.open_document`.
- `Esc`: clear focus or collapse inspector.

Adaptive layout behavior:

- Minimum 1100x720: result list full width, inspector drawer overlay.
- Preferred 1440x900: result list with collapsible right inspector.
- Large 1920x1080: result list and inspector can be side by side.
- Ultra-wide 2560x1440: result list constrained; inspector remains 360-440px.

Virtual list / pagination rules:

- Default result page size: 25.
- Maximum rendered result rows at once: viewport rows plus overscan.
- Do not request or render all search results.
- Infinite scroll may request next page only near viewport end.
- Opening a result must not preload neighboring Markdown documents.

Acceptance criteria:

- 搜索 calls `SearchService`.
- 搜索 does not read Markdown bodies for list rows.
- Default layers are formal only: `rules`, `checklists`, `snippets`.
- 文档预览 opens only after explicit user action.
- RSS and vector search are absent.

Implementation phase:

- GUI Phase 1C.

### 4.4 知识库

Purpose:

- Browse indexed formal knowledge by category and layer.
- Provide stable metadata browsing without Markdown body reads.
- Surface rules/checklists/snippets as subviews, not separate main navigation entries.

Service mapping:

- `CategoryService`: category tree, category summary, layer counts, paged document metadata.
- `SearchService`: optional list query/filter reuse.
- `DocumentService.open_document`: explicit document open only.

Data contract:

```json
{
  "category_tree": [
    {
      "category_id": "string",
      "display_name": "string",
      "path": "string",
      "counts": {
        "rules": 0,
        "checklists": 0,
        "snippets": 0
      }
    }
  ],
  "active_view": "all_formal|rules|checklists|snippets",
  "documents": [
    {
      "document_id": "string",
      "title": "string",
      "category_id": "string",
      "layer": "rules|checklists|snippets",
      "status": "active|deprecated|rejected",
      "confidence": "high|medium|low",
      "source_type": "string",
      "last_reviewed": "string|null",
      "review_required": false
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "has_more": true
  }
}
```

Component tree:

```text
AppShell
├── TopBar
├── SidebarNav
├── MainContent
│   └── KnowledgeLibraryScreen
│       ├── LibraryHeader
│       ├── FormalLayerTabs
│       ├── CategoryTreePane
│       ├── LibraryFilterBar
│       └── DocumentMetadataTable
└── InspectorPanel
    └── DocumentPreview
```

Loading / empty / error states:

- Loading: category tree skeleton and table row skeletons.
- Empty category: show category identity and zero formal document state.
- Empty layer: show selected layer and reset-layer action.
- Index missing: show missing-index state without auto-index.
- Error: category metadata service failure, page load failure, document open failure.

Keyboard interactions:

- `Ctrl+F`: focus local filter within 知识库.
- `ArrowUp` / `ArrowDown`: table row navigation.
- `ArrowLeft` / `ArrowRight`: category tree collapse/expand.
- `Enter`: open focused document in 文档预览.
- `Esc`: collapse inspector or clear table selection.

Adaptive layout behavior:

- Minimum 1100x720: category tree can collapse into a drawer; table remains primary.
- Preferred 1440x900: category tree 260px, table center, inspector collapsed.
- Large 1920x1080: category tree + table + optional inspector.
- Ultra-wide 2560x1440: table max width and row density remain stable.

Virtual list / pagination rules:

- Category tree may render all configured categories only if count is small; large category sets must virtualize.
- Document table default page size: 50.
- Render only viewport rows plus overscan.
- Do not preload Markdown body for table rows.
- Sort/filter changes reset pagination cursor.

Acceptance criteria:

- 知识库 calls `CategoryService`.
- 知识库 uses SQLite metadata through service boundaries.
- Rules / Checklists / Snippets are subviews, not top-level nav.
- No category edit controls are visible in Phase 1.
- No category `display_name` / `description` execute is exposed.

Implementation phase:

- GUI Phase 1D.

### 4.5 文档预览

Purpose:

- Render one explicitly opened Markdown document.
- Show metadata needed for trust and governance.
- Keep preview read-only.

Service mapping:

- `DocumentService.open_document`: read one selected document body and metadata.

Data contract:

```json
{
  "document_id": "string",
  "title": "string",
  "category_id": "string",
  "layer": "rules|checklists|snippets|distilled|raw",
  "status": "active|deprecated|rejected|quarantine|archived",
  "confidence": "high|medium|low",
  "source_type": "string",
  "source_url": "string|null",
  "review_required": false,
  "last_reviewed": "string|null",
  "body": "string",
  "open_mode": "read_only"
}
```

Component tree:

```text
DocumentPreview
├── PreviewHeader
├── MetadataBadgeRow
│   ├── LayerBadge
│   ├── StatusBadge
│   ├── ConfidenceBadge
│   └── ReviewRequiredBadge
├── SourceMetadataPanel
├── MarkdownReadOnlyRenderer
└── PreviewFooter
```

Loading / empty / error states:

- Empty: no document selected.
- Loading: preview skeleton with metadata placeholders.
- Error: document missing, open denied, parse/render error.
- Warning: raw/distilled/quarantine/review_required content displays explicit trust warning.

Keyboard interactions:

- `Esc`: close preview inspector/drawer.
- `Ctrl+F`: focus in-preview text search if implemented without changing source.
- `PageUp` / `PageDown`: scroll preview.
- `Home` / `End`: jump within preview.

Adaptive layout behavior:

- In inspector: 360-440px preview with compact metadata.
- In drawer: full-height preview overlay at minimum width.
- In main split: preview may use up to 50% width only after explicit selection.
- Long documents scroll inside preview, not the whole app shell.

Virtual list / pagination rules:

- Not a list screen.
- Large documents render incrementally if supported by the chosen GUI framework later.
- Only the selected document body is loaded.

Acceptance criteria:

- 文档预览 is read-only.
- Document body is loaded only through `DocumentService.open_document`.
- No edit button, save button, promote button, archive button, delete button, merge button, template apply button, or restore execute button is visible.

Implementation phase:

- GUI Phase 1C / 1D shared component.

### 4.6 任务中心摘要

Purpose:

- Show read-only task status, progress, and logs.
- Make long-running background activity visible without enabling destructive actions.

Service mapping:

- `TaskQueueService`: task list, task status, task progress, task log.

Data contract:

```json
{
  "tasks": [
    {
      "task_id": "string",
      "type": "string",
      "status": "pending|running|succeeded|failed|cancelled|blocked",
      "progress_percent": 0,
      "cancel_requested": false,
      "error": "string|null",
      "log_available": true,
      "result_summary": {},
      "elapsed_ms": 0,
      "created_at": "string",
      "updated_at": "string",
      "retry_of": "string|null",
      "retry_root": "string|null"
    }
  ],
  "pagination": {
    "limit": 25,
    "offset": 0,
    "has_more": true
  }
}
```

Component tree:

```text
AppShell
├── TopBar
├── SidebarNav
├── MainContent
│   └── TaskCenterSummaryScreen
│       ├── TaskSummaryHeader
│       ├── TaskStatusFilterBar
│       └── TaskList
│           └── TaskRow
└── InspectorPanel
    └── TaskReadOnlyDetail
        ├── ProgressPanel
        ├── TaskResultSummary
        └── TaskLogViewer
```

Loading / empty / error states:

- Loading: task row skeletons.
- Empty: no tasks recorded.
- Running: live progress indicator.
- Failed: error summary and log link.
- Cancelled: read-only cancelled state.
- Log unavailable: show task status without direct filesystem fallback.

Keyboard interactions:

- `ArrowUp` / `ArrowDown`: move task row focus.
- `Enter`: open read-only task detail/log.
- `Esc`: collapse inspector.
- `Ctrl+K`: focus global command search.

Adaptive layout behavior:

- Minimum 1100x720: list full width; task detail opens as drawer.
- Preferred 1440x900: list with collapsed inspector.
- Large and ultra-wide: inspector can remain open for log reading.
- Logs use their own scroll area.

Virtual list / pagination rules:

- Default task page size: 25.
- Render only viewport rows plus overscan.
- Logs are loaded per selected task and may use tail pagination.
- Do not read `.kb/tasks/` directly; all data comes from `TaskQueueService`.

Phase 1 restrictions:

- Read-only task status/progress/log only.
- No cleanup execute.
- No destructive action.
- No archive/delete/merge/template apply/restore task creation.
- No retry/cancel controls unless a later phase explicitly adds them; Phase 1 may display current task status only.

Acceptance criteria:

- 任务中心摘要 calls `TaskQueueService`.
- It displays task status/progress/log read-only.
- It does not expose cleanup execute or destructive action.
- It does not bypass service APIs to read task files.

Implementation phase:

- GUI Phase 1E.

### 4.7 设置入口

Purpose:

- Provide a read-only entry point for future settings areas.
- Clarify that editable settings and mutation workflows are outside Phase 1.
- Route users to service-backed status information only.

Service mapping:

- `WorkspaceStatusService`: workspace identity and config readiness.
- `IndexMetadataService`: index metadata summary.
- Future settings/category/template/source services remain outside Phase 1.

Data contract:

```json
{
  "settings_sections": [
    {
      "section_id": "category_settings",
      "label": "分类设置",
      "phase": "future",
      "read_only": true,
      "editable": false,
      "execute_available": false
    },
    {
      "section_id": "template_manager",
      "label": "模板管理",
      "phase": "future",
      "read_only": true,
      "editable": false,
      "execute_available": false
    },
    {
      "section_id": "source_manager",
      "label": "来源管理",
      "phase": "future",
      "read_only": true,
      "editable": false,
      "execute_available": false
    }
  ],
  "workspace": {
    "display_name": "string",
    "path": "string",
    "config_status": "ready|missing|invalid"
  }
}
```

Component tree:

```text
AppShell
├── TopBar
├── SidebarNav
└── MainContent
    └── SettingsEntryScreen
        ├── SettingsReadOnlyNotice
        ├── WorkspaceInfoPanel
        ├── SettingsSectionList
        │   ├── CategorySettingsEntry
        │   ├── TemplateManagerEntry
        │   └── SourceManagerEntry
        └── FutureMutationBoundaryPanel
```

Loading / empty / error states:

- Loading: workspace info skeleton.
- Empty: no optional settings sections available.
- Error: workspace status service unavailable.
- Disabled: future settings entries are visible as read-only/future if shown.

Keyboard interactions:

- `ArrowUp` / `ArrowDown`: move section focus.
- `Enter`: open read-only section details only if available.
- `Esc`: return focus to sidebar.
- `Ctrl+K`: focus global command search.

Adaptive layout behavior:

- Minimum 1100x720: single-column settings entry list.
- Preferred and larger: two-column read-only overview if needed.
- No complex settings grid in Phase 1.

Virtual list / pagination rules:

- No large list expected.
- If future settings section count grows, use simple pagination.

Phase 1 restrictions:

- 设置入口 only shows read-only entries.
- Do not show editable configuration forms.
- Do not show save/apply buttons.
- Do not expose category `display_name` / `description` execute.
- Do not expose archive/delete/merge/template apply/restore execute.

Acceptance criteria:

- 设置入口 is read-only.
- It communicates future settings boundaries without implementing mutation UI.
- It does not expose editable forms.
- It does not expose any execute path.

Implementation phase:

- GUI Phase 1F.

## 5. Keyboard Interaction Contract

Global:

- `Ctrl+K`: global search / command search.
- `Ctrl+F`: screen-local search where applicable.
- `Esc`: collapse inspector, close drawer, or clear transient focus state.
- `Tab` / `Shift+Tab`: standard focus order.
- `Enter`: activate focused read-only navigation, search, row open, or preview open.

List screens:

- `ArrowUp` / `ArrowDown`: move row focus.
- `PageUp` / `PageDown`: scroll virtual list.
- `Home` / `End`: move to first/last loaded row, not all rows unless paged data exists.

Forbidden shortcuts:

- No shortcut may execute mutation.
- No shortcut may create archive/delete/merge/template apply/restore tasks.
- No shortcut may bypass approval or service boundaries.

## 6. Adaptive Desktop Layout Contract

Target sizes:

- Minimum window: 1100x720.
- Preferred: 1440x900.
- Large: 1920x1080.
- Ultra-wide: 2560x1440.

Layout tokens:

- TopBar height: 52px.
- StatusBar height: 28px.
- Expanded sidebar width: 240-260px.
- Collapsed sidebar width: 56-64px.
- Inspector default width: 360px.
- Inspector large width: 440px.
- Content max width on ultra-wide: 1680px unless table density benefits from wider content.
- Base spacing: 8px.
- Section gap: 16-24px.
- Card radius: 8px maximum.

Behavior:

- Sidebar is collapsible.
- Inspector is collapsed by default.
- Small-height windows scroll screen content.
- Tables and lists own their scroll containers.
- Preview and logs own their scroll containers.
- Status indicators remain visible.
- Text must not overflow buttons, badges, table cells, or status indicators.

## 7. Virtual List and Pagination Rules

General:

- Do not render all search results.
- Do not render all library documents.
- Do not render all tasks.
- Use service pagination or cursor-based paging where available.
- Use virtual rows for visible viewport plus overscan.
- Keep row height stable enough to avoid layout jump.

Search:

- Default page size: 25.
- Request next page only near the end of the viewport.
- Do not preload Markdown bodies.

知识库:

- Default page size: 50.
- Reset pagination on category/layer/filter changes.
- Do not render all documents under a category at once.

任务中心摘要:

- Default page size: 25.
- Logs load only for selected task.
- Log tail should be paged or streamed through service later; Phase 1 can page on selection.

首页:

- Recent tasks max 5.
- Recommended actions max 3.
- Quick entries max 3.

## 8. State Coverage

Phase 1 must handle:

- no workspace selected.
- invalid workspace.
- index missing.
- index ready.
- index stale.
- index partial.
- index unavailable.
- search empty.
- search no results.
- library empty.
- category empty.
- document not selected.
- document open failed.
- task running.
- task failed.
- task cancelled.
- task log unavailable.
- backup missing.
- snapshot required.
- read-only settings.
- unsupported execute action.
- service unavailable.
- secret-scan warning indicator when reported by service summary.

Unsupported execute actions must render as disabled/future, not as hidden accidental functionality when the user might reasonably expect them from Phase 0.

## 9. Implementation Phases

GUI Phase 1A: App shell and 工作区入口

- Build AppShell, TopBar, SidebarNav, StatusBar, collapsed InspectorPanel contract.
- Wire only `WorkspaceStatusService` and `IndexMetadataService`.
- Validate startup does not scan/read/hash/index.

GUI Phase 1B: 首页 read-only summary

- Add compact health cards.
- Add recent tasks, recommended actions, and quick entries with strict caps.
- Keep all actions read-only or route-only.

GUI Phase 1C: 搜索 and 文档预览

- Add formal-layer search through `SearchService`.
- Add virtualized ResultList.
- Add `DocumentService.open_document` preview only after explicit selection.

GUI Phase 1D: 知识库 and shared 文档预览

- Add category/layer metadata browsing through `CategoryService`.
- Add formal subviews for all formal, Rules, Checklists, Snippets.
- Keep category edit controls absent.

GUI Phase 1E: 任务中心摘要

- Add task status/progress/log read path through `TaskQueueService`.
- Keep cleanup execute, retry/cancel controls, destructive task creation, and mutation controls absent.

GUI Phase 1F: 设置入口

- Add read-only settings entry.
- Show no editable forms.
- Show no save/apply/execute controls.

## 10. Acceptance Criteria

Service boundary:

- GUI does not directly read or write Markdown.
- GUI does not directly read or write SQLite.
- GUI does not build CLI command strings as the primary integration mechanism.
- All data comes through service/core APIs.
- Startup uses `WorkspaceStatusService` and `IndexMetadataService`.
- Startup does not scan `knowledge/`, read Markdown, hash files, or auto-index.
- Markdown body is loaded only through `DocumentService.open_document` for one explicit document.

Read-only MVP:

- Phase 1 does not expose category `display_name` / `description` execute.
- Phase 1 does not expose archive/delete/merge/template apply/restore execute.
- Phase 1 does not expose RSS.
- Phase 1 does not expose vector search.
- Phase 1 does not implement real mutation UI.
- Phase 1 does not expose destructive actions.
- 设置入口 only displays read-only entries and no editable configuration forms.
- 任务中心摘要 only displays task status/progress/log and provides no cleanup execute or destructive action.

Navigation and layout:

- TopBar is not main navigation.
- SidebarNav is the only main navigation.
- 首页 remains compact and does not list every feature.
- InspectorPanel is collapsed by default.
- Minimum 1100x720 layout remains usable.
- Small-height windows scroll correctly.

Performance:

- 搜索、知识库、任务中心摘要 use virtual scrolling or pagination.
- 10K+ list scenarios do not render all rows.
- 搜索 and 知识库 list rows use SQLite metadata / FTS through services.
- UI main thread does not run index, audit, backup, restore, archive, template apply, secret-scan, benchmark, or maintenance.

Safety:

- Unsupported execute actions render disabled/future or are absent from Phase 1 scope.
- No approval, snapshot, TaskQueue execute, restore-plan, archive, delete, merge, template apply, or promote execute UI is exposed in Phase 1.
- Phase 1 cannot mutate Markdown, config, workspace, category, template, or SQLite schema.
