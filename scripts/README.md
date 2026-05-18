# Scripts

`kb.py` 是本地知识库 CLI，负责初始化、创建知识卡片、增量索引、FTS5 搜索、打开单篇文档、生成统计和周报。

## 性能约束

- `search` 只查询 SQLite FTS5，不读取所有 Markdown。
- `list` 和 `weekly-report` 只读索引元数据。
- `open` 才读取完整 Markdown。
- `index` 支持增量更新，通过 path、mtime、size、sha256 判断变更。
- `reindex` 才会删除旧索引并全量重建。

## 常用命令

```bash
python scripts/kb.py init
python scripts/kb.py add-raw --category frontend --title "React memo notes" --source-url "https://react.dev" --text "..."
python scripts/kb.py new-card --category backend --type rule --title "API error handling" --status experimental
python scripts/kb.py promote --path knowledge/02-backend/distilled/api-error-handling.md --target-layer rules
python scripts/kb.py index
python scripts/kb.py search --query "error handling" --category backend
python scripts/kb.py research --query "agent workflow" --category ai_agent
python scripts/kb.py sources --enabled-only
python scripts/kb.py learning-queue
python scripts/kb.py distill-plan --path knowledge/09-ai-agent/raw/example.md
python scripts/kb.py digest
python tests/smoke_test.py
python scripts/kb.py lint
python scripts/kb.py audit
python scripts/kb.py review-queue
python scripts/kb.py stale --days 180
python scripts/kb.py conflicts
python scripts/kb.py dedupe
python scripts/kb.py deprecate --path knowledge/01-frontend/rules/old.md --reason "过期" --reviewed-by me
python scripts/kb.py quarantine --path knowledge/01-frontend/raw/suspicious.md --reason "来源不明"
python scripts/kb.py open --id 1
python scripts/kb.py weekly-report
```
