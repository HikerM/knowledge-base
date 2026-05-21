# AI Intent Taxonomy

本文定义 v2.1.0 AI 助手自然语言意图分类。当前阶段只做 taxonomy 设计，不实现路由器、不接真实 AI、不改变现有 service 行为。

## 1. Risk Levels

| Risk | Meaning | Default Policy |
| --- | --- | --- |
| R0 | 只读检索或打开 | 默认允许 |
| R1 | AI 生成解释、摘要、建议，不写入 | 默认允许，本地优先；云端需 context preview |
| R2 | plan-only，可能涉及未来 mutation | 只允许生成计划，执行必须禁止或另行确认 |
| R3 | 低风险 safe execute | 必须 plan/snapshot/approval/TaskQueue |
| R4 | destructive / forbidden | 当前禁止 |

## 2. Intent Table

| Intent | User examples | Risk | Read-only | Needs AI | Needs confirmation | Executable | v2.1.0 status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `search_knowledge` | “搜索启动时不能自动 index 的规则”；“找 GUI service boundary” | R0 | yes | no | no | future yes via `SearchService.search` | design allowed, no runtime implementation |
| `open_document` | “打开这条搜索结果”；“看第 3 篇文档” | R0 | yes | no | no | future yes via `DocumentService.open_document` | design allowed, no runtime implementation |
| `summarize_document` | “总结当前文档”；“把这篇规则压缩成要点” | R1 | yes | yes | cloud provider or non-current context needs confirmation | future suggestion only | design allowed, no provider implementation |
| `explain_document` | “解释这篇文档为什么这么规定”；“这条规则适用于什么场景” | R1 | yes | yes | cloud provider or unconfirmed context needs confirmation | future suggestion only | design allowed, no provider implementation |
| `compare_documents` | “比较这两篇规则的差异”；“找出这两个 checklist 的冲突” | R1 | yes | yes | yes when selecting multiple docs or using cloud | future suggestion only | design allowed, no provider implementation |
| `create_checklist_draft` | “根据当前文档生成 checklist 草稿”；“把这些结果整理成检查清单” | R1 / R2 if saving | response only is read-only | yes | yes if saving candidate | future suggestion only; save is future plan-only | design allowed, no write |
| `suggest_category` | “这篇文档应该放哪个分类”；“推荐分类但不要修改” | R1 | yes | yes | no for suggestion; yes for applying change | future suggestion only | design allowed, no write |
| `create_memory_candidate` | “记住我喜欢 concise 输出”；“以后默认给我验收命令” | R1 | no if persisted | yes | yes | future candidate only; save requires explicit confirmation | design allowed, no auto-save |
| `update_category_display_name` | “把 frontend 显示名改成前端工程” | R3 | no | no | yes | future safe execute via `SafeMutationService` | design only; must plan/snapshot/approval/task |
| `update_category_description` | “更新 backend 分类描述” | R3 | no | no | yes | future safe execute via `SafeMutationService` | design only; must plan/snapshot/approval/task |
| `archive_documents` | “把这些旧 raw 归档”；“归档过期规则” | R4 for execute, R2 for plan | no | optional | yes | execute forbidden; future plan-only only | design forbidden for execute |
| `delete_documents` | “删除这些文档”；“清空 raw” | R4 | no | no | yes but still denied | no | forbidden |
| `restore_backup` | “恢复昨天的备份”；“覆盖当前 workspace” | R4 for execute, R2 for plan | no | no | yes | execute forbidden; future restore-plan only | design forbidden for execute |
| `promote_knowledge` | “把这个 distilled 提升为 rule”；“自动 promote 这些建议” | R4 current, R2 future plan-only | no | optional | yes plus human review info | no current execute | forbidden; future plan-only with reviewer data |
| `unknown` | “随便整理一下”；ambiguous high-risk request | R4 | unknown | unknown | n/a | no | unsupported |
| `unsupported` | “安装模型”；“接 OpenAI”；“做向量检索”；“实现聊天 UI” | R4 | n/a | n/a | n/a | no | unsupported in v2.1.0 |

## 3. Intent Routing Rules

- 高风险和含混请求必须降级为 `unknown` 或 `unsupported`。
- 用户要求“自动处理”“帮我直接改”“清理掉”时，如果目标可能涉及 Markdown、SQLite、archive、delete、restore、promote 或 config mutation，必须走 policy 检查。
- `raw`、`distilled`、`research`、`review_required=true`、`quarantine`、`rejected` 或 archived 内容不得作为默认正式上下文。
- `summarize_document` 和 `explain_document` 默认只允许当前打开文档；批量文档总结必须用户明确选择文档范围。
- `create_checklist_draft` 默认只在对话中生成草稿；保存为知识卡片是未来单独 plan/approval 流程，不属于当前阶段。
- `create_memory_candidate` 只能生成候选，不得自动保存。
- `update_category_display_name` 和 `update_category_description` 是唯一可被设计为 L3 safe execute 的示例 intent；它们仍不得绕过 plan/snapshot/approval/TaskQueue。
- `archive_documents`、`delete_documents`、`restore_backup`、`promote_knowledge` 当前不得执行。

## 4. Intent Request Shape

```json
{
  "intent": "summarize_document",
  "user_text": "总结当前文档",
  "arguments": {
    "document_scope": "current_document"
  },
  "risk_level": "R1",
  "read_only": true,
  "needs_ai": true,
  "requires_confirmation": false,
  "current_version_allowed": "design_only"
}
```

## 5. Unsupported Response Contract

当 intent 为 `unknown` 或 `unsupported`：

- 返回 `system_notice` 或 `error_card`。
- 明确说明不能执行的原因。
- 如果存在安全替代路径，只能给出 plan-only 或 read-only 替代。
- 不得悄悄改写用户请求为低风险操作。
