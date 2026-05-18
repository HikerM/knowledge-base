# Large-scale Performance Design

本文定义 `personal-knowledge-base` 在 10,000 到 100,000+ Markdown 文档规模下的性能、索引、内存和体验边界。当前阶段不实现 GUI、不做 RSS、不做向量检索、不做 MCP、不做 Codex Skill、不打包 EXE；重点是建立未来大规模模式的原则、接口、测试护栏和验收标准。

## 1. 大规模目标

目标分层：

- 10,000 docs：应流畅。启动、搜索、增量索引都应保持可感知的快速反馈。
- 30,000 - 50,000 docs：优化后可稳定使用。需要更严格的批处理、后台任务、分页和内存上限。
- 100,000+ docs：进入 large-scale mode，需要后台索引、分层优先、checkpoint/resume、workspace 分片。

硬性边界：

- Markdown 仍是事实来源。
- SQLite FTS5 / 索引是搜索入口。
- 搜索只查 SQLite FTS5 / 索引，不扫描 Markdown 全文。
- 首次全量 `index` 允许较久，但必须后台执行。
- 软件启动不能等待全量 `index`。
- 日常使用依赖增量 `index`。
- `.kb/index.sqlite` 可以删除重建，不得当作事实来源。

大规模模式不是改变知识治理规则。`rules`、`checklists`、`snippets` 仍是默认正式层；`raw`、`distilled`、`deprecated` 的默认搜索策略不变。

## 2. 启动性能策略

启动阶段只允许读取轻量元数据：

- workspace 配置，例如 `config/categories.yaml`、`config/sources.yaml` 和未来 workspace manifest。
- index 状态，例如 `.kb/index.sqlite` 是否存在、schema 是否可用、last indexed time。
- 统计信息，例如 document count、chunk count、by layer、by status。
- 最近任务状态，例如最近 index/audit/secret-scan 是否失败、是否可 resume。

启动阶段不得：

- 扫描全部 Markdown。
- 读取所有 Markdown。
- 自动全量 `index`。
- 因 index missing/stale 阻塞 UI。

当 index missing/stale 时，界面或 service 应提示用户当前能力受限，并提供后台构建或恢复索引入口。提示不应阻塞 workspace 打开，也不应自动触发破坏性维护动作。

## 3. 大规模 index 策略

大规模 `index` 必须从同步 CLI 思维升级为可后台化的任务模型：

- background indexing：全量或长时间增量索引在后台 worker 中运行。
- batch indexing：每 500 或 1000 文件提交一次事务，降低锁持有时间和失败回滚成本。
- checkpoint / resume：记录已处理路径、当前 layer、失败文件和任务状态，中断后下次继续。
- partial index：允许正式层已可用而 raw/archive 仍在排队。
- cancellation：用户可取消后台任务，取消后保留已提交批次和 checkpoint。
- retry failed files：失败文件记录 `last_error`，后续可单独 retry。
- priority indexing by layer：先恢复最可信、最常用的正式层。

索引优先级：

1. `rules`
2. `checklists`
3. `snippets`
4. `distilled`
5. `raw`
6. `deprecated`
7. `archive`

计数和状态必须结构化记录：

- `indexed`
- `updated`
- `skipped`
- `failed`
- `deleted`
- `hashed`
- `elapsed_ms`
- `index_size_bytes`

变更检测策略：

- 未变化文件不 hash。
- 只有新文件、mtime/size 变化文件或显式 force-hash 时才 hash。
- deleted 文件必须从 `documents`、`chunks`、`chunks_fts` 清理。
- failed 文件必须记录 `last_error`、失败阶段和可 retry 标记。
- checkpoint 中需要记录最后成功提交批次，而不是只记录最后扫描文件。

事务策略：

- 每 500 或 1000 文件提交一次。
- 单批失败不应导致已成功批次回滚。
- 写任务串行化，避免多个 index/reindex/vacuum 同时写 SQLite。
- 读任务可在安全条件下继续使用已提交索引。

## 4. Partial index 状态

索引状态至少包括：

- `missing`：`.kb/index.sqlite` 不存在或不可打开。
- `ready`：schema 正常，目标层已完成索引，未发现明显 stale。
- `stale`：Markdown 与索引不一致，需要增量 index。
- `building`：后台索引正在运行。
- `partial`：部分层或部分 workspace 已完成，完整搜索不可用。
- `failed`：最近一次索引失败，需要查看日志或 retry。

GUI 或 service 展示建议：

- `full search unavailable`：索引缺失、失败或只完成部分层。
- `formal layer search ready`：`rules/checklists/snippets` 已完成，可以执行默认正式搜索。
- `raw indexing pending`：正式层可用，但 raw/distilled/deprecated/archive 仍待索引。
- `last index failed`：展示 error summary、log path 和 retry 入口。
- `resume indexing available`：检测到 checkpoint，可从上次任务继续。

状态展示必须区分“正式搜索可用”和“全库探索搜索可用”。不得因为 raw 尚未索引而阻止正式层搜索。

## 5. 搜索性能策略

搜索路径必须保持轻量：

- `search` 不读取 Markdown。
- `search` 只查 SQLite FTS5 / 索引。
- `search` 只返回 Top-K chunk 和必要元数据。
- 默认 Top-K 使用当前默认值，当前为 10；未来 GUI 可显示默认 20，但不得改变 CLI 现有默认行为。
- 最大 Top-K 必须有上限，超出需要显式确认或管理员配置。
- 大结果集使用 pagination，不一次返回全部命中。
- deprecated/raw/distilled 默认策略不变。
- 点击结果或调用 `open` 时才读取单篇全文。
- snippet 来自索引 chunk，不来自全量文件扫描。

大规模搜索建议：

- FTS 查询先取有限候选，例如 `top_k * 8` 或固定上限。
- rerank 只在候选集内执行。
- filter 使用 `documents` 元数据索引。
- GUI 使用 debounce，避免每个按键触发完整查询。
- 结果按页或增量加载，不把 10W 结果交给 UI。

## 6. 内存治理

大规模模式必须保证内存有界：

- 不缓存全部文档。
- 不缓存全部搜索结果。
- 不把 10W 结果交给 GUI。
- 使用 LRU / TTL cache。
- cache 必须有数量和字节上限。
- 长任务只保留结果摘要。
- 详细日志写文件，内存中只保留尾部窗口。
- 日志轮转，避免长期运行无限增长。
- 报告归档，按需读取。
- 大文件流式读取，hash 使用分块读取。
- 后台任务完成后释放文件句柄、DB connection、大型列表和正文缓存。

建议缓存边界：

- 最近打开文档缓存：按文档数和总字节双重限制。
- 搜索结果缓存：按 query/filter/top_k/page key 缓存短 TTL 摘要。
- stats/index status 缓存：短 TTL，避免高频刷新造成 DB 压力。
- 任务日志缓存：只保存最近 N KB 或最近 N 行，完整日志写入 log path。

## 7. GUI 流畅策略

虽然当前不实现 GUI，但未来 GUI 必须满足以下体验策略：

- virtual list：搜索结果、文档列表、review queue、日志列表都使用虚拟滚动。
- pagination：服务层返回分页模型，不把全量列表交给渲染层。
- lazy document loading：只在用户打开文档时读取正文。
- background workers：index、audit、secret-scan、reindex、dedupe、conflicts、benchmark、maintenance 都走后台任务。
- progress events：长任务持续发送阶段、计数、当前文件、耗时和估算剩余时间。
- task cancellation：后台任务可取消，取消后状态可恢复或重试。
- task logs：长任务写独立日志文件，UI 只展示尾部和摘要。
- non-blocking UI：主线程只做渲染和用户交互，不跑 IO 密集任务。
- search debounce：输入搜索时 debounce，避免过度查询。
- filter chips：分类、层级、状态、来源、confidence 使用结构化筛选。
- incremental result loading：先返回第一页或首批结果，再按需加载更多。

GUI 不得直接读写 Markdown 或 SQLite，必须通过 service/core API 访问。启动、搜索和后台任务都要以 service boundary 为中心设计。

## 8. SQLite 策略

SQLite 是本项目的索引层，不是事实来源。大规模模式下的 SQLite 策略：

- 使用 WAL。
- 使用 short transactions。
- 单 writer / 多 reader。
- read tasks 可以在安全条件下与 indexing 并行读取已提交数据。
- write tasks 必须串行化。
- `vacuum` 必须显式触发，不在启动或日常维护中自动运行。
- `reindex` 必须显式触发，不在启动时自动运行。
- `.kb/index.sqlite` 可重建。
- index corruption recovery 必须优先保护 Markdown。

索引损坏恢复流程：

1. 标记 index 状态为 `failed` 或 `missing`。
2. 提示用户 `.kb/index.sqlite` 是可重建索引。
3. 提供后台 `reindex` 或删除 `.kb` 后重建入口。
4. 不修改 `knowledge/**/*.md`。
5. 重建完成后运行 `doctor` 和 `stats` 验证。

并发策略：

- `search`、`stats`、`list` 只读连接。
- `index`、`reindex`、`vacuum` 写连接。
- 写任务队列一次只执行一个。
- 长写任务按批提交，降低 reader 被阻塞的时间。

## 9. Workspace 分片策略

100K+ 文档时建议不要把所有内容强行放进单一活跃 workspace。推荐：

- 多 workspace。
- active / archive 分离。
- raw archive 分离。
- 每个 workspace 独立 `.kb/index.sqlite`。
- 每个 workspace 独立 reports 和 task logs。
- cross-workspace search 作为未来增强，不作为 100K 首版前提。

建议分片方式：

- active workspace：当前项目常用 rules/checklists/snippets 和近期 distilled/raw。
- archive workspace：历史 raw、大型资料、低频 deprecated/archive。
- research workspace：探索性资料，不进入正式项目决策默认路径。

分片不改变事实来源规则。每个 workspace 内仍然由 Markdown 作为事实来源，SQLite 只做本 workspace 的索引。

## 10. 性能验收目标

10,000 docs：

- startup 不加载全文。
- search target < 300ms。
- second index target < 5s。
- UI non-blocking。
- 第二次 index 应主要为 `skipped`。
- 第二次 index 的 `hashed` 应为 0 或接近 0。

100,000 docs：

- startup still fast。
- first index background。
- search target < 1s。
- index resumable。
- memory bounded。
- GUI responsive。
- full index 可较久，但必须可取消、可 resume、可查看日志。

这些目标是设计验收目标，不要求当前测试真实导入 100K 文档。当前测试护栏先覆盖 10K 临时语料下的索引、二次跳过、搜索和统计。

## 11. Future progress API

未来 service/core API 可使用以下结构。当前不要求实现，但后续大规模功能应按此模型收敛。

`IndexProgress`：

```python
{
    "task_id": "index-20260518-001",
    "total_files": 100000,
    "processed_files": 21500,
    "indexed": 1000,
    "skipped": 20300,
    "failed": 2,
    "current_file": "knowledge/01-frontend/rules/example.md",
    "current_layer": "rules",
    "elapsed_ms": 120000,
    "estimated_remaining_ms": 430000,
    "status": "building",
    "can_cancel": True,
}
```

`IndexResult`：

```python
{
    "indexed": 1000,
    "updated": 50,
    "deleted": 5,
    "skipped": 98945,
    "failed": 2,
    "elapsed_ms": 550000,
    "index_size_bytes": 250000000,
    "partial": True,
    "resumable": True,
}
```

状态字段建议：

- `queued`
- `building`
- `partial`
- `ready`
- `failed`
- `cancelled`

后续实现要求：

- progress event 不携带全文。
- result summary 不携带大列表。
- failed files 使用分页或单独日志读取。
- checkpoint 可被 `doctor` 或 index status 命令识别。
