# Local Model Runtime Boundary

本文定义 v2.7.0 本地模型 runtime 的边界。当前阶段只做设计，不实现 `LocalModelProvider`，不启动模型，不执行 shell，不接 `llama.cpp` server，不开本地 HTTP 服务，不创建模型进程。

## 1. Current Boundary

v2.7.0 明确不做：

- 不实现本地推理。
- 不实现真实 AI provider。
- 不接 OpenAI。
- 不接 ModelScope 下载。
- 不启动 `llama.cpp`、Python server、Node server 或任意本地 HTTP 服务。
- 不执行 shell、PowerShell、batch、curl、wget 或任意用户提供命令。
- 不把用户输入拼接为 command line。
- 不读取 Markdown 或 SQLite。
- 不修改 `search` / `index` / `audit`。
- 不修改 GUI 执行逻辑。

## 2. Future Components

未来组件只允许在明确后续阶段实现。

### LocalModelProvider

职责：

- 实现 `AIProvider` 接口。
- 接收 ContextBuilder 已构造、已授权的上下文。
- 调用 ModelRuntimeManager。
- 返回 `AIResponse`、citations、policy notices 和错误卡片。

禁止：

- 直接读 `knowledge/**/*.md`。
- 直接查 SQLite。
- 直接读取 workspace 任意路径。
- 直接启动进程。
- 绕过 CapabilityRegistry / PermissionPolicy。

### ModelRuntimeManager

职责：

- 管理已注册模型的 runtime availability。
- 校验 installed model registry。
- 选择 future backend。
- 限制上下文长度、线程数和资源预算。
- 向 ModelProcessManager 发出受控启动请求。

禁止：

- 接受任意 binary path。
- 接受任意 args。
- 接受用户自然语言中的路径或命令。
- 在 App startup 自动启动模型。

### ModelProcessManager

职责：

- 未来如果需要本地进程，由它管理进程生命周期。
- 使用固定 binary path。
- 使用 args whitelist。
- 使用 env whitelist。
- 使用 installed model registry 中的模型路径。
- 记录 process state 和 controlled error。

禁止：

- arbitrary command execution。
- shell invocation。
- `cmd /c`、`powershell -Command`、`bash -c`。
- 从 catalog 字符串直接构造命令。
- 从用户输入直接构造 args。
- 开放未授权本地 HTTP port。
- 让 GUI / ViewModel / provider 直接启动进程。

### ModelHealthCheck

职责：

- 检查 registry 是否存在。
- 检查模型文件是否存在。
- 检查 sha256 是否匹配。
- 检查 expected size 是否合理。
- 检查配置是否支持当前 OS。
- 返回可显示的错误详情。

v2.7.0 的 `model_health_check` 设计不启动模型，不加载权重，不做推理。

## 3. Process Policy

未来如必须启动本地进程，必须满足：

- binary path 来自受信任安装清单。
- binary path 不在 workspace。
- binary path 不在用户任意输入目录。
- args 是固定 schema 和 whitelist。
- model path 来自 installed model registry。
- working directory 是受控 runtime 目录。
- environment variables 是 whitelist。
- stdout/stderr 日志要脱敏。
- timeout、memory policy 和 cancel policy 明确。
- crash 必须变成 controlled error。

任何阶段都不得允许：

```text
用户输入 -> shell command
catalog string -> shell command
model_id -> executable path
filename -> command argument without validation
```

## 4. Local HTTP Policy

v2.7.0 不开本地 HTTP 服务。

未来如引入本地 HTTP backend，必须先有独立设计：

- bind address。
- port allocation。
- authentication or loopback-only policy。
- request schema。
- prompt logging policy。
- shutdown policy。
- cross-workspace isolation。
- firewall and privacy note。
- no remote access by default。

在该设计完成前，本地模型 runtime 不得假设有 server。

## 5. Context Boundary

Local runtime 不是权限绕过。

Rules:

- `ContextBuilder` 仍是上下文唯一构建入口。
- `ContextBuilder` 只能通过 `knowledge_app.services` 读取资料。
- `SearchService` 仍只返回 formal 层默认结果。
- `DocumentService.open_document` 仍只能打开用户明确选择的单篇文档。
- raw、distilled、research、archived 内容必须带“未经审核，不能作为正式项目规则” warning。
- quarantine 和 rejected 默认 denied。
- LocalModelProvider 只能接收已构造上下文，不能自己扩展范围。

## 6. Capability Boundary

本地模型只能生成回答、摘要、草稿或建议。执行能力仍由 AI 控制平面决定。

Rules:

- CapabilityRegistry 是唯一 capability 白名单。
- PermissionPolicy 是唯一执行决策入口。
- L3 safe execute 仍必须 plan、snapshot、approval、TaskQueue。
- L4 forbidden 仍必须 deny。
- 本地模型输出不能作为 mutation approval。
- 本地模型输出不能作为 reviewer identity。
- 本地模型不能生成 shell command 后自动执行。

## 7. Runtime State

未来 runtime state 不得写入：

- `knowledge/`
- `.kb/index.sqlite`
- workspace formal layers
- 软件安装目录

允许的未来位置：

- `%LOCALAPPDATA%\PersonalKnowledgeBase\models\` for model files and installed model registry。
- `%LOCALAPPDATA%\PersonalKnowledgeBase\logs\` for app/runtime logs, with redaction。
- workspace-scoped `ai/conversations/` only for conversation persistence through existing service boundary, not model runtime state。

## 8. Future Tests

未来 runtime 实现前必须补测试：

- no `subprocess` or process start in provider。
- no shell invocation in runtime manager。
- args whitelist rejects unknown args。
- binary path must be fixed and trusted。
- model path must come from registry。
- provider cannot import `knowledge_core` or `sqlite3`。
- provider cannot read Markdown files。
- local provider cannot bypass CapabilityRegistry / PermissionPolicy。
- health check does not start model。
- App startup does not start runtime。
