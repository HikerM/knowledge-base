# Local Model Installer Design

本文定义 v2.7.0 Local Model Installer 的设计边界。当前阶段只做设计文档和配置草案，不下载模型，不接 ModelScope 实际下载，不接 OpenAI，不接本地 `llama.cpp` / server，不启动模型进程，不执行 shell 下载脚本，不做真实 AI provider，不修改 `knowledge/**/*.md`，不修改 SQLite schema，不改变 `search` / `index` / `audit` 行为，也不执行 mutation。

本设计的目标是让未来普通用户可以在明确知情和确认后安装极轻量本地模型，同时保持模型文件、运行时、AI 控制平面和知识库数据边界清晰。

## 1. Scope

本阶段交付：

- 本地模型安装助手的信息架构。
- 模型档位和默认模型策略。
- ModelScope 来源策略草案。
- 模型存储位置和删除策略。
- 硬件检测和下载前 warning 设计。
- TaskQueue 安装任务设计。
- 未来 runtime boundary 设计。
- 隐私和上下文边界。
- GUI contract。
- 配置草案 `config/local-model-catalog.example.yaml`。
- 未来测试计划。

本阶段不做：

- 不下载模型。
- 不接 ModelScope 实际下载。
- 不接 OpenAI。
- 不接本地 `llama.cpp`、推理 server 或本地 HTTP 服务。
- 不启动模型进程。
- 不执行 shell、PowerShell、batch、curl、wget 或任意下载脚本。
- 不实现真实 AI provider。
- 不修改 GUI 执行逻辑。
- 不把模型放 workspace。
- 不把模型放安装目录。
- 不自动选择大模型。
- 不把 30GB+ 模型作为默认或默认推荐。

## 2. User Flow

未来安装助手只在用户进入 AI 助手设置页并主动打开“本地模型”区域时出现。

建议流程：

```text
AI 助手设置页
  ↓
模型列表和默认推荐
  ↓
硬件检测和磁盘空间检测
  ↓
下载来源、大小、license、sha256 状态预览
  ↓
用户明确确认
  ↓
TaskQueue 创建 model_download task
  ↓
下载进度、取消、错误详情
  ↓
sha256 校验
  ↓
model_register
  ↓
model_health_check
  ↓
可用 / 不可用状态
```

v2.7.0 只设计该流程，不创建上述 service、task 或 UI 交互代码。

## 3. Model Tiers

默认模型必须是 `Qwen3-0.6B-GGUF Q4_K_M` 或等价极轻量档。默认推荐必须面向普通笔记本，显示“适合普通笔记本”和“无需显卡”。所有大小均为 catalog 估算值，正式下载前必须由 catalog 维护者校验 filename、license、expected size 和 sha256。

| Tier | Model | 面向用户 | 最低内存 | 推荐内存 | 是否需要显卡 | 下载大小 | 安装大小 | 是否默认 | 适合任务 | 不适合任务 | 风险提示 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ultra_light` | `Qwen3-0.6B-GGUF Q4_K_M` | 普通笔记本、低配置设备、首次试用 | 4 GB | 8 GB | 否 | 约 0.6 GB | 约 1.0 GB | 是 | 短问答、简单摘要、功能体验、离线隐私模式演示 | 长文档深度总结、复杂推理、多文档综合 | 质量有限，回答可能过短或不稳定；仍需遵守 citation 和 ContextPolicy |
| `light` | `Qwen3-1.7B-GGUF Q4_K_M` | 主流轻薄本、希望质量高于默认档的用户 | 8 GB | 12 GB | 否 | 约 1.4 GB | 约 2.2 GB | 否 | 单篇文档摘要、普通问答、清单草稿 | 大上下文、多轮复杂规划、代码深度审查 | 下载较大，请确认磁盘空间；低内存设备可能变慢 |
| `standard` | `Qwen3-4B-GGUF Q4` | 16 GB 内存设备、希望更稳定摘要的用户 | 12 GB | 16 GB | 否 | 约 3.0 GB | 约 5.0 GB | 否 | 较长文档摘要、结构化提炼、复杂一点的问答 | 超长上下文、专业代码推理、高质量多步规划 | 需要较大内存；运行时可能占用明显 CPU 和电量 |
| `high_quality` | `Qwen3-8B-GGUF Q4` | 高内存电脑、愿意接受更大下载和更慢速度的用户 | 16 GB | 24 GB | 否，显卡可作为未来加速 | 约 6.0 GB | 约 9.0 GB | 否 | 更高质量摘要、复杂问答、长一点的知识整理 | 低配置笔记本、需要实时响应的场景 | 下载较大，请确认磁盘空间；首次加载和推理会更慢 |

Rules:

- `ultra_light` 是唯一默认推荐档。
- 30GB+ 模型不得作为默认模型、默认推荐或首次安装建议。
- 安装助手不得自动把用户升级到更大模型。
- GPU 检测只能作为后置增强；所有默认推荐必须“无需显卡”。
- 任何模型如果 `sha256=pending`，只能显示为 pending catalog entry，不能进入 verified install。

## 4. Download Source Strategy

v2.7.0 只设计 ModelScope 来源，不实际访问 ModelScope，不解析远程仓库，不下载文件。

下载来源规则：

- 只允许单文件 GGUF。
- 不允许默认下载整个模型仓库。
- 不允许安装助手自动选择最大文件。
- 不允许 30GB+ 模型作为默认推荐。
- 不允许从用户输入的任意 URL 执行下载。
- 不允许执行远程脚本或本地 shell 下载脚本。
- 每个 catalog entry 必须写明 filename，未来 downloader 只能下载该 filename。

每个模型必须包含：

- `model_id`
- `filename`
- `url` 或 `modelscope_reference`
- `sha256`，可以先为 `pending`
- `expected_size`
- `license`
- `provider_kind=local`
- `quantization`
- `context_length`
- `recommended_threads`

校验规则：

- `sha256=pending` 或空值时，模型不能进入 verified install。
- `expected_size` 只用于下载前提示和磁盘预估，不能替代 checksum。
- license 为 pending 时必须显示 license review warning。
- catalog 更新不得由 GUI 自动拉取；未来应通过受控 release 或显式 catalog update plan。

## 5. Storage Policy

默认模型目录：

```text
%LOCALAPPDATA%\PersonalKnowledgeBase\models\
```

存储规则：

- 用户可在设置中自定义模型目录。
- 模型不得放入 workspace。
- 模型不得放入软件安装目录。
- 模型不得放入 `knowledge/`、`.kb/`、`config/`、`templates/` 或 `reports/`。
- 卸载软件不默认删除模型文件。
- 用户必须能在设置中删除已安装模型文件。
- 删除模型文件必须显示模型名称、路径、大小和不可恢复提示。
- 模型 catalog 和 installed model registry 不能被当作 formal knowledge。

建议未来目录：

```text
%LOCALAPPDATA%\PersonalKnowledgeBase\
  models\
    registry.json
    qwen3_0_6b_gguf_q4_k_m\
      model.gguf
      install-manifest.json
```

自定义目录也必须保持同等布局，并通过 path safety validator 拒绝 workspace 根目录、安装目录、系统目录和相对路径。

## 6. Hardware Detection

安装前需要展示硬件检测结果。v2.7.0 只设计字段，不实现检测。

检测字段：

- OS。
- RAM。
- free disk。
- CPU cores。
- GPU availability，后置增强，不作为默认推荐前置。
- 当前模型是否适合本机。
- 下载大小和安装后大小。
- 下载前 warning。

普通用户文案：

- “适合普通笔记本”
- “无需显卡”
- “需要较大内存”
- “下载较大，请确认磁盘空间”

建议判定：

| Condition | UI status | Copy |
| --- | --- | --- |
| RAM >= recommended | good | 当前设备适合此模型 |
| RAM >= minimum and < recommended | warning | 可以安装，但运行可能变慢 |
| RAM < minimum | blocked by default | 当前内存低于最低要求，不建议安装 |
| free disk < install size + 2 GB | blocked | 磁盘空间不足 |
| GPU missing | neutral for default tiers | 无需显卡 |

硬件检测不能自动下载模型，只能影响提示、默认展开的推荐档和安装按钮状态。

## 7. TaskQueue Installer Flow

未来安装必须进入 TaskQueue，不阻塞 GUI。所有下载必须由用户确认后才开始。

设计任务：

| Task | Purpose | Writes files | Requires confirmation | Cancellation |
| --- | --- | --- | --- | --- |
| `model_download_plan` | 生成下载计划、路径、大小、checksum 和 warning | 否 | 否 | n/a |
| `model_download` | 下载单个 GGUF 文件到临时 staging | 是 | 是 | cooperative |
| `model_verify` | 校验 sha256、大小和 manifest | 读 staging，写结果 | 是 | n/a |
| `model_register` | 写 installed model registry | 是 | 是 | n/a |
| `model_health_check` | 未来检查文件可读和元数据一致，不启动模型 | 读文件 | 是 | n/a |
| `model_uninstall` | 删除用户确认的模型文件和 registry entry | 是 | 是 | n/a |

Task requirements:

- 下载是 TaskQueue task。
- 可取消。
- 有进度。
- 有错误详情。
- 不阻塞 GUI。
- 不自动下载。
- 用户确认后才开始。
- task log 不得记录完整 prompt、文档正文、secret-like 文本或 arbitrary command。
- 失败必须保留可解释状态：network error、disk full、checksum mismatch、license pending、catalog invalid、cancelled。

v2.7.0 不把这些 task 加入 executable set；本阶段只做设计。

## 8. Runtime Boundary

本阶段只设计未来 runtime 组件，不实现。

未来组件：

- `LocalModelProvider`
- `ModelRuntimeManager`
- `ModelProcessManager`
- `ModelHealthCheck`

v2.7.0 边界：

- 不启动模型。
- 不执行 shell。
- 不接 `llama.cpp` server。
- 不开本地 HTTP 服务。
- 不创建本地推理进程。
- 不实现 prompt 到模型的调用链。

未来如果使用进程：

- binary path 必须固定在受信任配置中。
- args 必须 whitelist。
- 不允许 arbitrary command。
- 不允许把用户输入拼接进命令行。
- 不允许任意环境变量透传。
- 模型路径必须来自 installed model registry。
- 进程生命周期必须由 service layer 管理，GUI/ViewModel/provider 不能直接启动进程。

详细边界见 [docs/local-model-runtime-boundary.md](D:/AI/personal-knowledge-base/docs/local-model-runtime-boundary.md)。

## 9. Privacy And Context Boundary

本地模型模式下资料默认不离开本机，但本地模型仍然不能绕过 AI 控制平面。

Rules:

- 本地模型仍要遵守 ContextPolicy。
- 本地模型不能直接读 Markdown。
- 本地模型不能直接读 SQLite。
- ContextBuilder 仍只通过 `knowledge_app.services` 获取上下文。
- 模型不能绕过 CapabilityRegistry / PermissionPolicy。
- 本地 provider 不能读取 workspace 任意路径。
- 本地 provider 不能把 memory 当 formal knowledge。
- 云端模式后置；未来云端发送资料前仍必须 context preview + 用户确认。

详细策略见 [docs/local-model-privacy-and-storage-policy.md](D:/AI/personal-knowledge-base/docs/local-model-privacy-and-storage-policy.md)。

## 10. GUI Contract

安装助手入口位于 AI 助手设置页。

必须显示：

- 模型列表。
- 推荐模型标记。
- 最低配置。
- 推荐配置。
- 是否需要显卡。
- 下载大小。
- 安装大小。
- 本地 / 云端状态。
- 安装按钮。
- 删除按钮。
- 下载进度。
- 校验状态。
- 模型不可用错误。
- 无显卡友好提示。

GUI copy rules:

- 默认模型卡片显示“适合普通笔记本”。
- 默认模型卡片显示“无需显卡”。
- 大模型卡片显示“需要较大内存”。
- 下载前显示“下载较大，请确认磁盘空间”。
- `sha256=pending` 时安装按钮必须 disabled 或显示“等待校验信息”。
- 云端状态必须显示为后置或未启用，不能暗示已经接 OpenAI。
- 安装、删除、切换模型都不能绕过 service layer。

## 11. Future Test Plan

未来实现前必须先补测试：

- catalog parse。
- default model is `ultra_light`。
- no 30GB default。
- `sha256=pending` blocks verified install。
- install path not workspace/install dir。
- TaskQueue progress。
- cancel download。
- invalid checksum fails。
- no arbitrary command execution。
- no context bypass。
- privacy confirmation。
- GUI does not start download automatically。
- model uninstall requires explicit confirmation。
- local provider cannot directly read Markdown / SQLite。

## 12. Acceptance For v2.7.0

v2.7.0 的完成条件：

- 新增本设计文档。
- 新增 catalog policy、runtime boundary、privacy/storage policy。
- 新增 `config/local-model-catalog.example.yaml`。
- README 和 AGENTS 记录 design-only 边界。
- YAML 可静态解析。
- 默认模型为 `ultra_light` / `Qwen3-0.6B-GGUF Q4_K_M`。
- 默认模型下载估算小于 30 GB。
- 验收命令通过。
