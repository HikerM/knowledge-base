# AI Capability Registry

本文定义 AI 助手能力注册表。Registry 是未来 AI 助手可以调用的唯一能力白名单；未注册能力一律 forbidden。

本阶段只定义机器可读设计和示例配置，不实现 registry loader，不接真实 AI，不改变 service 行为。

## 1. Capability Levels

| Level | Name | Allowed behavior |
| --- | --- | --- |
| L0 | read_only | 只读 service 调用，例如搜索、打开文档、读取任务状态 |
| L1 | ai_suggestion | AI 生成摘要、解释、比较、草稿或建议，但不写入 |
| L2 | plan_only | 生成结构化计划，不执行 mutation |
| L3 | safe_execute | 低风险安全执行，必须 plan/snapshot/approval/TaskQueue |
| L4 | forbidden/destructive | 禁止能力或破坏性能力 |

## 2. Registry Rules

- AI 只能调用 registry 中存在且 policy 允许的 capability。
- 未注册 capability 一律 forbidden。
- Registry entry 必须声明 service boundary；不能写“call CLI”或“read file”。
- L0/L1 仍必须通过 `knowledge_app.services` 获取数据。
- L2 只能生成 plan，不得移动、删除、恢复或改写 Markdown。
- L3 必须满足 `plan -> snapshot -> approval -> TaskQueue -> execute`。
- L4 不得执行；如需要响应，只能返回拒绝、风险说明或未来 plan-only 建议。

## 3. Capability Entry Schema

```yaml
id: search_knowledge
intent: search_knowledge
level: L0
service: knowledge_app.services.search_service.SearchService.search
read_only: true
requires_ai: false
requires_confirmation: false
requires_cloud_context_preview: false
allowed_context:
  - formal_search_results
audit:
  record_intent: true
  record_citations: true
  record_context_ids: true
current_version: design_only
```

Required fields:

- `id`
- `intent`
- `level`
- `service` or `provider`
- `read_only`
- `requires_ai`
- `requires_confirmation`
- `allowed_context`
- `audit`
- `current_version`

## 4. Core Capabilities

| Capability | Intent | Service / provider | Level | Confirmation | Current status |
| --- | --- | --- | --- | --- | --- |
| `search_knowledge` | `search_knowledge` | `SearchService.search` | L0 | no | design only |
| `open_document` | `open_document` | `DocumentService.open_document` | L0 | no | design only |
| `summarize_current_document` | `summarize_document` | `DocumentService.open_document` + `AIProvider.summarize` | L1 | cloud or expanded context requires confirmation | design only |
| `explain_current_document` | `explain_document` | `DocumentService.open_document` + `AIProvider.generate` | L1 | cloud or expanded context requires confirmation | design only |
| `compare_selected_documents` | `compare_documents` | `DocumentService.open_document` + `AIProvider.compare` | L1 | yes when multiple docs or cloud | design only |
| `create_checklist_draft` | `create_checklist_draft` | `AIProvider.extract_checklist` | L1 | yes if saving later | design only |
| `suggest_category` | `suggest_category` | `CategoryService` + `AIProvider.classify` | L1 | no for suggestion | design only |
| `create_memory_candidate` | `create_memory_candidate` | future `AIMemoryService.create_candidate` | L1 | save requires yes | design only |
| `update_category_display_name` | `update_category_display_name` | `SafeMutationService` | L3 | yes | design only; future safe execute |
| `update_category_description` | `update_category_description` | `SafeMutationService` | L3 | yes | design only; future safe execute |
| `archive_documents_plan` | `archive_documents` | future plan service only | L2 | yes | future plan-only |
| `delete_document` | `delete_documents` | none | L4 | n/a | forbidden |
| `restore_backup_plan` | `restore_backup` | `RestorePlanService` | L2 | yes | future plan-only |
| `promote_knowledge` | `promote_knowledge` | future review plan only | L4 current / L2 future | yes plus reviewer data | forbidden current |

## 5. Safe Execute Contract

Only L3 capabilities can execute, and only if all gates pass:

```text
CapabilityRegistry says level=L3
  ↓
PermissionPolicy requires confirmation
  ↓
Plan is generated and shown
  ↓
Snapshot is created and verified
  ↓
User approval records exact plan hash
  ↓
TaskQueue runs approved task
  ↓
Result summary is returned and audited
```

L3 rules:

- The task input must include `capability_id`, `intent`, target id, proposed value, plan id/hash, snapshot id and approval id.
- The task result must include `task_id`, `status`, `result_summary`, warnings and errors.
- Approval expiry, plan hash mismatch or missing snapshot must deny execution.
- AI cannot retry by changing the plan silently.

## 6. Forbidden Capability Handling

For L4 capabilities:

- Return `error_card` or `risk_notice_card`.
- Explain that the capability is forbidden in current stage.
- If useful, offer read-only search, document summary or plan-only alternative.
- Do not create TaskQueue tasks for destructive work.
- Do not simulate execution in AI text.

## 7. Example Config

The draft machine-readable registry is in:

```text
config/ai-capabilities.example.yaml
```

That file is an example contract, not runtime configuration. Loading and enforcement are future work.
