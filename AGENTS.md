# Agent Rules

这个仓库是个人开发知识库，用来长期沉淀开发规则、模板、代码片段、检查清单和 Agent 可用上下文。

## 事实来源

- Markdown 是事实来源。
- SQLite 是 runtime hot index / 索引层，不是事实来源。
- `.kb/index.sqlite` 可以删除重建，不应手工编辑。

## 默认信任顺序

1. rules
2. checklists
3. snippets
4. distilled
5. raw

Codex 默认只能把 `rules`、`checklists`、`snippets` 当作正式可执行知识。`raw` 只能作为参考，`distilled` 是 AI 或人工提炼层，仍需人工审核。

## 防污染规则

- Codex 不得把 raw 当正式规则。
- Codex 不得把 distilled 当正式规则。
- Codex 使用知识库时必须优先用 `python scripts/kb.py search` 检索正式层。
- 如果使用 raw 或 `research` 结果，必须明确标注“未经审核，不能作为正式项目规则”。
- Codex 不得自动 promote，除非用户明确要求。
- Codex 不得删除 rejected/deprecated 的历史记录，除非用户明确要求。
- Codex 不得把 `review_required=true` 的内容作为项目决策依据。
- Codex 不得使用 quarantine 中的内容指导项目实现。

## 必须遵守的治理闭环

```text
外部内容 -> raw -> distilled -> review-queue -> promote -> rules/snippets/checklists -> search -> 项目使用 -> 实践验证 -> audit/stale/conflicts/deprecate -> 更新、废弃、修正
```

Codex 在这个仓库内工作时必须维护这个闭环：外部内容先进入 raw；AI 提炼只能进入 distilled；正式知识只能通过人工 promote 进入 rules、snippets、checklists；项目使用默认只能通过 search 读取正式层；实践反馈必须通过 audit、stale、conflicts、deprecate 或后续修正回流。

## 写入规则

- 不要把网上内容无审核直接放入 rules。
- 新知识必须保留 `source_url`、`status`、`confidence`、`last_reviewed`、`reviewed_by`、`verification_method`、`review_required`。
- 如果生成给项目使用的规则，必须写清楚适用场景、不适用场景、验证方式。
- promote 是人工审核动作，必须记录 `reviewed_by`、`confidence`、`valid_for`、`verification_method`、`review_note`。
- 不要存真实密钥、密码、token、客户隐私数据。

## Markdown Storage 规则

- Markdown 是事实来源，SQLite 是 runtime hot index / 索引层；`.kb/index.sqlite` 可以删除重建，不得当作事实来源。
- 不得创建无 frontmatter 的知识卡片。
- 不得创建 `untitled`、`test`、`final`、`copy`、`new`、`temp` 等无语义文件名。
- 不得把网页全文直接保存到 raw；raw 只能保存必要摘录、摘要、来源、访问时间、待验证问题和自己的理解。
- 不得把大量文件放进同一个目录而不考虑分片；10W+ 场景必须优先考虑 year/month、source/topic、topic family 或 workspace 分片。
- GUI/EXE 未来不得直接写 Markdown，必须通过 service/core API，由 core 负责 schema 校验、目录分片、原子写入、生命周期链路和增量索引调度。
- 修改 Markdown schema 必须说明 migration 策略，包括影响字段、影响层级、dry-run、原子写入、回滚、验收命令和如何从 Markdown 重建 SQLite index。
- promote、deprecate、reject、quarantine 必须保留 `source_url`、`source_file`、`promoted_from`、`supersedes`、`superseded_by` 等来源链路；不得为了整理目录切断历史。

## 整理归档规则

- Codex 不得自动 archive、delete 或 merge 知识卡片。
- organize/archive 功能默认必须生成 plan，不能直接移动、删除或改写 Markdown。
- archive、restore、deprecate、quarantine 必须人工确认。
- archive 操作前必须优先考虑 local snapshot / backup；Git snapshot、tag 只能作为高级用户可选补充。
- archive 不是 delete；归档内容必须可追溯、可显式搜索、可恢复。
- archive 不得破坏 `source_url`、`source_file`、`promoted_from`、`supersedes`、`superseded_by` 等来源链路。
- active formal knowledge 必须少而准；`rules`、`checklists`、`snippets` 应优先保持 canonical。
- raw 可以多，但必须可整理、可去重、可归档和可恢复，不能污染默认正式搜索。
- quarantine 是风险隔离，不得把 quarantine 内容作为项目实现依据，也不得用普通 archive 掩盖来源风险。

## Workspace / Template / Category 规则

- 后续 workspace、template、category 功能必须 plan-first；危险操作必须先输出影响分析、snapshot 建议、rollback plan 和验收命令。
- 所有会修改 Markdown、config、workspace、category、template 的 mutation operation 必须先走 plan-only service；plan-only service 只输出 JSON plan，不移动、不删除、不改写任何文件。
- PlanResult 必须保持稳定字段和稳定类型；`dry_run=true`、`would_modify=false`、`blocked` 必须与 `blockers` 是否为空一致，空列表和布尔字段不得省略。
- PlanResult 中的 `actions` 只能表示计划动作，不得表示已执行动作；`validation_commands` 必须存在，供未来 GUI / service 调用方直接消费。
- blocked plan 是成功构造出的计划，CLI 仍应返回 exit code 0；只有参数解析失败、代码异常或无法构造 plan 时返回非 0。
- archive、merge、delete、template apply 的未来执行必须要求 local snapshot / backup；Git 只能是可选高级同步，不得作为必需恢复机制。
- 危险 execute mutation 未来真正执行前必须先有 local snapshot；没有可验证 snapshot 时不得执行 archive、merge、delete、template apply、workspace upgrade 或 restore。
- backup/snapshot 不得依赖 Git，也不得要求普通用户必须 commit、tag、push。
- backup 默认不包含 `.kb/index.sqlite`，除非用户显式要求包含派生索引。
- restore-plan 只能生成只读计划，不得覆盖、移动、删除或恢复任何文件；真实 restore 执行是未来工作。
- 不得把 `display_name` 当作 `category_id`。`category_id` 是稳定身份，`display_name` 只用于 UI 和报告展示。
- 不得直接删除非空 category。非空 category 必须优先使用 disable、archive、merge 或 restore；advanced delete 只允许空分类且无 references、无 files、无 reports 依赖。
- category rename path、archive、merge、delete 必须生成 plan，不得破坏 `source_url`、`source_file`、`promoted_from`、`supersedes`、`superseded_by` 等来源链路。
- template 不得覆盖用户已有配置；应用模板到已有 workspace 必须生成 migration plan，列出配置 diff、冲突、写入文件、回滚方式和人工确认点。
- v1.5.0 起点阶段只实现 plan-only services 和 CLI wrappers；真实 execute/apply/archive/restore/merge/delete/template apply 是未来工作。
- v1.7.0 起点阶段只实现 TaskQueue baseline；TaskQueue enhancement 必须先补齐 progress/log 读取、分页、retry、cooperative cancellation 和 cleanup plan；`future_restore`、`future_archive`、`future_template_apply` 只能创建 task record，不得执行真实 restore/archive/template apply。
- destructive task 只能在 TaskQueue enhancement 稳定后的 safe execute mutation 阶段接入，并且必须先满足 plan-only、local snapshot / backup、人工确认、错误详情、日志和可回滚要求。
- template/source/RSS 等外部来源不得自动进入 `rules`、`snippets`、`checklists`，必须遵守 raw -> distilled -> review -> formal。
- workspace 切换不得扫描所有 workspace；只能关闭当前 workspace 资源并打开目标 workspace metadata/index metadata。
- workspace startup 只读当前 workspace `workspace.yaml`、轻量 config/cache 和 `.kb/index.sqlite` metadata，不得启动时扫描 `knowledge/`、读取 Markdown 或自动触发 index/reindex。
- 每个 workspace 必须有独立 `.kb/index.sqlite`；SQLite 仍然是可重建索引，不是事实来源。
- Git optional 规则仍然适用。workspace backup/restore/promote/audit/index/archive 不得依赖 Git，普通用户默认使用 Backup/Snapshot。

## 冲突处理

如果内容过期或冲突，优先使用：

1. `status=active`
2. `review_required=false`
3. `last_reviewed` 更新
4. `source_type` 更权威
5. `confidence` 更高

仍无法判断时，保留冲突并要求人工审核。

## 使用方式

推荐正式检索：

```bash
python scripts/kb.py search --query "react state" --category frontend --top-k 10
python scripts/kb.py open --id 12
```

探索性检索必须用：

```bash
python scripts/kb.py research --query "react state" --category frontend
```

`research` 结果未经审核，只能用于学习和待审核提炼。

## 长期运维与 GUI / EXE 边界

- 后续 GUI 任务必须先设计 service boundary，再实现界面。
- GUI 不得直接读写 Markdown 或 SQLite；必须通过 service/core API 访问。
- GUI 不得通过拼接 CLI 命令字符串作为主要集成方式。
- CLI 入口也必须复用 service/core API；不得把长期 GUI/EXE 启动逻辑只写在 `scripts/kb.py`。
- App startup、Dashboard、Category View、Search View、Review Queue、Archive / Trash View 默认只读取 SQLite metadata / FTS index，不得读取 Markdown 正文。
- App startup 不得扫描 `knowledge/`、不得读取所有 Markdown、不得自动触发 index。
- Dashboard 只读 workspace status、index status、cached stats 和最近任务摘要。
- GUI Dashboard/Search/Category/Review/Archive 页面必须调用 `knowledge_app.services` 中的 service；CLI 只作为自动化、调试和验收入口。
- Search View 必须调用 `SearchService`；Category View 必须调用 `CategoryService`；Review Queue 必须调用 `ReviewQueueService`；Archive / Trash / Quarantine View 必须调用 `ArchiveMetadataService`。
- Category View 必须从 SQLite `documents` metadata 聚合统计和分页查询；Search View 必须从 SQLite FTS5 查询，并用 `documents` metadata 做 hard filter。
- Review Queue 必须从 SQLite metadata 查询；Archive / Trash / Quarantine 页面必须从 SQLite metadata 分页查询。
- `workspace-status` 必须是轻量命令，只读 SQLite/config/cache；不得读 Markdown、不得 hash、不得 index。
- App startup 的稳定路径是 `WorkspaceStatusService` / `workspace-status`；App startup != first index，不能调用 index、doctor、audit 或 secret-scan。
- Markdown 正文只能通过 `DocumentService.open_document` 在用户明确打开单篇文档时读取；不得为了列表、搜索、分类、review queue 或 archive 页面批量读取 Markdown。
- Markdown 只作为 source of truth；只有 open/edit/index/reindex/doctor/promote/archive/restore/backup/secret-scan/schema migration 等明确操作才读取 Markdown。
- `.kb/index.sqlite` missing 时，GUI / service 只能显示 `index_status=missing`，并提示用户启动后台 index/reindex；不得在 startup 自动构建索引。
- 长任务必须后台化，提供 task_id、status、progress、cancellation、error detail、log path、retry lineage 和 result summary。
- GUI 长任务必须通过 `TaskQueueService`；TaskQueue 是未来 GUI / EXE 的后台任务边界。
- UI 主线程不得直接执行 index、audit、backup、restore、archive、template apply；这些操作必须进入 TaskQueue 或后续安全执行服务。
- 当前 TaskQueue baseline 只允许执行 `noop`、`workspace_status`、`backup_create`、`audit`、`index`，且不得修改 Markdown 源数据。
- 每个 task record 必须稳定包含 `task_id`、`status`、`progress_percent`、`cancel_requested`、`error`、`log_path`、`result_summary`、`elapsed_ms`。
- ProgressEvent 必须包含 `schema_version` 和单调 `sequence`；GUI 应通过 `task-progress` / `task-log` 或对应 service API 轮询或订阅任务状态。
- cancellation 是 cooperative，不得强中断 OS 线程；`task-cancel` 对 running task 只设置 `cancel_requested=true`，安全任务只能在可行检查点停止。
- retry 只能针对 failed / cancelled task，必须保留 `retry_of`、`retry_root` 或等价 lineage；不得通过 retry 绕过 future task blocked 规则。
- task cleanup 必须 plan-first；`task-cleanup-plan` 只能输出候选计划，不得删除 `.kb/tasks/` 文件。
- `.kb/tasks/` 是 runtime task storage，不是事实来源，不得提交；task logs 存放在 `.kb/tasks/<task_id>/task.log`。
- UI 主线程不得执行 index、audit、secret-scan、reindex、dedupe、conflicts、benchmark、maintenance、Optional Git Sync 或 backup/export。
- 不得把 GUI 写成单文件巨型 `App.tsx`、`main.py` 或等价的大型入口文件。
- EXE 相关开发必须保护 workspace 数据；软件安装目录不存用户知识数据，workspace 中的 Markdown 始终优先保护。
- SQLite 索引可删除重建；删除 `.kb/index.sqlite` 后，可通过后台 reindex 从 Markdown 重建，不得把 `.kb/index.sqlite` 当作事实来源。
- 所有维护命令默认不得删除、不得 promote、不得修改 raw/distilled/rules。
- `vacuum`、`reindex`、cleanup、restore 等操作必须显式触发，并在 GUI 中要求确认。
- 不得把 Git 作为 EXE 软件必需依赖。
- 不得要求普通用户必须 `git commit` 或 `git push`。
- promote、audit、index、archive、restore 不得依赖 Git。
- Git 相关功能必须位于 `OptionalGitService` 或等价可选模块。
- 普通用户默认使用 Backup/Snapshot 作为恢复机制。
- GUI 页面应叫 Backup & Sync，而不是只叫 Git Sync。

## 大规模性能与内存规则

- 不得实现启动时全量扫描知识库。
- 不得实现启动时全量读取 Markdown。
- 不得实现启动时自动触发 index/reindex。
- 启动、Dashboard、分类、搜索、review queue、archive/trash/quarantine 列表必须走 SQLite metadata / FTS5 热路径。
- Markdown 只在 open/edit/index/reindex/doctor/promote/archive/restore/backup/secret-scan/schema migration 等明确需要源文件的操作中读取。
- 不得让 GUI 一次渲染所有搜索结果。
- 不得在 UI 主线程跑 index、audit、secret-scan、reindex、dedupe、conflicts、benchmark、maintenance、Optional Git Sync 或 backup/export。
- 大规模功能必须考虑分页、Top-K、虚拟滚动、后台任务、内存上限和取消/恢复能力。
- 10K/100K 相关改动必须说明性能影响，包括启动是否扫描文件、搜索是否读取 Markdown、缓存是否有上限、长任务是否后台化。
- 搜索默认行为不得因大规模模式改变：默认仍只查 `rules`、`checklists`、`snippets`，并且只查 SQLite FTS5 / 索引。
- 100K+ 场景优先考虑 workspace 分片、active/archive 分离和 per-workspace index，而不是把所有历史资料强塞进单个活跃索引。

## 后续核心算法开发规则

- 后续搜索功能必须遵守 Layer-aware Hybrid Retrieval。
- 后续向量检索不得绕过 `layer`、`status`、`source_type`、`confidence` 过滤。
- 后续知识状态变更必须遵守 Content-addressed Lifecycle State Machine。
- `raw` / `distilled` 不得自动进入正式层。
- `organize` / `archive` 功能默认只能生成 plan，不能自动移动或删除。
- `archive` / `restore` / `deprecate` / `quarantine` 必须有人工确认。
- 后续 GUI 必须在 Search、Review、Archive 页面体现 `layer`、`status`、`source_type`、`confidence`、`review_required`、`archive_status` 等状态。

## 学习雷达边界

- Codex 可以帮助生成 learning queue。
- Codex 可以帮助根据 raw 生成 distill-plan，或把 raw 提炼为 distilled 草稿。
- Codex 不得自动 promote 到 rules、snippets、checklists，除非用户明确要求并提供审核信息。
- Codex 不得把 learning queue 当正式知识。
- Codex 不得抓取不可控全网内容；学习源必须来自 `config/sources.yaml` 或用户明确提供。
- Codex 生成的提炼结果默认 `review_required=true`，只能进入 distilled。
