# Knowledge Lifecycle

知识库使用 `raw -> distilled -> rules/snippets/checklists -> deprecated/rejected/quarantine` 生命周期。核心原则是：未经审核的信息不能直接影响工程决策。

## 完整闭环

```text
外部内容
  ↓
raw：只收集，不信任
  ↓
distilled：AI 提炼，仍需审核
  ↓
review-queue：待人工审核
  ↓
promote：人工确认
  ↓
rules / snippets / checklists：正式知识
  ↓
search：默认只查正式知识
  ↓
项目使用
  ↓
实践验证
  ↓
audit / stale / conflicts / deprecate
  ↓
更新、废弃、修正
```

每一步都必须保留来源、状态、审核信息和验证方式。不能跳过 review-queue/promote 直接从 raw 或 distilled 进入正式层。

## raw

raw 保存原始摘录、链接、会议记录、临时想法和未验证经验。

- status 必须是 `experimental`，或审核后进入 `rejected` / `deprecated`。
- confidence 通常为 `low`。
- raw 只能作为参考。
- raw 不得放入 rules、checklists、snippets。

## distilled

distilled 是提炼层，可以由 AI 或人工从 raw 中总结。

- 仍需人工审核。
- 可以记录结论、风险、适用场景和验证计划。
- 不得直接作为 Codex/Agent 的正式规则。

## rules、snippets、checklists

这些层是正式可执行知识：

- rules: 人工审核后的工程规则。
- snippets: 可复用代码、命令、配置或提示词。
- checklists: 可执行检查项和验收流程。

进入这些层必须保留 `source_url`、`status`、`confidence`、`last_reviewed`、`reviewed_at` 和验证方式。

## promote 条件

promote 只能从 distilled 或人工明确审核的文件进入正式层。promote 时需要：

- 设置 `status: active`。
- 追加 `reviewed_at`。
- 追加 `promoted_from`。
- 保留来源和适用场景。
- 写明验证方式。

promote 后应运行 `python scripts/kb.py index` 更新索引。

## deprecated 条件

以下情况应进入 deprecated 或标注 `superseded_by`：

- 来源过期。
- 技术版本变化导致不再适用。
- 被新的 active 规则替代。
- 和更权威来源冲突。
- 实践验证失败。

## rejected

rejected 用于记录明确不采用的内容，例如来源错误、结论不可靠、与项目方向不符或审核失败。rejected 保留历史，避免未来重复引入。

## quarantine

quarantine 用于隔离来源不明、AI 摘要可疑、无法验证、质量低或疑似污染的内容。隔离内容必须记录 `quarantine_reason`，且不得作为正式规则使用。

## 冲突规则处理

当规则冲突时，优先级为：

1. `status=active`
2. `last_reviewed` 更新
3. `source_type` 更权威
4. `confidence` 更高
5. 适用场景更接近当前项目

无法判断时，不自动合并，保留冲突说明并要求人工复查。

## 重复知识处理

重复内容不应直接删除。先运行：

```bash
python scripts/kb.py dedupe
python scripts/kb.py canonical-report
```

重复处理建议：

- 同一 `source_url` 的 raw 可以保留一份 canonical raw，其余标记为 supporting 或合并摘要。
- 同一 `topic_id` 下只能有一个 active canonical rule；多个 active rules 必须合并或废弃旧规则。
- `content_hash` 相同通常表示正文重复，应合并、废弃或拒绝其中一份。
- 不确定是否重复时，先保留并写入 `review_note`，不要直接删除历史。

## topic_id 和 canonical_id

`topic_id` 是跨层级追踪主题的稳定标识，建议格式为：

```text
<category>.<topic-slug>
```

例如：

- `ai_agent.codex-sandboxing`
- `frontend.react-state-management`
- `ui_ux.unity-canvas-scaler`

`canonical_id` 用于标记同一主题下推荐采用的 canonical 知识，建议格式为：

```text
<topic_id>.<kind>
```

例如 `frontend.react-state-management.rule`。

raw、distilled 和正式层可以共享同一个 `topic_id`，但只有经过人工审核的 rules、snippets、checklists 才能成为 canonical。

## 不直接删除旧知识

旧知识应通过 `deprecated`、`rejected` 或 `quarantine` 保留历史原因：

- `deprecated_reason`: 曾经有效，但已被替代、过期或实践验证失败。
- `rejected_reason`: 审核后明确不采用。
- `quarantined_reason`: 来源不明、无法验证、质量低或疑似污染。

保留历史可以帮助后续审计、解释规则变化，并避免相同低质量内容再次进入 raw 或 distilled。

## 过期知识复查机制

建议每周运行 `weekly-report`，每月检查：

- last_reviewed 超过 90 天的 active 规则。
- deprecated 但没有 `superseded_by` 的内容。
- source_type 为 blog/forum/video 且 confidence 低的内容。
- 与当前技术栈版本不一致的片段。

月度维护可以一键运行：

```bash
python scripts/kb.py monthly-maintenance
```
