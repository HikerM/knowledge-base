# Local Model Catalog Policy

本文定义 v2.7.0 本地模型 catalog 的策略。当前阶段只提供 example catalog，不作为运行时自动执行入口，不访问 ModelScope，不下载模型，不校验远程文件，也不注册真实 provider。

## 1. Catalog Purpose

Catalog 用于向未来安装助手提供可审计、可静态校验的模型候选列表。它不是用户知识，不进入 `knowledge/`，不进入 `.kb/index.sqlite`，也不参与 formal search。

Catalog 必须支持普通用户理解：

- 这个模型适合谁。
- 是否需要显卡。
- 最低和推荐内存。
- 下载大小和安装大小。
- 安装风险。
- 是否可以 verified install。
- 为什么默认推荐是极轻量模型。

## 2. Required Fields

每个模型 entry 必须包含：

- `id`
- `tier`
- `display_name`
- `provider_kind`
- `model_id`
- `filename`
- `url` 或 `modelscope_reference`
- `sha256`
- `expected_size`
- `expected_size_gb`
- `download_size_gb`
- `install_size_gb`
- `license`
- `quantization`
- `context_length`
- `recommended_threads`
- `minimum_ram_gb`
- `recommended_ram_gb`
- `requires_gpu`
- `is_default`
- `target_users`
- `suitable_tasks`
- `unsuitable_tasks`
- `risk_notice`
- `verification_status`

Validation rules:

- `provider_kind` 必须是 `local`。
- `tier` 必须存在于 `tiers`。
- `filename` 必须是单个 `.gguf` 文件名，不能是目录、glob 或仓库名。
- `sha256` 可以是 `pending`，但 pending 不允许 verified install。
- `expected_size_gb`、`download_size_gb`、`install_size_gb` 必须是数字。
- `is_default=true` 只能有一个。
- `default_model` 必须指向 `is_default=true` 的模型。
- 默认模型必须属于 `ultra_light`。
- 默认模型不得是 30GB+。

## 3. Tier Policy

必须至少定义以下档位：

| Tier | Required model | Default allowed |
| --- | --- | --- |
| `ultra_light` | `Qwen3-0.6B-GGUF Q4_K_M` | yes |
| `light` | `Qwen3-1.7B-GGUF Q4_K_M` | no |
| `standard` | `Qwen3-4B-GGUF Q4` | no |
| `high_quality` | `Qwen3-8B-GGUF Q4` | no |

Policy:

- `ultra_light` 是默认入口。
- `light` 可以作为用户主动升级选项。
- `standard` 和 `high_quality` 必须显示“需要较大内存”。
- 所有档位都必须显示“无需显卡”或明确说明 GPU 只是未来可选加速。
- 30GB+ 模型只能作为未来高级手动项设计，不能出现在默认推荐或首次安装流程中。

## 4. Source Policy

当前只设计 ModelScope 来源。

Rules:

- 只允许单文件 GGUF。
- 不允许默认下载整个模型仓库。
- 不允许 GUI 根据仓库列表自动选择最大文件。
- 不允许用户输入任意 URL 后直接下载。
- 不允许执行远程脚本。
- 不允许 shell 下载脚本。
- 不允许把 catalog entry 的 `model_id` 当作可执行命令或 filesystem path。

Allowed source shapes:

```yaml
source:
  kind: "modelscope"
  model_id: "Qwen/Qwen3-0.6B-GGUF"
  filename: "qwen3-0.6b-q4_k_m.gguf"
  modelscope_reference: "modelscope://Qwen/Qwen3-0.6B-GGUF/qwen3-0.6b-q4_k_m.gguf"
  url: ""
```

`modelscope_reference` 是 catalog reference，不是下载命令。未来 downloader 必须把 reference 解析为受控下载请求，且只能下载 `filename` 指定的单文件。

## 5. Verification Policy

Verification status:

| Status | Meaning | Install allowed |
| --- | --- | --- |
| `pending` | catalog 还没有可信 sha256 | no verified install |
| `verified` | sha256、expected size、license 已审核 | yes, after user confirmation |
| `blocked` | license、大小、checksum 或安全问题阻塞 | no |

Rules:

- `sha256=pending` 不能进入 verified install。
- sha256 mismatch 必须失败，不能降级为 warning。
- expected size mismatch 必须进入 warning 或 blocked，由 future policy 决定。
- license pending 必须显示 warning，不能默认安装。
- checksum、license 和 filename 审核必须有审计记录。

## 6. Default Selection Policy

安装助手不能自动选择大模型。

Default rules:

- `default_model` 必须是 `Qwen3-0.6B-GGUF Q4_K_M` 或等价极轻量档。
- 默认档必须 `requires_gpu=false`。
- 默认档必须面向普通笔记本。
- 默认档下载估算必须小于 30 GB。
- 如果默认模型 metadata invalid，安装助手必须进入 blocked catalog state，而不是选择下一档。

用户可以主动选择更高档，但 UI 必须显示内存、磁盘和性能 warning。

## 7. Storage And Registry Policy

Catalog example 位于仓库 `config/`，用于设计和测试。未来 installed model registry 应位于用户本地目录：

```text
%LOCALAPPDATA%\PersonalKnowledgeBase\models\registry.json
```

Rules:

- installed model registry 不放 workspace。
- installed model registry 不放安装目录。
- installed model registry 不进入 knowledge formal search。
- registry 写入必须由 service layer 负责。
- GUI、provider、ViewModel 不得直接写 registry。

## 8. Future Static Tests

未来必须补静态测试：

- YAML parse。
- schema version exists。
- all required tiers exist。
- default model exists。
- default model tier is `ultra_light`。
- default model display name includes `Qwen3-0.6B`。
- default model `download_size_gb < 30`。
- no model with `is_default=true` has `download_size_gb >= 30`。
- every model has single `.gguf` filename。
- every model has `provider_kind=local`。
- `sha256=pending` implies `verification_status=pending` and verified install blocked。
- storage policy rejects workspace path and install dir.
