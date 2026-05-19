# personal-knowledge-base

`personal-knowledge-base` 是 Markdown-first 的本地个人开发知识库，用来长期沉淀前端、后端、UI/UX、产品、算法、数据库、性能、安全、AI Agent 等领域的工程知识。

Markdown 是事实来源；SQLite + FTS5 是本地索引层和未来 GUI / EXE 的 runtime hot index。搜索默认只查索引，不全量读取 Markdown，也不在 `knowledge/` 中做字符串扫描。

SQLite-hot / Markdown-source runtime model：

- App startup、Dashboard、Category View、Search View、Review Queue、Archive / Trash View 默认只读取 SQLite metadata / FTS index。
- App startup 不扫描 `knowledge/`，不读取所有 Markdown，不自动触发 index。
- Dashboard 只读 workspace status、index status、cached stats 和最近任务摘要。
- Category View 从 SQLite `documents` metadata 聚合统计和分页查询。
- Search View 从 SQLite FTS5 查询，并用 `documents` metadata 做 layer/status/category/source_type/confidence hard filter。
- Review Queue 从 SQLite metadata 查询；Archive / Trash / Quarantine 页面从 SQLite metadata 分页查询。
- `workspace-status` 必须是轻量命令，只读 SQLite/config/cache，不读 Markdown，不 hash，不 index。
- Markdown 只作为 source of truth；只有 `open` / `edit` / `index` / `reindex` / `doctor` / `promote` / `archive` / `restore` / `backup` 等明确操作才读取 Markdown。
- `.kb/index.sqlite` 缺失时只显示 `index_status=missing`，并提示用户后台构建索引；不得在 App startup 自动构建索引。

启动状态检查：

```bash
python scripts/kb.py workspace-status
```

`workspace-status` 是未来 Windows EXE / GUI 的稳定启动路径。CLI 只调用 `WorkspaceStatusService`；未来 GUI 也应调用同一 service，而不是拼接 CLI 命令字符串。该路径只读 SQLite metadata / workspace status，不扫描 `knowledge/`，不读取 Markdown，不计算 hash，不运行 index。App startup != first index；first index 必须是用户显式触发的后台任务。

Service-layer read paths：

- Dashboard / startup：`WorkspaceStatusService` + `IndexMetadataService`。
- Search View：`SearchService`，复用现有 SQLite FTS5 search 行为，不启用 slow scan。
- Category View：`CategoryService`，读取 `config/categories.yaml` 和 SQLite `documents` metadata。
- Review Queue：`ReviewQueueService`，分页读取 SQLite metadata。
- Archive / Trash / Quarantine View：`ArchiveMetadataService`，分页读取 archive/deprecated/quarantine metadata。
- Document Open：`DocumentService.open_document` 是正文读取入口，只能读取用户明确打开的单篇 Markdown。

CLI 仍然是自动化、调试和验收入口，例如 `search-service`、`category-summary`、`review-queue-list`、`archive-list`、`document-open`。未来 GUI / EXE 必须直接调用 service layer，不能拼接 CLI 命令字符串作为集成方式。

Plan-only mutation services：

- 所有会修改 Markdown、config、workspace、category、template 的操作必须 plan-first。
- v1.5.0 起点阶段只提供 `CategoryPlanService`、`TemplatePlanService`、`WorkspacePlanService` 和对应 CLI wrappers；它们只生成 JSON plan，不执行写操作。
- plan-only services 固定 `dry_run=true`、`would_modify=false`；`blocked` 只表示未来执行被阻塞，blocked plan 仍是可消费的 JSON 输出。
- `actions` 是计划动作，不是已执行动作；`validation_commands` 必须始终存在，供未来 GUI 直接展示和执行前确认。
- v1.8.0 起点阶段建立 Safe Execute Mutation Framework：所有真实 execute mutation 必须经过 plan + local snapshot + approval + TaskQueue。
- v1.8.0 只允许一个最低风险执行动作：`category_update_display_name_execute`，并且只能修改 `config/categories.yaml` 中的 `display_name`，不得 path rename，不得改 Markdown，不得改 SQLite schema。
- v1.8.1 新增第二个低风险 config-only 执行动作：`category_update_description_execute`，并且只能修改 `config/categories.yaml` 中的 `description`。空 description 必须通过 `--allow-empty-description` 明确表示 intentional clear。
- category identity/path mutation 仍禁止：不得修改 `category_id`、`path`、slug 或由显示字段触发目录迁移。
- archive、delete、merge、template apply、restore 的真实执行仍是 future work；对应命令只允许 plan 或 unsupported，不得移动文件、删除文件或改写 Markdown。
- archive、merge、delete、template apply、restore 的未来执行必须先创建 local snapshot / backup；Git 只能作为可选高级同步，不是恢复前置条件。
- CLI wrappers：`category-update-display-name-plan`、`category-archive-plan`、`category-merge-plan`、`category-delete-plan`、`template-apply-plan`、`workspace-upgrade-plan`、`workspace-archive-plan`、`workspace-delete-plan`。
- Safe mutation CLI wrappers：`category-update-display-name-approve` 生成 plan、创建 snapshot 并保存 approval；`category-update-display-name-execute` 创建并运行 TaskQueue task。没有 approval、approval 过期、plan hash 不匹配或 snapshot 缺失时必须拒绝执行。
- Description safe mutation CLI wrappers：`category-update-description-plan`、`category-update-description-approve`、`category-update-description-execute`。它们遵守同样的 plan hash、snapshot、approval expiry 和 TaskQueue 门禁。

Backup / Snapshot services：

- `backup-create` 在 `backups/YYYY/MM/` 下创建本地 zip，zip 内包含 `backup-manifest.json`。
- 默认备份 `knowledge/`、`config/`、`templates/`、`reports/`、`docs/`、`README.md`、`AGENTS.md`。
- 默认不包含 `.kb/index.sqlite`，因为 SQLite 是可重建索引；只有显式 `--include-index` 时才包含 `.kb/`，并在 manifest 中标记 `include_index=true`。
- `backup-list` 只读取本地 `backups/` metadata；`backup-verify` 用 manifest 中的 `sha256` 校验 zip payload。
- `snapshot-create` 是危险 mutation 前的安全包装，底层复用 backup service，不依赖 Git。
- `restore-plan` 只读 backup manifest 和 zip 内容，只生成将创建、覆盖、冲突的文件计划，不恢复、不覆盖、不写目标 workspace。
- Git 仍然是 Optional Git Sync，不是 backup、snapshot、restore-plan 的前置条件。

TaskQueue baseline / enhancement：

- `TaskQueueService` 是未来 GUI / EXE 的后台长任务边界；GUI 长任务必须通过 TaskQueue，不得在 UI 主线程直接执行 index、audit、backup、restore、archive 或 template apply。
- 每个任务必须有稳定的 `task_id`、`status`、`progress_percent`、`cancel_requested`、`error`、`log_path`、`result_summary` 和 `elapsed_ms`；progress event 必须有 `schema_version` 和单调 `sequence`。
- v1.7.0 baseline 只允许执行安全任务：`noop`、`workspace_status`、`backup_create`、`audit`、`index`。其中 `workspace_status` 只读 SQLite/config/cache；`backup_create` 只写 `backups/`；`index` 只写 `.kb/index.sqlite`。
- GUI 可通过 `task-progress` / `task-log` 或对应 service API 轮询 progress 和日志；任务列表必须使用 `limit` / `offset` 分页。
- cancellation 是 cooperative：`task-cancel` 对 running task 只设置 `cancel_requested=true`，安全任务在可行检查点停止，不强中断 OS 线程。
- retry 只能针对 failed / cancelled task，并且必须通过 `retry_of` / `retry_root` / `retry_attempt` 保留原 task 链路。
- cleanup 必须 plan-first；`task-cleanup-plan` 只输出候选清理计划，不删除 `.kb/tasks/` 文件。
- `future_restore`、`future_archive`、`future_template_apply` 只能创建 task record；执行时必须返回 blocked / unsupported，不得执行真实 destructive mutation。
- v1.8.x 在 TaskQueue 中只接入 `category_update_display_name_execute` 和 `category_update_description_execute`；task input 必须包含目标 category、新值和 `approval_id`，result_summary 必须包含 `MutationResult`。
- destructive task 只能在后续阶段接入，并且必须先满足 plan、snapshot / backup、人工确认、TaskQueue、错误详情、日志和可回滚要求。
- CLI wrappers：`task-create`、`task-run`、`task-status`、`task-list`、`task-cancel`、`task-progress`、`task-log`、`task-retry`、`task-cleanup-plan`。所有输出都是 JSON；`task-create` 只创建 pending task，`task-run` 才执行。

## 代码结构

- `scripts/kb.py`: CLI 入口，保留命令解析、命令处理和索引/搜索/治理流程。
- `knowledge_core/paths.py`: 仓库路径、生命周期层目录和路径解析工具。
- `knowledge_core/config.py`: categories、sources、learning-radar、extract-rules 配置加载。
- `knowledge_core/frontmatter.py`: frontmatter 解析、渲染和 schema 枚举。
- `knowledge_core/security.py`: secret-scan 的扫描规则、路径排除和脱敏逻辑。
- `knowledge_app/services/workspace_status_service.py`: 长期稳定 startup status service，供 CLI 和未来 GUI/EXE 复用。
- `knowledge_app/services/index_metadata_service.py`: 只读 SQLite metadata service，不创建索引、不扫描 Markdown、不 hash。
- `knowledge_app/services/search_service.py`: Search View 的 SQLite FTS service wrapper。
- `knowledge_app/services/category_service.py`: Category View 的 config + SQLite metadata service。
- `knowledge_app/services/review_queue_service.py`: Review Queue 的分页 metadata service。
- `knowledge_app/services/archive_metadata_service.py`: Archive / Deprecated / Quarantine 的分页 metadata service。
- `knowledge_app/services/document_service.py`: 显式单篇 Markdown open service。
- `knowledge_app/services/category_plan_service.py`: category display name、description、archive、merge、delete 的 plan-only service。
- `knowledge_app/services/template_plan_service.py`: template list/apply 的 plan-only service。
- `knowledge_app/services/workspace_plan_service.py`: workspace upgrade、archive、delete 的 plan-only service。
- `knowledge_app/services/backup_service.py`: 本地 zip backup 创建、列表和校验 service。
- `knowledge_app/services/snapshot_service.py`: pre-operation snapshot service，复用 backup service。
- `knowledge_app/services/restore_plan_service.py`: read-only restore plan service。
- `knowledge_app/services/task_queue_service.py`: 文件系统 TaskQueue baseline，持久化 `.kb/tasks/<task_id>/task.json`、progress events 和 task logs。
- `knowledge_app/services/safe_mutation_service.py`: v1.8.x safe execute mutation service，管理 snapshot-backed approval，并只执行 category display_name / description 更新。
- `knowledge_app/models/workspace_status.py`: `workspace-status` 稳定输出模型。
- `knowledge_app/models/search_result.py`: service-layer search 输出模型。
- `knowledge_app/models/operation_result.py`: service 层结构化结果模型。
- `knowledge_app/models/plan_result.py`: plan-only mutation 稳定输出模型。
- `knowledge_app/models/backup_models.py`: `BackupManifest`、`SnapshotResult`、`RestorePlan` 稳定输出模型。
- `knowledge_app/models/task_models.py`: `TaskRecord`、`ProgressEvent`、`TaskResult`、`TaskStatus`、`TaskType` 稳定任务模型。
- `knowledge_app/models/mutation_models.py`: `MutationApproval`、`MutationResult` 稳定安全执行模型。

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

## Core Algorithms Roadmap

后续路线使用三套核心算法固定搜索、数据生命周期和整理归档方向，详见 [docs/algorithm-strategy.md](D:/AI/personal-knowledge-base/docs/algorithm-strategy.md) 和 [docs/roadmap.md](D:/AI/personal-knowledge-base/docs/roadmap.md)。

- Layer-aware Hybrid Retrieval（分层感知混合检索算法）：负责搜索。SQLite FTS5 / BM25 仍是默认精确搜索入口，后续向量检索只能作为增强，并且必须尊重 `layer`、`status`、`source_type`、`confidence` hard filter。
- Content-addressed Lifecycle State Machine（内容寻址生命周期状态机）：负责数据生命周期。用 `card_id`、`topic_id`、`canonical_id`、`source_hash`、`content_hash` 等身份字段管理 raw -> distilled -> formal -> deprecated/archive 的状态流转，promote 必须人工审核。
- Topic-aware Generational Archive Planner（主题感知分代归档算法）：负责整理归档。按主题、层级、状态、复查和访问情况生成 organize-plan / archive-plan，默认只给计划，不自动移动或删除数据。

## Organize & Archive

整理归档设计见 [docs/organize-archive-design.md](D:/AI/personal-knowledge-base/docs/organize-archive-design.md)。它补齐长期增长后的 active/archive 分层、canonical、restore、archive score 和未来命令规划。

核心原则：

- archive is not delete。归档用于降低 active working set 和默认搜索噪音，同时保留历史、来源链路和恢复能力。
- archive 默认不进入普通 `search`。普通 `search` 仍默认只查 active `rules`、`checklists`、`snippets`，不因 archive 设计改变默认行为。
- organize-plan before archive。整理、合并、canonical 修正和归档默认都必须先生成 plan；真实 archive/restore/deprecate/quarantine 需要人工确认。
- archive 前建议创建 local snapshot / backup；Git snapshot、tag 只能作为高级用户可选补充。
- archive 不得破坏 `source_url`、`source_file`、`promoted_from`、`supersedes`、`superseded_by` 等来源链路。
- `rules`、`checklists`、`snippets` 必须少而准，优先保持 canonical；raw 可以多，但必须可整理、可归档、可恢复。

## Generic Workspace / Template System

下一阶段是 Generic Workspace / Template System，设计见 [docs/generic-workspace-template-system.md](D:/AI/personal-knowledge-base/docs/generic-workspace-template-system.md) 和 [docs/category-management-design.md](D:/AI/personal-knowledge-base/docs/category-management-design.md)。目标是把本项目从单一“开发者知识库”升级为可创建不同 workspace、选择不同模板、配置不同分类/来源/提炼规则/质量规则的通用知识库引擎。

Workspace 是一个独立知识库实例，包含：

- `knowledge/`
- `config/`
- `templates/`
- `reports/`
- `.kb/index.sqlite`
- `workspace.yaml`

为什么需要 workspace：

- 不同用户或不同领域可以使用不同模板，例如 Developer、Designer、Product、Research、AI Agent 或 Custom Knowledge Base。
- 每个 workspace 可以有独立 categories、sources、learning-radar、extract-rules、quality-rules、review cycles 和 Markdown templates。
- 10W+ 场景下，workspace 分片比把所有历史资料强塞进一个活跃索引更可控。
- archive workspace 可以单独存在，降低 active working set，又保留可恢复历史。

为什么分类不能直接删除：

- category 不只是目录名，还被 Markdown frontmatter、SQLite index、reports、sources、templates、promoted_from、supersedes、superseded_by 等链路引用。
- 非空 category 直接删除会破坏来源链路和治理闭环。
- 默认应使用 disable、archive、merge、restore；只有空分类、无 references、无 files、无 reports 依赖时才允许 advanced delete，并且必须先生成 delete plan。

为什么 `display_name` 和 `category_id` 要分离：

- `category_id` 是稳定身份，用于 frontmatter、SQLite、配置引用、报告引用和未来 GUI 内部引用。
- `display_name` 只用于 UI 和报告展示，可翻译、可改名，不应影响搜索过滤或历史引用。
- `path` 可迁移，但属于危险操作，必须先生成 migration plan；不能因为改显示名称就移动文件。

为什么每个 workspace 独立 `.kb/index.sqlite`：

- `.kb/index.sqlite` 是该 workspace 从 Markdown 派生的可重建索引，不是事实来源。
- workspace 切换时只打开当前 workspace 的 index，不扫描其他 workspace。
- startup 只读取当前 workspace metadata / index metadata，不扫描 `knowledge/`、不全量读取 Markdown、不自动触发 index/reindex。
- cross-workspace search 是未来增强，不应影响当前默认 search 行为。

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

## Local Only, Backup & Optional Git Sync

Git is optional, not required. 未来 Windows EXE 默认应使用 Local Only mode：普通用户没有 Git、没有 GitHub 账号、没有命令行经验时，也能完整创建、检索、审核、promote、archive、restore 和维护知识库。

默认恢复机制是 Backup & Snapshot：

- Local snapshot / backup 是普通用户默认回滚方式。
- promote、archive、restore、bulk import、schema migration、destructive maintenance 和 workspace upgrade 前应创建 snapshot。
- 本地 zip backup 应覆盖 Markdown、config、templates、reports、docs、README 和 AGENTS。
- `.kb/index.sqlite` 是可重建索引，默认不作为备份核心；可选包含以加快恢复。
- 备份前应运行 `secret-scan` 或明确提示 secret/privacy 风险。

Optional Git Sync 是高级用户可选功能，用于跨设备同步、远端备份或开发者版本管理。GUI 不得把 commit/push 作为 promote、audit、index、archive 或 restore 的必需步骤。未来 GUI 页面应叫 Backup & Sync，而不是只叫 Git Sync。

备份和快照设计见 [docs/backup-snapshot-design.md](D:/AI/personal-knowledge-base/docs/backup-snapshot-design.md)。

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

- 启动、Dashboard、Category View、Search View、Review Queue、Archive / Trash View 默认只读 SQLite metadata / FTS index。
- 启动时不扫描 `knowledge/`，不加载全部 Markdown，不自动触发 index。
- Category View 从 SQLite `documents` metadata 聚合统计和分页查询。
- `search` 默认只走 SQLite FTS5，并用 metadata filter 收缩结果，不全量扫描 `knowledge/`。
- Review Queue 从 SQLite metadata 查询。
- Archive / Trash / Quarantine 页面从 SQLite metadata 分页查询。
- `workspace-status` 只读 SQLite/config/cache，不读 Markdown，不 hash，不 index。
- 搜索只返回 Top-K chunk 和元数据。
- Markdown 只作为 source of truth；`open` / `edit` / `index` / `reindex` / `doctor` / `promote` / `archive` / `restore` / `backup` 等明确操作才读取 Markdown。
- `.kb/index.sqlite` missing/stale 时，GUI 显示 index status；missing 时只显示 `index_status=missing`，并提供后台 index/reindex 任务入口。
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

首次全量 `index` 可能较久，因为它必须读取 Markdown、解析 frontmatter、切 chunk、写入 `documents/chunks/chunks_fts`。这可以接受，但必须后台执行。软件启动不能等待首次全量 `index`，只能读取 SQLite metadata、workspace status、index status、cached stats 和最近任务状态；index missing/stale 时只提示，不阻塞 UI。`.kb/index.sqlite` 缺失时，startup 只能返回 `index_status=missing` 并提示用户后台构建索引，不得自动触发 index。

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
Markdown + SQLite + Local Backup/Snapshot
  ↓
Optional Git Sync
```

GUI 不应直接读写 Markdown 或 SQLite，也不应通过拼接 CLI 命令字符串作为主要集成方式。CLI 继续保留给 CI、自动化、调试和高级用户；GUI 应调用 service/core API。

未来 EXE / GUI 的默认读取路径是 SQLite-hot：App startup、Dashboard、Category View、Search View、Review Queue、Archive / Trash View 都读取 SQLite metadata / FTS5；Markdown 只作为 source of truth，并且只在 open/edit、index/reindex、doctor、promote、archive、restore、backup、schema migration、secret-scan 等明确操作中读取。

长期任务必须后台化，包括 index、reindex、audit、secret-scan、dedupe、conflicts、benchmark、maintenance、Optional Git Sync、backup/export 和 learning queue generation。任务需要 task_id、status、progress、cancellation、retry、error detail、log path 和 result summary。

v1.7.0 起，后台任务的稳定边界是 `TaskQueueService`。GUI / EXE 应调用 service API 创建、查询、取消和运行任务，UI 主线程不得直接执行 index/audit/backup/restore/archive/template apply。v1.8.x 当前安全执行只接入 `noop`、`workspace_status`、`backup_create`、`audit`、`index` 以及最低风险的 `category_update_display_name_execute`、`category_update_description_execute`；两者都必须先有 plan、snapshot、approval，并且只写 `config/categories.yaml` 的对应展示字段。GUI 可通过 task progress/log API 轮询或订阅任务状态。Task cleanup 必须 plan-first；retry 必须保留 `retry_of` 链路；cancellation 是 cooperative。restore/archive/delete/merge/template apply 等 destructive task 仍是 future work。

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

`.kb/index.sqlite` 是可重建索引，不作为核心备份。恢复流程默认依赖本地 backup/snapshot，不依赖 Git：

```bash
python scripts/kb.py index
python scripts/kb.py doctor
```

Git commit、branch、tag 是开发者或高级用户的可选版本同步机制，不是普通用户知识库回滚的唯一机制。EXE 默认应使用本地 backup/snapshot 作为恢复机制。

如索引损坏，可删除 `.kb/index.sqlite` 后重建：

```powershell
Remove-Item -Force .kb/index.sqlite
python scripts/kb.py index
python scripts/kb.py doctor
```

公开仓库不得包含真实 secret、客户隐私数据或私有业务数据。发布前必须运行：

```bash
python scripts/kb.py secret-scan
```

## Why Markdown remains the source of truth

Markdown 保持为事实来源，因为它可读、可 review、可通过本地 backup/snapshot 恢复，也可以被高级用户用 Git 做可选版本管理，还能长期跨工具保存。知识治理所需的来源、状态、confidence、review、valid_for、verification_method 和生命周期历史都必须保存在 Markdown/frontmatter 中。

SQLite 不能替代 Markdown。SQLite 只是为了检索、统计和治理报告服务的索引层。

## Why SQLite index is rebuildable

`.kb/index.sqlite` 保存的是从 Markdown 解析出的索引、chunk、FTS5 和元数据快照。它可以删除后通过 `python scripts/kb.py index` 重建；未来 GUI 应把重建作为后台 index/reindex 任务执行。

这条边界让系统在索引损坏、schema migration、性能调优或未来 GUI 崩溃后仍可恢复：保护 Markdown 源数据优先，索引失败可重建。

## Markdown Storage Design

Markdown 长期存储设计见 [docs/markdown-storage-design.md](D:/AI/personal-knowledge-base/docs/markdown-storage-design.md)，frontmatter schema 见 [docs/markdown-schema.md](D:/AI/personal-knowledge-base/docs/markdown-schema.md)。

Markdown 是 source of truth，因为它可读、可 diff、可 review、可通过本地 backup/snapshot 恢复，也能被高级用户用 Git 做可选版本管理，并能长期跨工具迁移。知识治理所需的 `source_url`、`source_file`、`status`、`confidence`、`reviewed_by`、`verification_method`、`promoted_from`、`supersedes`、`superseded_by`、`topic_id` 和 `canonical_id` 必须保存在 Markdown/frontmatter 中。

SQLite 不是事实来源。`.kb/index.sqlite` 只是从 Markdown 派生出的 FTS5 索引和元数据快照，用于搜索、统计、分类、review queue 和归档类列表。删除或损坏索引时，应从 Markdown 重建，而不是手工修 SQLite：

```powershell
Remove-Item -Force .kb/index.sqlite
python scripts/kb.py index
python scripts/kb.py doctor
python scripts/kb.py stats
```

Markdown 文件不是自由笔记，而是结构化知识卡片。新增卡片必须有 frontmatter，并按 `raw_note`、`rule`、`checklist`、`snippet`、`pitfall`、`adr` 或 `changelog` 使用对应正文模板。

文件命名必须稳定可读：

- 使用小写 ASCII、数字和连字符。
- raw/changelog 可使用 `YYYY-MM-DD-topic-slug.md`。
- rules/checklists/snippets 优先使用 `topic-slug.md` 或 `topic-slug-checklist.md`。
- 不得使用 `untitled`、`test`、`final`、`copy`、`new`、`temp` 等无语义名称。
- 同主题版本关系通过 `topic_id`、`canonical_id`、`supersedes` 和 `superseded_by` 表达，不靠 `final-v2-copy`。

大规模 Markdown 必须分片组织。10W+ 文档时不能把所有文件放进一个目录；单个叶子目录目标不超过 500 个 Markdown 文件，超过 1,000 个文件必须分片。raw 优先按 `year/month` 或 `source/topic` 分片；rules、checklists、snippets 优先按 topic family 分片；archive/raw 历史内容应进入 archive workspace 或 archive 目录。

推荐路径示例：

```text
knowledge/01-frontend/raw/2026/05/react/2026-05-18-react-managing-state.md
knowledge/01-frontend/rules/react/state-management.md
knowledge/01-frontend/checklists/performance/core-web-vitals-release-checklist.md
knowledge/09-ai-agent/snippets/codex/agent-task-template.md
```

不要保存网页全文。raw 只保存必要摘录、摘要、关键引用、来源链接、访问时间、待验证问题和自己的理解。网页全文会带来版权风险、噪音、重复、过期内容和索引膨胀。附件、PDF、图片不要直接塞进 Markdown 正文；Markdown 只记录 `source_file`、摘要、页码或截图说明。

未来 GUI/EXE 写入 Markdown 必须通过 service/core API，由 core 负责 schema 校验、目录分片、原子写入、生命周期链路和增量索引调度。GUI 不得直接读写 Markdown 或 SQLite。

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

- App startup、Dashboard、Category View、Search View、Review Queue、Archive / Trash View 默认只读 SQLite metadata / FTS index。
- App startup 不扫描 `knowledge/`，不读取所有 Markdown，不自动触发 index。
- `workspace-status` 只读 SQLite/config/cache，不读 Markdown，不 hash，不 index。
- `.kb/index.sqlite` 缺失时只显示 `index_status=missing`，并提示后台构建索引。
- `category view` 从 SQLite `documents` metadata 聚合统计和分页查询。
- `search` 默认走 SQLite FTS5，并用 metadata filter 过滤，不全量读取 Markdown。
- `search` 不全量扫描 `knowledge/`。
- `review-queue` 从 SQLite metadata 查询。
- Archive / Trash / Quarantine 页面从 SQLite metadata 分页查询。
- Markdown 只作为 source of truth；`open` / `edit` / `index` / `reindex` / `doctor` / `promote` / `archive` / `restore` / `backup` 等明确操作才读取 Markdown。
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
