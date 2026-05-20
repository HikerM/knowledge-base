# GUI Phase 1 Engineering Preparation

This document defines the engineering preparation contract for GUI Phase 1 of `personal-knowledge-base`.

It sits between the Product UI Architecture Contract and the Read-only MVP Screen Contract:

- [docs/gui-product-ui-architecture.md](D:/AI/personal-knowledge-base/docs/gui-product-ui-architecture.md)
- [docs/gui-phase-1-read-only-mvp-contract.md](D:/AI/personal-knowledge-base/docs/gui-phase-1-read-only-mvp-contract.md)

This is not a GUI implementation, EXE packaging plan, RSS plan, vector-search plan, or framework selection. It must not be used to choose Tauri, Electron, PySide, WinUI, or any other GUI stack.

Phase 1 engineering preparation defines only:

- GUI-to-service adapter boundaries.
- read-only ViewModel contracts.
- service fixture strategy.
- UI test harness strategy.
- startup performance acceptance.

It must not change Markdown storage, SQLite schema, search behavior, index behavior, audit behavior, or knowledge lifecycle rules.

## 1. GUI-to-service adapter boundary

The GUI-to-service adapter is the only boundary a future GUI may use to load Phase 1 data. It is a thin, framework-neutral layer over `knowledge_app.services`.

The adapter may:

- receive workspace context and route/view requests from the UI.
- call service classes in `knowledge_app.services`.
- normalize `OperationResult` and service model payloads into read-only ViewModels.
- enforce Phase 1 pagination limits and read-only capability flags.
- preserve service `warnings`, `errors`, `elapsed_ms`, and source service names.
- expose cancellation/debounce handles for UI calls without cancelling service work that has already completed.
- provide dependency injection seams for fixture services and test doubles.

The adapter must not:

- read or write Markdown files directly.
- query or mutate SQLite directly.
- create or modify SQLite schema.
- scan `knowledge/`.
- hash Markdown files.
- start index/reindex/audit/secret-scan during app startup.
- construct CLI command strings such as `python scripts/kb.py ...` as its integration mechanism.
- reimplement search ranking, index metadata, category aggregation, review queue filtering, archive metadata, document parsing, task persistence, backup logic, snapshot logic, or safe mutation rules.
- expose any Phase 1 mutation action.

Allowed Phase 1 adapter methods:

```text
loadStartupView(workspace_context) -> StartupViewModel
loadHomeView(workspace_context) -> HomeViewModel
searchFormalKnowledge(SearchRequest) -> SearchViewModel
loadKnowledgeLibrary(LibraryRequest) -> KnowledgeLibraryViewModel
openDocumentPreview(DocumentOpenRequest) -> DocumentPreviewViewModel
loadTaskSummary(TaskListRequest) -> TaskSummaryViewModel
loadTaskDetail(TaskDetailRequest) -> TaskDetailViewModel
loadSettingsEntry(workspace_context) -> SettingsEntryViewModel
```

Allowed service mapping:

| Adapter method | Services | Phase 1 behavior |
|---|---|---|
| `loadStartupView` | `WorkspaceStatusService`, `IndexMetadataService` | Read startup/index metadata only. |
| `loadHomeView` | `WorkspaceStatusService`, `IndexMetadataService`, `TaskQueueService`, `BackupService`, `SnapshotService`, `ReviewQueueService` summary methods where available | Read compact health summary only. Partial service failure becomes partial ViewModel state. |
| `searchFormalKnowledge` | `SearchService` | Default layers stay `rules`, `checklists`, `snippets`. No Markdown body reads. |
| `loadKnowledgeLibrary` | `CategoryService`, optional `SearchService` for filtered metadata reuse | Metadata/counts only. No category mutation controls. |
| `openDocumentPreview` | `DocumentService.open_document` | Read exactly one explicitly selected document. |
| `loadTaskSummary` | `TaskQueueService.list_tasks` | Read-only paginated task rows. |
| `loadTaskDetail` | `TaskQueueService.get_task`, `get_task_progress`, `get_task_log` | Read-only task detail/progress/log through service only. |
| `loadSettingsEntry` | `WorkspaceStatusService`, `IndexMetadataService` | Read-only future settings entry metadata. |

The adapter owns UI-facing capability flags. A forbidden or future action must be represented as `enabled=false`, `execute_available=false`, or `phase="future"` in the ViewModel. It must not be represented by an implementation placeholder that later accidentally executes.

## 2. Read-only ViewModel contracts

ViewModels are framework-neutral JSON-like contracts. They must be serializable, deterministic, and independent of component libraries.

Shared result envelope:

```ts
type ViewState = "idle" | "loading" | "ready" | "empty" | "partial" | "error";

type UiError = {
  code: string;
  message: string;
  service: string;
  recoverable: boolean;
  details?: Record<string, unknown>;
};

type UiWarning = {
  code: string;
  message: string;
  service: string;
};

type ViewModelEnvelope<T> = {
  schema_version: 1;
  view_id: string;
  state: ViewState;
  data: T | null;
  warnings: UiWarning[];
  errors: UiError[];
  source_services: string[];
  elapsed_ms: number;
  generated_at: string;
};
```

Shared pagination contract:

```ts
type PageRequest = {
  limit: number;
  offset: number;
};

type PageInfo = {
  limit: number;
  offset: number;
  count: number;
  total?: number;
  has_more: boolean;
};
```

Startup ViewModel:

```ts
type StartupViewModel = ViewModelEnvelope<{
  workspace_path: string;
  index_path: string;
  index_exists: boolean;
  index_status: "missing" | "ready" | "stale" | "partial" | "failed";
  document_count: number;
  chunk_count: number;
  last_indexed_at: string;
  startup_guards: {
    markdown_scan_performed: false;
    markdown_body_read: false;
    hash_performed: false;
    auto_index_started: false;
  };
}>;
```

Home ViewModel:

```ts
type HomeViewModel = ViewModelEnvelope<{
  workspace: {
    path: string;
    health: "ready" | "warning" | "blocked";
  };
  index: {
    status: string;
    document_count: number;
    chunk_count: number;
    last_indexed_at: string;
  };
  review_summary: {
    pending_count: number;
    raw_count: number;
    distilled_count: number;
  };
  backup_summary: {
    status: "missing" | "recent" | "required" | "failed" | "unknown";
    latest_backup_at: string | null;
    latest_snapshot_at: string | null;
  };
  task_summary: {
    running: number;
    pending: number;
    failed: number;
    recent: TaskRowViewModel[];
  };
  recommended_actions: RouteOnlyAction[];
}>;
```

Search ViewModel:

```ts
type SearchRequest = {
  query: string;
  filters: {
    layers: ("rules" | "checklists" | "snippets")[];
    status: ("active" | "deprecated" | "rejected")[];
    category_id?: string;
    source_type?: string;
    confidence?: "high" | "medium" | "low";
  };
  page: PageRequest;
};

type SearchResultRowViewModel = {
  document_id: string;
  path: string;
  title: string;
  category_id: string;
  layer: "rules" | "checklists" | "snippets";
  status: string;
  confidence: "high" | "medium" | "low";
  source_type: string;
  review_required: boolean;
  snippet: string;
  updated_at: string | null;
  open_document_action: RouteOnlyAction;
};

type SearchViewModel = ViewModelEnvelope<{
  query: string;
  filters: SearchRequest["filters"];
  page: PageInfo;
  results: SearchResultRowViewModel[];
  index_status: string;
}>;
```

Knowledge Library ViewModel:

```ts
type KnowledgeLibraryViewModel = ViewModelEnvelope<{
  categories: {
    category_id: string;
    display_name: string;
    path: string;
    description: string;
    document_count: number;
    layer_counts: Record<string, number>;
    status_counts: Record<string, number>;
    review_required_count: number;
    edit_available: false;
  }[];
  active_category_id: string | null;
  active_view: "all_formal" | "rules" | "checklists" | "snippets";
  documents: SearchResultRowViewModel[];
  page: PageInfo;
}>;
```

Document Preview ViewModel:

```ts
type DocumentPreviewViewModel = ViewModelEnvelope<{
  document_id: string;
  path: string;
  title: string;
  category_id: string;
  layer: string;
  status: string;
  confidence: "high" | "medium" | "low";
  source_type: string;
  source_url: string | null;
  review_required: boolean;
  last_reviewed: string | null;
  trust_warning: string | null;
  body: string;
  open_mode: "read_only";
  mutation_actions_available: false;
}>;
```

Task ViewModels:

```ts
type TaskRowViewModel = {
  task_id: string;
  task_type: string;
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  title: string;
  progress_percent: number;
  progress_message: string;
  cancel_requested: boolean;
  error: Record<string, unknown>;
  log_available: boolean;
  result_summary: Record<string, unknown>;
  elapsed_ms: number;
  created_at: string;
  started_at: string;
  finished_at: string;
  retry_of: string | null;
  retry_root: string | null;
};

type TaskSummaryViewModel = ViewModelEnvelope<{
  tasks: TaskRowViewModel[];
  page: PageInfo;
  phase_1_controls: {
    create_task_available: false;
    run_task_available: false;
    cancel_task_available: false;
    retry_task_available: false;
    cleanup_execute_available: false;
  };
}>;

type TaskDetailViewModel = ViewModelEnvelope<{
  task: TaskRowViewModel;
  progress_events: {
    schema_version: number;
    sequence: number;
    timestamp: string;
    progress_percent: number;
    message: string;
    current_step: string;
    detail: Record<string, unknown>;
  }[];
  log_entries: {
    timestamp: string;
    message: string;
    detail: Record<string, unknown>;
  }[];
}>;
```

Settings Entry ViewModel:

```ts
type SettingsEntryViewModel = ViewModelEnvelope<{
  workspace_path: string;
  sections: {
    section_id: string;
    label: string;
    phase: "future" | "phase_1_read_only";
    read_only: true;
    editable: false;
    execute_available: false;
  }[];
}>;
```

Shared read-only action contract:

```ts
type RouteOnlyAction = {
  action_id: string;
  label: string;
  kind: "route" | "open_document" | "disabled_future";
  target: string;
  execute: false;
  enabled: boolean;
  reason?: string;
};
```

## 3. Service fixture strategy

Fixtures must prove the service boundary without relying on production knowledge files.

Fixture levels:

1. Service integration fixtures:
   - Use `tests/fixtures/*.md`.
   - Copy fixtures into a temporary workspace.
   - Build `.kb/index.sqlite` through the normal index path only.
   - Call `knowledge_app.services` directly.
   - Assert read-layer services do not scan `knowledge/`, read Markdown bodies, or hash files except for explicit `DocumentService.open_document`.
2. Adapter contract fixtures:
   - Capture or construct service-shaped `OperationResult` payloads.
   - Feed those payloads into adapter mappers.
   - Assert stable ViewModel envelopes, capability flags, pagination fields, warnings, and error mapping.
   - Keep adapter fixtures as JSON or typed in-memory objects. Do not use hand-edited SQLite files.
3. UI state fixtures:
   - Loading, empty, partial, error, warning, disabled/future, and ready states.
   - These fixtures must not touch the filesystem.
   - They exist to test component state rendering after a framework is chosen.

Required fixture scenarios:

- startup with missing index.
- startup with ready index.
- startup with partial/failed index metadata.
- formal search with results.
- formal search with no results.
- index missing during search.
- category list with zero-count configured categories.
- document preview read success for one explicit document.
- document preview open failure.
- task list empty.
- task list with pending/running/succeeded/failed/cancelled records.
- task progress events with monotonic `sequence`.
- task log unavailable.
- backup status missing/recent/failed summary.
- partial home load where one service fails but other cards still render.
- large list page with `limit`/`offset` and `has_more`.

Fixture rules:

- Do not modify `knowledge/**/*.md`.
- Do not commit `.kb/index.sqlite` or `.kb/tasks/`.
- Do not create fixture Markdown without frontmatter.
- Do not treat raw/distilled fixtures as formal rules.
- Do not use raw/research fixture content as project decision material.
- Do not make fixture updates implicit. Fixture refresh must be an explicit developer action with reviewable diffs.

## 4. UI test harness strategy

The Phase 1 UI test harness must be framework-neutral until a GUI stack is chosen.

Test layers:

1. Adapter mapper tests:
   - Input: service-shaped payloads or service test doubles.
   - Output: ViewModel envelopes.
   - Assertions: schema version, state, data shape, warnings/errors, capability flags, and elapsed/source service metadata.
2. Adapter integration tests:
   - Input: temporary workspace using `tests/fixtures`.
   - Calls: real services through the adapter.
   - Assertions: no direct Markdown/SQLite access by adapter; no startup scan/hash/index; formal search defaults preserved.
3. Guardrail tests:
   - Patch filesystem scanning and Markdown reads the same way `tests/startup_smoke.py` and `tests/service_read_layer_test.py` do.
   - Fail if startup calls `Path.rglob` on `knowledge/`.
   - Fail if read-only list/search paths call `Path.read_text` on Markdown.
   - Fail if startup or list paths call hashing.
   - Fail if adapter uses subprocess/shell command strings for `scripts/kb.py`.
4. View state tests:
   - After framework selection, render components against ViewModel fixtures.
   - Assert loading, empty, partial, error, warning, disabled/future, and ready states.
   - Assert no mutation controls appear in Phase 1 fixtures.
5. Interaction tests:
   - Search submit calls `searchFormalKnowledge`.
   - Result open calls `openDocumentPreview` for exactly one document.
   - Task row open calls `loadTaskDetail`.
   - Settings entries remain read-only.
   - Keyboard shortcuts never trigger mutation.
6. Startup performance tests:
   - Reuse `tests/startup_smoke.py` as the non-negotiable backend baseline.
   - Add adapter startup probes later without changing `workspace-status` behavior.

Future UI tests may use a browser, desktop automation, or a component runner only after framework selection. The contract here intentionally avoids choosing one.

## 5. Startup performance acceptance

Startup means app bootstrap before the user explicitly opens a document or starts a background task.

Startup must call only:

- `WorkspaceStatusService`
- `IndexMetadataService`
- optional read-only lightweight summary calls that do not scan `knowledge/`, read Markdown, hash, index, audit, or secret-scan.

Acceptance criteria:

- Startup does not scan `knowledge/`.
- Startup does not read Markdown bodies.
- Startup does not hash files.
- Startup does not create `.kb/index.sqlite`.
- Startup does not run index/reindex.
- Startup does not run doctor/audit/secret-scan.
- Startup does not read all task logs.
- Startup does not render all task rows, search results, library documents, review items, or archive items.
- Missing index returns `index_status=missing` and count fields as zero or service-provided metadata only.
- Ready index reads only SQLite metadata through read-only connections.
- 10,000-document startup remains far faster than first index. The current smoke baseline is `workspace-status elapsed_ms < max(1000, first_index_elapsed_ms / 5)`.
- UI startup should render a ready, missing-index, partial, or error state from the adapter response. It must not block waiting for index, audit, backup, secret scan, or maintenance.

The required verification command is:

```bash
python tests/startup_smoke.py
```

## 6. No direct Markdown/SQLite access rule

The future GUI and GUI-to-service adapter must not directly access Markdown or SQLite.

Forbidden:

- opening `knowledge/**/*.md` from UI code.
- parsing Markdown/frontmatter from UI code.
- writing Markdown from UI code.
- listing files under `knowledge/` from UI code.
- querying `.kb/index.sqlite` from UI code.
- changing SQLite schema from UI code.
- reading `.kb/tasks/*` files directly from UI code.
- reading backup zip contents directly from UI code.

Allowed:

- list/search/category/review/archive metadata through services.
- read one explicitly selected Markdown document through `DocumentService.open_document`.
- read task status/progress/log through `TaskQueueService`.
- read backup/snapshot/restore metadata through their services.
- read index status through `WorkspaceStatusService` and `IndexMetadataService`.

Markdown remains the source of truth. SQLite remains a rebuildable hot index. The GUI must respect both facts by using services instead of file/database shortcuts.

## 7. No CLI string shelling rule

The future GUI and GUI-to-service adapter must not use CLI command strings as their primary integration mechanism.

Forbidden:

- building strings like `python scripts/kb.py search ...` from GUI state.
- invoking shell commands to call `scripts/kb.py` for normal GUI operations.
- parsing CLI stdout as the GUI data contract.
- using shell escaping as an application boundary.

Allowed:

- CLI wrappers remain available for automation, smoke tests, debugging, and advanced users.
- Tests may execute CLI commands to verify backward compatibility.
- A future out-of-process app boundary may expose typed service calls, RPC, IPC, or a local API, but it must keep structured request/response contracts instead of shell strings.

The adapter contract is the stable GUI integration boundary. The CLI is not.

## 8. TaskQueue integration contract

Phase 1 TaskQueue integration is read-only.

Allowed in Phase 1:

- list recent tasks with `limit` and `offset`.
- read a selected task record.
- read selected task progress events.
- read selected task logs through `TaskQueueService`.
- display task status in TopBar, StatusBar, 首页, and 任务中心摘要.
- display task errors, warnings, elapsed time, result summary, and retry lineage.

Forbidden in Phase 1:

- creating tasks from GUI.
- running tasks from GUI.
- cancelling tasks from GUI.
- retrying tasks from GUI.
- executing cleanup.
- creating archive/delete/merge/template apply/restore tasks.
- exposing category `display_name` or `description` execute.
- reading `.kb/tasks/` directly.

Task row requirements:

- `task_id`
- `task_type`
- `status`
- `progress_percent`
- `progress_message`
- `cancel_requested`
- `error`
- `log_path` represented only as service-provided metadata
- `result_summary`
- `elapsed_ms`
- `created_at`
- `started_at`
- `finished_at`
- retry lineage when present

Progress requirements:

- Every progress event must include `schema_version`.
- Every progress event must include monotonic `sequence`.
- UI ordering must use `sequence`, then timestamp as a fallback.
- Missing or malformed progress events become warning state, not direct filesystem fallback.

Future write-capable task flows must preserve the existing safe chain:

```text
plan -> local snapshot / backup -> approval -> TaskQueue -> service result -> validation summary -> restore-plan entry
```

That future chain is not exposed in GUI Phase 1.

## 9. Error/loading/empty state model

Every ViewModel uses the shared `ViewModelEnvelope<T>` state model.

State rules:

- `idle`: no request has been made yet.
- `loading`: request is in flight; stale prior data may remain visible only if marked as stale by the UI layer.
- `ready`: data loaded successfully and contains displayable content.
- `empty`: request succeeded but there is no displayable content.
- `partial`: one or more services failed, but the view can render useful data from other services.
- `error`: the view cannot render its main content.

OperationResult mapping:

- `success=true` and non-empty data -> `ready`.
- `success=true` and empty list/count -> `empty`.
- `success=false` for required primary service -> `error`.
- `success=false` for secondary service on a composite view -> `partial`.
- service `warnings` -> `UiWarning[]`.
- service `errors` -> `UiError[]`.
- service `elapsed_ms` -> ViewModel `elapsed_ms` or child timing metadata.

Required error fields:

- stable `code`.
- user-readable `message`.
- `service` that produced or wrapped the error.
- `recoverable` boolean.
- optional structured `details`.

Required empty states:

- no workspace selected.
- index missing.
- search query empty.
- search no results.
- category has zero formal documents.
- library layer has no documents.
- no document selected.
- task list empty.
- task log unavailable.
- settings section is future/read-only.

Required disabled/future states:

- category execute unavailable.
- archive/delete/merge/template apply/restore execute unavailable.
- RSS unavailable.
- vector search unavailable.
- mutation UI unavailable.
- cleanup execute unavailable.

Disabled/future is not an error. It is a deliberate capability state.

## 10. Framework-neutral implementation assumptions

All contracts in this document assume no GUI framework has been selected.

Assumptions:

- The adapter exposes typed request/response contracts independent of UI widgets.
- ViewModels are serializable JSON-like objects.
- The UI framework may be web-based, native, or hybrid later.
- Service calls may become asynchronous, but the service contract remains structured.
- The adapter can run in-process during early prototypes or behind a typed process boundary later.
- The process boundary, if introduced, must preserve structured contracts and service semantics.
- UI components are consumers of ViewModels; they do not own knowledge governance logic.
- Pagination, disabled/future capability flags, and trust warnings are data contracts, not visual-only decisions.
- Tests can validate adapter behavior before any real GUI exists.

Implementation assumptions that are explicitly not made:

- No assumption about Tauri, Electron, PySide, WinUI, browser runtime, or rendering engine.
- No assumption about CSS, native widgets, or component libraries.
- No assumption about packaging, installer layout, auto-update, or EXE runtime.
- No assumption about RSS, vector search, MCP server, or RAG UI.
- No assumption that CLI stdout is the GUI API.

## Engineering readiness checklist

Before GUI coding starts, the project should have:

- adapter interfaces matching this document.
- mapper tests for every ViewModel envelope.
- service integration fixtures using temporary workspaces.
- guardrail tests preventing direct Markdown/SQLite/CLI-shell integration.
- startup performance probe aligned with `tests/startup_smoke.py`.
- UI state fixtures for loading, empty, partial, error, warning, disabled/future, and ready states.
- explicit review that Phase 1 still exposes no mutation UI.

This preparation is suitable for a v1.9.2 engineering milestone if it remains documentation and interface-contract only.
