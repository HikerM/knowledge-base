# Long-Term Operations

本文件定义 personal-knowledge-base 的长期治理、性能、内存、稳定性、备份恢复和未来 EXE-ready 运行原则。它不引入新的正式知识，不修改 `knowledge/**/*.md`，也不要求修改 SQLite schema。

## 1. 长期治理目标

长期治理不只是知识内容治理，还包括数据、索引、运行和发布的完整运维闭环。

长期目标：

- 数据质量治理：防止 raw、distilled、formal 层级污染，保留来源、审核、验证和生命周期状态。
- 搜索性能治理：搜索默认只走 SQLite FTS5，不扫描 Markdown 全文。
- 索引性能治理：增量索引优先用 `path + mtime + size` 判断变化，只有变化时才 hash。
- 内存治理：启动、搜索、列表和 GUI 常驻状态不得加载全部 Markdown。
- 长时间运行稳定性：未来 GUI 中 index、audit、dedupe、benchmark 等任务必须后台化。
- SQLite 并发与写锁：读任务可并发，写任务互斥，写事务短。
- 日志与报告归档：报告和日志需要按时间归档、可追溯、可轮转。
- 备份恢复：Markdown、config、templates、reports 是主要数据资产，本地 snapshot/backup 是默认回滚机制，Git 只是开发者或高级用户的可选同步机制，SQLite 索引可重建。
- schema/version migration：frontmatter 和 SQLite schema 的演进必须可审计、可回滚、向后兼容。
- release/tag 策略：每个稳定治理阶段都要有可复现的验收命令和 tag。
- EXE/GUI 常驻运行准备：GUI 只能通过 service/core API 访问知识库，不直接改 Markdown 或 SQLite。

## 2. 数据治理

### 层级原则

`raw` 可以多，用于保留原始材料、外部摘录、学习记录和未审核信息。`rules`、`checklists`、`snippets` 必须少而准，只保存人工审核、适用范围清晰、验证方式明确的正式知识。

默认信任边界：

- `rules`：正式工程规则。
- `checklists`：正式检查清单。
- `snippets`：正式可复用片段。
- `distilled`：提炼草稿，仍需人工审核。
- `raw`：原始参考，不能作为正式规则。
- `quarantine`：隔离内容，不能指导项目实现。
- `rejected`：审核拒绝内容，保留历史。
- `deprecated`：曾经有效但已过期或被替代的内容，保留历史。

### 生命周期

长期闭环保持为：

```text
external content -> raw -> distilled -> review -> promote -> formal -> deprecated
```

更完整的治理闭环为：

```text
外部内容 -> raw -> distilled -> review-queue -> promote -> rules/snippets/checklists -> search -> 项目使用 -> 实践验证 -> audit/stale/conflicts/deprecate -> 更新、废弃、修正
```

要求：

- 外部内容只能先进入 `raw`。
- AI 或人工提炼默认进入 `distilled`，且 `review_required=true`。
- `promote` 是人工审核动作，必须记录 reviewer、confidence、valid_for、verification_method 和 review_note。
- 正式知识只能通过 `rules`、`checklists`、`snippets` 对项目生效。
- 被替代或过期的正式知识使用 `deprecate`，不直接删除。

### dedupe / conflicts / stale / audit 职责

- `dedupe`：发现重复来源、重复标题、重复正文 hash、同一 `topic_id` 下的重复内容。
- `conflicts`：发现同一主题多个 active rules、失效 superseded_by、active 规则互相替代但未废弃的问题。
- `stale`：发现超出复查周期的 active 知识。
- `audit`：汇总缺少来源、缺少审核、低置信正式规则、unknown source、重复标题、过期和潜在冲突。

这些命令默认只报告，不删除、不 promote、不改写 raw/distilled/rules。

### quarantine / rejected / deprecated 区别

- `quarantine`：暂时隔离。用于来源不明、质量低、无法验证、疑似污染或 AI 摘要不可靠的内容。隔离内容不得指导实现。
- `rejected`：人工审核后明确不采用。用于防止同一错误内容未来重复进入知识库。
- `deprecated`：曾经有效，但因为版本、实践、来源或新规则变化而过期。应记录 `deprecated_reason` 或 `superseded_by`。

### topic_id / canonical rule 未来规划

`topic_id` 用于把同一主题下的 raw、distilled、rules、checklists 和 snippets 关联起来。未来目标是每个重要主题都有：

- 一个稳定 `topic_id`。
- 一个 canonical rule 或 canonical checklist。
- supporting raw/distilled 作为背景证据。
- deprecated/rejected 历史说明规则演进。

规划原则：

- `topic_id` 长期稳定，不包含日期和文件层级。
- 同一 `topic_id` 下不应长期存在多个 active canonical rules。
- `canonical_id` 只给人工审核后的正式层内容使用。
- raw 和 distilled 可以共享 `topic_id`，但不能成为 canonical。

### 每批导入后必须检查

每批导入 raw 或 distilled 后运行：

```bash
python scripts/kb.py index
python scripts/kb.py lint
python scripts/kb.py audit
python scripts/kb.py review-queue
python scripts/kb.py secret-scan
```

如本批导入包含同一主题的多份资料，还应运行：

```bash
python scripts/kb.py dedupe
python scripts/kb.py conflicts
```

### 每月维护必须检查

每月维护至少检查：

- frontmatter schema 与必填字段。
- 正式层缺少来源或审核信息。
- active 内容是否 stale。
- 同一 `topic_id` 下是否存在多个 active rules。
- deprecated/rejected/quarantine 是否保留原因。
- reports 是否需要归档。
- `.kb/index.sqlite` 是否明显膨胀，需要显式 vacuum。
- CI、secret-scan、search quality 和 perf smoke 是否仍通过。

## 3. 性能治理

### 搜索原则

`search` 只走 SQLite FTS5。默认搜索不得全量读取 `knowledge/` 下的 Markdown，不得使用文件系统字符串扫描作为常规路径。

搜索输出：

- 默认 Top-K 为 10。
- 大 Top-K 必须受 limit 和 `--force` 控制。
- 结果只返回命中 chunk、snippet 和元数据。
- 完整正文只能通过 `open` 单篇读取。
- 未来 GUI 必须分页，不一次性加载所有结果。

### 索引原则

`index` 可以遍历 `knowledge/`，但应优先用 `path + mtime + size` 判断未变化文件。只有以下情况才计算 hash 和读取正文：

- 新文件。
- `mtime` 或 `size` 变化。
- 显式传入 `--force-hash`。
- 显式 `reindex`。

### 何时 reindex

需要 reindex 的情况：

- `.kb/index.sqlite` 损坏或被删除。
- FTS5 查询异常。
- SQLite schema migration 需要重建索引。
- 大量文件移动、重命名或 lifecycle 迁移后，需要清理旧索引记录。
- search quality 明显异常且普通 `index` 无法修复。

`reindex` 可以删除并重建 `.kb/index.sqlite`，但不能改 Markdown 源数据。

### 何时 vacuum

`VACUUM` 是写任务，必须显式触发，不应作为默认维护动作。

适合 vacuum 的情况：

- 大批量删除或移动文件后，索引文件明显膨胀。
- reindex 之外发生了多次索引更新，`.kb/index.sqlite` 远大于预期。
- 月度维护报告提示索引大小异常。
- release 前需要压缩索引生成物。

不适合 vacuum 的情况：

- GUI 正在执行搜索或其他写任务。
- 没有足够磁盘空间。
- 只是日常导入少量文档。

### benchmark 与 perf_smoke

- `python scripts/kb.py benchmark` 用于当前真实知识库的查询延迟和搜索路径检查。
- `python tests/perf_smoke.py` 用 1,000 个生成文档验证首次索引、第二次增量 skip、默认 search、stats 和 doctor 的性能行为。

`perf_smoke` 是 CI 下限，不代表最终桌面应用体验目标。未来 GUI 可以加入更严格的本地 benchmark。

### 数据量目标

1,000 文档目标：

- 首次索引在 CI smoke 下必须小于 60 秒。
- 第二次无变化增量索引必须大部分 skipped，hashed 数量接近 0。
- 默认 search 必须走 FTS5，并在 CI smoke 下小于 10 秒。
- `stats` 和 `doctor` 应在可交互时间内完成。

10,000 文档未来目标：

- 默认 search p95 目标小于 2 秒。
- 无变化增量 index 目标小于 60 秒。
- 单次少量文件变更 index 目标小于 10 秒。
- GUI 搜索结果必须分页或虚拟滚动。
- audit、dedupe、conflicts、benchmark 允许较慢，但必须后台执行并提供进度。

### 正文读取边界

允许读取正文的命令：

- `index`：只读取新文件或变化文件，除非 `--force-hash`。
- `reindex`：显式全量重建索引。
- `open`：只读取指定单篇文档。
- `distill-plan`：只读取指定单篇 raw。
- `lint`：用于 frontmatter 和质量检查，可读取 Markdown，但应受 category/layer/limit 控制。
- `secret-scan`：扫描仓库文本以发现 secret，不作为搜索路径。

不应该读取正文的命令：

- `search` 默认路径。
- `list`。
- `stats`。
- `digest`。
- `weekly-report`。
- GUI Dashboard 默认加载。
- GUI Search 默认加载。

## 4. 内存治理

内存原则：

- 启动时不加载全部 Markdown。
- 搜索只返回 Top-K chunk。
- 用户点击 `open` 时才读取单篇文档。
- 大列表必须分页或虚拟滚动。
- 缓存必须有上限，例如按文档数量、字节数或 LRU 淘汰。
- 任务结果只保存摘要，不保存无限制全文。
- 日志和报告要归档或轮转。
- 大型报告按需读取，不在 Dashboard 一次性加载。
- 后台任务完成后关闭文件句柄、释放 DB connection、丢弃大对象引用。
- 未来 GUI 不得把所有文档常驻内存。

未来缓存建议：

- 搜索结果缓存只保留最近 N 次查询摘要。
- open 文档缓存只保留最近 N 篇，且有总字节上限。
- 大报告只显示目录、摘要和路径，用户打开时再读取正文。
- 后台任务 stdout/stderr 日志写入文件，UI 只持有尾部摘要。

## 5. 长时间运行稳定性

未来 EXE/GUI 中以下任务不能阻塞 UI 主线程：

- `index`
- `reindex`
- `audit`
- `secret-scan`
- `dedupe`
- `conflicts`
- `benchmark`
- `maintenance`
- Optional Git Sync
- backup/export
- learning queue generation

后台任务队列原则：

- 每个任务有唯一 `task_id`。
- 状态枚举为 `pending`、`running`、`succeeded`、`failed`、`cancelled`。
- 必须有 `progress_percent`。
- 必须有 `progress_message`。
- 支持 cancellation。
- 支持 retry，但 retry 不得重复破坏性写入。
- 失败保留 `error_detail`。
- 每个任务有 `log_path`。
- 完成后返回 `result_summary`，而不是无限制全文。

建议任务结果模型：

```text
task_id
task_type
status
started_at
finished_at
progress_percent
progress_message
error_detail
log_path
result_summary
```

写任务必须经过队列互斥调度。读任务可以并发，但不能长期占用 SQLite connection。

## 6. SQLite 并发策略

任务分类：

- `search` 是读任务。
- `list`、`stats`、`doctor`、`digest` 默认是读任务。
- `index`、`reindex`、`vacuum` 是写任务。
- `maintenance` 中的 `index` 和可选 `vacuum` 是写步骤，其余多为读检查。

并发策略：

- 同一时间只允许一个写任务。
- 读任务可并发。
- SQLite 使用 WAL。
- 写事务要短，避免长时间持有写锁。
- GUI 不长期持有 DB connection。
- 每个 service 调用按需打开连接，完成后关闭或释放。
- 写任务失败不能破坏 Markdown 源数据。
- `.kb/index.sqlite` 可删除重建，不是事实来源。

失败处理：

- `index` 失败时不应修改 Markdown。
- `reindex` 失败后可以重新执行 `index` 重建。
- `vacuum` 失败只影响索引压缩，不影响 Markdown。
- GUI 应提示用户索引可重建，而不是让用户手工编辑 `.kb/index.sqlite`。

## 7. 备份与恢复

主要资产：

- `knowledge/`
- `config/`
- `templates/`
- `reports/`
- `README.md`
- `AGENTS.md`
- `docs/`

Markdown、config、templates、reports 和核心文档是主要数据资产。`.kb/index.sqlite` 是可重建索引，不作为备份核心；它可以在备份中作为可选加速恢复内容，但不能替代 Markdown。

### 默认回滚机制

Local snapshot / backup 是默认回滚机制。普通用户不需要 Git、GitHub 账号或命令行，也应能完整备份、恢复和继续使用知识库。

升级、promote、archive、bulk import、schema migration、destructive maintenance 和 workspace upgrade 前应创建 snapshot。恢复时优先从本地 backup/snapshot 恢复，再重建索引。

推荐恢复后运行：

```bash
python scripts/kb.py index
python scripts/kb.py doctor
```

### Optional Git Sync

Git 是开发者或高级用户的可选版本同步机制，可用于跨设备同步、远端备份、代码审查和软件项目自身 release 管理。Git 不得成为 EXE 软件的必需依赖，也不得成为 promote、audit、index、archive、restore 的前置条件。

Git tag 主要用于软件项目自身 release，不应是普通用户知识库回滚的唯一机制。即使启用 Git Sync，本地 snapshot/backup 仍是恢复前的默认安全网。

### 索引重建

如索引损坏或恢复后需要刷新，可删除 `.kb` 后重建：

```powershell
Remove-Item -Recurse -Force .kb
python scripts/kb.py index
python scripts/kb.py doctor
```

在非 PowerShell 环境中删除 `.kb` 后运行同样的 `index` 和 `doctor`。删除 `.kb` 不应影响 Markdown 源数据。

### public repo 安全

公开仓库不得包含：

- 真实密钥、密码、token。
- 客户隐私数据。
- 私有业务数据。
- 未授权的外部全文复制内容。

发布前必须运行：

```bash
python scripts/kb.py secret-scan
```

### backup/export 未来设计

未来 backup/export 应满足：

- 默认导出 Markdown、config、templates、docs、reports，不要求导出 `.kb/index.sqlite`。
- 支持包含或排除 reports。
- 支持可选包含 `.kb/index.sqlite` 以加快恢复。
- 支持导出 manifest，记录文件数量、hash、创建时间和工具版本。
- 支持导入前 dry-run。
- 支持恢复后自动 `index` 和 `doctor`。
- 私有 workspace 导出必须提醒 secret-scan 和敏感数据风险。
- public repo 不等于 backup。公开仓库不能替代本地备份，也不能保证包含用户全部私有 workspace 数据。

## 8. Schema / version migration

### Markdown frontmatter schema 演进

frontmatter 是长期事实来源的一部分。新增字段应：

- 保持向后兼容。
- 有默认值或可缺省解析。
- 不让旧知识卡片无法解析。
- 在模板、lint、docs 中同步说明。
- 避免一次性强制重写全库。

推荐字段演进方式：

1. 文档说明新字段和用途。
2. 模板加入新字段。
3. parser 对缺省字段使用默认值。
4. lint 先 warning，再在未来版本升级为 error。
5. 需要批量修复时生成报告，由人工确认后处理。

### SQLite schema 版本

SQLite schema 未来应记录版本，例如：

- `schema_version` 表。
- `PRAGMA user_version`。
- migration history 表。

当前 `.kb/index.sqlite` 是索引层，可以删除重建。未来如果加入 schema version，也必须保持“可重建索引”原则。

### migration 原则

Migration 应：

- 可重复执行。
- 可审计，有版本号、时间、说明。
- 可回滚，至少能通过删除 `.kb` 后重建恢复。
- 保持旧 Markdown 可解析。
- 不把 raw/distilled 自动 promote。
- 不默认删除 deprecated/rejected/quarantine 历史。

### 何时需要 version bump

需要 bump version 的情况：

- frontmatter 必填字段或语义改变。
- SQLite schema 改变。
- search ranking 或默认过滤策略改变。
- promote/audit/secret-scan 等治理门禁改变。
- maintenance/release 验收流程改变。
- GUI/service API 契约改变。

## 9. Release / tag 策略

版本基线：

- `v1.0.0`：stable baseline。
- `v1.1.0`：modular core baseline。
- `v1.2.0`：可作为 long-term operations / EXE-ready design baseline。

release 前运行：

```bash
python scripts/kb.py --help
python scripts/kb.py index
python scripts/kb.py audit
python scripts/kb.py secret-scan
python scripts/kb.py doctor
python scripts/kb.py benchmark
python scripts/kb.py monthly-maintenance
python tests/smoke_test.py
python tests/search_quality_test.py
python tests/search_explain_test.py
python tests/search_deprecated_status_test.py
python tests/governance_test.py
python tests/perf_smoke.py
```

如果启用 `maintenance` 命令，也运行：

```bash
python scripts/kb.py maintenance
```

tag 前必须确认：

- CI green。
- secret-scan clean。
- tests passed。
- search quality passed。
- perf smoke passed。
- monthly-maintenance 或 maintenance 报告已生成并检查。
- 没有未解释的 dirty worktree。

Git tag 属于软件项目自身 release 管理。普通用户知识库回滚不得只依赖 Git tag；EXE 默认应提供本地 backup/snapshot 恢复路径。

## 10. 维护频率建议

每批导入后：

- `index`
- `lint`
- `audit`
- `review-queue`
- `secret-scan`

每周：

- `audit`
- `stale`
- `review-queue`
- `secret-scan`

每月：

- `maintenance`
- `dedupe`
- `conflicts`
- `stats`
- optional `vacuum`
- report archive review

每季度：

- schema review
- source-policy review
- deprecated cleanup
- performance baseline review
- backup/restore rehearsal

季度 cleanup 不是删除历史。它应检查 deprecated/rejected/quarantine 的原因是否完整，是否需要补充 superseded_by、review_note 或归档说明。
