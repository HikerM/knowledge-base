# Memory Model

本文定义未来 GUI / EXE 和 service/core 在大规模 workspace 下的内存模型。当前不实现 GUI、不打包 EXE；该文档用于约束未来实现，避免 10K/100K 文档规模下出现启动慢、搜索卡顿或内存无界增长。

## Startup memory

启动阶段只加载必要元数据，并通过 `WorkspaceStatusService` / `IndexMetadataService` 读取：

- workspace 配置。
- index 状态。
- 统计摘要。
- 最近任务摘要。
- 最近错误摘要。

启动阶段不得预加载全部 Markdown，不得自动全量扫描 `knowledge/`，不得为了判断 stale 而读取每篇正文，不得计算 hash，不得触发 index/reindex。index missing/stale 只产生状态提示和后台任务入口。App startup != first index；first index 是后台任务，不属于 startup memory budget。

`workspace-status` 的内存预算只允许 SQLite metadata、workspace config/cache 和小型计数字典常驻结果对象。它不得保存 10K/100K 文件路径列表，也不得把 Markdown 正文放入内存。

## Search memory

搜索只依赖 SQLite FTS5 / 索引：

- 输入 query/filter/top_k/page。
- 输出有限数量的 chunk 结果和元数据。
- snippet 来自索引 chunk。
- 不读取 Markdown 全文。
- 不缓存全量命中集合。
- 不把所有结果一次性交给 GUI。

搜索缓存可以使用 LRU / TTL，但必须有上限。缓存键应包含 query、filter、top_k、page token 和 search mode，避免不同层级策略互相污染。

## Document open memory

完整 Markdown 只在用户明确 open 单篇文档时读取：

- 打开时读取单篇。
- 关闭后释放大正文引用。
- 最近打开缓存必须有文档数和字节上限。
- 大文件应按需流式读取或分块渲染。
- 编辑或预览模式不得把整个 workspace 的正文载入内存。

单篇 open 可以返回 frontmatter、body、path、size、mtime 等结构化结果，但不应顺带返回邻近目录的全文内容。

## Task memory

长任务包括 index、reindex、audit、secret-scan、dedupe、conflicts、benchmark、maintenance、backup/export 和 Optional Git Sync。任务内存规则：

- 任务在后台 worker 执行。
- UI 主线程只接收 progress event 和 result summary。
- 任务日志写文件，内存中只保留尾部窗口。
- 任务完成后释放 DB connection、文件句柄、批次列表和大对象。
- 失败详情写入 log path，UI 只展示摘要。
- checkpoint/resume 保存结构化状态，不保存全文。

索引任务应按批处理文件。每个批次结束后提交事务并释放该批次中的正文、chunk 和失败临时对象。

## Cache policy

所有缓存必须同时定义：

- 用途。
- key。
- max entries。
- max bytes。
- TTL。
- invalidation 条件。

建议缓存：

- stats cache：短 TTL，用于 dashboard 高频刷新。
- index status cache：短 TTL，用于启动和任务状态展示。
- search result page cache：短 TTL，只缓存有限页结果。
- opened document cache：LRU，按文档数和总字节限制。
- config cache：配置文件 mtime 变化时失效。

禁止无上限缓存 Markdown 正文、完整搜索命中、大型报告、完整任务日志和 100K 文件路径列表。

## Log and report retention

日志和报告必须从一开始就有保留策略：

- task log 写入 log path，不常驻内存。
- UI 只读取最近 N 行或最近 N KB。
- 大型报告归档到 `reports/` 或未来 AppData task logs。
- report list 使用分页和摘要。
- log rotation 必须限制总大小和保留时间。
- 维护命令默认不删除历史报告，清理必须显式触发。

长期运行的 GUI 不应因为日志视图打开而持续累积内存。

## GUI virtual list

未来 GUI 的大列表必须虚拟化：

- 搜索结果。
- 文档列表。
- review queue。
- audit issues。
- stale/conflict/dedupe 结果。
- task logs。
- source list。

service 返回分页数据；GUI 只渲染可见窗口和少量 overscan。排序、筛选和分页应下推到 service/SQLite，不应在前端持有全量列表后再处理。

## Large document handling

大文件处理策略：

- hash 使用分块读取。
- index 读取后立即 chunk，批次结束释放正文。
- open 大文件时可只返回 frontmatter 和首屏摘要，按需加载后续内容。
- preview 使用分块渲染。
- 超大 raw 文档应提示拆分或归档。
- failed large documents 记录 last_error，不阻断整个批次。

任何单篇大文件都不应导致全局索引任务或 GUI 主线程失控。

## Memory anti-patterns

明确禁止：

- preload all Markdown。
- render all search results。
- keep all task logs in memory。
- hold DB connections forever in UI。
- keep large raw documents in memory after close。
- 在启动时扫描并读取完整 `knowledge/`。
- 在启动时调用 index、doctor、audit 或 secret-scan。
- 在 UI 主线程运行 index/audit/secret-scan/reindex。
- 把 10W 文件路径、10W 搜索结果或完整 audit issue 一次性交给渲染层。
- 通过全局变量长期保存完整 workspace 状态。
- 用无限增长的 list 收集所有进度事件。

## Acceptance checks

未来涉及 10K/100K 的改动必须说明：

- 是否会在启动时扫描文件系统。
- 是否会读取 Markdown 全文。
- search 是否仍只读索引。
- 是否有 Top-K、分页或虚拟滚动。
- 是否有缓存上限。
- 长任务是否后台化。
- 任务完成后是否释放资源。
- 失败时是否保留可恢复状态和日志路径。
