# Workspace Creation Wizard Design

本文定义 v2.0.0-beta.5 起点阶段的“新建知识库”向导设计和 GUI 合同。本阶段只做设计文档，不实现真实创建逻辑，不新增 mutation UI，不修改 `knowledge/**/*.md`，不修改 SQLite schema，不改变 `search` / `index` / `audit` 行为，不自动创建 workspace。

## 1. Scope

目标：

- 让第一次使用的普通用户不仅能选择已有 workspace，也能理解如何安全创建一个新 workspace。
- 定义向导步骤、状态、错误提示、创建计划预览和验收边界。
- 明确未来 service 边界：创建必须 plan-first，执行必须由未来 `WorkspaceCreateService` 承担，长任务可接入 `TaskQueueService`。

非目标：

- 不做 installer、one-file、code signing 或 auto update。
- 不做 AI、RSS、vector search、template marketplace 或自动采集。
- 不做真实创建命令，不创建 `workspace.yaml`，不写任何新 workspace 目录。
- 不暴露 category、archive、delete、merge、template apply、restore 等 mutation UI。
- 不把安装目录、当前工作目录或任意无确认目录自动当作 workspace。

平台和设计模式：

- 目标平台是 Windows desktop GUI，当前推荐实现路线仍是 PySide6 / Qt for Python。
- 本设计属于中等规模 GUI 模块合同，必须复用现有 `View -> ViewModel -> Adapter -> knowledge_app.services` 边界。
- 主布局必须自适应，不使用主布局绝对坐标；最小窗口下向导内容应可滚动，超宽窗口下应限制内容宽度。

## 2. User Scenarios

### 2.1 第一次安装后没有 workspace

用户首次启动 EXE，没有最近 workspace，也没有通过命令行传入 `--workspace`。

期望体验：

- 进入 Workspace Gate。
- Gate 显示两个明确入口：`选择已有知识库` 和 `新建知识库`。
- 点击 `新建知识库` 进入向导。
- 未点击确认前，应用不得创建目录、不得写配置、不得创建 `.kb`、不得运行 index。

### 2.2 用户想新建个人知识库

用户想在 `D:\Knowledge\PersonalKB` 或文档目录下创建一个本地知识库。

期望体验：

- 用户选择父目录或目标目录。
- 用户输入知识库名称。
- 用户选择模板，例如 `个人资料` 或 `学习`。
- 系统展示创建计划：将创建哪些目录、哪些配置文件、是否包含 `backups/`、不会创建正式知识、不会运行 index。
- 用户确认后，未来执行服务才允许写入。
- 创建成功后回到 workspace gate/status，显示 workspace 已选择且 `index_status=missing`。

### 2.3 用户已有旧目录但不是 workspace

用户选择一个已有资料目录，例如 `D:\Notes`，其中已有 Markdown、PDF 或杂项文件，但没有 `workspace.yaml`。

期望体验：

- 向导不得直接在该非空目录中初始化。
- 向导显示“该文件夹已存在内容，不能直接初始化”的安全提示。
- 推荐选项是创建一个新的子目录，例如 `D:\Notes\Personal Knowledge Base`。
- 若未来支持在非空目录中初始化，必须先生成 plan，展示冲突、将写入的文件、不会导入旧资料、不会扫描旧资料，并要求用户显式确认。
- 旧资料导入不是本阶段能力；未来也必须走单独 import plan，不得混入 workspace creation。

## 3. Wizard Steps

### Step 1: 选择创建位置

输入：

- 父目录或目标目录路径。
- 可选“在此目录下创建新文件夹”开关。

规则：

- 默认推荐在用户数据目录、文档目录或用户显式选择的本地目录下创建。
- 不得默认使用软件安装目录。
- 不得默认使用当前进程工作目录。
- 只允许本地文件系统路径；网络盘、同步盘或受限目录可以允许但必须显示风险提示。
- 只做路径存在性、权限和是否为空的轻量检查；不得扫描已有文件内容，不得读取 Markdown，不得递归枚举子树。

状态：

- 空路径：禁用下一步。
- 路径不存在：计划中显示将创建目标目录。
- 路径存在且为空：允许继续。
- 路径存在且非空：默认 blocked，除非用户选择创建子目录或未来生成非空目录初始化 plan。
- 路径位于安装目录：blocked。
- 权限不足：blocked。

### Step 2: 输入知识库名称

输入：

- `display_name`：用户可读名称，例如“我的知识库”。
- 可选描述：用于 `workspace.yaml.description`。

规则：

- `display_name` 只用于 UI 和报告展示，不得作为稳定 ID。
- `workspace_id` 由未来 service 生成，不能由显示名称推导为唯一身份。
- 目录名可以由名称建议生成，但必须允许用户修改，且必须经过路径校验。
- 名称为空、全空格、过长、包含非法文件名字符时不能继续。

### Step 3: 选择模板

内置模板选项：

| 模板 | 适用场景 | 不适用场景 |
| --- | --- | --- |
| `个人资料` | 私人笔记、生活资料、长期收藏和手动整理 | 自动导入浏览器收藏或网盘资料 |
| `学习` | 课程、读书、论文、主题学习和复盘 | 未审核内容直接进入正式规则 |
| `工作` | 项目经验、会议结论、流程、交付检查清单 | 存放客户隐私、真实密钥或公司敏感数据 |
| `开发者` | 工程规则、代码片段、检查清单、Agent 上下文 | 把 raw/research 结果当项目正式规则 |
| `自定义` | 只创建最小结构，用户后续配置分类和模板 | 自动生成完整分类或迁移旧 workspace |

规则：

- 模板只决定初始目录、配置和卡片模板。
- 模板不得创建正式知识卡片。
- 模板不得自动抓取外部内容。
- 第三方模板导入不是本阶段能力；未来必须先 schema validation、secret-scan 和 template import plan。

### Step 4: 预览将创建的目录和文件

向导必须展示 plan preview，而不是只展示一行确认文案。

预览至少包含：

- workspace 根目录。
- 将创建的目录：`knowledge/`、`config/`、`templates/`、`reports/`、可选 `backups/`。
- 将写入的文件：必须包含 `workspace.yaml`，可包含模板配置和模板 Markdown 文件。
- 不会创建的内容：不会创建正式知识、不会导入旧资料、不会创建索引、不会运行 index。
- `.kb/` 状态：不作为事实来源，可延迟创建；若未来执行阶段为了 task 或 index metadata 创建 `.kb/`，也不得创建 `.kb/index.sqlite` 并不得运行 index。
- 风险和 blockers：非空目录、安装目录、权限不足、路径冲突、文件名冲突、磁盘不可写。
- 验收命令：未来至少包含 `workspace-status`，不包含自动 index。

建议计划结构：

```json
{
  "schema_version": "1.0",
  "operation": "workspace_create",
  "dry_run": true,
  "would_modify": false,
  "blocked": false,
  "blockers": [],
  "target_path": "D:\\Knowledge\\PersonalKB",
  "template_id": "personal",
  "actions": [
    {
      "action": "create_file",
      "path": "workspace.yaml",
      "reason": "workspace metadata entry"
    }
  ],
  "created_directories": ["knowledge", "config", "templates", "reports"],
  "optional_directories": ["backups"],
  "deferred_runtime_directories": [".kb"],
  "will_not_do": [
    "run index",
    "create .kb/index.sqlite",
    "import existing files",
    "create formal knowledge cards",
    "use Git"
  ],
  "validation_commands": [
    "python scripts/kb.py workspace-status --workspace <target>"
  ]
}
```

`actions` 表示计划动作，不表示已执行动作。

### Step 5: 创建前确认

确认页必须让用户看到：

- 目标路径。
- 知识库名称。
- 模板。
- 将创建的目录和文件。
- 安全承诺：不自动 index、不自动导入、不创建正式知识、不依赖 Git、不写安装目录。
- 若目录非空，必须显示额外确认和 plan blockers；默认推荐返回选择新目录。

交互规则：

- `确认创建` 只有在 plan unblocked 时可用。
- `返回` 保留用户已输入内容。
- `取消` 返回 Workspace Gate，不写任何文件。
- 错误态必须保留 plan preview，方便用户判断如何修正。

### Step 6: 创建后进入 workspace gate/status

未来执行成功后：

- GUI 将新 workspace 路径写入应用级最近 workspace 设置，设置仍在 LocalAppData，不写安装目录。
- GUI 调用 `WorkspaceStatusService` 或同等 adapter path 读取新 workspace status。
- 新 workspace 初始状态应显示 `index_status=missing`。
- 不自动运行 `index`、`audit`、`secret-scan` 或 `doctor`。
- 用户可以选择稍后通过后台任务创建索引；该入口不属于 creation wizard 的自动行为。

## 4. Safety Rules

- 不允许在非空目录中直接初始化，除非用户显式确认并先生成 plan。
- 非空目录 plan 必须列出将写入的文件、冲突、风险、回滚建议和不会执行的行为。
- 不自动 index，不创建 `.kb/index.sqlite`。
- 不自动导入资料，不读取旧目录文件内容，不扫描旧目录作为知识库。
- 不创建 `rules`、`checklists`、`snippets` 等正式知识卡片。
- 不把 template、source、RSS 或外部内容自动放入正式层。
- 不依赖 Git；Git 只能作为未来 Optional Git Sync。
- 不写软件安装目录，不把安装目录当 workspace。
- 必须写入 `workspace.yaml`；没有 `workspace.yaml` 的目录不得被视为新建成功的 workspace。
- `workspace.yaml` 不得包含真实密钥、token、客户隐私或不可恢复运行时缓存。
- `.kb/` 是 runtime storage，不是事实来源；可以延迟创建，创建后也不得被当作 source of truth。
- 创建失败不得留下半初始化状态；未来执行服务必须使用临时写入、原子 rename 或可清理的 transaction directory。
- 所有失败必须返回结构化错误，GUI 不得只显示通用“失败”。

## 5. Creation Artifacts

未来创建成功后的最小结构：

```text
workspace-root/
  workspace.yaml
  knowledge/
  config/
  templates/
  reports/
```

可选结构：

```text
workspace-root/
  backups/
```

延迟 runtime 结构：

```text
workspace-root/
  .kb/
```

说明：

- `workspace.yaml` 是 workspace metadata 入口，必须存在。
- `knowledge/` 初始可以为空，或只包含分类目录和空层级目录；不得创建正式知识卡片。
- `config/` 保存模板生成的 categories、sources、quality-rules、extract-rules 等配置。
- `templates/` 保存卡片模板和报告模板。
- `reports/` 初始为空或只包含非知识类初始化说明；不得伪造 audit/report 结果。
- `backups/` 可选，默认可由用户勾选创建，但不应强制。
- `.kb/index.sqlite` 不应在创建向导中生成；索引由用户后续显式后台任务创建。

建议 `workspace.yaml` 字段：

```yaml
workspace_id: "pkb-20260521-a1b2c3d4"
display_name: "我的知识库"
description: ""
template_id: "personal"
schema_version: "1.0"
created_at: "2026-05-21T00:00:00+08:00"
updated_at: "2026-05-21T00:00:00+08:00"
app_version_created: "2.0.0-beta.5"
app_version_last_opened: "2.0.0-beta.5"
default_language: "zh-CN"
storage_mode: "local"
git_enabled: false
backup_enabled: true
index_status:
  state: "missing"
  schema_version: ""
  document_count: 0
  chunk_count: 0
  last_error: ""
last_indexed_at: ""
```

## 6. GUI Interaction Contract

### Workspace Gate

现有 Gate 增加设计入口：

- Primary action：`选择已有知识库`。
- Secondary action：`新建知识库`。
- Gate 文案必须继续说明：不会自动扫描、不会自动创建索引、不会自动修改文件。

当前阶段不实现按钮行为；只定义未来行为。

### Wizard Page Structure

建议组件树：

```text
WorkspaceGateScreen
└── WorkspaceCreationWizard
    ├── WizardStepper
    ├── StepContent
    │   ├── LocationStep
    │   ├── NameStep
    │   ├── TemplateStep
    │   ├── PlanPreviewStep
    │   └── ConfirmationStep
    ├── PlanSummaryPanel
    ├── ErrorPanel
    └── WizardActions
        ├── BackButton
        ├── CancelButton
        ├── NextButton
        └── ConfirmCreateButton
```

布局规则：

- 1100x720 以下：单列，计划预览折叠为下方区域，内容可滚动。
- 1440x900：左侧主步骤，右侧固定宽度 `PlanSummaryPanel`。
- 超宽屏：内容最大宽度限制，避免表单横向拉伸。
- `PlanSummaryPanel` 始终显示目标路径、模板、blocked 状态和将写入数量。
- 长路径必须中间省略，并提供 tooltip 或详情展开。
- 计划预览文件列表必须分页或折叠，避免大模板撑爆窗口。

### Controls

- `选择文件夹`：打开系统目录选择器。
- `知识库名称`：文本输入，显示非法字符和长度错误。
- `模板选择`：卡片或列表，展示适用场景和不适用场景。
- `创建 backups/`：复选框，默认开启或按模板建议，但可关闭。
- `返回`：回到上一步，不丢失输入。
- `取消`：退出向导，不写文件。
- `确认创建`：仅 plan unblocked 且用户在确认页时可用。

### Existing Folder Prompt

当目标文件夹已存在：

- 空文件夹：显示“将初始化为空 workspace”，允许继续。
- 非空文件夹：显示“该文件夹已有内容，默认不能直接初始化”。
- 推荐操作：`创建新子文件夹`、`选择其他位置`。
- 未来高级操作：`生成非空目录初始化计划`，必须 blocked-by-default，并明确不会导入旧资料。

### Error States

错误态至少包括：

- 路径为空。
- 路径位于安装目录。
- 路径权限不足。
- 目标文件已存在且不是目录。
- 目标目录非空。
- `workspace.yaml` 已存在但 schema invalid。
- 模板不可用或模板 schema invalid。
- 计划构造失败。
- 磁盘空间不足。
- LocalAppData 设置不可写。

错误呈现规则：

- 错误必须包含原因、受影响路径、用户可执行的下一步。
- blocked plan 不是异常；GUI 应显示为可读计划和修正建议。
- 代码异常或无法构造 plan 才是失败状态。

## 7. Service Boundary

### WorkspaceCreationPlanService

未来新增 plan-only service。职责：

- 接收目标路径、display name、description、template_id、是否创建 `backups/` 等输入。
- 校验路径、名称、模板、权限和冲突。
- 输出稳定 `PlanResult` 或专用 `WorkspaceCreationPlan`。
- `dry_run=true`、`would_modify=false`。
- `actions` 只表示计划动作。
- `validation_commands` 必须存在。
- 不创建目录，不写文件，不读取 Markdown，不扫描 `knowledge/`，不创建 SQLite。

建议输入：

```json
{
  "target_path": "D:\\Knowledge\\PersonalKB",
  "display_name": "我的知识库",
  "description": "",
  "template_id": "personal",
  "default_language": "zh-CN",
  "create_backups_directory": true,
  "allow_non_empty_directory": false
}
```

### WorkspaceCreateService

未来执行 service。职责：

- 只接受已确认的 plan 或 plan hash。
- 执行前重新校验目标路径和 blockers。
- 写入 `workspace.yaml`、目录结构、模板配置和模板文件。
- 采用原子写入和失败清理策略。
- 不运行 index，不导入旧资料，不创建正式知识，不依赖 Git。
- 返回结构化 `OperationResult`，包含创建摘要、warnings、errors、elapsed_ms。

`WorkspaceCreateService` 当前阶段不得实现。

### TaskQueue Integration

未来可选接入：

- `workspace_create` 可以作为短任务直接执行，也可以通过 `TaskQueueService` 统一调度。
- 若接入 TaskQueue，task input 必须包含 plan hash 和用户 confirmation。
- task progress 必须显示阶段：validate、write workspace.yaml、create directories、write template config、final status check。
- task 完成后调用 `WorkspaceStatusService` 获取初始状态。
- retry 只能针对 failed / cancelled task，必须保留 lineage。

## 8. Acceptance Rules

本阶段验收：

- 新增设计文档，不实现真实创建逻辑。
- README / AGENTS 明确 workspace creation wizard 仍是设计阶段。
- README / AGENTS 明确未来创建逻辑必须 plan-first。
- README / AGENTS 明确不得把安装目录当 workspace。
- 不修改 `knowledge/**/*.md`。
- 不修改 SQLite schema。
- 不改变 search/index/audit 行为。

未来实现验收：

- 创建向导不会在启动时自动出现写操作。
- 用户未确认前不修改任何目录。
- 不自动 index，不创建 `.kb/index.sqlite`。
- 不自动导入资料，不读取旧文件内容，不扫描既有目录作为知识库。
- 不创建正式知识。
- 不依赖 Git。
- 不写安装目录。
- 新建后 `workspace-status` 可读，并显示 `index_status=missing`。
- 空 workspace 不会被自动 index；用户必须显式触发后台 index。
- 非空目录默认 blocked；只有 plan + 显式确认后，未来执行服务才可写入安全的 workspace metadata 和目录结构。

## 9. v2.0.0-beta.5 Recommendation

建议纳入 v2.0.0-beta.5，但仅作为设计阶段交付：

- 文档定义了普通用户首次创建知识库的完整向导。
- 安全边界与现有 Workspace Gate、Local Only mode、SQLite-hot / Markdown-source 模型兼容。
- Service 边界清楚，后续可以先实现 `WorkspaceCreationPlanService`，再实现 `WorkspaceCreateService`。
- 真实创建、导入、索引、模板应用和 mutation UI 必须留到后续阶段，并继续遵守 plan-first、LocalAppData 设置、TaskQueue 和不写安装目录规则。
