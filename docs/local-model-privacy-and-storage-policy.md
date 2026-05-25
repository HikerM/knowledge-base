# Local Model Privacy And Storage Policy

本文定义 v2.7.0 本地模型安装助手的隐私和存储策略。当前阶段只做设计，不安装模型，不接真实 provider，不启动 runtime，不保存 prompt，不改变 conversation / memory 持久化边界。

## 1. Privacy Principles

本地模型模式下资料默认不离开本机。

这不代表本地模型可以绕过控制平面。所有本地模型调用仍必须遵守：

- AI Assistant Control Plane。
- AI Context Policy。
- CapabilityRegistry。
- PermissionPolicy。
- service-layer read boundary。
- memory 和 conversation policy。
- secret / sensitive blocking。

Rules:

- 本地模型不能直接读 Markdown。
- 本地模型不能直接读 SQLite。
- 本地模型不能扫描 workspace。
- 本地模型不能读取 backup zip。
- 本地模型不能读取 `.kb/tasks/`。
- 本地模型不能把 raw / distilled / research 当正式规则。
- 本地模型不能绕过 `SearchService` formal 层边界。
- 本地模型不能自动保存长期记忆。
- 本地模型不能执行 mutation。

## 2. Storage Locations

默认模型目录：

```text
%LOCALAPPDATA%\PersonalKnowledgeBase\models\
```

允许：

- 用户本地 LocalAppData 模型目录。
- 用户显式选择的自定义模型目录。

禁止：

- workspace 根目录。
- `knowledge/`。
- `.kb/`。
- `config/`。
- `templates/`。
- `reports/`。
- 软件安装目录。
- 系统目录。
- 相对路径。

卸载策略：

- 卸载软件不默认删除模型。
- 模型文件属于用户本地数据。
- 用户可在设置中删除模型文件。
- 删除模型前必须显示路径、大小、模型名和确认文案。

## 3. Installed Model Registry

未来 installed model registry 推荐：

```text
%LOCALAPPDATA%\PersonalKnowledgeBase\models\registry.json
```

Registry 记录：

- installed model id。
- catalog id。
- filename。
- local path。
- sha256。
- installed_at。
- install_size。
- license。
- verification status。
- source reference。

Registry rules:

- 只能由 service layer 写入。
- GUI 不得直接写 registry。
- Provider 不得直接写 registry。
- Registry 不是 formal knowledge。
- Registry 不进入 `.kb/index.sqlite`。
- Registry 不参与 `SearchService`。

## 4. Backup And Uninstall

默认知识库 backup 不包含模型文件。

Reasons:

- 模型文件很大。
- 模型文件可从来源重新下载。
- 模型 license 和 checksum 必须单独审核。
- 模型不属于 Markdown source of truth。

Future optional backup:

- 必须显式 `include_local_models=true`。
- 必须显示体积 warning。
- 必须记录模型 license 和 sha256。
- 必须允许用户排除模型。

卸载软件：

- 只删除安装目录和快捷方式。
- 不删除 `%LOCALAPPDATA%\PersonalKnowledgeBase\models\`。
- 不删除用户 workspace。
- 不删除 backups。

## 5. Context Policy For Local Provider

Local provider 的输入只能来自 ContextBuilder。

Allowed context:

- 当前打开的单篇文档。
- 用户选中的搜索结果。
- formal 层 `SearchService` top-k 结果。
- 用户确认保存的长期记忆，且 memory policy 允许。
- 当前会话短期状态。

Denied context:

- 全库无边界读取。
- 直接 filesystem path。
- 直接 SQLite query。
- raw 全文。
- distilled 作为正式规则。
- quarantine。
- rejected。
- archived 默认内容。
- secret-like content。

本地 provider 返回的回答如果基于知识库内容，仍必须带 citation。citation 至少包含 document/title/layer/status/source_type/confidence 或 service 返回的等价 metadata。

## 6. Cloud Mode Boundary

云端模式后置。v2.7.0 不接 OpenAI 或任何云端 provider。

未来云端模式必须：

- 先展示 context preview。
- 获得用户确认。
- 显示 provider kind。
- 列出将发送的文档、chunk、memory 和会话内容。
- 绑定 preview hash 或等价不可变快照。
- 阻止 sensitive、quarantine、rejected 和 unconfirmed 内容。

本地模型安装完成不代表云端功能启用。

## 7. Logs And Diagnostics

未来 installer 和 runtime 日志必须脱敏。

Allowed log data:

- task id。
- model id。
- filename。
- byte progress。
- checksum status。
- controlled error code。
- elapsed time。

Denied log data:

- prompt 全文。
- 文档正文。
- memory 正文。
- secret-like text。
- 用户输入的任意命令。
- access credential。

## 8. User Controls

AI 助手设置页必须提供：

- 本地模型状态。
- 云端状态，当前显示为未启用或后置。
- 模型目录查看。
- 自定义模型目录入口。
- 安装模型。
- 删除模型。
- 校验状态。
- 模型不可用错误。
- 隐私说明。
- 无显卡友好提示。

安装按钮必须只在用户确认后创建 TaskQueue task。删除按钮必须只删除用户明确选择的模型。

## 9. Future Tests

未来测试必须覆盖：

- model path not workspace。
- model path not install dir。
- uninstall app preserves model dir by default。
- delete model requires explicit confirmation。
- default backup excludes models。
- local provider receives only ContextBuilder output。
- local provider cannot direct-read Markdown。
- local provider cannot query SQLite。
- cloud mode requires context preview。
- citation required when local model uses knowledge content。
- logs do not contain prompt/document/memory body。
