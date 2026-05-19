# Core Algorithm Strategy

本文固定 personal-knowledge-base 后续搜索、数据生命周期、整理归档三条主线的算法方向。当前阶段只做文档和路线图同步，不实现算法、不修改 SQLite schema、不修改 `knowledge/**/*.md`，也不改变现有 search/index/audit 行为。

## 不变架构边界

- Markdown 仍是 source of truth，frontmatter 和正文保存来源、状态、审核、适用范围和生命周期历史。
- SQLite FTS5 仍是默认精确搜索引擎，`.kb/index.sqlite` 是可删除重建的索引层，不是事实来源。
- Vector search 后续只能作为增强召回或 rerank，不能替代 SQLite FTS5、BM25 和正式层过滤。
- 所有搜索必须尊重 `layer`、`status`、`source_type`、`confidence` 等 metadata hard filter。
- `raw`、`distilled`、`deprecated`、`quarantine`、`rejected` 默认不得进入正式搜索结果。
- `organize` / `archive` 默认只生成计划，不自动移动、删除或改写数据。
- `promote` 必须是人工审核动作，不能由算法自动完成。

## 1. Layer-aware Hybrid Retrieval

中文名：分层感知混合检索算法。

### 解决的问题

在知识库规模扩大、未来可能加入向量检索和 GUI 搜索页后，必须保证搜索仍优先服务正式可执行知识，避免 `raw`、`distilled`、过期内容或隔离内容绕过治理规则进入项目决策。

### 输入

- `query`：用户检索词或 GUI 搜索输入。
- `category`、`layer`、`type`、`status`、`source_type`、`confidence` 等筛选条件。
- SQLite FTS5 `documents`、`chunks`、`chunks_fts` 索引数据。
- Markdown frontmatter 映射到索引层的 metadata 快照。
- 可选向量候选集，仅用于未来语义召回增强。

### 输出

- 经过 metadata hard filter 后的 Top-K chunk。
- 每条结果的路径、层级、状态、来源类型、confidence、snippet 和可解释 score。
- 可选 explain 信息，用于审计 BM25、字段命中、层级权重和过滤原因。
- 当正式层无结果时，默认返回空结果，而不是自动回退到未审核层。

### 核心规则

- SQLite FTS5 / BM25 是默认入口，先做精确召回和候选排序。
- `layer`、`status`、`source_type`、`confidence` 必须作为 hard filter，不得只作为软权重。
- 默认只返回 `rules`、`checklists`、`snippets`，且排除 `status=deprecated/rejected/quarantine`。
- 默认不返回 `raw`、`distilled`、`deprecated`，必须通过显式 research 或 include 参数进入探索路径。
- 后续向量检索必须先经过 metadata hard filter，或只对已过滤候选做补充召回和 rerank。
- 向量检索不能替代 SQLite FTS5，不能绕过正式层过滤，不能让未审核内容影响正式搜索默认结果。
- score 可以优化，但默认信任边界不得因排序策略变化而改变。

### 适用阶段

- SQLite Search Optimization
- Vector Search / Hybrid Search
- GUI Search Page
- Large-scale Search

### 不适用场景

- 不用于 `research` 的未审核探索结果直接作为项目规则。
- 不用于自动 promote。
- 不用于替代 `open` 读取单篇 Markdown 全文。
- 不用于全库字符串扫描或启动时全量读取 Markdown。

### 和现有 Markdown + SQLite 架构的关系

Markdown 保存事实和治理字段；SQLite FTS5 保存可重建索引、chunk、BM25 和 metadata 快照。该算法只定义搜索入口、过滤顺序和未来混合检索边界，不改变 Markdown-first 原则，也不要求当前修改 SQLite schema。

### 后续实现优先级

优先级：高。先固化现有 FTS5 + metadata hard filter，再做可解释排序和 GUI filter chips；向量检索排在最后，且必须服从同一 metadata filter。

### 风险和边界

- 过滤过严可能导致正式搜索无结果，这是正确行为，不应自动回退到 raw。
- metadata 不完整会影响过滤质量，应通过 audit/lint 暴露，而不是放宽默认搜索。
- 向量候选如果绕过过滤会造成治理污染，必须作为硬性禁止项。
- 大规模场景下 rerank 只能处理有限候选集，不能把全量 chunk 交给内存排序。

## 2. Content-addressed Lifecycle State Machine

中文名：内容寻址生命周期状态机。

### 解决的问题

知识库长期增长后，同一内容可能以 raw、distilled、rules、deprecated 等形态存在。需要用稳定身份和状态流转管理来源、提炼、审核、promote、废弃、隔离和恢复，防止未审核内容污染正式层。

### 输入

- Markdown 文件路径、layer 和 frontmatter。
- `card_id`、`topic_id`、`canonical_id`、`source_hash`、`content_hash` 等未来身份字段。
- `status`、`review_required`、`confidence`、`reviewed_by`、`last_reviewed`、`verification_method`。
- promote、deprecate、quarantine、restore、dedupe、conflicts 等人工或维护动作。

### 输出

- 明确的生命周期状态和合法转移结果。
- review queue、promote plan、dedupe report、conflict report、stale report。
- canonical 关系、替代关系和历史状态记录。
- 增量 index 可使用的变化检测线索。

### 核心规则

- 生命周期主线为 `raw -> distilled -> review-queue -> promote -> rules/checklists/snippets -> deprecated/archive`。
- `raw` 和 `distilled` 不能自动进入正式层。
- `promote` 必须人工审核，并记录 `reviewed_by`、`confidence`、`valid_for`、`verification_method`、`review_note`。
- `card_id` 标识知识卡片，`topic_id` 关联同一主题，`canonical_id` 指向主题下推荐正式知识。
- `source_hash` 用于来源重复检测，`content_hash` 用于正文重复检测。
- `deprecated`、`rejected`、`quarantine` 历史不得自动删除。
- `review_required=true` 的内容不能作为项目决策依据。
- `restore`、`deprecate`、`quarantine` 等状态变更必须保留原因和人工确认。

### 适用阶段

- Markdown Storage Design
- Lifecycle Governance
- Promote / Review Workflow
- Long-term Maintenance
- Service Layer
- GUI Review Queue

### 不适用场景

- 不用于自动抓取不可控全网内容。
- 不用于自动 promote 未审核知识。
- 不用于静默改写 `knowledge/**/*.md`。
- 不用于把 SQLite 当作事实来源。

### 和现有 Markdown + SQLite 架构的关系

生命周期状态必须记录在 Markdown/frontmatter 中。SQLite 只缓存这些状态以支持 search、audit、review queue、dedupe 和 conflicts。即使索引删除重建，生命周期事实也必须能从 Markdown 恢复。

### 后续实现优先级

优先级：高。先在 Markdown Storage Design 中定义字段语义和兼容策略，再细化合法状态转移、人工确认点和 GUI Review Queue。SQLite schema 只有在字段稳定后再规划，不在当前阶段修改。

### 风险和边界

- 身份字段设计过早固化会带来迁移成本，因此先文档化再逐步落地。
- 自动状态转移容易破坏治理闭环，必须保持人工审核边界。
- 内容 hash 不能替代人工判断，近似重复和语义冲突仍需 review。
- restore 不能覆盖当前 active canonical 内容，必须先生成计划并人工确认。

## 3. Topic-aware Generational Archive Planner

中文名：主题感知分代归档算法。

### 解决的问题

随着 raw 和历史资料持续增长，active working set 会膨胀，影响搜索质量、维护成本和未来 GUI 体验。需要按主题、层级、状态和访问频率生成整理/归档计划，让正式层保持少而准，同时保留 raw 的可追溯和可恢复能力。

### 输入

- `topic_id`、`layer`、`status`、`review_required`、`confidence`。
- `last_reviewed`、可选 `last_accessed_at`、`review_cycle_days`。
- `source_hash`、`content_hash`、重复检测和冲突检测结果。
- 搜索访问、打开次数或未来 GUI 使用频率摘要。
- active workspace、archive workspace 和 workspace sharding 策略。

### 输出

- `organize-plan`：建议合并、补字段、标记 canonical、补 review 或拆主题。
- `archive-plan`：建议归档的 raw、deprecated、低频历史资料和重复支撑材料。
- `restore-plan`：需要从 archive 恢复到 active workspace 的候选和理由。
- 风险说明、影响范围、建议 snapshot/backup 和人工确认点。

### 核心规则

- 默认只生成计划，不自动移动文件、不删除文件、不修改知识卡片。
- `archive`、`restore`、`deprecate`、`quarantine` 必须人工确认。
- active `rules`、`checklists`、`snippets` 应保持少而准。
- raw 可以增长，但必须可归档、可恢复、可显式搜索。
- deprecated/rejected/quarantine 历史应保留原因，不应因归档被抹除。
- 100K+ 优先 active/archive 分离和 per-workspace index，而不是扩大单一活跃索引。
- 真实移动前应有 local snapshot / backup 或 dry-run 报告；Git snapshot 只能作为可选补充。

### 适用阶段

- Organize & Archive Design
- Long-term Governance
- Large-scale Performance
- Workspace Sharding
- GUI Archive Manager

### 不适用场景

- 不用于自动删除历史知识。
- 不用于自动 promote 或自动修正正式层。
- 不用于替代 audit、dedupe、conflicts 的人工判断。
- 不用于启动时全库扫描和阻塞 GUI。

### 和现有 Markdown + SQLite 架构的关系

Markdown 仍保存所有知识和归档状态。SQLite 可提供 metadata、访问摘要和重复检测索引，但归档计划不能以 SQLite 为唯一依据。archive workspace 的索引也应是 per-workspace 可重建索引。

### 后续实现优先级

优先级：中高。先在 large-scale 和 long-term governance 中定义 plan-only 行为，再在 service layer 提供 dry-run API，最后进入 GUI Archive Manager。真实 archive/restore 必须晚于备份、snapshot 和人工确认能力。

### 风险和边界

- 访问频率低不等于低价值，归档建议必须展示理由和风险。
- raw archive 不能让来源证据不可追溯。
- workspace 分片会增加跨 workspace 搜索复杂度，应作为 100K+ 后续增强。
- 自动移动文件容易破坏 Git review 和历史链接，因此默认禁止。

## 后续实现优先级总览

1. 先完善文档契约：本文件、roadmap、large-scale performance、future Markdown Storage Design。
2. 固化现有搜索边界：FTS5、BM25、正式层默认过滤、metadata hard filter。
3. 设计生命周期字段和状态转移：先兼容旧卡片，再进入 service/API。
4. 设计 organize/archive plan-only API：先 dry-run，再人工确认。
5. GUI Search、Review、Archive 页面只展示和调用这些状态，不直接绕过 service/core。
6. Vector / Hybrid Search 最后实现，并且只能作为增强。
