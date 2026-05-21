# AI Context Policy

本文定义 AI 助手可以读取、组合和发送的上下文边界。当前阶段只做设计，不实现 ContextBuilder，不接真实 AI。

## 1. Default Allowed Context

默认允许：

- 当前打开文档。
- 用户选中的搜索结果。
- formal 层 `SearchService` 结果。
- 用户确认的长期记忆。
- 当前会话短期状态。
- 当前 plan 和任务状态。

Formal 层默认只包括：

- `rules`
- `checklists`
- `snippets`

并且应满足：

- `status=active`
- `review_required=false`
- 不在 quarantine。
- 不在 rejected。

## 2. Default Denied Context

默认不允许：

- quarantine。
- rejected。
- 未确认资料。
- 敏感资料。
- 归档资料。
- 全库无边界读取。
- raw 全文。
- distilled 作为正式规则。
- `.kb/index.sqlite` 直接读取。
- `knowledge/**/*.md` 直接读取。
- backup zip 直接读取。
- `.kb/tasks/` 直接读取。

如用户明确选择 raw、distilled、research 或 archived 内容用于学习，AI 必须标注：

```text
未经审核，不能作为正式项目规则
```

## 3. ContextBuilder Rules

ContextBuilder 必须：

- 只通过 `knowledge_app.services` 获取上下文。
- 使用 `SearchService` 获取搜索结果。
- 使用 `DocumentService.open_document` 打开用户明确选择的单篇文档。
- 使用 TaskQueue service 获取任务状态。
- 使用 future memory service 获取已确认长期记忆。
- 强制 top-k、分页和 token budget。
- 记录 context source ids，用于 citation 和 audit。

ContextBuilder 不得：

- 扫描 `knowledge/`。
- 批量读取 Markdown 正文。
- 查询 SQLite。
- 拼接 CLI 命令。
- 读取所有搜索结果。
- 为了总结“全部资料”绕过分页和确认。

## 4. Context Scope

Allowed scopes:

| Scope | Description | Confirmation |
| --- | --- | --- |
| `current_document` | 当前用户打开的单篇文档 | no for local; cloud needs preview |
| `selected_search_results` | 用户明确选择的搜索结果 | cloud needs preview |
| `formal_search_top_k` | formal 搜索 top-k 结果 | no for local; cloud needs preview |
| `current_task` | 当前任务状态和进度 | no |
| `confirmed_memory` | 用户确认保存的长期记忆 | cloud needs preview |

Denied scopes:

- `entire_workspace`
- `all_markdown`
- `all_raw`
- `all_distilled`
- `quarantine`
- `rejected`
- `all_archives`
- `filesystem_path`
- `sqlite_query`

## 5. Cloud Context Preview

云端发送前必须展示 context preview。

Preview must include:

- provider kind.
- operation purpose.
- selected documents or chunks.
- title, layer, status, confidence and source type.
- whether full body, snippet or metadata will be sent.
- estimated size.
- excluded context and exclusion reason.
- privacy warning.
- confirmation action.

User confirmation must bind to the preview. If context changes, confirmation must be requested again.

## 6. Citation Requirements

AI 回答必须带 citation when it relies on knowledge-base content.

Citation shape:

```json
{
  "citation_id": "string",
  "document_id": "string",
  "title": "string",
  "layer": "rules|checklists|snippets|distilled|raw",
  "status": "active|deprecated|rejected|quarantine|archived",
  "source_type": "official|github|paper|blog|forum|video|internal_practice|unknown",
  "confidence": "high|medium|low",
  "chunk_id": "string|null",
  "review_required": false,
  "warning": "string|null"
}
```

Rules:

- Formal citations can support project guidance.
- Raw/research/distilled citations must show unconfirmed warning.
- Quarantine and rejected citations are denied by default.
- If no citation exists, AI must not claim the answer came from the knowledge base.

## 7. Context For Specific Intents

`search_knowledge`:

- Input: query and filters.
- Context: none before service call.
- Output context: search result cards with citations.

`open_document`:

- Input: explicit document id/result id.
- Context: selected document only.

`summarize_document`:

- Input: current document or explicitly selected document.
- Context: document body via `DocumentService.open_document`.
- Cloud: preview required.

`compare_documents`:

- Input: explicitly selected documents.
- Context: selected documents only.
- Confirmation: required when count > 1 or cloud provider is used.

`create_checklist_draft`:

- Input: current document or selected citations.
- Context: selected content only.
- Output: draft in conversation, not saved.

`update_category_description`:

- Input: category id and proposed description.
- Context: category metadata and plan result only.
- Execution: L3 safe execute policy.

## 8. Large-scale Rules

AI context must preserve existing large-scale constraints:

- No startup scan.
- No full-library context.
- Search uses SQLite FTS through service.
- Lists use top-k, pagination or virtual selection.
- Document body loads one explicit document at a time.
- Context cache must have size limits.
- Long-running context expansion must become a TaskQueue task if ever supported.

## 9. Failure Handling

If context is unavailable:

- Return `error_card`.
- State which service failed.
- Do not fall back to direct filesystem reads.
- Do not ask AI provider to hallucinate missing content.
- Offer a safe read-only retry or narrower query.
