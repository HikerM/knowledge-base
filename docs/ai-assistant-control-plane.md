# AI Assistant Control Plane

本文定义 v2.1.0 AI Assistant Control Plane 的设计边界。当前阶段只做控制平面设计，不实现真实 AI，不接入 OpenAI、本地大模型或 ModelScope，不下载模型，不实现右下角悬浮聊天 UI，不做 RSS、vector search 或 mutation UI。

本设计的目标是让未来 AI 助手可以通过自然语言搜索资料、总结文档、生成计划和发起安全能力，同时保持受控、可审计、可确认、可撤回。

## 1. Scope

本阶段交付：

- AI 助手总架构。
- Intent taxonomy。
- Capability registry。
- Permission policy。
- Memory / conversation store 设计。
- Context policy。
- Floating assistant UI contract。
- AIProvider 抽象和模型档位记录。
- 示例配置草案。

本阶段不做：

- 不实现 AI 模型。
- 不接 OpenAI、本地大模型或 ModelScope。
- 不下载或安装模型。
- 不实现悬浮聊天 UI。
- 不做 RSS。
- 不做 vector search。
- 不做 mutation UI。
- 不修改 `knowledge/**/*.md`。
- 不修改 SQLite schema。
- 不改变 `search` / `index` / `audit` 行为。

## 2. Architecture

AI 助手必须走控制平面：

```text
用户自然语言
  ↓
IntentRouter
  ↓
CapabilityRegistry
  ↓
PermissionPolicy
  ↓
ContextBuilder
  ↓
AIProvider
  ↓
Response / Plan
  ↓
Confirmation if needed
  ↓
Service / TaskQueue
```

说明：

- `IntentRouter` 只负责把自然语言映射成受控 intent，不执行能力。
- `CapabilityRegistry` 是能力白名单。AI 只能调用 registry 中允许的 capability；未注册能力一律 forbidden。
- `PermissionPolicy` 决定 capability 是否允许、是否需要确认、是否必须本地执行、是否允许云端发送上下文。
- `ContextBuilder` 只能通过 `knowledge_app.services` 获取上下文，不得直接读 Markdown、SQLite 或 task 文件。
- `AIProvider` 是抽象接口。本阶段只定义接口，不接真实模型。
- `Response / Plan` 必须区分普通回答、引用结果、计划和待确认操作。
- 需要确认的能力必须先返回 `ConfirmationCard`，确认后才能进入 service 或 TaskQueue。
- 写操作必须遵守 `plan -> snapshot -> approval -> TaskQueue -> execute`。

## 3. Non-bypass Rules

AI 助手不得绕过现有 service 边界：

- AI 助手不能直接读写 Markdown。
- AI 助手不能直接读写 SQLite。
- AI 助手不能拼接 CLI 命令字符串。
- AI 助手不能直接读取 `.kb/tasks/`、backup zip 或 runtime cache。
- AI 助手只能通过 `knowledge_app.services` 获取搜索、文档、分类、任务、备份、计划和安全执行结果。
- AI 输出不能把 `raw`、`distilled`、`research` 或 `review_required=true` 内容当正式项目规则。
- AI 不能自动删除、归档、恢复、promote、修改文件或清空资料。
- AI 不能自动保存长期记忆。
- 云端 AI 发送资料前必须展示 context preview 并获得用户确认。

## 4. Component Responsibilities

### IntentRouter

职责：

- 从用户自然语言中识别 intent。
- 输出结构化 `IntentRequest`。
- 对无法识别、含混或高风险请求返回 `unknown` / `unsupported`。
- 不读取知识库，不调用 provider，不执行 service。

建议输出：

```json
{
  "intent": "search_knowledge",
  "confidence": "high",
  "arguments": {
    "query": "startup no auto index"
  },
  "risk_level": "low",
  "needs_ai": false
}
```

### CapabilityRegistry

职责：

- 保存 intent 到 capability 的白名单映射。
- 定义每个 capability 的 level、service、输入、输出、确认要求和审计字段。
- 拒绝未注册 capability。
- 阻止 AI 自行发明 service、读取路径或执行命令。

能力等级：

| Level | Name | Meaning |
| --- | --- | --- |
| L0 | read_only | 只读 service 能力，不需要 AI 或只需要轻量路由 |
| L1 | ai_suggestion | 生成摘要、解释、草稿或建议，不直接写入 |
| L2 | plan_only | 只生成计划，不执行 mutation |
| L3 | safe_execute | 低风险安全执行，必须 plan/snapshot/approval/task |
| L4 | forbidden/destructive | 当前禁止或破坏性能力 |

### PermissionPolicy

职责：

- 根据 capability level、上下文、用户设置和数据敏感性做 allow / confirm / deny。
- 控制云端 provider 的上下文发送。
- 强制 safe execute 的 plan、snapshot、approval 和 TaskQueue。
- 强制 destructive / forbidden 能力不可执行。

### ContextBuilder

职责：

- 只从明确允许的上下文中构建 prompt context。
- 默认只允许当前打开文档、用户选中的搜索结果、formal 层 `SearchService` 结果和用户确认保存的长期记忆。
- 对 cloud provider 必须先生成 context preview。
- 对 raw / distilled / research 结果必须标注“未经审核，不能作为正式项目规则”。
- 控制上下文大小，不允许全库无边界读取。

### AIProvider

设计接口：

```text
AIProvider
  generate(request, context) -> AIResponse
  summarize(document_context, options) -> AIResponse
  classify(text, taxonomy) -> ClassificationResult
  extract_checklist(context, options) -> ChecklistDraft
  compare(left_context, right_context, options) -> ComparisonResult
```

Provider 类型：

- `MockAIProvider`: 测试和离线占位，返回 deterministic mock response。
- `LocalModelProvider`: 后续本地模型 provider，仅设计，不实现。
- `CloudModelProvider`: 后续云端模型 provider，必须受 cloud context preview 和 privacy confirmation 约束。

本阶段不实现上述 provider。

## 5. Service And TaskQueue Boundary

只读能力可以直接走 service：

- `SearchService.search`
- `DocumentService.open_document`
- `CategoryService` metadata read paths
- `TaskQueueService` read-only status/progress/log paths

写操作必须走安全链路：

```text
PlanService / SafeMutationService plan
  ↓
SnapshotService
  ↓
User approval
  ↓
TaskQueueService create task
  ↓
TaskQueueService execute safe task
  ↓
Result summary + audit trail
```

当前已存在的低风险 safe execute 只能作为未来 AI 控制平面的候选能力：

- `category_update_display_name_execute`
- `category_update_description_execute`

即使这些后端能力存在，AI 助手也不能自动执行；必须展示计划、snapshot、approval 和任务结果。

Archive、delete、restore、template apply、promote 等能力不得由 AI 自动执行。当前只允许 forbidden 或 future plan-only 设计。

## 6. Audit Trail

每次 AI 控制平面调用都应形成可审计记录：

```json
{
  "event_id": "string",
  "conversation_id": "string",
  "workspace_id": "string",
  "created_at": "string",
  "intent": "search_knowledge",
  "capability_id": "search_knowledge",
  "capability_level": "L0",
  "policy_decision": "allow|confirm|required_context_preview|deny",
  "context_sources": [],
  "citations": [],
  "provider_kind": "mock|local|cloud|none",
  "confirmation_id": "string|null",
  "approval_id": "string|null",
  "task_id": "string|null",
  "result_type": "assistant_text|plan_card|task_progress_card|error_card"
}
```

审计记录不应默认复制完整私密正文；应记录 document id、chunk id、source metadata、policy decision、用户确认和 task id。

## 7. Model Strategy Design Only

后续模型档位仅作为设计记录：

| Tier | Candidate |
| --- | --- |
| 超轻量 | Qwen3-0.6B-GGUF Q4_K_M |
| 轻量增强 | Qwen3-1.7B-GGUF Q4_K_M |
| 标准 | Qwen3-4B-GGUF Q4 |
| 高质量 | Qwen3-8B-GGUF Q4 |

本阶段规则：

- 不下载模型。
- 不接真实模型。
- 不做模型安装助手。
- 不要求用户安装模型运行时。
- 模型安装助手必须作为后续独立设计，并继续遵守 permission、context preview 和 service boundary。

## 8. Future Test Plan

未来测试文件规划：

- `tests/ai_intent_routing_test.py`
- `tests/ai_capability_registry_test.py`
- `tests/ai_permission_policy_test.py`
- `tests/ai_context_builder_test.py`
- `tests/ai_memory_service_test.py`
- `tests/ai_conversation_store_test.py`
- `tests/ai_assistant_mock_test.py`
- `tests/gui_ai_assistant_test.py`

本阶段可以只写文档；若新增示例配置，应做 YAML 静态解析检查。

## 9. Acceptance Boundary

v2.1.0 建议纳入范围：

- AI Control Plane 设计文档。
- Intent / capability / permission / memory / context / UI contract 文档。
- `config/ai-capabilities.example.yaml` 示例配置草案。
- README / AGENTS 安全边界更新。

不纳入范围：

- 真实 AI provider。
- 模型安装。
- 悬浮聊天 UI 实现。
- RSS / vector search。
- mutation UI。
- Markdown 或 SQLite schema 修改。
