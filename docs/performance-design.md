# Performance Design

这个知识库采用 Markdown 源数据 + SQLite FTS5 索引层。目标是长期保存开发知识，同时避免搜索时读取整个 `knowledge/` 目录。

## 为什么不能每次全量读取 Markdown

全量读取会随着文件数量和大文件增长线性变慢，并且会把大量无关正文加载进内存。对 Codex/Agent 来说，这还会带来上下文污染：搜索一个问题时不应把所有 raw、distilled 和 deprecated 内容都暴露给决策过程。

## 架构

- Markdown 是事实来源，保存在 `knowledge/<category>/<layer>/`。
- SQLite 是索引层，保存在 `.kb/index.sqlite`。
- `documents` 表保存路径、分类、层级、状态、来源、时间戳和校验信息。
- `chunks` 表保存按标题层级拆分后的正文片段。
- `chunks_fts` 是 FTS5 虚拟表，用于全文检索 title、heading、content。

SQLite 可以删除重建；Markdown 文件不能被索引层替代。

## 增量索引如何工作

`index` 命令会遍历 `knowledge/` 查找 Markdown 文件，但只在索引阶段执行。它用相对路径和索引中已有记录对比：

- 新文件：解析 frontmatter、切 chunk、写入 document/chunks/FTS。
- 修改文件：只删除并重建该文件对应的 document/chunks/FTS。
- 未变化文件：如果 path、mtime、size 都未变化，直接跳过，不计算 sha256。
- 已删除文件：从 document/chunks/FTS 中删除。

`search`、`list`、`weekly-report` 不触发全量 reindex，也不会自动回退到慢扫描。

## sha256、mtime、size 判断变更

索引记录同时保存：

- `mtime`: 文件修改时间，用于快速判断。
- `size`: 文件大小，用于快速排除未变化文件。
- `sha256`: 内容校验，用于避免仅时间戳变化造成误判。

增量索引先比较 `path + mtime + size`。如果三者未变化，直接 `skipped`，不会读取文件计算 sha256。只有新文件、mtime/size 变化的文件，或用户显式传 `--force-hash` 时，才计算 sha256。`index` 输出 `hashed`，用于观察本次实际做了多少内容校验。

## chunk 切分

chunk 优先按 Markdown 标题层级切分。每个 section 记录最近标题作为 `heading`。如果 section 超过推荐长度，会再按字符数切分，目标范围为 800 到 1500 字符。这样搜索返回的是命中片段，而不是整篇文档。

## 为什么 search 只返回 Top-K chunk

检索目标是找到最相关的可行动知识。默认 Top-K 为 10，避免输出过多低相关片段。Top-K 最大为 50，除非显式使用 `--force`。搜索结果只包含 snippet 和元数据，完整正文必须用 `open` 单篇读取。

## list 和 weekly-report 为什么基于元数据

列表和周报主要回答“有什么、在哪、状态如何”，不需要正文。它们读取 `documents` 元数据表，避免把整个知识库加载进内存。

## open 为什么才读取完整文件

完整 Markdown 只在用户明确指定 `open --path` 或 `open --id` 时读取。推荐流程是先 `search`，再 `open` 少量命中文档。

## 如何防止卡顿

- 查询默认走 FTS5。
- 搜索不遍历文件系统。
- 输出限制 Top-K。
- snippet 默认截断到 500 字符。
- 增量索引只更新变化文件。
- SQLite 使用 WAL、NORMAL synchronous 和外键约束。

## 数据量增长后的扩展方向

- 为 `documents` 元数据字段增加普通索引。
- 增加向量索引作为 FTS5 的二阶段 rerank，而不是替代事实来源。
- 增加 RSS/GitHub Releases 的受控采集，但采集结果必须进入 raw。
- 增加 MCP 或 Codex Skill，让 Agent 只能通过 CLI 查询索引。
- 对超大 Markdown 采用更细粒度流式解析。
