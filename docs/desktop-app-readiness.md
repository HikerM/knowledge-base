# Desktop App Readiness

本文件为未来 Windows EXE / GUI 软件化提供设计边界。当前阶段只做架构准备，不实现 GUI，不选择最终技术栈，不打包 EXE。

## 1. 未来架构

正确架构：

```text
Desktop GUI
  ↓
Service Layer
  ↓
knowledge_core
  ↓
Markdown + SQLite + Git
```

错误架构：

```text
Desktop GUI
  ↓
直接改 Markdown / SQLite
```

也不推荐：

```text
Desktop GUI
  ↓
拼接 CLI 命令字符串
```

原因：

- GUI 直接改 Markdown 容易绕过 promote、audit、lint、secret-scan 等治理门禁。
- GUI 直接写 SQLite 会把可重建索引误当事实来源。
- 拼接 CLI 字符串难以做结构化错误处理、取消、进度、并发互斥和输入安全。
- service/core API 可以复用 CLI 能力，同时给 GUI 提供稳定的数据模型。

CLI 可以继续保留为：

- CI 入口。
- 自动化入口。
- 调试入口。
- 高级用户入口。

未来 GUI 应调用 service/core API，不应把 CLI stdout 当主要集成协议。

## 2. 未来 service layer 规划

未来可以新增应用层模块：

```text
knowledge_app/
  services/
    knowledge_service.py
    search_service.py
    review_service.py
    index_service.py
    audit_service.py
    source_service.py
    git_service.py
    maintenance_service.py
  tasks/
    task_queue.py
    task_status.py
    progress.py
  models/
    operation_result.py
    search_result.py
    audit_result.py
    task_result.py
```

### services

`knowledge_service.py`

- 负责 workspace 初始化、路径校验、单篇 open、文档元数据读取。
- 不直接绕过 lifecycle 规则写正式层。
- 写入操作返回结构化 `OperationResult`。

`search_service.py`

- 负责 FTS5 搜索、过滤、Top-K、分页和 search explain。
- 默认只查正式层。
- 不读取全部 Markdown 正文。

`review_service.py`

- 负责 review queue、promote、deprecate、quarantine、rejected 相关工作流。
- 所有 promote 必须带人工审核信息。
- 不自动 promote。

`index_service.py`

- 负责 index、reindex、doctor、stats、vacuum。
- `index`、`reindex`、`vacuum` 是写任务，必须进入后台队列。
- `vacuum` 必须显式确认。

`audit_service.py`

- 负责 lint、audit、stale、dedupe、conflicts、canonical-report。
- 默认生成报告，不删除、不 promote。

`source_service.py`

- 负责 sources、learning radar、learning queue。
- 不抓取不可控全网内容。
- 学习结果进入 raw 前必须保留来源。

`git_service.py`

- 负责 status、diff、commit、tag、sync、rollback 指引。
- public repo 发布前必须检查 secret-scan 状态。
- 不应自动丢弃用户未提交修改。

`maintenance_service.py`

- 负责 monthly maintenance、maintenance、报告归档、可选 vacuum、release checklist。
- 默认只检查和报告。
- destructive action 必须显式确认。

### tasks

`task_queue.py`

- 管理后台任务队列。
- 写任务互斥，读任务可并发。
- 保证 UI 主线程不运行长任务。

`task_status.py`

- 定义 `pending`、`running`、`succeeded`、`failed`、`cancelled`。
- 记录 task_id、开始时间、结束时间、错误摘要和 log_path。

`progress.py`

- 提供 progress percent、progress message、阶段名称和取消信号。
- 支持任务完成后释放资源。

### models

`operation_result.py`

- 通用操作结果：ok、message、elapsed_ms、warnings、errors。

`search_result.py`

- 搜索结果：query、filters、top_k、results、elapsed_ms、next_page_token。

`audit_result.py`

- 审计结果：summary、issues、report_path、elapsed_ms。

`task_result.py`

- 后台任务结果：task_id、status、progress、log_path、result_summary、error_detail。

## 3. Workspace 设计

原则：

- 软件安装目录不存用户知识数据。
- 用户选择 knowledge workspace。
- `knowledge/`、`config/`、`templates/`、`reports/`、`.kb/` 属于 workspace。
- GUI 设置放 AppData。
- GUI logs 放 AppData。
- backup/export 路径可配置。
- 未来支持多 workspace。

建议 Windows 路径：

```text
Install directory:
  C:\Program Files\Personal Knowledge Base\

Workspace example:
  D:\AI\personal-knowledge-base\

User settings:
  %APPDATA%\PersonalKnowledgeBase\settings.json

Logs:
  %LOCALAPPDATA%\PersonalKnowledgeBase\logs\

Task logs:
  %LOCALAPPDATA%\PersonalKnowledgeBase\tasks\
```

Workspace 打开流程：

1. 用户选择目录。
2. GUI 检查是否存在 `knowledge/`、`config/`、`scripts/kb.py` 或未来 workspace manifest。
3. service 执行 doctor。
4. 如果 `.kb/index.sqlite` 不存在，提示可重建索引。
5. 不在安装目录创建或迁移用户知识文件。

## 4. GUI 页面规划

### Dashboard

- purpose：显示 workspace 状态、最近报告、索引状态、待审核数量、secret-scan 状态和维护建议。
- service dependencies：`knowledge_service`、`index_service`、`audit_service`、`maintenance_service`。
- read/write behavior：默认只读元数据和摘要。
- long-running tasks：doctor、stats、maintenance。
- progress/error states：显示后台任务状态、最近错误、log_path。
- destructive confirmations：无默认破坏性动作，reindex 和 vacuum 需要确认。

### Search

- purpose：正式知识检索、研究性检索、结果分页和单篇 open。
- service dependencies：`search_service`、`knowledge_service`。
- read/write behavior：搜索只读索引，open 按需读单篇 Markdown。
- long-running tasks：默认无，复杂 explain 或大查询可后台化。
- progress/error states：显示搜索耗时、无结果、索引缺失、查询错误。
- destructive confirmations：无。

### Raw Inbox

- purpose：查看 raw、补来源、标记待提炼、生成 distill plan。
- service dependencies：`knowledge_service`、`source_service`、`review_service`。
- read/write behavior：可写 raw 元数据，但不能直接 promote。
- long-running tasks：learning queue generation、批量 lint。
- progress/error states：显示 source 缺失、review_required、质量警告。
- destructive confirmations：quarantine 或 move 操作需要确认。

### Distilled Review

- purpose：人工审核 distilled，决定 promote、reject、quarantine 或继续修改。
- service dependencies：`review_service`、`audit_service`、`knowledge_service`。
- read/write behavior：可写 distilled 审核字段，可通过 promote 进入正式层。
- long-running tasks：review-queue、audit。
- progress/error states：显示缺少审核字段、缺少 source_url、promote 门禁失败。
- destructive confirmations：promote、reject、quarantine 需要确认并填写原因。

### Rules / Checklists / Snippets

- purpose：浏览正式知识层、查看 canonical rule、检查 stale 和 deprecated 关系。
- service dependencies：`knowledge_service`、`search_service`、`audit_service`、`review_service`。
- read/write behavior：默认只读，修改必须经过结构化 service。
- long-running tasks：stale、canonical-report、conflicts。
- progress/error states：显示 stale、冲突、缺少审核字段。
- destructive confirmations：deprecate 或移动正式层文件需要确认。

### Sources

- purpose：查看配置的学习源、优先级、分类和边界。
- service dependencies：`source_service`。
- read/write behavior：读取和编辑 `config/sources.yaml`，不抓取全文。
- long-running tasks：source-policy review。
- progress/error states：显示 disabled、unknown type、缺少 category。
- destructive confirmations：删除 source 或禁用高优先级 source 需要确认。

### Learning Queue

- purpose：生成和查看学习队列。
- service dependencies：`source_service`、`maintenance_service`。
- read/write behavior：写 reports，不写 raw、不写 rules。
- long-running tasks：learning queue generation。
- progress/error states：显示报告路径、任务数量、失败详情。
- destructive confirmations：无默认破坏性动作。

### Audit Center

- purpose：集中查看 lint、audit、stale、dedupe、conflicts、secret-scan。
- service dependencies：`audit_service`、`index_service`。
- read/write behavior：默认只读和写报告。
- long-running tasks：audit、secret-scan、dedupe、conflicts、stale。
- progress/error states：显示 issue severity、error_detail、log_path、report_path。
- destructive confirmations：quarantine、deprecate、reject 需要确认。

### Maintenance

- purpose：运行月度维护、report archive review、可选 vacuum、性能 baseline。
- service dependencies：`maintenance_service`、`index_service`、`audit_service`。
- read/write behavior：默认只检查和写报告。
- long-running tasks：maintenance、benchmark、optional vacuum、backup/export。
- progress/error states：显示任务状态、进度、失败阶段、报告路径。
- destructive confirmations：vacuum、reindex、cleanup、restore 需要确认。

### Git Sync

- purpose：显示 Git status、commit、tag、push、pull 和恢复指引。
- service dependencies：`git_service`、`audit_service`。
- read/write behavior：执行 Git 操作前显示 diff 和影响范围。
- long-running tasks：pull、push、backup before sync。
- progress/error states：显示冲突、未提交文件、远端错误。
- destructive confirmations：reset、checkout、clean、restore 必须二次确认。

### Settings

- purpose：管理 workspace、日志目录、backup/export 路径、UI 偏好和多 workspace。
- service dependencies：`knowledge_service`、`maintenance_service`。
- read/write behavior：写 AppData 设置，不写安装目录。
- long-running tasks：workspace doctor、restore rehearsal。
- progress/error states：显示路径不可写、workspace 无效、索引缺失。
- destructive confirmations：切换 workspace、删除本地设置、清理日志需要确认。

## 5. EXE 稳定性原则

- UI 主线程不跑长任务。
- 长任务可取消。
- 任务错误可恢复。
- 写任务互斥。
- 日志轮转。
- 崩溃后可重新 index。
- Markdown 源数据优先保护。
- SQLite 索引可重建。
- 不把所有文档常驻内存。
- 不把 GUI 写成单文件巨型 `App.tsx` 或 `main.py`。
- service API 必须提供结构化结果，不依赖解析终端文本。

崩溃恢复建议：

1. 启动时检查上次未完成任务。
2. 标记为 failed 或 cancelled。
3. 提供 log_path 和重试入口。
4. 对索引异常提示重新 index。
5. 不自动删除 Markdown 或 reports。

## 6. 技术路线建议

### Tauri + React

优点：

- 桌面包体相对小。
- 前端生态成熟。
- 适合长期扩展出复杂 UI。
- 可以将 Python core 作为 sidecar 或逐步服务化。

风险：

- Python 复用需要设计进程边界或 API 边界。
- Windows 打包、签名、sidecar 管理需要额外工程投入。

适合：界面质量和长期扩展优先。

### Electron + React

优点：

- 开发速度快。
- 生态成熟。
- 调试和插件能力强。
- 与 Web UI 研发习惯一致。

风险：

- 包体和内存占用较高。
- 长期常驻需要更严格的资源治理。

适合：开发速度优先。

### PySide6 / Qt

优点：

- 最大化复用 Python。
- 与现有 `knowledge_core` 集成直接。
- 不需要单独维护 JS runtime。

风险：

- 现代 UI 体验和前端生态弱于 React 方案。
- 大型复杂界面需要更多 Qt 专项经验。

适合：最大化复用 Python 优先。

### .NET / WinUI

优点：

- Windows 原生体验好。
- 系统集成、安装、签名和企业环境支持强。
- 长期桌面稳定性成熟。

风险：

- Python core 复用需要进程或服务边界。
- 团队需要维护 .NET 与 Python 双栈。

适合：Windows 原生生态优先。

### 当前结论

当前不做最终选型。可以记录为：

- 界面质量和长期扩展优先：Tauri + React。
- 开发速度优先：Electron + React。
- 最大化复用 Python 优先：PySide6。
- Windows 原生生态优先：WinUI/.NET。

无论选择哪条路线，都必须先实现 service boundary、task queue、workspace protection 和结构化 result model。
