---
title: ""
category: ai_agent
type: codex_task
status: experimental
confidence: medium
source_type: internal_practice
source_url: ""
created_at: ""
last_reviewed: ""
reviewed_by: ""
valid_for: []
not_valid_for: []
project_scope: ""
supersedes: []
superseded_by: ""
risk_level: medium
verification_method: ""
review_required: true
---

# Codex / Agent 任务上下文

用于把已审核知识整理成可交给 Codex 或其他 Agent 的任务说明。不得引用未审核 raw 作为正式规则。

## 任务目标

写清楚 Agent 需要完成的最终产物、约束和验收标准。

## 可用知识

- 引用 rules、checklists、snippets 中的文件路径或文档 id。
- 如需参考 distilled，必须标注仍需人工判断。

## 禁止使用

- 不得把 raw 当作正式指导。
- 不得保存真实密钥、密码、token 或客户隐私数据。
- 不得在搜索知识库时全量读取 knowledge/。

## 执行步骤

1. 先用 `python scripts/kb.py search` 检索相关知识。
2. 只对少量命中文档使用 `python scripts/kb.py open`。
3. 根据 rules、checklists、snippets 生成项目方案或代码修改。
4. 明确列出验证命令和结果。

## 验证方式

- 检索命令:
- 引用文档:
- 项目测试:
- 人工审查:

## 输出要求

最终输出需要说明使用了哪些已审核知识、哪些内容只是参考，以及剩余风险。
