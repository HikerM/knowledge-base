# AI Conversation History Manual Acceptance

适用阶段：v2.5.5 Conversation history polish。

边界确认：

- 不接真实 AI / OpenAI / 本地模型 / ModelScope。
- 不实现 memory persistence，不保存长期记忆到磁盘。
- 不把 conversation 加入 formal search。
- 不修改 `knowledge/**/*.md`、SQLite schema、search/index/audit 行为。
- 不在 startup 自动加载 conversations。
- GUI 只能通过 View -> ViewModel -> Adapter -> `ConversationPersistenceService`。

## 验收步骤

1. 启动窗口：

   ```bash
   python -m gui.app --workspace D:\AI\personal-knowledge-base
   ```

2. 打开 AI 助手。

   期望：只显示模拟模式入口；此时不应加载对话历史。

3. 点击“对话历史”。

   期望：此时才触发分页加载。

4. 验证未启用 AI 对话记录存储。

   期望：显示“未启用 AI 对话记录存储”或等价空态；不自动 bootstrap，不创建 `workspace/ai`。

5. 验证暂无对话历史。

   期望：显示“暂无对话历史”；上一页/下一页不可用。

6. 验证有历史列表。

   期望：列表显示标题、更新时间、provider、消息数、引用数和状态；对话记录标识为非正式知识。

7. 验证分页。

   期望：显示当前页信息；第一页“上一页”不可用；存在更多数据时“下一页”可用；空页显示友好提示；每页 limit 不超过 50。

8. 打开单个 conversation 详情。

   期望：展示 messages、citations、policy decisions、task refs 的快照；不读取 task logs，不进入 formal search。

9. 验证详情筛选。

   - “全部”：显示消息、引用、策略、任务。
   - “消息”：只做 UI 过滤，显示消息。
   - “引用”：只做 UI 过滤，显示引用快照。
   - “策略”：只做 UI 过滤，显示 policy decision 快照。
   - “任务”：只做 UI 过滤，显示 task ref 快照。

   期望：切换筛选不重新读取 conversation 文件、不读取 task logs、不触发 search。

10. 点击“导出预览”。

    期望：显示 JSON preview；preview 内包含 `not_formal_knowledge=true` 或等价字段；不自动写文件。

11. 点击“复制 JSON”。

    期望：剪贴板内容等于当前 export payload preview；复制失败时显示错误态。

12. 删除确认。

    期望：取消确认时不删除；确认后显示“对话已删除”；不删除知识库、索引、memory 或其他对话外数据。

13. corrupt/error 状态。

    期望：corrupt conversation 打开时显示“读取对话失败”或等价错误态；不崩溃，不自动修复，不自动删除，不自动 bootstrap。

14. 确认不 startup auto-load。

    期望：仅打开主窗口或 AI 助手面板时不调用 conversation list；只有点击“对话历史”后才加载。

## 自动化验收命令

```bash
python scripts/kb.py audit
python scripts/kb.py secret-scan
python tests/smoke_test.py
python tests/governance_test.py
python tests/startup_smoke.py
python tests/ai_conversation_persistence_test.py
python tests/gui_ai_assistant_test.py
python tests/gui_conversation_history_test.py
python tests/gui_viewmodel_test.py
python -m compileall knowledge_app gui tests
```
