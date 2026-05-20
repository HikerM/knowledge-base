# GUI Technology Selection

This document evaluates Windows desktop GUI / EXE technology options for `personal-knowledge-base`.

It follows:

- [docs/gui-product-ui-architecture.md](D:/AI/personal-knowledge-base/docs/gui-product-ui-architecture.md)
- [docs/gui-phase-1-read-only-mvp-contract.md](D:/AI/personal-knowledge-base/docs/gui-phase-1-read-only-mvp-contract.md)
- [docs/gui-phase-1-engineering-prep.md](D:/AI/personal-knowledge-base/docs/gui-phase-1-engineering-prep.md)

This is only a technology selection document. It does not implement GUI screens, create a GUI project, write Tauri/Electron/PySide/WinUI code, package an EXE, change Markdown storage, change SQLite schema, or change search/index/audit behavior.

## 1. Selection context

Current project constraints:

- The backend is already Python-first.
- The GUI must preserve the SQLite-hot / Markdown-source runtime model.
- The GUI must call `knowledge_app.services` through a GUI-to-service adapter.
- The GUI must not directly read or write Markdown.
- The GUI must not directly query or mutate SQLite.
- The GUI must not build CLI command strings as the integration mechanism.
- GUI Phase 1 is read-only: startup, home, search, knowledge library, document preview, task summary, and settings entry.
- Long-running work must go through `TaskQueueService`.
- `DocumentService.open_document` is the only document body read path.
- Future write-capable flows must keep plan -> local snapshot / backup -> approval -> TaskQueue -> service result.
- Local Only mode must work without Git, GitHub, or command-line knowledge.

Official documentation checked for this evaluation:

- [Qt for Python](https://doc.qt.io/qtforpython-6/) states that PySide6 lets Python applications use Qt6 APIs, and [Qt for Python deployment](https://doc.qt.io/qtforpython-6/deployment/index.html) recommends `pyside6-deploy` for optimized desktop deployment.
- [Tauri sidecar documentation](https://v2.tauri.app/develop/sidecar/) supports embedding external binaries as sidecars, including Python CLI apps or API servers bundled with PyInstaller.
- [Tauri distribution documentation](https://v2.tauri.app/distribute/) includes Windows installer paths, and [Tauri overview](https://v2.tauri.app/start/) positions the framework around small binaries using the system webview.
- [Electron process model documentation](https://www.electronjs.org/docs/latest/tutorial/process-model) describes Chromium-style main/renderer processes and secure preload/IPC boundaries, and [Electron packaging documentation](https://www.electronjs.org/docs/latest/tutorial/application-distribution) requires packaging/rebranding for distribution.
- [Windows App SDK documentation](https://learn.microsoft.com/en-us/windows/apps/windows-app-sdk/) and [WinUI 3 documentation](https://learn.microsoft.com/en-us/windows/apps/winui/winui3/) position WinUI as a modern native UI framework for Windows desktop apps.
- [PyInstaller operating mode documentation](https://pyinstaller.org/en/stable/operating-mode.html) documents that one-file bundles are slower to start than one-folder bundles because files are extracted to a temporary folder.

## 2. Candidate A: PySide6 / Qt for Python

Summary:

PySide6 is the closest fit for the first Read-only MVP because it can run in the same Python process as the existing service layer. It avoids a sidecar protocol, avoids a local HTTP server, and keeps the GUI-to-service adapter as a normal Python module boundary.

Evaluation:

| Area | Assessment |
|---|---|
| Integration with current Python service layer | Excellent. Views can call ViewModels, ViewModels call Python adapters, adapters call `knowledge_app.services` directly. No language bridge is required. |
| Need for local HTTP service / sidecar / bridge | Not required for Phase 1. A typed Python adapter is enough. |
| Startup performance | Good. Qt startup plus Python import cost is real, but there is no browser runtime, Node runtime, Rust host, local API server, or Python sidecar startup chain. |
| Memory risk | Moderate-low compared with webview/browser stacks. Qt widgets still require care for large tables, but virtualized/paginated models are enough for Phase 1. |
| Packaging complexity | Moderate. PyInstaller or `pyside6-deploy` can package a Python/Qt app, but Qt plugins, fonts, icons, and platform DLLs must be validated. |
| Windows EXE / installer complexity | Moderate. First release should use PyInstaller one-folder, then installer wrapping later. One-file should wait because of startup/extraction cost. |
| TaskQueue integration | Excellent. `TaskQueueService` can be called directly. UI polling can stay in Python timers/threads without IPC. |
| SQLite-hot runtime difficulty | Low. Existing services already preserve read-only SQLite metadata paths; GUI must not bypass them. |
| `DocumentService.open_document` access | Direct adapter call for one explicit document. No HTTP serialization needed. |
| GUI testing difficulty | Moderate. Model/adapter tests are straightforward in Python; full widget tests need Qt test tooling and screenshot/interaction checks later. |
| UI quality and component ecosystem | Good. Qt Widgets are mature for dense desktop tools. Visual polish is lower than modern React design systems unless a disciplined token/widget layer is added. |
| Long-term maintenance cost | Good for this repo because one language owns backend and GUI adapter. Qt-specific UI work must remain modular. |
| Future RSS / vector search / safe mutation UI | Good. Future services remain Python; GUI can add views without sidecars. Rich visualization may require custom widgets or a later web UI route. |
| Local Only mode fit | Excellent. A single Python desktop app can operate on user-selected workspaces without Git or network. |
| Risk of inducing CLI shelling | Low if adapter rules are enforced. Developers have no reason to shell out because services are importable. |
| Risk of direct Markdown/SQLite access | Medium-low. Python makes it easy to read files directly, so adapter tests must block this. But the service boundary is simple and enforceable. |

Fit for Phase 1:

- Best first version choice.
- Use Python adapter + ViewModel modules.
- Keep views thin and service-blind.
- Do not let views import `knowledge_core` or read filesystem paths.

## 3. Candidate B: Tauri + React + Python sidecar/service

Summary:

Tauri is attractive for a polished future UI because it uses web technologies and can keep bundle size lower than Electron by using the system webview. For this project, the main cost is that the Python service layer becomes a sidecar or local service, which adds lifecycle, IPC/API, logging, error propagation, and packaging complexity before Phase 1 has proven its read-only UI.

Evaluation:

| Area | Assessment |
|---|---|
| Integration with current Python service layer | Medium. Python services cannot be imported directly by React/Rust; they need a Python sidecar, local HTTP API, stdio protocol, or generated bridge. |
| Need for local HTTP service / sidecar / bridge | Required unless the backend is rewritten in Rust, which is not appropriate for Phase 1. Tauri officially supports sidecars/external binaries. |
| Startup performance | Good for the shell, but total startup depends on launching the Python sidecar and warming service modules. |
| Memory risk | Low-medium. Tauri avoids bundling Chromium, but it still runs a webview plus Python sidecar. |
| Packaging complexity | High for first version. Must package Rust/Tauri app, React build, Python sidecar, Python dependencies, and sidecar protocol. |
| Windows EXE / installer complexity | Medium-high. Tauri has Windows installer paths, but Python sidecar inclusion, updates, signing, and crash handling add complexity. |
| TaskQueue integration | Medium. Needs sidecar API endpoints/events for task list/progress/log. Streaming/log tail must be designed. |
| SQLite-hot runtime difficulty | Medium. The sidecar can preserve existing service paths, but React/Tauri must be prevented from using Tauri SQL/file plugins against `.kb/index.sqlite` or Markdown. |
| `DocumentService.open_document` access | Sidecar endpoint or IPC method returning one document payload. Must guard against bulk document reads. |
| GUI testing difficulty | Good for web components, medium for desktop integration. Needs contract tests for sidecar APIs and webview e2e tests. |
| UI quality and component ecosystem | Excellent. React ecosystem is strongest for adaptive shell, virtual lists, tables, search, and polished state views. |
| Long-term maintenance cost | Medium-high. Adds Rust/Tauri, frontend, build pipeline, sidecar API, and Python runtime packaging. |
| Future RSS / vector search / safe mutation UI | Excellent once sidecar contracts are solid. Web UI handles complex flows well. |
| Local Only mode fit | Good, but installer must reliably bundle Python sidecar and keep user data outside install dir. |
| Risk of inducing CLI shelling | Medium. Sidecar examples often start external binaries; this project must expose structured service APIs, not `scripts/kb.py` command strings. |
| Risk of direct Markdown/SQLite access | Medium. Tauri plugins can access filesystem/SQL; capabilities must forbid bypassing Python services. |

Fit for Phase 1:

- Strong second choice.
- Better as a Phase 2+ UI quality route after PySide6 validates the adapter/ViewModel contracts.
- If selected later, Python sidecar/service must preserve the same ViewModel contracts and SQLite-hot rules.

## 4. Candidate C: Electron + React + Python sidecar/service

Summary:

Electron provides the fastest path to a mature React desktop UI and has excellent testing/tooling familiarity. Its main drawbacks for this project are memory footprint, package size, multi-process complexity, and the same Python sidecar/API requirement as Tauri.

Evaluation:

| Area | Assessment |
|---|---|
| Integration with current Python service layer | Medium. Requires Python sidecar/local service or a separate bridge. Electron main/renderer processes cannot import Python services directly. |
| Need for local HTTP service / sidecar / bridge | Required for a clean architecture. The main process should own sidecar lifecycle; renderer should use secure IPC/preload APIs. |
| Startup performance | Medium-low. Electron starts Chromium/Node plus a Python sidecar. Acceptable for many tools, but not ideal for the SQLite-hot startup target. |
| Memory risk | High relative to other options because each app includes Chromium/Node process overhead. |
| Packaging complexity | Medium. Electron packaging is common and well documented, but Python sidecar bundling adds a second runtime. |
| Windows EXE / installer complexity | Medium. Electron Forge/build tools help, but sidecar signing, updates, and antivirus friction remain. |
| TaskQueue integration | Medium. Needs IPC or local API for task list/progress/log; renderer must not touch task files. |
| SQLite-hot runtime difficulty | Medium. Python sidecar can preserve it, but Electron main/renderer must be blocked from using Node filesystem/SQLite shortcuts. |
| `DocumentService.open_document` access | Sidecar endpoint or IPC method. Must ensure preview opens one explicit document only. |
| GUI testing difficulty | Good. React component tests and Playwright/Electron automation are mature. |
| UI quality and component ecosystem | Excellent. React ecosystem is rich and fast for UI iteration. |
| Long-term maintenance cost | Medium-high. Web frontend, Electron security updates, Node tooling, and Python sidecar all need upkeep. |
| Future RSS / vector search / safe mutation UI | Good. Complex workflows fit React well after sidecar contracts exist. |
| Local Only mode fit | Good if packaged correctly, but package size and runtime overhead are less friendly for a small local-only tool. |
| Risk of inducing CLI shelling | Medium-high. It is easy to spawn child processes from the main process; rules must require structured sidecar API rather than CLI strings. |
| Risk of direct Markdown/SQLite access | High if Node integration or main-process shortcuts are allowed. Must enforce preload/IPC and service-only access. |

Fit for Phase 1:

- Viable backup if rapid React UI is more important than footprint.
- Not preferred for first Read-only MVP because it adds sidecar and browser runtime costs before the Python service adapter is proven.

## 5. Candidate D: WinUI / .NET + Python bridge

Summary:

WinUI is the strongest native Windows UI option and aligns with Fluent Design. For this project, it is not a good first-version choice because the backend is Python. A WinUI app would need a Python bridge/sidecar/local API or a partial backend rewrite, which increases risk before the Read-only MVP exists.

Evaluation:

| Area | Assessment |
|---|---|
| Integration with current Python service layer | Poor-medium. Requires a Python bridge, local service, COM/IPC style integration, or backend rewrite. |
| Need for local HTTP service / sidecar / bridge | Required unless core services are rewritten in .NET. |
| Startup performance | Excellent for native UI, but bridge/sidecar startup reduces the advantage. |
| Memory risk | Low-medium. Native UI footprint is generally favorable, but Python bridge still adds runtime cost. |
| Packaging complexity | High for this repo. Must coordinate Windows App SDK deployment and Python runtime/bridge packaging. |
| Windows EXE / installer complexity | Medium-high. Strong Windows tooling, but Python data/service bundling complicates Local Only distribution. |
| TaskQueue integration | Poor-medium. Requires bridge APIs for task records, progress, logs, and cancellation states. |
| SQLite-hot runtime difficulty | Medium. A .NET app may be tempted to query SQLite directly; this must be prohibited to preserve Python service behavior. |
| `DocumentService.open_document` access | Bridge call into Python service. Direct file reads from .NET must be forbidden. |
| GUI testing difficulty | Medium. Good native tooling, but Python bridge and service contract testing add complexity. |
| UI quality and component ecosystem | Excellent for Windows-native Fluent UI. |
| Long-term maintenance cost | High for this Python-first repo because it introduces a second primary backend ecosystem. |
| Future RSS / vector search / safe mutation UI | Medium. Good UI capability, but every Python service expansion needs bridge work. |
| Local Only mode fit | Good in principle, but installer must safely handle Python runtime and user workspace separation. |
| Risk of inducing CLI shelling | Medium. If bridge is not designed, developers may shell out to `scripts/kb.py`. |
| Risk of direct Markdown/SQLite access | Medium-high. .NET has easy SQLite/file access; service-only policy must be enforced. |

Fit for Phase 1:

- Not recommended for first version.
- Reconsider only if Windows-native integration becomes a higher priority than Python service reuse.

## 6. Decision matrix

Scoring uses 1-10 per dimension. Weighted score is `score / 10 * weight`, with a maximum total of 100.

| Dimension | Weight | PySide6 / Qt for Python | Tauri + React + Python sidecar | Electron + React + Python sidecar | WinUI / .NET + Python bridge |
|---|---:|---:|---:|---:|---:|
| Python service reuse | 20 | 10 | 6 | 6 | 3 |
| Startup performance | 15 | 8 | 8 | 5 | 9 |
| Packaging simplicity | 15 | 8 | 5 | 6 | 5 |
| Long-term stability | 15 | 8 | 7 | 7 | 8 |
| GUI quality | 10 | 7 | 9 | 9 | 9 |
| TaskQueue integration | 10 | 10 | 6 | 6 | 4 |
| Testing strategy | 10 | 7 | 8 | 9 | 7 |
| Future extensibility | 5 | 7 | 9 | 8 | 6 |
| Weighted total | 100 | 83.5 | 69.5 | 67.0 | 62.0 |

Ranking:

1. PySide6 / Qt for Python: 83.5
2. Tauri + React + Python sidecar/service: 69.5
3. Electron + React + Python sidecar/service: 67.0
4. WinUI / .NET + Python bridge: 62.0

## 7. Recommendation

First choice:

- PySide6 / Qt for Python.

Why:

- It maximizes reuse of the existing Python service layer.
- It does not require a sidecar, local HTTP service, IPC protocol, or backend rewrite for Phase 1.
- It keeps startup aligned with the SQLite-hot model.
- It makes `TaskQueueService` and `DocumentService.open_document` direct adapter calls.
- It gives the smallest architecture delta between v1.9.2 engineering preparation and the first Read-only MVP skeleton.

Second choice:

- Tauri + React + Python sidecar/service.

Why:

- It is a strong future UI-quality route with excellent React ecosystem support and lower browser-bundle overhead than Electron.
- It should wait until the Python adapter/ViewModel contracts are proven because it requires sidecar lifecycle and API design.

Not recommended for first version:

- Electron + React + Python sidecar/service.
- WinUI / .NET + Python bridge.

Why Electron is not first:

- It is viable and fast for React UI work, but the first MVP would pay both Chromium/Node overhead and Python sidecar complexity.
- It creates more risk around CLI shelling and direct filesystem/SQLite shortcuts unless IPC boundaries are tightly enforced.

Why WinUI is not first:

- It has excellent Windows-native UI quality, but the Python bridge or rewrite cost is too high for the first Read-only MVP.
- It is a better option only if native Windows integration becomes the dominant requirement.

Decision:

```text
GUI Phase 1 Read-only MVP should start with PySide6 / Qt for Python.
Tauri + React should remain the preferred later UI-quality enhancement route.
Electron is a rapid Web UI fallback.
WinUI/.NET is deferred beyond the first version.
```

## 8. Recommended PySide6 GUI engineering structure

This structure is a design only. Do not create these files until the implementation skeleton phase starts.

```text
gui/
  app.py
  main_window.py
  shell/
    app_shell.py
    top_bar.py
    sidebar_nav.py
    status_bar.py
    inspector_panel.py
  views/
    workspace_gate_view.py
    home_view.py
    search_view.py
    knowledge_library_view.py
    document_preview_view.py
    task_summary_view.py
    settings_entry_view.py
  viewmodels/
    base.py
    startup_vm.py
    home_vm.py
    search_vm.py
    library_vm.py
    document_vm.py
    task_vm.py
    settings_vm.py
  adapters/
    gui_service_adapter.py
    workspace_adapter.py
    search_adapter.py
    category_adapter.py
    document_adapter.py
    task_adapter.py
    settings_adapter.py
  widgets/
    empty_state.py
    error_state.py
    loading_state.py
    metadata_badge.py
    virtual_table.py
    read_only_markdown_viewer.py
    task_progress_panel.py
  fixtures/
    startup_missing_index.json
    startup_ready_index.json
    search_results.json
    search_empty.json
    library_summary.json
    document_preview.json
    task_summary.json
  tests/
    adapter_contract_test.py
    startup_guard_test.py
    search_viewmodel_test.py
    library_viewmodel_test.py
    document_preview_test.py
    task_summary_test.py
```

Layer rules:

- View modules only own UI rendering, focus, layout, and widget state.
- View modules must not import `knowledge_core`.
- View modules must not import concrete services directly.
- ViewModels call the GUI-to-service adapter.
- Adapters call `knowledge_app.services`.
- Adapters convert `OperationResult` and service payloads into read-only ViewModel envelopes.
- GUI code must not directly read or write Markdown.
- GUI code must not directly read or write SQLite.
- GUI code must not build CLI command strings.
- Long-running work must go through `TaskQueueService`.
- Document body reads must go through `DocumentService.open_document` for one explicit document.
- Phase 1 must not expose mutation UI, RSS, vector search, category execute, archive/delete/merge/template apply/restore execute, or cleanup execute.

Threading and responsiveness:

- Service calls that may block the UI should run through a worker abstraction.
- Startup status should remain lightweight and should not trigger index/audit/secret-scan.
- Search and library calls should use pagination.
- Task progress polling should use a timer or worker that calls `TaskQueueService`.
- UI cancellation in Phase 1 cancels only the UI request display, not backend tasks.

## 9. First packaging strategy

This is packaging design only. Do not implement packaging in this phase.

Development mode:

- Run the Python app directly.
- Use the repository workspace during development.
- Keep GUI settings separate from workspace data.
- Run service and adapter tests before opening the GUI.

Packaging mode:

- Prefer PyInstaller one-folder for the first packaged build.
- Defer one-file packaging because PyInstaller documents slower startup from temporary extraction and harder diagnosis compared with one-folder.
- Validate Qt plugins, platform DLLs, icons, fonts, markdown renderer assets, and Python service imports in one-folder mode first.
- Add an installer only after the one-folder build passes startup/search/document/task smoke checks.

Data layout:

```text
Install directory:
  application binaries only
  bundled Python/Qt runtime only
  no user knowledge data

User AppData:
  GUI settings
  GUI logs
  recent workspace list
  non-source UI cache with explicit size limits

Workspace selected by user:
  knowledge/
  config/
  templates/
  reports/
  docs/
  .kb/index.sqlite
  .kb/tasks/
  backups/
```

Rules:

- User data must not live in the install directory.
- Workspace selection must be explicit.
- `.kb/index.sqlite` remains rebuildable and workspace-local.
- Backup/Snapshot remains the default recovery mechanism.
- Git remains optional.
- Packaged GUI must still use `WorkspaceStatusService` at startup.
- Missing index must show `index_status=missing` and must not auto-index.

## 10. Next phase

The next phase should be:

```text
GUI Phase 1 Read-only MVP Implementation Skeleton
```

It may start only after this technology selection document is reviewed and accepted.

The skeleton phase should create only the minimal PySide6 project structure, adapter interfaces, ViewModel models, and test harness needed to prove:

- startup path.
- formal search path.
- category/library metadata path.
- explicit document preview path.
- read-only task summary path.
- settings entry read-only path.

It must still not expose mutation UI, destructive actions, RSS, vector search, or direct Markdown/SQLite access.
