# GUI 手动验收清单

适用版本：`v2.0.0-alpha.3`

目标：验证 PySide6 只读 GUI MVP 的真实窗口交互、键盘、焦点、窗口适配、空态、错误态和只读边界。该清单不包含 EXE 打包、写操作、RSS、向量检索或 AI 助手。

## 启动前检查

- [ ] `git status --short` 没有未预期改动。
- [ ] 已运行 `python scripts/kb.py audit`。
- [ ] 已运行 `python scripts/kb.py secret-scan`。
- [ ] 已运行 `python tests/startup_smoke.py`，确认 `index_created_by_workspace_status=false`、`markdown_scan_blocked=true`、`markdown_read_blocked=true`。
- [ ] 启动前不要删除或重建 `.kb/index.sqlite`，除非本轮明确验证索引缺失态。

## 启动

命令：

```bash
python -m gui.app
```

无真实窗口环境时：

```bash
QT_QPA_PLATFORM=offscreen PKB_GUI_AUTO_CLOSE_MS=1000 python -m gui.app
```

验收项：

- [ ] 应用可以正常打开。
- [ ] 启动后默认停留在「首页」。
- [ ] 启动阶段只显示工作区路径、索引状态、文档数量、分块数量。
- [ ] 最近任务、备份/快照和推荐操作显示“摘要尚未加载”或等价中文空态。
- [ ] 启动不自动触发索引、搜索、知识库加载、任务详情、设置详情或文档打开。

## 主导航和键盘

- [ ] 左侧主导航包含：首页、搜索、知识库、审核、任务中心、维护、设置。
- [ ] 审核、维护在第一阶段不可用，并显示只读阶段提示。
- [ ] `Alt+1` 到 `Alt+7` 可定位到对应导航项；不可用项不会进入页面。
- [ ] Tab 顺序优先进入当前页面的主要控件，例如搜索输入框、筛选器、刷新按钮或表格。
- [ ] 所有主界面可见文案使用简体中文；英文内部名只应出现在路径、开发者元数据或服务来源信息中。

## 首页

- [ ] 点击「刷新首页摘要」后才加载首页摘要。
- [ ] 刷新后显示工作区、索引、文档数量、分块数量、备份/快照、任务摘要。
- [ ] 推荐操作最多 3 个。
- [ ] 刷新首页摘要不会触发 index/reindex。
- [ ] 服务不可用时显示中文错误态，不出现可执行修复按钮。

## 搜索

- [ ] 空查询显示空态，不调用搜索服务。
- [ ] 输入查询词并回车或点击「搜索」后显示结果列表。
- [ ] 结果项显示标题、摘要、层级、状态、可信度、来源和路径。
- [ ] 点击或按 Enter 激活单条结果后，只打开该单篇文档预览。
- [ ] 「打开所选」只在有有效结果选中时可用。
- [ ] 「上一页」「下一页」根据分页状态启用或禁用。
- [ ] 「隐藏预览」「显示预览」可以折叠和恢复右侧预览区。
- [ ] 索引缺失、无结果、服务错误均显示中文状态。

## 知识库

- [ ] 首次进入知识库后读取正式层摘要，不在应用启动时读取。
- [ ] 层级筛选仅包含全部正式层、规则、清单、片段。
- [ ] 列表不展示 raw/distilled 作为正式知识。
- [ ] 默认每页最多 25 条，不一次渲染所有记录。
- [ ] 「上一页」「下一页」根据分页状态启用或禁用。
- [ ] 选中行不会立即读取正文；点击「打开所选」或按 Enter 激活行后才打开单篇文档。
- [ ] 右侧预览区可折叠和恢复。

## 文档预览

- [ ] 预览显示标题、路径、层级、状态、可信度、来源、审核状态。
- [ ] 元数据区域只读。
- [ ] 文档内容区域只读，长文可以滚动查看。
- [ ] 打开失败时显示中文错误态。
- [ ] 不提供保存、编辑、应用、删除、归档、合并、恢复、promote 或 execute 入口。

## 任务中心

- [ ] 首次进入任务中心后读取最近任务，不在应用启动时读取。
- [ ] 列表显示任务标题、类型、状态、进度、耗时和错误摘要。
- [ ] 选中任务后需要点击「查看日志摘要」才读取日志摘要。
- [ ] 日志摘要显示状态、进度、错误、结果摘要、进度事件和日志尾部。
- [ ] 不显示可用的 retry、cancel、cleanup 执行按钮。

## 设置

- [ ] 首次进入设置后读取只读设置入口，不在应用启动时读取。
- [ ] 显示工作区、服务状态、索引状态、文档数量和分块数量。
- [ ] 设置表格不可编辑。
- [ ] 不提供编辑表单、保存、应用或 execute 操作。

## AI 记忆设置 v2.6.2 补充

命令：

```bash
python -m gui.app --workspace D:\AI\personal-knowledge-base
```

边界：

- [ ] 「设置」中存在「AI 记忆」入口。
- [ ] 启动应用和打开「设置」页不会自动加载 MemoryCandidate、SavedMemory、backup preview、export preview 或 privacy status。
- [ ] 进入「AI 记忆」页后显示：`AI 记忆当前为内存模拟模式，关闭应用后不会保留。`
- [ ] 页面说明长期记忆必须由用户确认后才会保存。
- [ ] 页面说明 AI 记忆不会作为正式知识，也不会进入搜索规则。
- [ ] 页面说明当前不会发送到云端。
- [ ] 页面说明删除为删除记录，不是正式知识删除。
- [ ] 当前实现只使用 in-memory MemoryService；关闭应用后不会持久化，不创建 `workspace/ai`，不写 `workspace/ai/memory/*.jsonl`。

MemoryCandidate：

- [ ] 点击「加载候选」后才显示候选列表。
- [ ] 候选筛选包含：全部、待确认、已接受、已拒绝、已过期。
- [ ] 候选项显示 `proposed_text`、type、sensitivity、source_message_ids 和 status。
- [ ] 点击「接受」会显示确认提示；未确认不会保存。
- [ ] `sensitivity=blocked` 候选不可接受，页面显示 blocked candidate 错误态。
- [ ] 点击「拒绝」只把候选标记为 rejected，不保存 SavedMemory。
- [ ] 点击「标记过期」会显示确认提示；确认后候选变为 expired，且不保存 SavedMemory。
- [ ] 无候选时显示空态，不自动创建候选。

SavedMemory：

- [ ] 点击「加载已保存记忆」后才显示 SavedMemory 列表。
- [ ] SavedMemory 筛选包含：全部、启用、已禁用、已删除。
- [ ] active / disabled / deleted 状态显示正确。
- [ ] 删除后显示 tombstone：`已删除，仅保留删除记录`。
- [ ] redacted text 显示：`内容已删除`。
- [ ] 禁用、删除、清空只影响当前工作区的内存模拟记忆，不影响 conversation，不影响正式知识。

Preview：

- [ ] backup preview 显示 `include_ai_memory=false` 和 `include_ai_drafts=false`。
- [ ] export preview 显示 `writes_file=false`、`cloud_send_allowed=false`、`formal_search_records=false`。
- [ ] 可复制 export preview JSON；复制只进入剪贴板，不写入文件。
- [ ] privacy mode 时显示禁止保存 AI 记忆，并阻止保存。

## 窗口适配

- [ ] 在 `920x640` 附近窗口尺寸下，主导航、顶部栏、列表和预览区不重叠。
- [ ] 在 `1280x800` 常规桌面尺寸下，搜索和知识库的左侧列表与右侧预览比例合理。
- [ ] 拖动 splitter 或点击预览折叠按钮时，主列表仍可用。
- [ ] 长路径、长标题和长正文不会把窗口撑出可用区域。

## 发布前自动验收

```bash
python scripts/kb.py audit
python scripts/kb.py secret-scan
python tests/gui_viewmodel_test.py
python tests/gui_smoke_test.py
python tests/gui_interaction_test.py
```

全部通过后，才建议进入候选审计。
