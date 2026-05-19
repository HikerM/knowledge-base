# Organize & Archive Design

本文定义 `personal-knowledge-base` 在 Markdown Storage Design 之后的长期整理、归档、恢复、canonical 和 active/archive 分层策略。当前阶段只做设计、文档、README/AGENTS 规则和未来命令规划；不实现 GUI、RSS、向量检索、MCP、Codex Skill、EXE，不修改 `knowledge/**/*.md`，不修改 SQLite schema，也不改变 `search` 默认行为。

## 1. 设计目标

长期知识库会持续吸收 raw、distilled、正式规则、历史规则、报告和实践反馈。如果没有 organize/archive，系统会逐渐出现：

- raw 堆积，来源重复、过期材料和低价值摘录不断扩大。
- active formal knowledge 膨胀，同一主题存在多个 active rules/checklists/snippets。
- 搜索污染，低置信、旧版本、重复来源或未审核内容更容易干扰正式项目使用。
- canonical 不清楚，Agent 和未来 GUI 无法判断同一主题下当前推荐采用哪条知识。
- Git review、索引、备份、维护报告和人工复查成本持续上升。

核心原则：

- Markdown 仍是事实来源，SQLite 仍是可删除重建的索引层。
- raw 可以增长，但 active formal knowledge 必须少而准。
- archive 不是 delete。archive 是降低活跃工作集和默认搜索噪音，同时保留历史、来源和恢复能力。
- archive 默认不参与普通 `search`。普通 `search` 仍默认只查 `rules`、`checklists`、`snippets` 中的 active formal knowledge。
- archive 必须可恢复。恢复也必须先生成 plan，不能覆盖当前 canonical 内容。
- organize/archive 默认只生成 plan，不自动移动文件、不删除文件、不改写 Markdown。
- `archive`、`restore`、`deprecate`、`quarantine` 必须人工确认。
- archive 前建议有 Git snapshot、tag、backup/export 或等价快照。
- archive 不能破坏 `source_url`、`source_file`、`promoted_from`、`supersedes`、`superseded_by` 等来源链路。

## 2. Archive 不是删除

archive 的目的不是清除历史，而是把低频、历史、重复或支撑性资料从 active workspace 中移出默认工作集。归档后的知识仍应满足：

- 文件内容可读。
- frontmatter 保留完整来源、审核、状态和生命周期字段。
- 可通过显式 archive search、workspace search 或 restore plan 找回。
- 可作为历史证据解释为什么某条规则被替代、废弃或拒绝。
- 可在需要时恢复到 active workspace，但恢复前必须检查 canonical 冲突和安全风险。

删除只适用于用户明确要求且确认的特殊情况，例如误提交的 secret、客户隐私、版权风险全文复制或临时生成物。普通过期知识应优先 `deprecate`、`reject`、`quarantine` 或 archive，而不是 delete。

## 3. Active Formal Knowledge 必须少而准

正式层包括 `rules`、`checklists`、`snippets`。这些层是 Codex/Agent 默认可执行知识，因此必须保持：

- 每个重要 `topic_id` 有清晰 canonical。
- 同一主题不长期保留多个 active canonical rules。
- 每条正式知识有明确适用场景、不适用场景、验证方式和审核记录。
- 过期、被替代或低置信正式知识进入 `deprecate-plan` 或 `review`，而不是继续留在 active formal set。

raw 和 distilled 的作用是支撑学习、提炼和审查。它们可以多，但必须可被整理、去重、归档和恢复。raw 不应因为数量庞大而污染正式搜索。

## 4. Topic-aware Generational Archive Planner

Topic-aware Generational Archive Planner 是整理归档的计划生成算法。它按 topic、layer、状态、来源、置信度、复查周期、访问情况、重复关系和 canonical 关系生成建议动作。它不直接移动或修改文件。

### 4.1 算法目标

- 让 active `rules`、`checklists`、`snippets` 保持小、准、canonical。
- 把旧 raw、旧 distilled、重复来源、低置信材料和被替代历史识别为 archive 候选。
- 发现同一主题下缺少 canonical、多个 canonical、重复正式规则或 stale formal knowledge。
- 为 archive、restore、merge、deprecate、quarantine 和 set-canonical 提供可解释 plan。
- 在 100K+ 场景下减少 active workspace 的文件和索引压力。
- 保持来源链路、生命周期链路和可恢复性。

### 4.2 输入字段

Planner 至少使用以下字段。字段事实以 Markdown/frontmatter 为准；SQLite 只能作为可重建索引和候选枚举来源。

| field | 用途 |
| --- | --- |
| `topic_id` | 关联同一主题下 raw、distilled、formal、deprecated、archive supporting files |
| `canonical_id` | 判断当前主题下推荐采用的 canonical 知识 |
| `layer` | 区分 raw、distilled、rules、checklists、snippets、deprecated、rejected、quarantine、archive |
| `status` | 判断 active、experimental、deprecated、rejected 等生命周期状态 |
| `confidence` | 低置信内容更适合 review、archive-plan 或 quarantine-plan |
| `source_type` | 官方、论文、GitHub、博客、论坛、unknown 等权威性输入 |
| `source_url` | 来源追踪、重复来源检测和 source chain 保护 |
| `last_reviewed` | 判断是否 stale、是否近期复查 |
| `review_cycle_days` | 单条知识复查周期，覆盖默认 stale 阈值 |
| `last_accessed_at` | 未来 service/GUI 记录的最近访问时间，只用于建议，不作为价值唯一依据 |
| `superseded_by` | 被替代内容通常进入 deprecate-plan 或 archive-plan |
| `promoted_from` | 保留 raw/distilled -> formal 的来源链路 |
| `content_hash` | 正文规范化重复检测 |
| `source_hash` | 来源 URL 或来源文件重复检测 |

`last_accessed_at` 不应由 SQLite 单独成为事实来源。未来如果记录访问时间，应由 service/core 回写到受控元数据或单独可审计日志，再由 planner 引用。

### 4.3 输出动作

Planner 输出 action plan，不直接执行 action。

| action | 含义 | 默认是否写文件 |
| --- | --- | --- |
| `keep` | 保留在当前 active/warm 位置，无需处理 | 否 |
| `review` | 需要人工复查来源、置信度、适用范围或 stale 状态 | 否 |
| `merge-plan` | 同主题内容建议合并到 canonical，列出来源和差异 | 否 |
| `archive-plan` | 建议归档，列出原因、目标位置、影响和恢复方式 | 否 |
| `deprecate-plan` | 建议废弃正式知识，必须说明替代项或废弃原因 | 否 |
| `quarantine-plan` | 建议隔离可疑、未知、低质量或不安全来源 | 否 |
| `restore-plan` | 建议从 archive 恢复到 active/warm，说明触发原因和冲突 | 否 |
| `set-canonical-plan` | 建议设置或修正 canonical，列出候选和理由 | 否 |

任何 `*-plan` 都必须包含：

- candidate file。
- reason。
- evidence fields。
- risk。
- expected destination or state change。
- source chain impact。
- confirmation requirement。
- suggested validation commands。

### 4.4 决策顺序

建议顺序：

1. 先按 `topic_id` 分组；缺少 `topic_id` 的内容进入 `review` 或 `set-canonical-plan` 前置整理。
2. 在同一 topic 内识别 canonical formal card。
3. 使用 `source_hash`、`content_hash`、标题和来源字段识别重复。
4. 使用 `status`、`superseded_by`、`last_reviewed` 和 `review_cycle_days` 识别过期或被替代内容。
5. 使用 `layer`、`confidence`、`source_type`、`last_accessed_at` 和 archive score 生成建议。
6. 输出 plan，并明确哪些动作需要人工确认、snapshot 和后续验证。

Planner 不应把 low access 等同于 low value。低访问只能增加归档建议权重，不能单独决定归档。

## 5. Archive Score

archive score 是可解释评分，用于排序归档候选，不用于自动移动文件。

示例公式：

```text
archive_score =
  age_score
+ stale_score
+ duplicate_score
+ promoted_source_score
+ low_confidence_score
+ low_access_score
- active_formal_score
- recent_review_score
- authoritative_source_score
```

### 5.1 分项含义

- `age_score`：创建时间或来源时间越久，分数越高；正式层不能只因年龄高而归档。
- `stale_score`：超过 `review_cycle_days` 或默认 stale 阈值，分数升高。
- `duplicate_score`：同 `source_hash`、`content_hash` 或同 topic 重复越明显，分数越高。
- `promoted_source_score`：raw/distilled 已被 promote 到 formal，且 formal 保留了 `promoted_from`，支撑材料可进入 archive-plan。
- `low_confidence_score`：`confidence=low` 或来源不明时升高。
- `low_access_score`：长期未被打开或搜索引用时升高，但只作为辅助信号。
- `active_formal_score`：active `rules`、`checklists`、`snippets` 降低归档分，避免误归档正式知识。
- `recent_review_score`：近期人工复查过的内容降低归档分。
- `authoritative_source_score`：官方、论文或内部实践证据强的来源降低归档分。

### 5.2 评分输出

每条候选应输出：

```json
{
  "path": "knowledge/01-frontend/raw/2026/05/example.md",
  "topic_id": "frontend.example-topic",
  "archive_score": 72,
  "action": "archive-plan",
  "score_breakdown": {
    "age_score": 15,
    "stale_score": 12,
    "duplicate_score": 20,
    "promoted_source_score": 15,
    "low_confidence_score": 5,
    "low_access_score": 8,
    "active_formal_score": 0,
    "recent_review_score": -3,
    "authoritative_source_score": 0
  },
  "reason": "old raw source is duplicated and already promoted to canonical rule",
  "requires_confirmation": true
}
```

### 5.3 硬性边界

- score 只用于建议，不自动移动文件。
- 高分只进入 `archive-plan`，不直接 archive。
- 用户确认后才执行 archive。
- active formal knowledge 即使高分，也应优先进入 `review` 或 `deprecate-plan`，不能静默归档。
- `quarantine` 由安全和来源风险触发，不应只靠 archive score。

## 6. Active / Warm / Cold / Archive 分层

分层用于描述 working set 热度，不替代现有 lifecycle layer。它可以通过未来 `archive_status` 或 workspace 策略表达。

| tier | 内容 | 搜索行为 | 处理方式 |
| --- | --- | --- | --- |
| `hot` | active rules/checklists/snippets、近期 distilled、当前项目常用 canonical knowledge | 普通 `search` 默认只覆盖 active formal；近期 distilled 只在显式 include/research 中出现 | 保持少而准，优先复查、去重、设置 canonical |
| `warm` | 有用 raw、reviewed distilled、近期 supporting materials、暂时保留的主题证据 | 不进入普通正式搜索，显式 research 或 include 才查 | 定期 review，必要时 promote 或归档 |
| `cold` | old raw、old distilled、duplicate source、low confidence notes、低频 supporting files | 默认不进入普通 search | 进入 archive-plan 或 review |
| `archive` | old raw、deprecated、superseded、low-value historical source、已被 formal 吸收的支撑材料 | 默认不参与普通 search；未来通过 archive workspace/search 显式访问 | 可恢复，保留来源链路 |
| `quarantine` | suspicious、unsafe、unknown source、疑似污染、无法验证内容 | 不得指导实现，不进入普通 search | 人工审核后 reject、修正、restore 或保留隔离 |

`archive` 和 `quarantine` 必须区分：archive 是低频历史；quarantine 是风险隔离。quarantine 内容不得因为访问低就普通归档，也不得作为项目实现依据。

## 7. 目录和 Workspace 策略

### 7.1 小中规模：category 内 archive 目录

适用于文档规模较小、维护者主要在单一 workspace 内工作的情况：

```text
knowledge/<category>/archive/
knowledge/01-frontend/archive/raw/2026/...
knowledge/01-frontend/archive/deprecated/...
knowledge/09-ai-agent/archive/distilled/...
```

优点：

- 路径简单。
- Git history 和同 category 语境容易查看。
- 现有工具适配成本较低。

限制：

- active workspace 仍包含 archive 文件，索引和文件枚举压力会继续增长。
- 需要 search/index 明确默认排除 archive，否则会污染普通搜索。
- 100K+ 时不建议只靠 category 内 archive 目录。

### 7.2 大规模：archive workspace

100K+ 时建议使用 workspace archive：

```text
workspaces/active/
workspaces/archive-raw-2026/
workspaces/research-archive/
workspaces/deprecated-archive/
```

每个 workspace 保持：

```text
knowledge/
config/
reports/
.kb/index.sqlite
```

原则：

- active workspace 保持轻量，只保存当前高价值 formal knowledge、近期 distilled/raw 和正在审查的资料。
- archive workspace 保存历史 raw、低频 supporting materials、deprecated/superseded 历史和大型研究资料。
- 每个 workspace 使用独立 `.kb/index.sqlite`，索引仍可删除重建。
- cross-workspace search 是未来增强，不是 100K+ 首版前提。
- archive workspace 的普通搜索也必须保持 layer/status/source_type/confidence 过滤语义，不得绕过治理规则。

### 7.3 迁移约束

无论采用哪种策略：

- 迁移前必须生成 `archive-plan`。
- 真实移动前建议 snapshot/backup。
- 移动必须保留 `source_url`、`source_file`、`promoted_from`、`supersedes`、`superseded_by`。
- 被移动文件的 path 变化不能切断 canonical、superseded、promoted 来源链路。
- 迁移后必须运行 index/audit/lint/secret-scan 等验证。

## 8. 未来命令规划

以下命令为设计规划。本阶段不实现或修改 CLI。已有只读命令如 `canonical-report` 继续保持只读语义，未来可扩展输出字段。

| command | 输入 | 输出 | 只读 | 会移动文件 | 人工确认 | snapshot |
| --- | --- | --- | --- | --- | --- | --- |
| `organize-plan` | `--category`、`--topic-id`、`--layer`、`--status`、`--limit`、`--output` | organize 建议、缺字段、重复、canonical 候选、review 任务 | 是 | 否 | 否 | 否 |
| `archive-plan` | `--category`、`--topic-id`、`--older-than`、`--min-score`、`--include-raw`、`--output` | archive 候选、score breakdown、目标位置、风险、恢复方式 | 是 | 否 | 否 | 建议 |
| `archive` | `--plan`、`--confirm`、`--snapshot-id`、`--target` | 执行结果、移动清单、链路校验、后续验证命令 | 否 | 是 | 是 | 是 |
| `restore` | `--path` 或 `--plan`、`--target-workspace`、`--confirm` | restore-plan 或执行结果、冲突提示、canonical 影响 | 默认先只读；确认后写 | 确认后可能 | 是 | 是 |
| `merge-plan` | `--topic-id`、`--canonical`、`--candidates`、`--output` | 合并差异、保留字段、建议 deprecate/archive 的 supporting files | 是 | 否 | 否 | 建议 |
| `canonical-report` | `--category`、`--topic-id`、`--include-archive` | canonical rule/checklist/snippet、重复、冲突、缺失 canonical | 是 | 否 | 否 | 否 |
| `set-canonical` | `--topic-id`、`--path`、`--canonical-id`、`--confirm` | canonical 变更结果、冲突检查、需 deprecate 的旧项 | 否 | 否，但会改 Markdown | 是 | 建议 |
| `archive-report` | `--workspace`、`--category`、`--since`、`--output` | archive 规模、分层统计、restore 候选、过期计划 | 是 | 否 | 否 | 否 |

### 8.1 organize-plan

用途：生成整理计划，发现同 topic 重复、缺少 `topic_id`、缺少 `canonical_id`、正式层膨胀、低置信和 stale 内容。

约束：

- 只读。
- 不移动文件。
- 不修改 Markdown。
- 不需要人工确认。
- 可作为 `archive-plan`、`merge-plan`、`set-canonical-plan` 的上游。

### 8.2 archive-plan

用途：根据 archive score、topic、layer、status、访问情况和重复关系生成归档候选。

约束：

- 只读。
- 不移动文件。
- 输出必须包含 score breakdown 和 source chain impact。
- 高分候选也只能进入 plan。
- 建议在真实 archive 前创建 snapshot。

### 8.3 archive

用途：在用户确认后执行 archive plan。

约束：

- 会移动文件或更新 archive status。
- 必须人工确认。
- 必须指定 plan 或明确 candidate。
- 执行前必须考虑 snapshot/backup。
- 执行后必须验证来源链路、运行 index/lint/audit。

### 8.4 restore

用途：把 archive 内容恢复到 active/warm 位置。

约束：

- 默认先生成 `restore-plan`。
- 确认后才移动文件或更新状态。
- 不能覆盖当前 active canonical。
- 必须检查 `topic_id`、`canonical_id`、`superseded_by` 和 quarantine 风险。
- 建议 snapshot。

### 8.5 merge-plan

用途：为同 topic 重复内容生成合并计划，帮助人工把有效信息合入 canonical。

约束：

- 只读。
- 不直接合并正文。
- 输出差异、保留字段、来源链路和建议后续动作。
- 合并后被替代正式层应走 `deprecate`，supporting raw/distilled 可走 `archive-plan`。

### 8.6 canonical-report

用途：报告每个 `topic_id` 的 canonical 状态和 unresolved issues。

约束：

- 只读。
- 不设置 canonical。
- 可显示 active/deprecated/raw/archive supporting files。
- 可作为 `set-canonical` 的输入证据。

### 8.7 set-canonical

用途：人工确认后设置或修正 canonical。

约束：

- 会修改 Markdown/frontmatter。
- 必须人工确认。
- 不能把 raw、distilled、review_required=true 或 quarantine 内容设为正式 canonical。
- 如果同 topic 已有 canonical，必须输出冲突和迁移建议。
- 建议 snapshot。

### 8.8 archive-report

用途：周期性报告 archive 状态、规模、增长趋势和 restore 候选。

约束：

- 只读。
- 不移动文件。
- 不修改 Markdown。
- 可用于月度维护和 100K+ workspace 分片决策。

## 9. GUI 页面规划

当前不做 GUI。本节只为未来 service/API 和页面设计建立边界。

### 9.1 Organize Center

- purpose：集中展示 organize-plan、重复主题、缺 canonical、stale formal knowledge、低置信内容和待 review 队列。
- service dependency：`organize-plan`、`dedupe`、`conflicts`、`stale`、`canonical-report`、`audit`。
- long-running task：是。大库下必须后台运行，返回 `task_id`、progress、log path 和 paginated results。
- confirmation requirements：页面本身只读；进入 archive/set-canonical/deprecate/quarantine 才需要确认。
- empty/error states：无问题时显示 last run、扫描范围和空结果；索引缺失时提示先后台 index；任务失败时显示 error detail 和 retry。

### 9.2 Archive Manager

- purpose：查看 archive-plan、执行已确认 archive、浏览 archive workspace/category、生成 archive-report。
- service dependency：`archive-plan`、`archive`、`archive-report`、workspace manifest、backup/snapshot service、index service。
- long-running task：是。archive-plan 和 archive 执行都可能长时间运行，必须可取消、可查看日志。
- confirmation requirements：真实 archive 必须二次确认，显示移动清单、source chain impact、snapshot 状态和验证命令。
- empty/error states：没有 archive 候选时显示筛选条件和最近 score 阈值；snapshot 不存在时阻止执行或要求用户明确跳过；移动失败时显示已完成/未完成文件和恢复建议。

### 9.3 Canonical Topics

- purpose：按 `topic_id` 管理 canonical rule/checklist/snippet，显示同主题 raw/distilled/deprecated/archive supporting files。
- service dependency：`canonical-report`、`set-canonical`、`merge-plan`、`conflicts`、`dedupe`。
- long-running task：报告生成可能长时间运行；设置 canonical 是短写任务但必须走写队列。
- confirmation requirements：`set-canonical` 必须确认；如果替换已有 canonical，必须显示旧 canonical、影响范围和建议 deprecate/merge/archive 后续动作。
- empty/error states：缺 `topic_id` 时显示需补字段；无 canonical 时显示候选；多个 canonical 时显示冲突；quarantine 内容不得作为候选。

### 9.4 Restore View

- purpose：从 archive 中查找、预览并恢复内容，或生成 restore-plan。
- service dependency：archive workspace search、`restore`、`canonical-report`、conflict check、backup/snapshot service、index service。
- long-running task：跨 archive workspace 搜索和 restore plan 可能长时间运行；真实 restore 必须后台化。
- confirmation requirements：restore 必须确认，显示目标路径、canonical 冲突、是否覆盖、source chain、quarantine 风险和 snapshot 状态。
- empty/error states：archive index 缺失时提示构建 archive index；无匹配时显示筛选条件；恢复冲突时要求先处理 canonical/deprecate 冲突。

## 10. 验收与后续实现边界

本阶段验收只要求：

- 新增本设计文档。
- README 补充 Organize & Archive 摘要。
- AGENTS 补充不可自动 archive/delete/merge、plan-first、确认和 backup/snapshot 规则。
- 不修改 `knowledge/**/*.md`。
- 不修改 SQLite schema。
- 不改变 search 默认行为。
- 运行指定 lint/audit/test/secret-scan/perf smoke。

后续实现顺序建议：

1. 先实现只读 `organize-plan` 和 `archive-plan`。
2. 再扩展 `canonical-report` 输出 archive/cold/warm 状态。
3. 再实现受控 `set-canonical`。
4. 最后实现真实 `archive` / `restore`，且必须依赖 snapshot、人工确认、原子移动和验证。

