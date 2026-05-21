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
- v1.5.0 起点阶段只实现 plan-only services 和 CLI wrappers；v1.8.0 之前真实 execute/apply/archive/restore/merge/delete/template apply 是未来工作。
- v1.7.0 起点阶段只实现 TaskQueue baseline；TaskQueue enhancement 必须先补齐 progress/log 读取、分页、retry、cooperative cancellation 和 cleanup plan；`future_restore`、`future_archive`、`future_template_apply` 只能创建 task record，不得执行真实 restore/archive/template apply。
- v1.8.x Safe Execute Mutation Framework 只允许低风险 config-only execute mutation，并且必须满足 plan、local snapshot / backup、approval、TaskQueue。
- v1.8.0 允许 `category_update_display_name_execute`；v1.8.1 允许 `category_update_description_execute`。两者只能修改 `config/categories.yaml` 中目标 category 的对应字段，不得 path rename、不得修改 `category_id` / `path` / slug、不得修改 Markdown、不得修改 SQLite schema。
- 空 description 必须通过 `--allow-empty-description` 明确表示 intentional clear。
- archive、delete、merge、template apply、restore 的真实执行仍是 future work；没有 execute 命令或必须返回 unsupported。destructive task 只能在后续 safe execute mutation 阶段接入，并且必须先满足 plan-only、local snapshot / backup、人工确认、错误详情、日志和可回滚要求。
- v2.0.0-beta.8 workspace creation wizard 支持最小安全创建执行和 first-run polish；GUI 必须先通过 `WorkspaceCreationPlanService` 生成 dry-run 计划和预览，不得绕过 service layer。
- 创建 workspace 必须 plan-first + explicit confirm；`WorkspaceCreationService` 只能在用户确认 plan 后写入 `workspace.yaml`、`knowledge/`、`config/`、`templates/`、`reports/` 和可选 `backups/` 等计划内产物。
- 新建 workspace 不得自动导入旧资料，不得创建正式知识或 sample knowledge，不得依赖或初始化 Git，不得把软件安装目录或当前工作目录默认当作 workspace，不得自动创建 `.kb/index.sqlite`，不得自动 index。
- first-run polish 只能改文案、错误态、成功态和下一步引导；不得引入 installer、AI/RSS/vector、自动 index、自动导入或额外 mutation UI。
- template/source/RSS 等外部来源不得自动进入 `rules`、`snippets`、`checklists`，必须遵守 raw -> distilled -> review -> formal。
- workspace 切换不得扫描所有 workspace；只能关闭当前 workspace 资源并打开目标 workspace metadata/index metadata。
- workspace startup 只读当前 workspace `workspace.yaml`、轻量 config/cache 和 `.kb/index.sqlite` metadata，不得启动时扫描 `knowledge/`、读取 Markdown 或自动触发 index/reindex。
- 每个 workspace 必须有独立 `.kb/index.sqlite`；SQLite 仍然是可重建索引，不是事实来源。
- Git optional 规则仍然适用。workspace backup/restore/promote/audit/index/archive 不得依赖 Git，普通用户默认使用 Backup/Snapshot。

## AI Assistant Control Plane 规则

- v2.1.0 只允许设计 AI 助手控制平面，不得实现真实 AI 模型、模型安装、OpenAI/本地模型接入、RSS、vector search、悬浮聊天 UI 或 mutation UI。
- v2.1.1 只允许实现 AI config loader、capability schema validation、PermissionPolicy 静态校验和测试；不得接真实 AI、OpenAI、本地大模型、ModelScope、模型下载、AI 聊天 UI、RSS/vector 或 mutation UI。
- v2.2.0 只允许实现 MockAIProvider 和右下角悬浮 AI 助手 UI skeleton；不得接真实 AI、OpenAI、本地大模型、ModelScope、模型下载、RSS/vector、真实 memory service 或 mutation UI。
- v2.2.0 MockAIProvider 必须 deterministic，不访问网络，不读取文件，不读取 SQLite，不调用真实 service，不保存长期记忆，不执行 mutation。
- v2.2.0 悬浮 AI UI 必须走 `View -> ViewModel -> Adapter -> knowledge_app.ai.AssistantService -> CapabilityRegistry -> PermissionPolicy -> MockAIProvider`；View 不得直接调用 provider、service、Markdown、SQLite 或 CLI。
- v2.3.0 只允许实现 Ask My Knowledge / Summarize Current Document mock flow；不得接真实 AI、OpenAI、本地模型、ModelScope、模型下载、RSS/vector、ConversationStore、MemoryService 或 mutation UI。
- v2.4.0 只允许设计 ConversationStore / MemoryService；不得实现真实持久化 memory service，不得保存真实长期记忆，不得实现 conversation store 写入，不得接真实 AI、OpenAI、本地模型、ModelScope、模型下载、RSS/vector 或 mutation UI。
- memory 持久化前必须先有 deletion、retention、backup、export、privacy mode、secret/sensitive blocking 和用户可见控制策略。
- memory 和 conversation 不得写入 `knowledge/`，不得放入 `.kb/`，不得放入安装目录；推荐未来放在 workspace-scoped `ai/conversations/`、`ai/memory/`、`ai/drafts/` 并由 service/core API 管理。
- `ask_my_knowledge` 必须通过 `SearchService.search` 搜索 formal 层 rules/checklists/snippets；不得直接查询 SQLite、不得读取所有 Markdown、不得自动 index。
- `summarize_current_document` 必须要求明确 `current_document_id` 或当前阅读器明确打开的单篇文档，并通过 `DocumentService.open_document` 打开单篇文档；不得猜测当前文档、不得批量读取 Markdown。
- AI 助手必须遵守 `用户自然语言 -> IntentRouter -> CapabilityRegistry -> PermissionPolicy -> ContextBuilder -> AIProvider -> Response / Plan -> Confirmation if needed -> Service / TaskQueue`。
- AI 助手不得绕过 service layer；只能通过 `knowledge_app.services` 调用搜索、文档打开、分类、任务、备份、计划和安全执行能力。
- AI 助手不得直接读写 Markdown，不得直接读写 SQLite，不得直接读取 `.kb/tasks/` 或 backup zip，不得拼接 CLI 命令字符串。
- AI capabilities 必须先通过 `CapabilityRegistry.load_from_yaml` 的 schema validation；未通过 loader 校验的 YAML 不得作为能力白名单。
- L3 / L4 capability 的 PermissionPolicy 静态测试必须通过；L3 必须确认 snapshot / approval / TaskQueue 门禁，L4 必须 deny。
- AI 助手只能调用 CapabilityRegistry 中允许的 capability；未注册能力一律 forbidden。
- 未注册 capability 的 policy decision 必须是 deny / forbidden，不得 fallback 到 CLI、service 猜测或自然语言模拟执行。
- `config/ai-capabilities.example.yaml` 只能作为 example contract 和测试输入，不得作为运行时自动执行入口；加载示例 YAML 不代表允许 AI 执行任何 capability。
- AI 输出如果基于知识库内容，必须带来源引用；引用至少包含 document/title/layer/status/source_type/confidence 或 service 返回的等价 metadata。
- AI 使用 raw、distilled、research、archived 或 `review_required=true` 内容时，必须明确标注“未经审核，不能作为正式项目规则”；不得把这些内容当正式项目决策依据。
- AI 不得自动保存长期记忆；长期记忆必须通过 MemoryCandidateCard 或等价确认流程由用户确认后保存，用户必须能查看、删除和关闭记忆。
- 对话记录不等于长期记忆；conversation store 不得作为正式知识层，不得被索引为 rules/checklists/snippets。
- MemoryCandidate 不是 saved memory；必须用户确认后才能保存，rejected candidate 不应重复打扰用户。
- AI 不得把 memory 当 formal knowledge，不得用 memory 绕过 `SearchService` formal 层边界，不得用 memory 作为 mutation approval、reviewer identity、plan hash 或 snapshot。
- 云端 AI 发送资料前必须展示 context preview，并获得用户确认；敏感资料、quarantine、rejected 和未确认资料默认不得发送。
- AI 不得自动删除、归档、恢复、promote、修改 Markdown、修改 SQLite、清空资料或执行 destructive mutation。
- AI 发起写操作必须遵守 `plan -> local snapshot / backup -> approval -> TaskQueue -> execute`；没有 snapshot、approval 或 plan hash 校验时不得执行。
- `update_category_display_name` 和 `update_category_description` 即使作为未来 safe execute，也只能通过 `SafeMutationService` 修改 `config/categories.yaml` 对应展示字段，不得改 category id、path、slug、Markdown 或 SQLite schema。
- archive、delete、restore、template apply、merge、promote 当前只能 forbidden 或 future plan-only，不得由 AI 自动执行。

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

- GUI 开发必须先遵守 `docs/gui-product-ui-architecture.md` 中的 Product UI Architecture Contract。
- GUI Phase 1 必须遵守 `docs/gui-phase-1-read-only-mvp-contract.md` 中的 Read-only MVP Screen Contract。
- GUI Phase 1 工程准备必须遵守 `docs/gui-phase-1-engineering-prep.md`；在技术选型和 GUI 编码前，先定义 GUI-to-service adapter、read-only ViewModel contracts、service fixtures、UI test harness 和 startup performance acceptance。
- GUI 技术选型必须先通过 `docs/gui-technology-selection.md`；当前第一版 Read-only MVP 推荐 PySide6 / Qt for Python，Tauri + React 只作为后续 UI 质量增强路线。
- GUI 顶部栏不得作为主导航；顶部栏只保留 workspace switch、global search / command search、index status indicator、task status indicator、backup status indicator、settings/user entry。
- GUI 左侧栏是唯一主导航；只保留：首页、搜索、知识库、审核、任务中心、维护、设置。
- 归档、整理中心、备份与同步、审计中心 必须归入「维护」；模板管理、来源管理、分类设置 必须归入「设置」。
- Raw Inbox、Distilled Review 必须归入「审核」子视图；Rules / Checklists / Snippets 必须归入「知识库」子视图。
- GUI Phase 1 只能做 read-only MVP：工作区入口、首页、搜索、知识库、文档预览、任务中心摘要、设置入口。
- GUI Phase 1 不得提前实现写操作，不得显示可编辑配置表单，不得接入真实 mutation UI。
- GUI Phase 1 不得暴露 category `display_name` / `description` execute。
- GUI Phase 1 不得暴露 archive/delete/merge/template apply/restore execute，不得暴露 RSS 或 vector search。
- GUI 不得提前接入 destructive execute；archive、delete、merge、template apply、restore execute 在 service 明确支持前必须 disabled 或 plan-only。
- 后续 GUI 任务必须先设计 service boundary，再实现界面。
- GUI 不得直接读写 Markdown 或 SQLite；必须通过 service/core API 访问。
- GUI 不得通过拼接 CLI 命令字符串作为主要集成方式。
- GUI-to-service adapter 必须保持 framework-neutral，只把 `knowledge_app.services` 的结构化结果转换为 read-only ViewModel；不得在 adapter 中重写 search/index/audit、解析 Markdown、查询 SQLite 或执行 mutation。
- GUI 不得绕过 service layer；即使使用 PySide6，View 也不得直接调用 `knowledge_core`，只能通过 ViewModel -> adapter -> `knowledge_app.services`。
- GUI 代码必须按职责拆分在 `gui/app.py`、`gui/main_window.py`、`gui/shell/`、`gui/views/`、`gui/viewmodels/`、`gui/adapters/`、`gui/widgets/`、`gui/fixtures/`；不得把页面、ViewModel、Adapter、Service 混在单个大文件。
- `gui/app.py` 只负责 QApplication 和 MainWindow 启动；`gui/main_window.py` 只负责挂载 AppShell。
- `gui/views/` 只能放页面 UI，不得直接 import `knowledge_app.services`、`knowledge_core`、`sqlite3`，不得直接读取 Markdown、SQLite、`.kb/tasks/` 或 backup zip。
- `gui/viewmodels/` 只能调用 adapter，不得直接读写文件系统，不得直接调用 service/core。
- `gui/adapters/service_adapter.py` 是 GUI 到 service layer 的唯一入口；adapter 不得拼接 CLI 命令字符串，不得重写 search/index/audit/category/document/task 逻辑，不得暴露 Phase 1 mutation execute 能力。
- GUI Phase 1 startup 只能调用 adapter 的 workspace status 路径；不得在启动时触发 search、library load、task list、index、audit、backup 或 Markdown open。
- `gui/fixtures/` 只能放测试/开发 fake adapter 和 fixture 数据；真实 View/ViewModel 不得内嵌 fake 数据。
- GUI Phase 1 不得暴露 mutation execute：不得显示 category display_name / description execute，不得显示 archive/delete/merge/template apply/restore execute，不得显示 cleanup/retry/cancel 的可用按钮。
- 如果未来使用 Tauri 或 Electron，Python sidecar/service 必须保持 SQLite-hot / Markdown-source 边界，不得让前端、Rust/Node host、插件或 bridge 直接读写 Markdown 或 SQLite。
- 不得为了 GUI 开发方便直接读取 `knowledge/**/*.md`、`.kb/index.sqlite`、`.kb/tasks/` 或 backup zip；Document body 只能通过 `DocumentService.open_document`，task/progress/log 只能通过 `TaskQueueService`。
- CLI 入口也必须复用 service/core API；不得把长期 GUI/EXE 启动逻辑只写在 `scripts/kb.py`。
- App startup、首页、搜索、知识库、审核、维护中的 metadata 列表默认只读取 SQLite metadata / FTS index，不得读取 Markdown 正文。
- App startup 不得扫描 `knowledge/`、不得读取所有 Markdown、不得自动触发 index。
- 首页只保留索引状态、待审核数量、备份状态、任务状态、最近任务、推荐操作和快速入口，不得铺满所有功能入口。
- GUI 首页、搜索、知识库、审核、任务中心、维护、设置页面必须调用 `knowledge_app.services` 中的 service；CLI 只作为自动化、调试和验收入口。
- 搜索必须调用 `SearchService`；知识库必须调用 `CategoryService`；审核必须调用 `ReviewQueueService`；维护 > 归档 子视图必须调用 `ArchiveMetadataService`。
- 知识库必须从 SQLite `documents` metadata 聚合统计和分页查询；搜索必须从 SQLite FTS5 查询，并用 `documents` metadata 做 hard filter。
- 审核必须从 SQLite metadata 查询；维护 > 归档 子视图必须从 SQLite metadata 分页查询。
- `workspace-status` 必须是轻量命令，只读 SQLite/config/cache；不得读 Markdown、不得 hash、不得 index。
- App startup 的稳定路径是 `WorkspaceStatusService` / `workspace-status`；App startup != first index，不能调用 index、doctor、audit 或 secret-scan。
- Markdown 正文只能通过 `DocumentService.open_document` 在用户明确打开单篇文档时读取；不得为了列表、搜索、分类、review queue 或 archive 页面批量读取 Markdown。
- Markdown 只作为 source of truth；只有 open/edit/index/reindex/doctor/promote/archive/restore/backup/secret-scan/schema migration 等明确操作才读取 Markdown。
- `.kb/index.sqlite` missing 时，GUI / service 只能显示 `index_status=missing`，并提示用户启动后台 index/reindex；不得在 startup 自动构建索引。
- 长任务必须后台化，提供 task_id、status、progress、cancellation、error detail、log path、retry lineage 和 result summary。
- GUI 长任务必须通过 `TaskQueueService`；TaskQueue 是未来 GUI / EXE 的后台任务边界。
- UI 主线程不得直接执行 index、audit、backup、restore、archive、template apply；这些操作必须进入 TaskQueue 或后续安全执行服务。
- 当前 TaskQueue safe executable set 只允许执行 `noop`、`workspace_status`、`backup_create`、`audit`、`index`、`category_update_display_name_execute`、`category_update_description_execute`；其中 category config-only 执行必须有 approval 且不得修改 Markdown 源数据。
- 每个 task record 必须稳定包含 `task_id`、`status`、`progress_percent`、`cancel_requested`、`error`、`log_path`、`result_summary`、`elapsed_ms`。
- ProgressEvent 必须包含 `schema_version` 和单调 `sequence`；GUI 应通过 `task-progress` / `task-log` 或对应 service API 轮询或订阅任务状态。
- cancellation 是 cooperative，不得强中断 OS 线程；`task-cancel` 对 running task 只设置 `cancel_requested=true`，安全任务只能在可行检查点停止。
- retry 只能针对 failed / cancelled task，必须保留 `retry_of`、`retry_root` 或等价 lineage；不得通过 retry 绕过 future task blocked 规则。
- task cleanup 必须 plan-first；`task-cleanup-plan` 只能输出候选计划，不得删除 `.kb/tasks/` 文件。
- `.kb/tasks/` 是 runtime task storage，不是事实来源，不得提交；task logs 存放在 `.kb/tasks/<task_id>/task.log`。
- UI 主线程不得执行 index、audit、secret-scan、reindex、dedupe、conflicts、benchmark、maintenance、Optional Git Sync 或 backup/export。
- 不得把 GUI 写成单文件巨型 `App.tsx`、`main.py` 或等价的大型入口文件。
- EXE 相关开发必须保护 workspace 数据；软件安装目录不存用户知识数据，workspace 中的 Markdown 始终优先保护。
- PyInstaller 打包默认只允许 one-folder baseline / hardening；Windows installer 必须作为独立 Inno Setup 6 spike 基于 one-folder 产物制作，不得切换 one-file。code signing、auto update 仍是后续独立阶段。
- Installer 不得删除用户数据：卸载器只允许删除安装目录和快捷方式，不得删除 `%LOCALAPPDATA%\PersonalKnowledgeBase\`、GUI settings/logs、用户 workspace、用户 backups、`knowledge/`、`config/`、`templates/` 或 `reports/`。
- Installer 不得要求普通用户安装 Git 或 Python；Git 仍是 optional，Python 只能是开发/构建环境依赖，不得成为已安装 EXE 的运行前置。
- Installer 不得把 workspace 数据放入安装目录，不得把 workspace、`.kb/`、backups、LocalAppData settings/logs 或用户 runtime 数据打进安装包。
- Installer smoke 必须验证 install、launch、empty workspace no auto index、uninstall、reinstall、LocalAppData preservation、workspace preservation、Git not required 和 Python not required。
- 发布说明必须明确当前限制：候选版本、未签名、非 one-file、无 auto update、无 AI、无 RSS、无 vector search、无 mutation UI、无 archive/delete/merge/template apply/restore/promote execute。
- GUI 本地窗口设置只能写入 `%LOCALAPPDATA%\PersonalKnowledgeBase\settings\gui-settings.json` 或等价用户目录，不得写入安装目录、workspace、`knowledge/`、`.kb/` 或 `config/`。
- GUI 日志只能写入 `%LOCALAPPDATA%\PersonalKnowledgeBase\logs\pkb-gui.log` 或等价用户目录，不得写入安装目录或 workspace。
- GUI 启动可以读取本地 GUI 设置以恢复窗口大小、位置和最大化状态；该读取不得触发 workspace index/search/library/task/document open。
- SQLite 索引可删除重建；删除 `.kb/index.sqlite` 后，可通过后台 reindex 从 Markdown 重建，不得把 `.kb/index.sqlite` 当作事实来源。
- 所有维护命令默认不得删除、不得 promote、不得修改 raw/distilled/rules。
- `vacuum`、`reindex`、cleanup、restore 等操作必须显式触发，并在 GUI 中要求确认。
- 不得把 Git 作为 EXE 软件必需依赖。
- 不得要求普通用户必须 `git commit` 或 `git push`。
- promote、audit、index、archive、restore 不得依赖 Git。
- Git 相关功能必须位于 `OptionalGitService` 或等价可选模块。
- 普通用户默认使用 Backup/Snapshot 作为恢复机制。
- GUI 备份入口应位于「维护 > 备份与同步」，不得把 Git Sync 作为主导航。

## 大规模性能与内存规则

- 不得实现启动时全量扫描知识库。
- 不得实现启动时全量读取 Markdown。
- 不得实现启动时自动触发 index/reindex。
- 启动、首页、搜索、知识库、审核、维护中的 metadata 列表必须走 SQLite metadata / FTS5 热路径。
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
- 后续 GUI 必须在 搜索、知识库、审核、维护 > 归档 子视图体现 `layer`、`status`、`source_type`、`confidence`、`review_required`、`archive_status` 等状态。

## 学习雷达边界

- Codex 可以帮助生成 learning queue。
- Codex 可以帮助根据 raw 生成 distill-plan，或把 raw 提炼为 distilled 草稿。
- Codex 不得自动 promote 到 rules、snippets、checklists，除非用户明确要求并提供审核信息。
- Codex 不得把 learning queue 当正式知识。
- Codex 不得抓取不可控全网内容；学习源必须来自 `config/sources.yaml` 或用户明确提供。
- Codex 生成的提炼结果默认 `review_required=true`，只能进入 distilled。
