# Markdown Schema

本文定义 `personal-knowledge-base` 的 Markdown knowledge card schema。当前代码的可执行校验仍以 `knowledge_core/frontmatter.py` 和 `knowledge_core/quality.py` 为准；本文件用于明确长期 schema 目标、模板字段和后续 migration 规则。

## 1. Schema version

新建知识卡片建议包含：

```yaml
schema_version: 1
```

现有卡片可能没有 `schema_version`。本阶段不迁移 `knowledge/**/*.md`，因此 `schema_version` 是新模板字段和后续 migration 依据，不改变当前 lint 行为。

## 2. Required frontmatter fields

当前可执行必填字段如下，所有 knowledge card 都应包含：

```yaml
title: ""
category: ""
type: ""
status: ""
confidence: ""
source_type: ""
source_url: ""
created_at: ""
last_reviewed: ""
reviewed_by: ""
valid_for: []
not_valid_for: []
project_scope: ""
supersedes: []
superseded_by: ""
risk_level: ""
verification_method: ""
review_required: true
```

这些字段必须保存在 Markdown frontmatter 中，不能只存在 SQLite 或报告中。

## 3. Optional frontmatter fields

当前治理字段和模板推荐字段：

```yaml
schema_version: 1
card_id: ""
topic_id: ""
canonical_id: ""
source_file: ""
source_hash: ""
content_hash: ""
promoted_from: ""
reviewed_at: ""
review_note: ""
deprecated_reason: ""
deprecation_reason: ""
rejected_reason: ""
quarantine_reason: ""
quarantined_reason: ""
archive_status: active
last_accessed_at: ""
review_cycle_days: ""
language: ""
```

可选不代表不重要。进入正式层、废弃层、拒绝层或隔离层时，部分可选字段会变成该 layer 或 type 的必填字段。

## 4. Allowed layer

允许的 layer：

- `raw`
- `distilled`
- `rules`
- `snippets`
- `checklists`
- `deprecated`
- `rejected`
- `quarantine`

`rules`、`snippets`、`checklists` 是 formal layers。默认 search 只查这些正式层，且不应因为大规模模式或 schema migration 改变默认行为。

## 5. Allowed type

知识卡片的核心 type：

- `raw_note`
- `rule`
- `checklist`
- `snippet`
- `pitfall`
- `adr`
- `changelog`

兼容当前 CLI 和历史内容的 type：

- `raw`: legacy raw note alias，后续可迁移为 `raw_note`。
- `pattern`
- `case`

系统报告或任务模板可以使用非知识卡片 type，例如 `report`、`codex_task`、`learning_queue`、`category_digest`、`monthly_maintenance`、`maintenance`。这些 type 不应进入正式知识层，除非后续 schema 明确允许。

## 6. Allowed status

允许的 `status`：

- `active`: 当前有效。正式层 active 内容必须经过人工审核。
- `experimental`: 未完全验证，常用于 raw 和 distilled。
- `deprecated`: 曾经有效但已过期、被替代或实践验证失败。
- `rejected`: 审核后明确不采用。

`quarantine` 是 layer，不是 status。隔离内容通常保持 `experimental` 或 `rejected`，并必须写明 `quarantined_reason` 或 `quarantine_reason`。

## 7. Required fields by layer

### raw

必须满足：

- `type`: `raw_note` 或兼容历史的 `raw`。
- `status`: 默认 `experimental`。
- `confidence`: 默认 `low`。
- `review_required`: `true`。
- `source_url` 或 `source_file`: 至少一个可追踪来源。
- `source_type`: 不得为空；未知时写 `unknown`。

raw 不得使用 `status=active`，不得作为正式项目规则。

### distilled

必须满足：

- `status`: 通常为 `experimental`。
- `review_required`: `true`。
- `source_url`、`source_file` 或 `promoted_from`: 至少能追溯到 raw 或来源。
- `topic_id`: 推荐填写，用于后续 promote 和冲突治理。
- `verification_method`: 可以为空，但正文必须说明待验证方式。

distilled 不得作为 Codex/Agent 默认正式规则。

### rules

必须满足：

- `type`: `rule`。
- `status`: `active` 或迁移中的 `deprecated`。
- `confidence`: `high` 或有明确说明的 `medium`。
- `review_required`: `false`。
- `reviewed_by`: 必填。
- `last_reviewed`: 必填。
- `reviewed_at`: 推荐必填。
- `verification_method`: 必填。
- `valid_for`: 必填且非空。
- `not_valid_for`: 必填，可为空数组但必须存在。
- `source_url`: 必填，除非 `source_type=internal_practice`。
- `review_note`: 推荐必填。
- `promoted_from`: 推荐必填。

### snippets

必须满足：

- `type`: `snippet`。
- `language`: 推荐必填。
- `status`: `active` 或 `deprecated`。
- `review_required`: `false`。
- `reviewed_by`、`last_reviewed`、`verification_method`: 必填。
- `valid_for`、`not_valid_for`: 必须存在。
- 正文必须包含可执行片段、使用方式、风险与验证方式。

### checklists

必须满足：

- `type`: `checklist`。
- `status`: `active` 或 `deprecated`。
- `review_required`: `false`。
- `reviewed_by`、`last_reviewed`、`verification_method`: 必填。
- `valid_for`、`not_valid_for`: 必须存在。
- 正文必须包含 `- [ ]` 检查项和关键证据要求。

### deprecated

必须满足：

- `status`: `deprecated`。
- `review_required`: `false`。
- `deprecated_reason` 或 `deprecation_reason`: 必填，除非 `superseded_by` 已完整指向新卡片。
- `superseded_by`: 推荐填写。
- `last_reviewed`、`reviewed_by`: 必填。

deprecated 是历史层，不得作为默认项目规则。

### rejected

必须满足：

- `status`: `rejected`。
- `review_required`: `false`。
- `rejected_reason` 或 `review_note`: 必填。
- `last_reviewed`、`reviewed_by`: 必填。

rejected 不得删除，除非用户明确要求。

### quarantine

必须满足：

- `review_required`: `true`。
- `risk_level`: `high`。
- `quarantined_reason` 或 `quarantine_reason`: 必填。
- `last_reviewed`: 推荐填写。

quarantine 内容不得指导项目实现，也不得自动 promote。

## 8. Required fields by type

### raw_note

Frontmatter：

- `source_url` 或 `source_file`
- `source_type`
- `source_hash` 推荐填写
- `review_required: true`

正文：

- 来源
- 原始摘录或摘要
- 我的初步理解
- 风险与待验证
- 下一步处理

### rule

Frontmatter：

- `valid_for`
- `not_valid_for`
- `risk_level`
- `verification_method`
- `reviewed_by`
- `last_reviewed`
- `review_required: false`

正文：

- 适用场景
- 不适用场景
- 正式规则
- 原因
- 实施方式
- 验证方式
- Codex / Agent 指令

### checklist

Frontmatter：

- `valid_for`
- `not_valid_for`
- `verification_method`
- `risk_level`
- `review_required: false`

正文：

- 使用时机
- 不适用场景
- 检查项
- 高风险项
- 验证方式

### snippet

Frontmatter：

- `language`
- `valid_for`
- `not_valid_for`
- `risk_level`
- `verification_method`
- `review_required: false`

正文：

- 适用场景
- 不适用场景
- 片段
- 使用方式
- 风险与注意
- 验证方式

### pitfall

Frontmatter：

- `risk_level`
- `valid_for`
- `not_valid_for`
- `verification_method` 或待验证说明

正文：

- 症状
- 根因
- 触发条件
- 影响范围
- 避免方式
- 验证方式

### adr

Frontmatter：

- `valid_for`
- `not_valid_for`
- `review_cycle_days`
- `reviewed_by` 和 `last_reviewed`，如果 ADR 已被采纳

正文：

- Context
- Decision
- Alternatives
- Consequences
- Scope
- Review

### changelog

Frontmatter：

- `source_url` 或 `source_file`
- `valid_for`
- `not_valid_for`
- `review_required: true`，除非人工审核后转为正式影响记录

正文：

- 变化摘要
- 影响版本或时间范围
- Breaking changes
- Migration steps
- 风险和回滚策略
- 需要更新的规则、snippet 或 checklist

## 9. Future fields

以下字段是长期治理字段。新模板可以先包含，旧内容通过后续 migration 回填。

| field | 作用 | 回填建议 |
| --- | --- | --- |
| `card_id` | 单卡片稳定 ID，未来跨文件 rename、archive、GUI 引用使用 | 由路径或内容生成，生成后不随文件名变化 |
| `topic_id` | 同一主题跨 raw、distilled、formal、deprecated 的稳定标识 | 人工或半自动按主题回填 |
| `canonical_id` | 同一主题下当前推荐采用的 canonical 文件标识 | 只给审核后的 canonical formal card 设置 |
| `source_hash` | 来源 URL 或 source_file 的稳定 hash，用于重复来源治理 | 从 normalized source 计算 |
| `content_hash` | 正文规范化后的 hash，用于重复内容治理 | 从去空白后的正文计算 |
| `archive_status` | active、archive、cold 等归档状态 | 初始为 `active`，归档计划确认后修改 |
| `last_accessed_at` | 最近打开或使用时间，未来 archive planner 使用 | 由 service/core 更新，不能由 SQLite 单独成为事实 |
| `review_cycle_days` | 单卡片复查周期 | 按风险和来源类型设置，默认 180 |

这些字段不得绕过 `layer`、`status`、`review_required` 和人工审核规则。

## 10. Schema migration rules

修改 Markdown schema 必须提交 migration 说明，至少包含：

- 变更背景。
- schema version 变化。
- 新增、删除、重命名或语义改变的字段。
- 影响的 layer 和 type。
- 对现有 `knowledge/**/*.md` 的影响。
- dry-run 输出格式。
- 原子写入策略。
- 回滚策略。
- 验收命令。

执行规则：

1. migration 默认只生成 plan，不自动改文件。
2. 批量修改必须由用户明确确认。
3. 修改 Markdown 必须通过 service/core 或受控脚本，不能手工改 SQLite。
4. 每个文件写入前后都要能解析 frontmatter。
5. 不得删除 `deprecated`、`rejected`、`quarantine` 的历史记录。
6. 不得把 `raw` 或 `distilled` 自动 promote 到正式层。
7. migration 后必须运行 `python scripts/kb.py lint`、`python scripts/kb.py audit`、`python scripts/kb.py secret-scan`。
8. 如果 schema 影响索引字段，必须删除或重建 `.kb/index.sqlite`，再运行 `python scripts/kb.py index` 和 `python scripts/kb.py doctor`。

SQLite schema migration 不能替代 Markdown schema migration。SQLite 只是 derived index，任何事实字段的最终版本必须回到 Markdown frontmatter。

