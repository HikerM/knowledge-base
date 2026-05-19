# Markdown Storage Design

本文定义 `personal-knowledge-base` 的 Markdown 长期存储设计。当前阶段只补齐 Markdown storage 规范、模板约束、文档和 Agent 规则；不做 GUI、RSS、向量检索、MCP、Codex Skill、EXE，也不修改 `knowledge/**/*.md`、SQLite schema 或默认搜索行为。

## 1. 核心边界

Markdown 是 source of truth。每条知识的标题、分类、层级、状态、来源、审核信息、适用范围、生命周期链路和正文，都必须以 Markdown 文件和 frontmatter 为准。

SQLite 是 derived index，也是未来 GUI / EXE 的 runtime hot index。`.kb/index.sqlite` 只保存从 Markdown 解析出的元数据、chunk、FTS5 和统计信息。它可以删除重建，不应手工编辑，也不能作为事实来源。

Markdown 文件不是自由笔记，而是结构化知识卡片。每个知识卡片必须有 frontmatter，正文必须按 type 使用稳定模板。自由笔记、整页网页复制、未标注来源的片段和临时草稿不能直接进入正式层。

知识库的最小事实单元是 knowledge card：

- 一个 Markdown 文件对应一条可治理知识。
- frontmatter 负责机器可读字段。
- 正文负责人类可读的结论、上下文、风险、验证方式和来源说明。
- 文件路径负责 category、layer 和分片定位。
- SQLite 只能从这些事实派生索引，不能反向覆盖 Markdown。
- 运行时页面优先读取 SQLite metadata / FTS5；只有 open/edit/index/reindex/doctor/promote/archive/restore/backup 等明确操作读取 Markdown 源文件。

## 2. 生命周期层职责

当前目录层级保持：

```text
knowledge/<category>/<layer>/...
```

各层职责如下。

| layer | 职责 | 默认可信度 | 项目使用规则 |
| --- | --- | --- | --- |
| `raw` | 原始摘录、链接摘要、会议记录、临时想法和未验证来源 | 低 | 只能参考；不能作为正式项目规则 |
| `distilled` | AI 或人工从 raw 提炼出的草稿结论、风险和验证计划 | 中 | 仍需人工审核；不能默认作为正式规则 |
| `rules` | 人工审核后的可执行工程规则 | 高 | Codex/Agent 默认可信正式知识 |
| `snippets` | 人工审核后的可复用代码、命令、配置或提示词片段 | 高 | Codex/Agent 默认可信正式知识 |
| `checklists` | 人工审核后的审查、验收、上线或排障清单 | 高 | Codex/Agent 默认可信正式知识 |
| `deprecated` | 曾经有效但已过期、被替代或实践验证失败的知识 | 历史 | 保留历史，不用于默认决策 |
| `rejected` | 审核后明确不采用的内容 | 历史 | 保留拒绝原因，避免重复引入 |
| `quarantine` | 来源不明、质量低、无法验证、AI 摘要可疑或疑似污染的内容 | 隔离 | 不得指导项目实现 |

默认信任顺序仍是 `rules -> checklists -> snippets -> distilled -> raw`，但 Codex 默认只能把 `rules`、`checklists`、`snippets` 当作正式可执行知识。

## 3. 知识卡片正文模板

不同 type 必须使用不同正文结构，避免把知识库退化为散文笔记。

### raw_note

用途：保存外部资料、项目观察、会议记录或临时想法的受控摘录。

正文必须包含：

- 原始摘录或摘要：只保留必要片段，不保存网页全文。
- 来源：`source_url`、`source_file`、作者或组织、发布时间、捕获时间。
- 我的初步理解：明确哪些是转述，哪些是个人判断。
- 风险与待验证：来源权威性、过期风险、冲突风险、需要补充的实验或文档。
- 下一步处理：是否值得进入 distilled，审核标准是什么。

raw 只能作为后续提炼和学习材料。任何来自 raw 的项目建议都必须标注“未经审核，不能作为正式项目规则”。

### rule

用途：保存人工审核后的正式工程规则。

正文必须包含：

- 一句话结论。
- 适用场景和不适用场景。
- 正式规则：必须、默认、禁止、例外。
- 原因：工程权衡、风险和替代方案。
- 实施方式：落地步骤、迁移策略、代码审查关注点。
- 验证方式：测试、benchmark、日志、监控、人工验收或项目复盘证据。
- Codex / Agent 指令：可直接用于项目任务上下文。

rule 必须位于 `rules` 或 `deprecated` 等生命周期目录中，并且只有 `review_required=false`、`status=active` 且有审核记录时才是默认可信规则。

### checklist

用途：保存可执行检查清单。

正文必须包含：

- 使用时机、责任人和输出物。
- 不适用场景。
- 检查项，使用 `- [ ]` 格式。
- 高风险项和阻断条件。
- 每个关键检查项的证据要求。
- Codex / Agent 执行时需要反馈的结果。

checklist 不是说明文章。每个检查项都应能被人工、测试、日志、截图或 benchmark 验证。

### snippet

用途：保存可复用代码、命令、配置或提示词片段。

正文必须包含：

- 语言、框架、运行环境、依赖版本和输入输出。
- 不适用场景：版本限制、安全限制、性能限制和禁止直接复制的条件。
- 片段正文，使用 fenced code block。
- 使用方式：需要替换的变量、集成位置和运行步骤。
- 风险与注意：安全、性能、兼容性和维护成本。
- 验证方式：运行命令、预期输出和失败排查。

snippet 必须足够具体，不能只保存模糊提示词或未经验证的代码。

### pitfall

用途：保存常见坑、失败模式、事故原因或容易误用的实践。

正文必须包含：

- 症状：如何识别问题。
- 根因：为什么会发生。
- 触发条件：哪些技术栈、规模、版本或流程会触发。
- 影响范围：可靠性、性能、安全、UI、协作或数据风险。
- 避免方式：明确禁止事项和推荐替代方案。
- 验证方式：如何证明风险已被覆盖。

pitfall 可以先进入 distilled；成为正式规则前需要人工审核并迁移或 promote 到 `rules`、`checklists` 或 `snippets` 中的合适形式。

### adr

用途：保存架构决策记录。

正文必须包含：

- Context：决策背景、约束、目标和非目标。
- Decision：被采用的方案。
- Alternatives：考虑过但未采用的方案。
- Consequences：正面影响、负面影响和后续成本。
- Scope：适用项目、时间窗口和撤销条件。
- Review：何时复查、由谁复查、用什么证据复查。

ADR 不等于全局规则。只有被提炼并审核后的规则，才能进入 `rules` 成为默认项目指导。

### changelog

用途：保存版本变化、破坏性变更、迁移说明或依赖升级记录。

正文必须包含：

- 变化摘要。
- 影响版本或时间范围。
- Breaking changes。
- Migration steps。
- 风险和回滚策略。
- 需要更新的规则、snippet 或 checklist。

changelog 通常进入 `raw` 或 `distilled`，不能直接变成正式规则；正式影响必须通过 promote 流程进入 `rules`、`snippets` 或 `checklists`。

## 4. 文件命名规范

文件名必须稳定、可读、可排序，不能使用 `untitled`、`test`、`final`、`copy`、`new`、`temp` 等无语义名称。

通用规则：

- 使用小写 ASCII、数字和连字符。
- 不使用空格、中文标点、特殊符号或自动生成的随机长串。
- 文件名表达主题，不表达临时状态。
- 日期只用于 raw、changelog、报告或明确需要时间排序的内容。
- 同主题多文件通过 `type`、`topic_id` 和 `canonical_id` 区分，而不是 `final-v2-copy`。

推荐格式：

```text
raw/YYYY/MM/<source-slug>/<YYYY-MM-DD-topic-slug>.md
distilled/<topic-family>/<topic-slug>-draft.md
rules/<topic-family>/<topic-slug>.md
checklists/<topic-family>/<topic-slug>-checklist.md
snippets/<topic-family>/<language-or-tool>/<topic-slug>.md
deprecated/<topic-family>/<topic-slug>.md
```

当前代码仍兼容已有的 `knowledge/<category>/<layer>/<filename>.md` 扁平路径。新规范用于后续新增内容和迁移计划，不要求本轮移动已有 `knowledge/**/*.md`。

## 5. 目录分片策略

10W+ 文档时不能把所有文件放进一个目录。单目录文件数过大将拖慢文件系统枚举、编辑器浏览、备份、Git diff、人类审查和未来 GUI 文档列表。

建议控制：

- 单个叶子目录目标不超过 500 个 Markdown 文件。
- 超过 1,000 个文件必须分片。
- raw 优先按 `year/month` 或 `source/topic` 分片。
- rules、checklists、snippets 优先按 topic family 分片。
- snippets 可再按 `language`、`framework` 或 `tool` 分片。
- deprecated/rejected/quarantine 保留原主题分片，方便追溯历史。

raw 分片示例：

```text
knowledge/01-frontend/raw/2026/05/react/2026-05-18-react-managing-state.md
knowledge/09-ai-agent/raw/2026/05/openai/2026-05-18-codex-sandboxing.md
knowledge/03-ui-ux/raw/apple-hig/layout/2026-05-18-apple-hig-layout.md
```

正式层分片示例：

```text
knowledge/01-frontend/rules/react/state-management.md
knowledge/01-frontend/checklists/performance/core-web-vitals-release-checklist.md
knowledge/09-ai-agent/snippets/codex/agent-task-template.md
```

archive/raw 历史内容应进入 archive workspace 或 archive 目录。100K+ 场景优先 active/archive workspace 分离，每个 workspace 使用独立 `.kb/index.sqlite`，而不是把所有历史资料塞进单个活跃索引。

## 6. 文件大小与附件策略

Markdown 卡片应短而结构化。建议：

- 普通知识卡片目标 2KB 到 20KB。
- 单文件超过 50KB 应考虑拆分。
- 单文件超过 100KB 必须说明原因，并优先拆成多个 topic card。
- 搜索命中的 chunk 应能独立说明问题，不依赖整篇长文。

不要保存网页全文。raw 只保存必要摘录、摘要、关键引用、来源链接、访问时间、待验证问题和自己的理解。网页全文会带来版权风险、噪音、重复、过期内容和索引膨胀。

附件、PDF、图片不要直接塞进 Markdown 正文。推荐做法：

- Markdown 只记录附件路径、来源、摘要、页码或截图说明。
- PDF 和图片放入受控资产目录或外部资料库，并记录 `source_file`。
- 大型二进制文件不进入默认 Markdown 搜索路径。
- 对重要图片或 PDF，只提炼与工程规则相关的文字摘要进入 raw/distilled。

## 7. 原子写入策略

任何修改 Markdown 的 service/core API 必须使用原子写入，避免 GUI 崩溃、断电、进程中断或并发任务导致半写文件。

推荐流程：

1. 读取原文件并解析 frontmatter。
2. 校验 schema、layer、status、filename 和 source chain。
3. 在同一目录写入临时文件，例如 `.target.md.tmp.<pid>`。
4. 使用 UTF-8 和 LF 换行写完整 frontmatter 与正文。
5. 刷新文件内容，条件允许时执行 fsync。
6. 再次解析临时文件，确认 frontmatter 可读。
7. 使用原子 rename/replace 替换目标文件。
8. 记录操作结果，必要时触发增量 index。

同一目标文件的写入必须串行化。长任务不得边扫描边直接覆盖 Markdown；应先生成 plan 或变更集，再由用户确认后通过 service/core 执行。

## 8. GUI / EXE 写入边界

未来 GUI 不得直接读写 Markdown 或 SQLite，也不得通过拼接 CLI 命令字符串作为主要集成方式。正确边界是：

```text
Desktop GUI
  -> service layer
  -> knowledge_core
  -> Markdown + SQLite + Local Backup/Snapshot
  -> Optional Git Sync
```

GUI 写入必须通过 service/core API，由 core 负责：

- schema 校验。
- 文件名校验。
- 目录分片选择。
- 原子写入。
- 生命周期链路更新。
- 增量 index 调度。
- 错误详情和日志路径。

UI 主线程不得执行 index、audit、secret-scan、reindex、dedupe、conflicts、benchmark、maintenance、Optional Git Sync 或 backup/export。

## 9. 来源链路与生命周期保留

promote、deprecate、quarantine 都必须保留来源链路。不得为了整理目录而切断历史。

关键字段职责：

- `source_url`: 外部网页、官方文档、GitHub、论文、视频或论坛来源。
- `source_file`: 本地来源文件、PDF、截图、会议记录或导入文件路径。
- `promoted_from`: 正式层卡片从哪个 distilled 文件提升而来。
- `supersedes`: 当前卡片替代了哪些旧卡片。
- `superseded_by`: 当前卡片被哪个新卡片替代。
- `deprecated_reason`: 曾经有效但已废弃的原因。
- `rejected_reason`: 审核后明确拒绝的原因。
- `quarantined_reason`: 隔离原因。

promote 是人工审核动作，必须记录 `reviewed_by`、`confidence`、`valid_for`、`verification_method` 和 `review_note`。deprecate、reject、quarantine 也必须保留原因，不得直接删除历史记录。

## 10. topic_id 与 canonical_id

`topic_id` 是跨层级追踪主题的稳定标识。raw、distilled、rules、checklists、snippets、deprecated 都可以共享同一个 `topic_id`，用于把来源、提炼、正式规则和历史替代关系串起来。

推荐格式：

```text
<category>.<topic-slug>
```

示例：

- `frontend.react-state-management`
- `performance.core-web-vitals`
- `ai_agent.codex-sandboxing`

`canonical_id` 用于标记同一主题下当前推荐采用的 canonical 知识。通常只给人工审核后的 active formal cards 设置。

推荐格式：

```text
<topic_id>.<type>
```

示例：

- `frontend.react-state-management.rule`
- `performance.core-web-vitals.checklist`
- `ai_agent.codex-sandboxing.snippet`

长期治理中，`topic_id` 用于 dedupe、conflicts、canonical-report、archive-plan 和迁移计划；`canonical_id` 用于让 Agent 和未来 GUI 找到当前推荐版本。

## 11. Markdown schema version 与 migration

Markdown schema 必须版本化。新卡片建议写入：

```yaml
schema_version: 1
```

schema migration 只迁移 Markdown，不以 SQLite 为事实来源。每次 schema 变更必须说明：

- 变更目的。
- 新增、删除、重命名或语义变化的字段。
- 影响哪些 layer 和 type。
- 是否需要回填已有文件。
- migration 是否可逆。
- 如何 dry-run。
- 如何验证。
- 如何重建 `.kb/index.sqlite`。

迁移原则：

- 默认先生成 plan，不自动批量改文件。
- 修改前依赖 Git 记录或备份。
- 使用 service/core 原子写入。
- 保留旧字段直到迁移完成并经过审核。
- 不通过手工编辑 SQLite 来修复 Markdown schema。
- migration 完成后运行 `lint`、`audit`、`secret-scan` 和索引重建验证。

## 12. Markdown 与 SQLite index 同步关系

SQLite index 的内容来自 Markdown：

- `index` 扫描 Markdown 文件。
- 解析 frontmatter 得到 metadata。
- 解析正文并切 chunk。
- 写入 `documents`、`chunks` 和 `chunks_fts`。
- App startup、Dashboard、Category View、Search View、Review Queue、Archive / Trash View 默认读取 SQLite metadata / FTS5。
- 搜索默认只查 SQLite FTS5 / 索引，不全量读取 Markdown。
- Category View 从 `documents` metadata 聚合 category/layer/status/review_required/confidence 统计并分页查询。
- Search View 用 SQLite FTS5 查询 chunk，并用 `documents` metadata 做 layer/status/category/source_type/confidence hard filter。
- Review Queue 从 `documents` metadata 查询待审核项。
- Archive / Trash View 从 `documents` metadata 分页查询列表。
- Markdown 只作为 source of truth；`open` / `edit` / `index` / `reindex` / `doctor` / `promote` / `archive` / `restore` / `backup` 等明确操作才读取 Markdown。

同步方向只能是：

```text
Markdown -> parser -> SQLite index -> search/audit/report
```

不能把 SQLite 中的状态当成事实反写 Markdown，除非该写入动作本身由 service/core 针对 Markdown 执行，并保留完整审计链路。

未来 EXE 启动必须遵守 SQLite-hot / Markdown-source 运行时边界：

- App startup 只读 SQLite metadata、workspace status、index status、cached stats 和最近任务摘要。
- App startup 不扫描 `knowledge/`，不读取所有 Markdown，不自动触发 index。
- `workspace-status` 是轻量命令，只读 SQLite/config/cache，不读 Markdown，不 hash，不 index。
- `.kb/index.sqlite` missing 时，GUI / service 只显示 `index_status=missing` 和受限能力，并提供后台 index/reindex 任务；不得扫描 Markdown 来补全统计。
- 后台 index/reindex 可以读取 Markdown 并重建 `.kb/index.sqlite`，但不得把 SQLite 当作事实来源修改 Markdown。

删除或损坏 `.kb/index.sqlite` 后，可以从 Markdown 重建：

```powershell
Remove-Item -Force .kb/index.sqlite
python scripts/kb.py index
python scripts/kb.py doctor
python scripts/kb.py stats
```

重建过程中不得修改 `knowledge/**/*.md`。如果 Markdown schema 与当前索引器不兼容，应先做 Markdown schema migration，再重建索引。

## 13. 本阶段验收边界

本阶段只完成设计与模板约束：

- 新增 Markdown storage 设计文档。
- 新增 Markdown schema 文档。
- 更新模板字段。
- 更新 README 和 AGENTS 规则。
- 保持默认 search 行为不变。
- 保持 SQLite schema 不变。
- 不移动、删除或修改任何现有 `knowledge/**/*.md`。

