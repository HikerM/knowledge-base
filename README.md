# personal-knowledge-base

`personal-knowledge-base` 是 Markdown-first 的本地个人开发知识库，用来长期沉淀前端、后端、UI/UX、产品、算法、数据库、性能、安全、AI Agent 等领域的工程知识。

Markdown 是事实来源；SQLite + FTS5 是本地索引层。搜索默认只查索引，不全量读取 Markdown，也不在 `knowledge/` 中做字符串扫描。

## 代码结构

- `scripts/kb.py`: CLI 入口，保留命令解析、命令处理和索引/搜索/治理流程。
- `knowledge_core/paths.py`: 仓库路径、生命周期层目录和路径解析工具。
- `knowledge_core/config.py`: categories、sources、learning-radar、extract-rules 配置加载。
- `knowledge_core/frontmatter.py`: frontmatter 解析、渲染和 schema 枚举。
- `knowledge_core/security.py`: secret-scan 的扫描规则、路径排除和脱敏逻辑。

## 目录结构

每个 category 都有完整生命周期层级：

- `raw`: 原始摘录，只能参考。
- `distilled`: AI 或人工提炼层，仍需人工审核。
- `rules`: 人工审核后的正式规则。
- `snippets`: 可复用代码、命令、配置或提示词。
- `checklists`: 检查清单和验收流程。
- `deprecated`: 过期或被替代知识，保留历史。
- `rejected`: 明确拒绝的知识，保留原因和历史。
- `quarantine`: 来源不明、质量低、无法验证或疑似污染的隔离区。

Codex/Agent 默认只信任 `rules`、`checklists`、`snippets`。

## 数据质量治理

所有知识卡片 frontmatter 支持：

```yaml
title: ""
category: ""
type: rule
status: active | experimental | deprecated | rejected
confidence: high | medium | low
source_type: official | github | paper | blog | forum | video | internal_practice | unknown
source_url: ""
created_at: ""
last_reviewed: ""
reviewed_by: ""
valid_for: []
not_valid_for: []
project_scope: ""
supersedes: []
superseded_by: ""
risk_level: low | medium | high
verification_method: ""
review_required: true | false
```

`lint` 检查 schema、必填字段、枚举、来源、审核信息和 deprecated 记录。`audit` 输出全库质量报告，包括缺少来源、缺少审核、过期、低置信正式规则、unknown source、重复标题和可能冲突规则。

## 知识治理闭环

本知识库的目标流程是：

```text
外部内容
  ↓
raw：只收集，不信任
  ↓
distilled：AI 提炼，仍需审核
  ↓
review-queue：待人工审核
  ↓
promote：人工确认
  ↓
rules / snippets / checklists：正式知识
  ↓
search：默认只查正式知识
  ↓
项目使用
  ↓
实践验证
  ↓
audit / stale / conflicts / deprecate
  ↓
更新、废弃、修正
```

这个闭环用于保证：错误不会轻易进入正式规则层，未经审核内容不会默认影响项目，过期内容会被发现，冲突规则会被检测，来源不明内容会被隔离，Codex 不会全量读取和盲目信任。

## 防污染机制

- `search` 默认只返回 `rules`、`checklists`、`snippets`。
- `raw`、`distilled`、`deprecated` 必须显式 `--include-raw`、`--include-distilled`、`--include-deprecated` 才能进入 search。
- `research` 专门用于学习探索 raw/distilled，并会标注“未经审核，不能作为正式项目规则”。
- `review_required=true` 的内容不得作为正式决策依据。
- `quarantine` 用来隔离来源不明、质量低或疑似污染的内容。

## 常用流程

初始化：

```bash
python scripts/kb.py init
```

添加原始资料：

```bash
python scripts/kb.py add-raw --category frontend --title "React notes" --source-url "https://react.dev" --text "摘录内容"
```

## 学习源与分类知识雷达

学习源配置在 [config/sources.yaml](D:/AI/personal-knowledge-base/config/sources.yaml)。每个 source 支持：

- `name`
- `category`
- `type`: `manual`、`rss`、`github_releases`、`github_repo`、`official_docs`
- `url`
- `priority`
- `enabled`
- `learn_focus`
- `output_targets`
- `notes`

分类学习雷达配置在 [config/learning-radar.yaml](D:/AI/personal-knowledge-base/config/learning-radar.yaml)，用于定义每个类别的学习目标、频率、重点关注内容、忽略内容和偏好的输出类型。

查看学习源：

```bash
python scripts/kb.py sources
python scripts/kb.py sources --category frontend --enabled-only
```

生成学习队列：

```bash
python scripts/kb.py learning-queue
```

该命令只基于配置生成 `reports/learning-queue-YYYY-MM-DD.md`，不会抓取全文，不会创建 raw，也不会写入 rules。

## 从 raw 生成提炼计划

提炼规则配置在 [config/extract-rules.yaml](D:/AI/personal-knowledge-base/config/extract-rules.yaml)。它规定 `changelog`、`best_practice`、`pitfall`、`snippet`、`checklist`、`case`、`adr` 的必填字段，确保 AI 输出的是可执行知识，而不是普通摘要。

```bash
python scripts/kb.py distill-plan --path knowledge/09-ai-agent/raw/example.md
```

`distill-plan` 只读取指定单篇 raw 文件，只输出建议提炼成 `rule`、`pitfall`、`checklist`、`snippet` 或 `changelog` 的计划。它不写入 rules，提炼结果仍需进入 distilled 并等待人工审核。

创建待审核卡片：

```bash
python scripts/kb.py new-card --category backend --type rule --title "API error handling" --status experimental
```

人工审核并 promote：

```bash
python scripts/kb.py promote \
  --path knowledge/02-backend/distilled/api-error-handling.md \
  --target-layer rules \
  --reviewed-by "me" \
  --confidence high \
  --valid-for "python-api,production" \
  --verification-method "unit tests and production review" \
  --review-note "来源和适用范围已人工确认"
```

promote 会设置 `status=active`、`review_required=false`、`reviewed_at`、`promoted_from`，并保留 `source_url`。

### promote 来源门禁

promote 到 `rules`、`snippets`、`checklists` 时默认必须有 `source_url`。唯一例外是 `source_type=internal_practice`，用于来自本人项目实践、事故复盘、代码审查结论或本地 benchmark 的知识。

`internal_practice` 合法使用条件：

- 必须提供 `reviewed_by`
- 必须提供 `confidence`
- 必须提供 `valid_for`
- 必须提供 `verification_method`
- 必须提供 `review_note`
- 必须能说明实践证据，例如测试、复盘、benchmark、生产问题或人工审查

如果 `source_url` 为空且 `source_type` 不是 `internal_practice`，promote 会拒绝。

建立或刷新索引：

```bash
python scripts/kb.py index
python scripts/kb.py index --force-hash
python scripts/kb.py reindex
```

`index` 会先比较 `path + mtime + size`。未变化文件直接 skipped，不计算 sha256；只有新文件、mtime/size 变化文件或显式 `--force-hash` 时才计算 sha256。输出中的 `hashed` 表示本次实际计算 sha256 的文件数。

正式搜索：

```bash
python scripts/kb.py search --query "sql injection" --category security --top-k 10
```

探索未审核内容：

```bash
python scripts/kb.py research --query "agent workflow" --category ai_agent
```

打开单篇文档：

```bash
python scripts/kb.py open --id 1
python scripts/kb.py open --path knowledge/01-frontend/rules/example.md
```

## 质量命令

```bash
python scripts/kb.py lint
python scripts/kb.py audit
python scripts/kb.py review-queue
python scripts/kb.py stale --days 180
python scripts/kb.py conflicts
python scripts/kb.py dedupe
```

`review-queue` 会列出 distilled 中 high/medium confidence、权威来源、近期高优先级 raw 和 `review_required=true` 的内容。

分类摘要：

```bash
python scripts/kb.py digest
```

`digest` 基于 SQLite 索引元数据生成 `reports/category-digest-YYYY-MM-DD.md`，不全量读取正文。

## Smoke Test

项目提供标准库 smoke test，使用临时目录复制项目运行，不污染真实 `knowledge/`：

```bash
python tests/smoke_test.py
```

覆盖内容包括：`init`、`add-raw`、`index`、默认 search 不返回 raw、promote 来源门禁、`internal_practice` promote、promote 后 search、单文件 open、`stats`、`doctor`、`benchmark`。

大型性能 smoke 不进入默认 CI，需要本地手动运行：

```bash
python tests/perf_10k_smoke.py
```

`perf_10k_smoke.py` 会在临时目录复制项目并生成 10,000 个 Markdown 文档，覆盖 `raw`、`distilled`、`rules`、`checklists`、`snippets`、`deprecated`，然后运行首次 `index`、第二次 `index`、`search` 和 `stats`。它输出 `document_count`、`chunk_count`、`first_index_elapsed_ms`、`second_index_elapsed_ms`、`search_elapsed_ms`、`skipped`、`hashed` 和 `index_size_bytes`。第二次 `index` 应接近全量 skipped，`hashed` 应为 0 或接近 0。

## CI 与自动验收

GitHub Actions 配置在 [.github/workflows/ci.yml](D:/AI/personal-knowledge-base/.github/workflows/ci.yml)。每次 `push` 和 `pull_request` 都会运行：

```bash
python scripts/kb.py --help
python scripts/kb.py init
python scripts/kb.py index
python scripts/kb.py stats
python scripts/kb.py doctor
python scripts/kb.py benchmark
python scripts/kb.py audit
python tests/smoke_test.py
python tests/search_quality_test.py
python tests/search_explain_test.py
python tests/perf_smoke.py
python tests/governance_test.py
python scripts/kb.py secret-scan
```

CI 会在 GitHub public repo 环境中重建本地索引，但 `.kb/index.sqlite` 仍然是生成物，不应提交。

## Secret Scan

公开仓库发布前必须运行：

```bash
python scripts/kb.py secret-scan
```

`secret-scan` 默认排除 `.git/`、`.kb/`、`__pycache__/`、`.venv/`、`tmp/`、`exports/`，并检查 API key、GitHub token、OpenAI key、`password=`、`secret=`、private key block、bearer token 和 `.env` 泄露。发现高风险 secret 时命令返回非 0。测试 fixture 如需包含假值，必须在同一行写明 `TEST_ONLY_SECRET_PATTERN`。

公开仓库安全规则见 [docs/security-public-repo.md](D:/AI/personal-knowledge-base/docs/security-public-repo.md)。

## Search Quality Test

检索质量测试使用 [tests/benchmark_corpus](D:/AI/personal-knowledge-base/tests/benchmark_corpus) 中的可控 Markdown fixture，在临时目录复制项目并建立索引：

```bash
python tests/search_quality_test.py
```

覆盖内容包括：正式层可检索、默认不返回 raw、默认不返回 deprecated、category filter、layer filter、主题相关结果排序，以及自定义 benchmark query 的稳定断言。

需要审计搜索排序时，可以显式使用：

```bash
python scripts/kb.py search --query "react state" --explain-score
```

默认 search 不输出 score 拆解，以保持常规 JSON 精简和兼容。`--explain-score` 会在每条结果中额外输出 `score_breakdown`，用于查看 BM25、title/heading/content 命中加权、layer/status/source_type/confidence 权重和最终分数；它只用于审计和调参，不改变默认排序和正式层过滤策略。

大样本性能 smoke test 会在临时目录生成 1,000 个 Markdown 文档，验证首次索引、第二次增量 skip、默认搜索走索引、`stats` 和 `doctor` 在较大样本下完成：

```bash
python tests/perf_smoke.py
```

## stale 复查流程

默认 180 天未复查视为 stale。单个文件可通过 `review_cycle_days` 覆盖默认周期。

```bash
python scripts/kb.py stale --days 180
```

复查后更新 `last_reviewed`、`reviewed_by`、`verification_method` 和必要的 `review_note`。

## deprecated / rejected / quarantine

- `deprecated`: 曾经有效，但已经过期或被替代。必须记录 `deprecation_reason` 或 `superseded_by`。
- `rejected`: 审核后明确不采用。保留历史，避免重复引入。
- `quarantine`: 暂时隔离，原因可能是来源不明、低质量、无法验证、AI 摘要可疑或疑似污染。

废弃规则：

```bash
python scripts/kb.py deprecate --path knowledge/01-frontend/rules/old.md --reason "React 版本变化" --superseded-by "new-rule.md" --reviewed-by "me"
```

隔离内容：

```bash
python scripts/kb.py quarantine --path knowledge/01-frontend/raw/unknown.md --reason "来源不明且无法验证"
```

## 长期数据治理

新增治理字段：

- `topic_id`: 同一主题的稳定标识，例如 `ai_agent.codex-sandboxing`。
- `canonical_id`: 主题下推荐采用的 canonical 文件标识，例如 `ai_agent.codex-sandboxing.rule`。
- `source_hash`: 来源 URL 的稳定 hash，用于来源重复治理。
- `content_hash`: 正文规范化后的 hash，用于内容重复治理。
- `deprecated_reason` / `rejected_reason` / `quarantined_reason`: 历史状态原因。
- `review_cycle_days`: 单条知识的复查周期。

重复检查：

```bash
python scripts/kb.py dedupe
```

`dedupe` 会检查 `source_url`、归一化标题、`content_hash`、`category + topic_id` 重复，并给出 recommended canonical file 和 suggested action。

冲突检查：

```bash
python scripts/kb.py conflicts
```

`conflicts` 会检查同一 `topic_id` 下多个 active rules、失效的 `superseded_by`、active 规则 supersedes 的旧规则仍 active，以及适用范围重叠但结论疑似相反的规则。输出包含 evidence，结论仍需人工判断。

主题 canonical 报告：

```bash
python scripts/kb.py canonical-report
```

该报告按 `topic_id` 输出 canonical rule、canonical checklist、active/deprecated/raw supporting files、未解决重复和未解决冲突。

月度维护：

```bash
python scripts/kb.py monthly-maintenance
```

它会运行 `index`、`lint`、`audit`、`dedupe`、`conflicts`、`stale`、`secret-scan`，并生成 `reports/monthly-maintenance-YYYY-MM.md`。

不要直接删除旧知识。对于被替代、过期或错误的正式规则，使用 `deprecate`、`rejected` 或 `quarantine` 保留历史原因，这样 Codex/Agent 能理解规则演进并避免重复引入旧问题。

更完整的治理流程见 [docs/data-governance.md](D:/AI/personal-knowledge-base/docs/data-governance.md)。

## Long-term Operations

长期运维不只管理知识内容，还管理数据质量、搜索性能、索引性能、内存占用、SQLite 并发、日志归档、备份恢复、schema migration、release/tag 和未来 EXE/GUI 常驻运行边界。

长期运维设计见 [docs/long-term-operations.md](D:/AI/personal-knowledge-base/docs/long-term-operations.md)。未来桌面软件化设计见 [docs/desktop-app-readiness.md](D:/AI/personal-knowledge-base/docs/desktop-app-readiness.md)。

## Maintenance workflow

`monthly-maintenance` 保持现有月度治理快照，不破坏历史行为：

```bash
python scripts/kb.py monthly-maintenance
```

`maintenance` 是更面向长期运维的安全包装，默认只检查和生成报告，不删除、不 promote、不修改 raw/distilled/rules：

```bash
python scripts/kb.py maintenance
```

报告写入：

```text
reports/maintenance/YYYY-MM-maintenance.md
```

如需压缩 SQLite 索引，必须显式开启：

```bash
python scripts/kb.py maintenance --vacuum
```

`--vacuum` 只作用于 `.kb/index.sqlite`，不修改 Markdown 源数据。日常维护不应默认运行 vacuum。

## Memory and performance principles

- 启动时不加载全部 Markdown。
- `search` 默认只走 SQLite FTS5，不全量扫描 `knowledge/`。
- 搜索只返回 Top-K chunk 和元数据。
- `open` 才读取完整单篇文档。
- 大列表必须分页，未来 GUI 必须使用分页或虚拟滚动。
- 缓存必须有上限，不能无限保存全文。
- 后台任务完成后释放文件句柄、DB connection 和大型结果对象。
- 报告和日志要归档或轮转，大型报告按需读取。

`index` 使用 `path + mtime + size` 优先判断文件是否变化。未变化文件直接 skipped；只有新文件、mtime/size 变化或显式 `--force-hash` 时才计算 sha256。

## Large-scale mode

大规模设计见 [docs/large-scale-performance.md](D:/AI/personal-knowledge-base/docs/large-scale-performance.md)，内存模型见 [docs/memory-model.md](D:/AI/personal-knowledge-base/docs/memory-model.md)。

规模目标：

- 10,000 docs：应流畅，启动不加载全文，搜索目标 < 300ms，第二次 index 目标 < 5s，UI 不阻塞。
- 30,000 - 50,000 docs：优化后可稳定使用，需要更严格的批处理、后台任务、分页和内存上限。
- 100,000+ docs：进入 large-scale mode，需要后台索引、分层优先、checkpoint/resume 和 workspace 分片。

首次全量 `index` 可能较久，因为它必须读取 Markdown、解析 frontmatter、切 chunk、写入 `documents/chunks/chunks_fts`。这可以接受，但必须后台执行。软件启动不能等待首次全量 `index`，只能读取 workspace 配置、index 状态、统计信息和最近任务状态；index missing/stale 时只提示，不阻塞 UI。

日常使用依赖增量 `index`。未变化文件通过 `path + mtime + size` 直接 skipped，不计算 sha256；只有新文件、mtime/size 变化文件或显式 `--force-hash` 才 hash。搜索仍只查 SQLite FTS5 / 索引，不读取 Markdown 全文；点击结果或 `open` 单篇时才读取完整 Markdown。

未来 GUI 必须使用虚拟滚动、分页、lazy document loading、background workers、progress events、task cancellation、task logs、search debounce、filter chips 和 incremental result loading。GUI 不得一次渲染所有搜索结果，不得在 UI 主线程运行 index、audit、secret-scan、reindex、dedupe、conflicts、benchmark 或 maintenance。

100K+ 建议 workspace 分片，而不是把所有历史资料塞进单一活跃 workspace：active / archive 分离、raw archive 分离、每个 workspace 独立 `.kb/index.sqlite`。跨 workspace search 可作为未来增强，不作为 100K 首版前提。

## EXE / Desktop app future direction

未来 Windows EXE / GUI 的正确架构是：

```text
Desktop GUI
  ↓
Service Layer
  ↓
knowledge_core
  ↓
Markdown + SQLite + Git
```

GUI 不应直接读写 Markdown 或 SQLite，也不应通过拼接 CLI 命令字符串作为主要集成方式。CLI 继续保留给 CI、自动化、调试和高级用户；GUI 应调用 service/core API。

长期任务必须后台化，包括 index、reindex、audit、secret-scan、dedupe、conflicts、benchmark、maintenance、Git sync、backup/export 和 learning queue generation。任务需要 task_id、status、progress、cancellation、retry、error detail、log path 和 result summary。

当前不做 GUI、不做 EXE 打包、不做 Tauri/Electron/PySide/WinUI 选型。未来路线建议：

- 界面质量和长期扩展优先：Tauri + React。
- 开发速度优先：Electron + React。
- 最大化复用 Python 优先：PySide6。
- Windows 原生生态优先：WinUI/.NET。

## Backup / restore principles

主要资产是：

- `knowledge/`
- `config/`
- `templates/`
- `reports/`
- `docs/`
- `README.md`
- `AGENTS.md`
- Git commit、branch、tag

`.kb/index.sqlite` 是可重建索引，不作为核心备份。恢复流程优先依赖 Git：

```bash
git log --oneline --decorate
git checkout <tag-or-commit>
python scripts/kb.py index
python scripts/kb.py doctor
```

如索引损坏，可删除 `.kb` 后重建：

```powershell
Remove-Item -Recurse -Force .kb
python scripts/kb.py index
python scripts/kb.py doctor
```

公开仓库不得包含真实 secret、客户隐私数据或私有业务数据。发布前必须运行：

```bash
python scripts/kb.py secret-scan
```

## Why Markdown remains the source of truth

Markdown 保持为事实来源，因为它可读、可 diff、可 review、可 Git 回滚，也能长期跨工具保存。知识治理所需的来源、状态、confidence、review、valid_for、verification_method 和生命周期历史都必须保存在 Markdown/frontmatter 中。

SQLite 不能替代 Markdown。SQLite 只是为了检索、统计和治理报告服务的索引层。

## Why SQLite index is rebuildable

`.kb/index.sqlite` 保存的是从 Markdown 解析出的索引、chunk、FTS5 和元数据快照。它可以删除后通过 `python scripts/kb.py index` 重建。

这条边界让系统在索引损坏、schema migration、性能调优或未来 GUI 崩溃后仍可恢复：保护 Markdown 源数据优先，索引失败可重建。

## Recommended maintenance frequency

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

## 性能保证

- `search` 默认走 SQLite FTS5，不全量读取 Markdown。
- `search` 不全量扫描 `knowledge/`。
- `list`、`audit`、`review-queue`、`stale` 尽量基于索引元数据。
- `open` 才读取完整单篇 Markdown。
- 搜索只返回命中 chunk，不返回整篇文档。
- 默认 Top-K 为 10，超过 50 需要 `--force`。
- 增量索引用 `path + mtime + size + sha256` 判断变化。

## 后续扩展方向

- RSS 和 GitHub Releases 受控采集，结果先进入 raw。
- 自动摘要和人工审核队列。
- 向量检索作为 FTS5 补充召回或 rerank。
- RAG 查询接口。
- MCP Server。
- Codex Skill，让 Agent 通过受控工具读取知识库。

## 自动学习的边界

- V1 不做不可控全网爬虫。
- `learning-queue` 只生成待学习任务，不抓取正文。
- 外部内容必须先进入 raw。
- AI 只能帮助从 raw 提炼到 distilled。
- 未经人工审核的内容不能进入 rules、snippets、checklists。
- `search` 默认只查正式知识，项目使用不能依赖 learning queue 或 raw/research 结果。
