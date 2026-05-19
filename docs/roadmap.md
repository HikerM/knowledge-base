# Project Roadmap

本文固定 personal-knowledge-base 后续阶段顺序。当前路线图只做规划同步，不代表立即实现算法、GUI、RSS、向量检索、MCP、Skill 或 SQLite schema 变更。

核心算法引用：

- Layer-aware Hybrid Retrieval：分层感知混合检索算法，负责搜索。
- Content-addressed Lifecycle State Machine：内容寻址生命周期状态机，负责数据生命周期。
- Topic-aware Generational Archive Planner：主题感知分代归档算法，负责整理归档。

v1.2.0 已完成的设计基线包括 long-term operations、large-scale readiness、Markdown storage design、SQLite-hot / Markdown-source model、backup/snapshot design、organize/archive design、10K performance smoke 和 core algorithm roadmap。下一阶段固定为 Phase 5：Generic Workspace / Template System。GUI/EXE 仍然后置。

## Phase 1：内容治理闭环收尾

目标：

- 稳定 raw -> distilled -> review-queue -> promote -> rules/checklists/snippets -> search -> audit/stale/conflicts/deprecate 的闭环。
- 保持 Markdown 是 source of truth，SQLite 只是索引层。
- 继续确保默认 search 只返回正式层。

使用算法：

- Layer-aware Hybrid Retrieval：使用，作为默认搜索边界。
- Content-addressed Lifecycle State Machine：使用，收尾 promote、deprecate、quarantine、review queue 规则。
- Topic-aware Generational Archive Planner：不作为主线，仅记录未来 archive 输入。

## Phase 2：Markdown Storage Design

状态：已完成 `docs/markdown-storage-design.md`，并纳入 v1.2.0 候选基线。本阶段固定 Markdown storage、schema、目录分片、migration 和 GUI/EXE 写入边界，不实际修改现有知识卡片。

未来必须支持的字段规划：

- `card_id`
- `topic_id`
- `canonical_id`
- `source_hash`
- `content_hash`
- `promoted_from`
- `supersedes`
- `superseded_by`
- `archive_status`
- `last_accessed_at`，可选
- `review_cycle_days`

目标：

- 定义字段语义、兼容策略、默认值和 lint/audit 迁移顺序。
- 先保持旧卡片可解析，再考虑模板和索引层同步。
- 不修改 SQLite schema，除非字段语义已经稳定并另行规划。

使用算法：

- Layer-aware Hybrid Retrieval：使用，字段需要支持搜索 hard filter。
- Content-addressed Lifecycle State Machine：重点使用，字段设计必须服务身份、状态和生命周期转移。
- Topic-aware Generational Archive Planner：使用，字段需要支持 archive_status、topic_id 和访问频率规划。

## Phase 3：Large-scale Performance / Memory

目标：

- 保证启动不全量扫描、不全量读取 Markdown、不自动触发 index/reindex。
- 搜索保持 SQLite FTS5 / 索引路径。
- 后台化 index/audit/secret-scan/reindex/dedupe/conflicts/benchmark/maintenance。
- 10W+ 时优先 active/archive/workspace 分片和 per-workspace index。

使用算法：

- Layer-aware Hybrid Retrieval：重点使用，控制大规模搜索候选集和正式层过滤。
- Content-addressed Lifecycle State Machine：使用，辅助增量 index、变化检测和状态过滤。
- Topic-aware Generational Archive Planner：重点使用，减少 active working set。

## Phase 4：Lifecycle State Machine 细化

目标：

- 细化合法状态、状态转移、人工确认点、失败回滚和审计记录。
- 明确 raw/distilled 不得自动进入正式层。
- 明确 restore/deprecate/quarantine 的确认和记录要求。

使用算法：

- Layer-aware Hybrid Retrieval：使用，搜索结果必须反映生命周期状态。
- Content-addressed Lifecycle State Machine：重点使用。
- Topic-aware Generational Archive Planner：使用，归档和恢复动作必须服从生命周期状态。

## Phase 5：Generic Workspace / Template System

目标：

- 建立 workspace model，把单一开发者知识库升级为通用知识库引擎。
- 设计 template catalog，支持 Developer、Designer、Product、Research、AI Agent 和 Custom Knowledge Base。
- 建立 category management 模型，区分稳定 `category_id`、可编辑 `display_name` 和可迁移 `path`。
- 支持 custom sources、extract-rules、quality-rules、review cycles 和 Markdown templates，但不得绕过治理闭环。
- 固定 per-workspace index，每个 workspace 独立 `.kb/index.sqlite`、独立配置、独立 reports。
- 规划 workspace backup/restore/export/upgrade/archive/delete 生命周期。
- 规划 category rename/archive/merge/delete plan，危险操作默认 plan-first。

边界：

- 本阶段只做设计文档、README、AGENTS 规则和未来命令规划。
- 不做 GUI、EXE、RSS、向量检索、MCP、Codex Skill。
- 不修改 `knowledge/**/*.md`。
- 不改变现有 search/index/audit 行为。

使用算法：

- Layer-aware Hybrid Retrieval：使用，workspace/search 仍需 hard filter，未来跨 workspace 搜索不得绕过正式层边界。
- Content-addressed Lifecycle State Machine：重点使用，workspace/template/category 变更不得破坏 raw -> distilled -> review -> formal。
- Topic-aware Generational Archive Planner：使用，workspace 分片和分类归档必须保留恢复能力和来源链路。

## Phase 6：Service Layer

目标：

- GUI 和未来 EXE 只能通过 service/core API 访问知识库。
- GUI 不直接读写 Markdown 或 SQLite，不拼接 CLI 命令字符串作为主要集成方式。
- 长任务提供 task_id、status、progress、cancellation、error detail、log path 和 result summary。
- Workspace/template/category 的 plan/apply 边界在 service 层固定。

使用算法：

- Layer-aware Hybrid Retrieval：重点使用，提供 search API 和 explain/filter contract。
- Content-addressed Lifecycle State Machine：重点使用，提供 review/promote/deprecate/quarantine/restore API contract。
- Topic-aware Generational Archive Planner：使用，提供 plan-only organize/archive/category API。

## Phase 7：GUI Design Contract

目标：

- 先设计 Search、Review、Archive、Workspace Selector、Template Picker、Workspace Settings、Category Settings、Source Settings、Template Manager、Backup & Restore 页面契约，再实现界面。
- 明确分页、虚拟滚动、后台任务、错误展示和确认弹窗。
- GUI 必须体现 workspace、template、category、layer、status、source_type、confidence、review_required、archive_status 等状态。

使用算法：

- Layer-aware Hybrid Retrieval：重点使用，Search 页面必须遵守。
- Content-addressed Lifecycle State Machine：重点使用，Review 页面和 Category Settings 必须体现。
- Topic-aware Generational Archive Planner：重点使用，Archive 和 workspace 分片必须体现。

## Phase 8：GUI MVP

目标：

- 实现最小可用 Search、Review、Archive、Workspace Selector 和 Category Settings 工作流。
- UI 主线程不得跑 index、audit、secret-scan、reindex、dedupe、conflicts、benchmark、maintenance、Optional Git Sync 或 backup/export。
- 搜索结果分页或虚拟滚动，不一次渲染所有结果。
- Workspace startup 只读当前 workspace metadata / index metadata，不扫描所有 workspace。

使用算法：

- Layer-aware Hybrid Retrieval：重点使用。
- Content-addressed Lifecycle State Machine：重点使用。
- Topic-aware Generational Archive Planner：使用，仍以 plan-only 为默认。

## Phase 9：Windows EXE 打包

目标：

- 打包前保护 workspace 数据，软件安装目录不存用户知识数据。
- Markdown 始终优先保护，SQLite index 可删除重建。
- maintenance、reindex、vacuum、restore、workspace delete 等操作必须显式触发并确认。
- Git optional 规则继续适用，普通用户默认依赖 Backup/Snapshot。

使用算法：

- Layer-aware Hybrid Retrieval：使用，确保 EXE 搜索行为不变。
- Content-addressed Lifecycle State Machine：使用，确保状态变更可审计。
- Topic-aware Generational Archive Planner：使用，确保 archive/restore 有确认和备份边界。

## Phase 10：RSS 受控来源采集

目标：

- 只从 `config/sources.yaml` 或用户明确提供的来源采集。
- 外部内容先进入 raw。
- AI 提炼默认进入 distilled 且 `review_required=true`。
- 不自动 promote。

使用算法：

- Layer-aware Hybrid Retrieval：使用，采集内容默认不得进入正式搜索。
- Content-addressed Lifecycle State Machine：重点使用，确保 raw/distilled/promote 边界。
- Topic-aware Generational Archive Planner：使用，长期 raw 增长后进入归档计划。

## Phase 11：Vector / Hybrid Search

目标：

- 在 SQLite FTS5 / BM25 和 metadata hard filter 稳定后再考虑向量检索。
- 向量检索只能作为语义召回增强或 rerank。
- 向量检索不得绕过 `layer`、`status`、`source_type`、`confidence` 过滤。

使用算法：

- Layer-aware Hybrid Retrieval：重点使用，是本阶段准入条件。
- Content-addressed Lifecycle State Machine：使用，向量索引必须尊重 lifecycle metadata。
- Topic-aware Generational Archive Planner：使用，active/archive/workspace 分片会影响向量索引范围。

## 版本建议

- v1.2.0：适合纳入 Markdown Storage Design、核心算法策略、路线图、长期运维、大规模性能、organize/archive 和 backup/snapshot 设计基线。
- v1.3.0：适合纳入 Generic Workspace / Template System、Category Management Design、workspace/template/category plan-only command contract 和后续 Service Layer 准备。
- GUI/EXE 仍然后置，必须等 workspace/template/category/service contract 稳定后再进入实现。
- RSS、Vector / Hybrid Search、MCP 和 Codex Skill 建议晚于 v1.3.0，等 metadata hard filter、service layer 和 GUI contract 稳定后再实现。
