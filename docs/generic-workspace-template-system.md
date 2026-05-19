# Generic Workspace / Template System Design

本文定义 `personal-knowledge-base` 从“开发者知识库”升级为“通用知识库引擎”的 workspace、template、category、配置定制、索引隔离和未来命令规划。当前阶段只做设计文档、README、AGENTS 规则和未来命令规划；不实现 GUI、EXE、RSS、向量检索、MCP、Codex Skill，不修改 `knowledge/**/*.md`，不修改 SQLite schema，也不改变现有 `search`、`index`、`audit` 行为。

## 1. Workspace 概念

Workspace 是一个独立知识库实例。一个 workspace 至少包含：

```text
workspace-root/
  knowledge/
  config/
  templates/
  reports/
  .kb/
    index.sqlite
  workspace.yaml
```

核心边界：

- 每个 workspace 有独立 `knowledge/`，Markdown 仍然是事实来源。
- 每个 workspace 有独立 `config/`，包括 categories、sources、learning-radar、extract-rules、quality-rules 等配置。
- 每个 workspace 有独立 `templates/`，用于该 workspace 的卡片模板、报告模板和提炼模板。
- 每个 workspace 有独立 `reports/`，audit、maintenance、learning queue、category digest 等报告不跨 workspace 混写。
- 每个 workspace 有独立 `.kb/index.sqlite`，它是该 workspace 的可重建索引，不是事实来源。
- `workspace.yaml` 是 workspace 级元数据入口，用于创建、打开、升级、备份、恢复和未来 GUI/EXE 的 workspace 切换。
- 不同 workspace 可以使用不同模板。例如开发者知识库、设计知识库、产品知识库、研究知识库或自定义知识库。

未来 GUI/EXE 支持打开、创建、切换 workspace，但必须通过 service/core API；GUI 不得直接读写 Markdown 或 SQLite。workspace 切换只应打开目标 workspace 的 `workspace.yaml` 和 `.kb/index.sqlite` 元数据，不扫描其他 workspace。

## 2. Workspace Metadata

`workspace.yaml` 是 workspace 根目录下的稳定元数据文件。建议结构：

```yaml
workspace_id: "pkb-dev-20260519-a1b2c3d4"
display_name: "Developer Knowledge Base"
description: "Engineering rules, snippets, checklists and reviewed references."
template_id: "developer"
schema_version: "1.0"
created_at: "2026-05-19T00:00:00+08:00"
updated_at: "2026-05-19T00:00:00+08:00"
app_version_created: "1.3.0"
app_version_last_opened: "1.3.0"
default_language: "zh-CN"
storage_mode: "local"
git_enabled: false
backup_enabled: true
index_status:
  state: "missing" # missing | ready | stale | rebuilding | error
  schema_version: ""
  document_count: 0
  chunk_count: 0
  last_error: ""
last_indexed_at: ""
```

字段说明：

| field | 含义 |
| --- | --- |
| `workspace_id` | 稳定身份，不随显示名称、目录名或模板升级改变 |
| `display_name` | 用户可编辑名称，只用于 UI 和报告展示 |
| `description` | 用户可编辑描述 |
| `template_id` | 初始或当前主模板，例如 `developer`、`research`、`custom` |
| `schema_version` | workspace 配置和 Markdown schema 兼容版本 |
| `created_at` / `updated_at` | workspace 元数据创建和更新时间 |
| `app_version_created` | 创建 workspace 时的应用版本 |
| `app_version_last_opened` | 最近打开 workspace 的应用版本，用于升级提示 |
| `default_language` | 默认内容语言，不限制卡片混合语言 |
| `storage_mode` | 当前只设计 `local`，不引入云同步依赖 |
| `git_enabled` | Optional Git Sync 是否启用，默认 `false` |
| `backup_enabled` | 本地 Backup/Snapshot 是否启用，默认 `true` |
| `index_status` | 当前 workspace 索引状态摘要，只是可重建索引元数据 |
| `last_indexed_at` | 最近索引成功时间 |

`workspace.yaml` 不应记录真实密钥、token、客户隐私或不可恢复的运行时缓存。

## 3. Template System

Template 是创建 workspace 时的初始结构、配置和默认规则包。Template 不替代用户配置，也不得在后续应用时静默覆盖用户已有配置。模板应用到已有 workspace 必须生成 migration plan。

内置模板建议：

- Developer Knowledge Base：工程规则、代码片段、检查清单、技术调研和 Agent 上下文。
- Designer Knowledge Base：设计系统、交互模式、视觉规范、可访问性、设计评审记录。
- Product Knowledge Base：PRD、用户路径、指标、竞品、功能决策、发布检查。
- Research Knowledge Base：论文、实验、资料摘录、研究问题、证据链和引用管理。
- AI Agent Knowledge Base：Agent 工作流、工具边界、提示词、治理规则、安全检查。
- Custom Knowledge Base：最小默认结构，用户自行定义分类、来源、质量规则和模板。

每个模板必须包含：

- `categories`：默认分类集合和稳定 `category_id`。
- `layers`：生命周期层，例如 raw、distilled、rules、snippets、checklists、deprecated、rejected、quarantine。
- `types`：知识卡片类型，例如 rule、checklist、snippet、raw_note、pitfall、adr、changelog、research_note。
- `sources`：默认来源配置，例如 manual、official_docs、github_repo、paper、internal_practice。
- `learning-radar`：学习目标、关注主题、忽略主题、输出目标。
- `extract-rules`：从 raw 提炼到 distilled 的结构化规则。
- `quality-rules`：schema、来源、review、confidence、valid_for、verification_method 等质量门禁。
- `source-policy`：允许来源、禁止来源、权威优先级、未经审核内容边界。
- `templates`：Markdown 卡片模板、报告模板、review 模板。
- `review workflow defaults`：默认 review cycle、review queue 排序、promote 门禁。
- `dashboard defaults`：未来 GUI 的默认统计卡片、过滤器、分组和空状态。

Template 只提供初始值和建议。正式项目使用仍必须遵守 raw -> distilled -> review -> formal 的治理闭环。

## 4. Template Package Structure

模板目录建议：

```text
templates_catalog/
  developer/
    template.yaml
    config/
      categories.yaml
      sources.yaml
      learning-radar.yaml
      extract-rules.yaml
      quality-rules.yaml
      source-policy.yaml
    templates/
      raw-note.md
      rule.md
      checklist.md
      snippet.md
      review-note.md
    README.md
  research/
    template.yaml
    config/
      categories.yaml
      sources.yaml
      learning-radar.yaml
      extract-rules.yaml
      quality-rules.yaml
      source-policy.yaml
    templates/
      research-note.md
      paper-summary.md
      evidence-card.md
      review-note.md
    README.md
```

`template.yaml` 必须包含：

```yaml
template_id: "developer"
display_name: "Developer Knowledge Base"
description: "Engineering knowledge base for rules, snippets, checklists and reviewed references."
version: "1.0.0"
categories:
  - category_id: "frontend"
    display_name: "Frontend"
    path: "knowledge/01-frontend"
    status: "active"
layers:
  - "raw"
  - "distilled"
  - "rules"
  - "snippets"
  - "checklists"
  - "deprecated"
  - "rejected"
  - "quarantine"
types:
  - "raw_note"
  - "rule"
  - "checklist"
  - "snippet"
  - "pitfall"
  - "adr"
  - "changelog"
default_sources:
  - "manual"
  - "official_docs"
  - "github_repo"
  - "internal_practice"
default_quality_policy:
  require_frontmatter: true
  require_source_for_formal: true
  require_review_for_formal: true
  secret_scan_required: true
default_extract_rules:
  require_actionable_output: true
  distilled_review_required: true
supported_languages:
  - "zh-CN"
  - "en"
intended_use:
  - "personal engineering rules"
  - "project implementation guidance"
  - "reviewed snippets and checklists"
not_intended_for:
  - "unreviewed web clipping archive"
  - "customer secret storage"
  - "legal or medical advice without domain review"
```

模板包必须可校验、可导出、可导入。导入第三方模板时必须运行 schema validation 和 secret-scan，并显示来源、版本、将写入的文件、将修改的配置和回滚方式。

## 5. Category Management

Category 是 workspace 内的知识分类。分类必须采用稳定身份模型：

- `category_id` 是稳定身份，用于 frontmatter、SQLite、配置引用、报告引用和未来 GUI 内部引用。
- `display_name` 可编辑，只用于 UI、报告标题和用户可读展示。
- `path` 可迁移，但必须 plan-first，不能随意改。
- 不能把 `display_name` 当作内部 ID。
- 删除分类默认禁止。
- 支持 `disable`、`archive`、`merge`、`restore`，优先替代永久删除。
- 非空分类不能直接 delete。
- category rename path 需要 migration plan。
- category merge 需要影响分析和 rollback plan。
- category 操作不能破坏 `source_url`、`source_file`、`promoted_from`、`supersedes`、`superseded_by` 等来源链路。

建议分类配置：

```yaml
categories:
  frontend:
    category_id: "frontend"
    display_name: "Frontend"
    path: "knowledge/01-frontend"
    status: "active" # active | disabled | archived | merged
    description: "Frontend engineering knowledge."
    merged_into: ""
    archived_at: ""
    updated_at: "2026-05-19T00:00:00+08:00"
```

分类 path 迁移不是简单重命名目录。必须先生成计划，列出受影响文件、frontmatter、索引、报告、来源链路、备份需求和回滚计划。

## 6. Customization Rules

用户可以自定义：

- `categories`
- `sources`
- `extract-rules`
- `quality-rules`
- `review cycles`
- `templates`

约束：

- 不得破坏 required fields。
- 不得绕过 raw -> distilled -> review -> formal。
- 不得让 RSS/source 自动进入 `rules`、`snippets`、`checklists`。
- 不得禁用 secret-scan / audit 的安全边界。
- 不得把 `review_required=true` 的内容作为项目决策依据。
- 不得让 raw、distilled、learning queue 或 research 结果默认进入正式搜索。
- 修改 schema 需要 migration plan，包含影响字段、影响层级、dry-run、原子写入、回滚、验收命令和如何从 Markdown 重建 SQLite index。
- Template 应用到已有 workspace 时不得覆盖用户已有配置，必须输出 diff、冲突和建议迁移路径。

允许用户降低噪音，例如禁用某个 source、调整 review cycle、添加自定义卡片模板；不允许用户关闭治理底线，例如 formal 知识不审核、secret-scan 永久禁用或来源链路丢失。

## 7. Per-workspace Index

每个 workspace 有自己的 `.kb/index.sqlite`：

- workspace A 的搜索只打开 workspace A 的 `.kb/index.sqlite`。
- workspace B 的搜索只打开 workspace B 的 `.kb/index.sqlite`。
- workspace 切换时关闭当前 index connection，再打开目标 workspace 的 index metadata。
- startup 只读取当前 workspace 的 `workspace.yaml` 和 `.kb/index.sqlite` 元数据。
- startup 不扫描其他 workspace，不全量读取 Markdown，不自动全量 index。
- `.kb/index.sqlite` 可删除重建，不能手工编辑，不能当作事实来源。
- cross-workspace search 是未来增强，不是本阶段目标。
- archive workspace 可以单独存在，用于长期历史和低频资料隔离。

跨 workspace 搜索未来必须显式触发，且仍要遵守 layer、status、source_type、confidence、review_required、archive_status 等 hard filter。

## 8. Workspace Lifecycle

### Create Workspace

输入 workspace 路径、display name、template_id、default_language。创建 `workspace.yaml`、目录结构、模板配置和空 `.kb/`。不应自动抓取外部内容，不应自动 index 大量文件。

### Open Workspace

读取 `workspace.yaml` 和 index metadata。若 index missing/stale，只提示状态，不阻塞打开，不扫描全库。

### Close Workspace

关闭 index connection、释放文件句柄、保存最近任务状态。不得隐式运行 maintenance 或 backup。

### Switch Workspace

关闭当前 workspace，再打开目标 workspace。不得扫描所有 workspace。最近 workspace 列表只能来自应用级 registry 或用户显式选择，不通过全盘搜索发现。

### Rename Workspace Display Name

只修改 `workspace.yaml.display_name` 和 `updated_at`。不移动目录，不重建索引，不改变 `workspace_id`。

### Export Workspace

生成可复制导出包，包含 Markdown、config、templates、reports、docs、README、AGENTS 和 manifest。默认不把 `.kb/index.sqlite` 当作核心资产，可选包含。

### Backup Workspace

创建本地 backup/snapshot。高风险操作前建议 backup，workspace upgrade、restore、schema migration 前应要求 snapshot。

### Restore Workspace

先 dry-run，展示将恢复的文件、冲突、覆盖风险、index 重建建议和 secret/privacy 风险。确认后恢复，随后建议运行 `index`、`doctor`、`audit`、`secret-scan`。

### Upgrade Workspace Schema

先生成 upgrade plan。计划必须包含当前 schema、目标 schema、影响字段、影响层级、dry-run、原子写入、回滚、snapshot 要求和验收命令。

### Archive Workspace

archive workspace 是把整个 workspace 标记为低频或历史，而不是删除。archive 后仍可显式打开、搜索和 restore。archive 前建议 backup。

### Delete Workspace

默认只允许空 workspace delete。非空 workspace 删除必须要求 backup + confirmation，并明确 `.kb/index.sqlite` 可重建但 Markdown 不可从索引恢复。删除不应依赖 Git。

## 9. Future Commands

以下命令只做设计，不在本阶段实现。

| command | 只读 | 写文件 | 需要 snapshot | 需要人工确认 | 输出 |
| --- | --- | --- | --- | --- | --- |
| `workspace-list` | 是 | 否 | 否 | 否 | 已注册 workspace 摘要、路径、模板、index 状态 |
| `workspace-create` | 否 | 是 | 否 | 是 | 创建计划、目标路径、模板文件清单、结果 summary |
| `workspace-open` | 是 | 否 | 否 | 否 | workspace metadata、index metadata、stale/missing 提示 |
| `workspace-status` | 是 | 否 | 否 | 否 | workspace.yaml 摘要、index 状态、最近报告、待处理风险 |
| `workspace-export` | 否 | 是 | 建议 | 是 | export manifest、文件数量、大小、是否包含 `.kb` |
| `workspace-backup` | 否 | 是 | 不适用 | 是 | backup manifest、hash 摘要、secret-scan 提示 |
| `workspace-restore` | 否 | 是 | 是 | 是 | restore dry-run、冲突、覆盖清单、执行结果 |
| `workspace-upgrade-plan` | 是 | 否 | 否 | 否 | schema diff、影响范围、snapshot 要求、验收命令 |
| `template-list` | 是 | 否 | 否 | 否 | 可用模板、版本、适用场景、不适用场景 |
| `template-create` | 否 | 是 | 建议 | 是 | 新模板目录、template.yaml、默认 config/templates 清单 |
| `template-apply` | 否 | 是 | 是 | 是 | migration plan、配置 diff、冲突、回滚方式 |
| `template-export` | 否 | 是 | 否 | 是 | 模板包、manifest、校验结果 |
| `template-import` | 否 | 是 | 建议 | 是 | 来源、写入文件、schema validation、secret-scan 结果 |
| `category-list` | 是 | 否 | 否 | 否 | category_id、display_name、path、status、counts、references |
| `category-update-display-name` | 否 | 是 | 否 | 是 | display name diff、受影响报告展示项 |
| `category-archive-plan` | 是 | 否 | 否 | 否 | affected files、search/index impact、snapshot 建议、restore plan |
| `category-merge-plan` | 是 | 否 | 否 | 否 | source/target、frontmatter changes、config refs、rollback plan |
| `category-delete-plan` | 是 | 否 | 否 | 否 | empty check、references、blocking files、confirmation requirements |

执行类命令未来应与 plan 命令分离，例如 `category-archive-apply`、`category-merge-apply`、`workspace-upgrade-apply`。本阶段仅规划 plan 命令。

## 10. GUI Implications

本阶段不做 GUI，只规划未来页面和 service dependency。

| Page | 目的 | Service dependency | 危险操作确认 | Empty/error states |
| --- | --- | --- | --- | --- |
| Workspace Selector | 打开、创建、切换 workspace，显示最近 workspace | `WorkspaceService`、`IndexMetadataService` | 删除/移除最近项、打开缺失路径需确认 | 无 workspace、路径不存在、schema 不兼容、index missing |
| Template Picker | 新建 workspace 时选择模板，查看 intended/not intended use | `TemplateService`、`WorkspaceCreationService` | 使用第三方模板、覆盖默认模板需确认 | 无可用模板、模板校验失败、语言不支持 |
| Workspace Settings | 编辑 display_name、description、language、backup/git 选项 | `WorkspaceService`、`BackupService`、`OptionalGitService` | schema upgrade、archive/delete workspace 需确认 | metadata 损坏、backup 不可用、Git 不可用 |
| Category Settings | 查看分类、计数、状态，生成 rename/archive/merge/delete plan | `CategoryService`、`PlanService`、`IndexMetadataService` | archive、merge、advanced delete empty category 需确认 | 无分类、分类配置冲突、index stale |
| Source Settings | 管理来源、启用/禁用、source-policy、learning focus | `SourceService`、`QualityPolicyService` | 导入第三方来源、启用自动采集需确认 | 无来源、URL 无效、policy 冲突 |
| Template Manager | 导入、导出、创建、升级模板，比较模板和 workspace 配置 | `TemplateService`、`MigrationPlanService` | template-apply、template-import 需确认 | 模板缺字段、版本冲突、校验失败 |
| Backup & Restore | 创建 backup/snapshot，查看 restore dry-run 和恢复历史 | `BackupService`、`SnapshotService`、`VersioningService` | restore、delete backup、workspace delete 需确认 | 无 backup、备份损坏、空间不足、secret-scan 风险 |

GUI 约束：

- GUI 不直接读写 Markdown 或 SQLite。
- GUI 不通过拼接 CLI 命令字符串作为主要集成方式。
- 长任务必须后台化，提供 task_id、status、progress、cancellation、error detail、log path 和 result summary。
- UI 主线程不得执行 index、audit、secret-scan、reindex、dedupe、conflicts、benchmark、maintenance、Optional Git Sync 或 backup/export。
- Workspace startup 只读当前 workspace metadata / index metadata，不扫描所有 workspace。
- 危险操作必须 plan-first，并优先创建 local snapshot / backup。

## 11. Acceptance Boundary

本设计进入 v1.3.0 实现准备前，应保持以下验收边界：

- 现有 `python scripts/kb.py search` 默认行为不变。
- 现有 `index`、`audit`、`secret-scan`、smoke test 不变。
- 不修改现有 `knowledge/**/*.md`。
- 不引入 GUI/EXE/RSS/vector/MCP/Skill 实现。
- 新增 workspace/template/category 能力先以 plan-only 命令设计落地，再进入 service/core 实现。
