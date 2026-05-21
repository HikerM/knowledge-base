# AI Floating Assistant UI Contract

本文定义未来右下角悬浮 AI 助手的 UI contract。当前阶段只做设计，不实现 UI，不接真实 AI，不暴露 mutation UI。

本 contract 适用于 Windows desktop GUI，当前推荐实现路线仍是 PySide6 / Qt for Python。未来若切换 Tauri / React，仍必须保留 View -> ViewModel -> adapter -> `knowledge_app.services` 边界。

## 1. Product Scope

包含：

- 右下角悬浮按钮。
- 点击打开悬浮聊天框。
- 用户消息右侧。
- AI 消息左侧。
- 用户有头像 / “我”。
- AI 有头像 / “AI 助手”。
- 不同气泡样式。
- 系统提示。
- 来源引用卡片。
- 操作计划卡片。
- 任务进度卡片。
- 风险提醒卡片。
- 记忆候选卡片。

不包含：

- 真实聊天 UI 实现。
- AI provider 接入。
- RSS。
- vector search。
- mutation UI。
- 绕过 service layer 的快捷入口。

## 2. Screen Placement

AssistantLauncher:

- Anchor: bottom-right of app window.
- Margin: 24px desktop, 16px narrow window.
- Size: 48px default, 44px compact.
- Must not cover StatusBar critical indicators.
- Must be keyboard reachable after main shell navigation.

AssistantPanel:

- Opens above launcher as a floating panel.
- Default desktop size: 420px wide, 560px high.
- Large screen max: 480px wide, 720px high.
- Minimum usable size: 360px wide, 440px high.
- At narrow widths, panel becomes bottom sheet or right drawer.
- Panel must not become the main navigation surface.

## 3. Component Tree

```text
AssistantOverlay
├── AssistantLauncher
└── AssistantPanel
    ├── AssistantHeader
    │   ├── AssistantAvatar
    │   ├── Title: AI 助手
    │   ├── ProviderModeBadge
    │   └── CloseButton
    ├── ConversationViewport
    │   ├── SystemNotice
    │   ├── UserMessageBubble
    │   ├── AssistantMessageBubble
    │   ├── CitationCards
    │   ├── SearchResultCards
    │   ├── PlanCard
    │   ├── ConfirmationCard
    │   ├── TaskProgressCard
    │   ├── RiskNoticeCard
    │   ├── MemoryCandidateCard
    │   └── ErrorCard
    └── Composer
        ├── ContextChips
        ├── TextInput
        └── SendButton
```

## 4. Message Presentation Rules

- 普通回答是气泡。
- 用户消息右侧，头像显示“我”。
- AI 消息左侧，头像显示“AI 助手”。
- 搜索结果是卡片，不塞进普通气泡。
- 计划是 `PlanCard`。
- 需要确认是 `ConfirmationCard`。
- 任务是 `TaskProgressCard`。
- 长期记忆候选是 `MemoryCandidateCard`。
- 风险和隐私提示是 `RiskNoticeCard` 或 `PrivacyNoticeCard`。
- 引用来源用 `CitationCards`，必须可展开查看 layer/status/source_type/confidence。

## 5. Card Contracts

### CitationCard

Purpose:

- Show the exact sources behind an AI answer.

Fields:

- title.
- layer.
- status.
- source type.
- confidence.
- review_required.
- citation id.
- warning if unconfirmed.

Rules:

- Formal citations can be compact.
- Unconfirmed citations must show warning.
- Quarantine/rejected citations should not appear unless explicitly part of a blocked/denied explanation.

### SearchResultCard

Purpose:

- Display service-backed search results.

Actions:

- Open document through service.
- Add to selected context.

Rules:

- Must not preload Markdown body.
- Must show layer/status/confidence.
- Must preserve pagination.

### PlanCard

Purpose:

- Show structured plan before any risky operation.

Fields:

- operation.
- target ids.
- actions.
- blockers.
- validation commands.
- snapshot requirement.
- rollback notes.

Rules:

- PlanCard represents planned actions only, not executed actions.
- `blocked=true` plans are valid display states.
- PlanCard cannot execute by itself.

### ConfirmationCard

Purpose:

- Gate cloud context sending, memory save and safe execute.

Fields:

- exact action.
- context preview summary.
- risks.
- required snapshot/approval/task.
- approve/reject actions.

Rules:

- Approval must bind to plan hash or context preview hash.
- If context changes, confirmation expires.

### TaskProgressCard

Purpose:

- Show TaskQueue status.

Fields:

- task id.
- status.
- progress percent.
- cancel requested.
- error.
- log path reference through service.
- result summary.

Rules:

- Reads task state through `TaskQueueService`.
- Does not read `.kb/tasks/` directly.
- Destructive task creation is not exposed.

### RiskNoticeCard

Purpose:

- Surface denied or high-risk operations.

Examples:

- delete forbidden.
- restore execute forbidden.
- cloud context requires confirmation.
- unconfirmed sources warning.

### MemoryCandidateCard

Purpose:

- Let users decide whether to save a long-term memory.

Actions:

- Save.
- Edit then save.
- Reject.
- Dismiss.

Rules:

- Candidate is not saved until confirmed.
- Sensitive candidates default to blocked.

## 6. Data And Service Mapping

| UI action | Service boundary | Notes |
| --- | --- | --- |
| Send message | future AI assistant service | routes through IntentRouter |
| Search from assistant | `SearchService.search` | formal results by default |
| Open citation | `DocumentService.open_document` | explicit one document only |
| Summarize current doc | `DocumentService.open_document` + `AIProvider.summarize` | cloud preview if needed |
| Create plan | plan service / registry | plan-only unless L3 |
| Confirm safe execute | `SafeMutationService` + `SnapshotService` + `TaskQueueService` | future only |
| Show task progress | `TaskQueueService` | read-only status/log/progress |
| Save memory | future `AIMemoryService` | explicit confirmation only |

The UI must never call `knowledge_core`, filesystem, SQLite or CLI command strings directly.

## 7. Adaptive Layout

Target desktop sizes:

- Minimum: 1100x720.
- Preferred: 1440x900.
- Large: 1920x1080.
- Ultra-wide: 2560x1440.

Rules:

- Main app shell remains usable when assistant is open.
- Panel scrolls conversation internally.
- Composer remains pinned inside panel.
- Long cards collapse sections instead of overflowing.
- Citations and task logs have their own scroll areas when expanded.
- Text must not overlap bubbles, cards, buttons or status chips.
- Focus trap applies inside modal-like confirmation cards only when required.

## 8. States

Required states:

- closed.
- opening.
- open idle.
- composing.
- provider unavailable.
- context preview required.
- waiting for confirmation.
- task running.
- task succeeded.
- task failed.
- memory candidate pending.
- denied operation.
- no workspace.
- index missing.
- document not selected.
- service unavailable.

## 9. Accessibility

Requirements:

- Launcher has accessible name.
- Header identifies provider mode.
- Message order follows reading order.
- User and AI messages have role labels.
- Cards have headings.
- Confirmation actions are keyboard reachable.
- Escape closes panel unless a blocking confirmation is active.
- Focus returns to launcher when panel closes.
- Color is not the only signal for risk, source status or task status.

## 10. Implementation Boundary

Future implementation must follow existing GUI boundaries:

```text
View
  ↓
ViewModel
  ↓
gui/adapters/service_adapter.py
  ↓
knowledge_app.services
```

Forbidden:

- Direct Markdown read/write.
- Direct SQLite read/write.
- CLI command construction.
- Direct `.kb/tasks/` read.
- Embedding fake data in reusable UI components.
- Exposing destructive execute buttons.

## 11. Acceptance Criteria

- Floating button is bottom-right and does not block core status controls.
- Chat panel distinguishes user and AI messages.
- Ordinary answers render as bubbles.
- Search results render as cards.
- Plans render as `PlanCard`.
- Confirmation renders as `ConfirmationCard`.
- Tasks render as `TaskProgressCard`.
- Memory candidates render as `MemoryCandidateCard`.
- Risk and privacy states are visible.
- Citations are visible for knowledge-base-backed answers.
- All meaningful actions map to service boundaries.
- No mutation UI is implemented in this stage.
