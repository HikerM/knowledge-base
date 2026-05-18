# Search Design

搜索默认使用 SQLite FTS5。除非显式使用 `--slow-scan`，否则不允许回退到全量文件扫描。

## FTS5 检索流程

1. CLI 接收 `--query` 和过滤条件。
2. 检查 `.kb/index.sqlite` 是否存在。
3. 检查 SQLite 是否支持 FTS5。
4. 使用 `chunks_fts MATCH ?` 查询命中 chunk。
5. join `chunks` 和 `documents` 获取元数据。
6. 计算综合 score。
7. 返回 Top-K 片段和 elapsed_ms。

搜索只返回命中 chunk，不返回整篇文档。

## 元数据过滤

支持以下强过滤：

- `--category`
- `--layer`
- `--type`
- `--status`
- `--confidence`
- `--source-type`

如果用户指定 category 或 layer，必须作为 SQL WHERE 条件过滤，而不是仅作为权重。

## 权重策略

基础相关性来自 FTS5 BM25。综合分数再考虑：

- title 命中高于 heading 命中。
- heading 命中高于 content 命中。
- layer: rules > checklists > snippets > distilled > raw > deprecated。
- status: active > experimental > deprecated。
- source_type: official > github > paper > blog > forum > video > unknown。
- confidence: high > medium > low。
- last_reviewed 越新优先级越高。

V1 的 score 是可解释的启发式排序，不声称等价于机器学习排序。

## 默认正式层搜索

`search` 默认只返回 `rules`、`checklists`、`snippets`。`raw`、`distilled`、`deprecated` 不会因为正式层无结果而自动回退返回。

探索 raw/distilled 应使用：

```bash
python scripts/kb.py research --query "topic"
```

或在 `search` 中显式添加 `--include-raw`、`--include-distilled`、`--include-deprecated`。

## deprecated 默认排除

默认不返回 deprecated layer 或 status。只有传入 `--include-deprecated` 时才返回。deprecated 内容必须带有替代说明，尤其是正式规则被废弃时应标注 `superseded_by`。

## raw 低权重策略

raw 是原始资料，不是正式规则。默认 search 不返回 raw；research 可以检索 raw，但会明确标注未经审核。Codex/Agent 不得把 raw 当作项目指导。

## snippet 生成策略

结果 snippet 来自命中 chunk。默认最多 500 字符，优先围绕 query 命中位置截取；如果无法定位命中词，则截取 chunk 开头。

## 精准度限制与后续向量检索

FTS5 擅长关键词、短语和术语匹配，但对语义近义词、跨语言概念和隐含关系有限。后续可以增加向量检索：

- Markdown 仍是事实来源。
- SQLite FTS5 仍是默认检索入口。
- 向量检索作为可选 rerank 或补充召回。
- 任何 RAG 输出仍必须标注来源路径和 layer。
