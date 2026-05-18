# Long-Term Data Governance

本知识库的治理目标是防止长期积累后出现重复、冲突、过期和正式层污染。治理命令只发现问题和生成报告，不会自动删除历史知识，也不会自动 promote。

## topic_id 命名规范

`topic_id` 用来把同一主题下的 raw、distilled、rules、checklists 和 snippets 关联起来。建议格式：

```text
<category>.<topic-slug>
```

示例：

- `ai_agent.codex-sandboxing`
- `frontend.react-state-management`
- `ui_ux.unity-canvas-scaler`
- `performance.core-web-vitals`

命名规则：

- 使用小写 ASCII、数字和连字符。
- 不包含日期、版本号和文件层级。
- 一个主题长期保持稳定，不因文件迁移而改变。
- 如果主题拆分，应创建新的 `topic_id`，并在旧规则里记录 `deprecated_reason` 或 `superseded_by`。

## canonical_id

`canonical_id` 用来标记同一主题下推荐采用的 canonical 知识。通常只给正式层 active 文件设置。

建议格式：

```text
<topic_id>.<kind>
```

示例：

- `ai_agent.codex-sandboxing.rule`
- `performance.core-web-vitals.checklist`

## 处理重复

运行：

```bash
python scripts/kb.py dedupe
```

dedupe 会检查：

- `source_url` 重复。
- 归一化标题重复。
- `content_hash` 重复。
- 同一 `category + topic_id` 下重复。

处理原则：

- 同来源 raw 可以保留为支撑材料，但要指定同一 `topic_id`。
- 同主题多个正式规则应合并为一个 canonical rule，其他规则应 `deprecate` 或转为 supporting note。
- 内容完全重复时优先保留来源更权威、审核更新、confidence 更高、层级更正式的文件。
- 不确定是否重复时不要删除，先记录 review note 或进入 quarantine。

## 处理冲突

运行：

```bash
python scripts/kb.py conflicts
```

conflicts 会检查：

- 同一 `topic_id` 下多个 active rules。
- `superseded_by` 指向不存在的文件或标识。
- active 规则 supersedes 的旧规则仍是 active。
- active 规则引用 deprecated 历史内容。
- `valid_for` 重叠但文本信号疑似相反的规则。

冲突处理原则：

- 不自动选择赢家。
- 优先看来源权威性、最后复查时间、confidence、适用范围和项目实践验证。
- 被替代的旧规则使用 `deprecate`，不要直接删除。
- 如果冲突来自不同适用范围，应拆分 `valid_for` / `not_valid_for`，而不是合并成模糊规则。

## 废弃旧规则

运行：

```bash
python scripts/kb.py deprecate --path knowledge/.../rules/old.md --reason "被新规则替代" --superseded-by "knowledge/.../rules/new.md" --reviewed-by "me"
```

废弃时必须记录：

- `deprecated_reason` 或 `deprecation_reason`
- `reviewed_by`
- `last_reviewed`
- 可选 `superseded_by`

不要直接删除旧知识。历史记录可以解释为什么规则变化、避免重复引入旧错误，也能帮助 Codex/Agent 在冲突时识别过期内容。

## 合并相同主题

推荐流程：

1. 给同一主题文件补充相同 `topic_id`。
2. 运行 `dedupe` 和 `canonical-report`。
3. 选择 canonical rule/checklist/snippet。
4. 把有价值的信息合并到 canonical 文件。
5. 对被替代的正式层文件执行 `deprecate`。
6. raw/distilled 可保留为 supporting files，但不能作为正式项目规则。
7. 运行 `index`、`audit`、`conflicts` 验证。

## canonical-report

运行：

```bash
python scripts/kb.py canonical-report
```

报告按 `topic_id` 输出：

- canonical rule
- canonical checklist
- active files
- deprecated files
- raw supporting files
- unresolved duplicates
- unresolved conflicts

这个报告用于月度治理和人工复查，不会修改文件。

## monthly-maintenance

运行：

```bash
python scripts/kb.py monthly-maintenance
```

该命令会运行：

- index
- lint
- audit
- dedupe
- conflicts
- stale
- secret-scan

并生成 `reports/monthly-maintenance-YYYY-MM.md`。报告是治理快照，适合在导入一批 raw、promote 一批规则或发布版本前运行。
