---
title: "Codex Sandboxing Permission Boundary Checklist"
category: ai_agent
type: checklist
status: experimental
confidence: medium
source_type: official
source_url: "https://developers.openai.com/codex/concepts/sandboxing"
source_file: "knowledge/09-ai-agent/raw/2026-05-18-openai-codex-sandboxing.md"
created_at: "2026-05-18T14:48:07+08:00"
last_reviewed: ""
reviewed_by: ""
reviewed_at: ""
review_required: true
valid_for: ["Codex local execution review", "sandbox policy design", "command approval boundary review"]
not_valid_for: ["automatic escalation policy", "unreviewed destructive command execution", "non-Codex sandbox assumptions"]
project_scope: "personal-knowledge-base"
topic_id: "ai_agent.codex-sandboxing"
canonical_id: ""
source_hash: ""
content_hash: ""
risk_level: high
verification_method: "Not verified yet. Human reviewer must compare against the official Codex sandboxing documentation and test filesystem, command, and network boundaries in a disposable workspace before promotion."
review_cycle_days: 90
supersedes: []
superseded_by: ""
deprecated_reason: ""
rejected_reason: ""
quarantined_reason: ""
review_note: ""
---

# 一句话结论

Codex sandbox 策略应默认限制高影响操作，并把例外审批记录清楚；本卡片未审核，不能作为正式权限规则。

## 来源

- source_url: https://developers.openai.com/codex/concepts/sandboxing
- source_file: knowledge/09-ai-agent/raw/2026-05-18-openai-codex-sandboxing.md
- source_type: official
- raw summary: Codex sandboxing 与文件系统、命令和网络边界相关。

## 适用场景

- 为本地 Codex 工作流定义默认 sandbox 和审批姿态。
- 评估哪些命令、文件操作或网络访问需要显式确认。
- 为长期自动化任务制定权限边界。

## 不适用场景

- 不适用于绕过用户审批或系统权限。
- 不适用于把高风险命令加入默认允许列表。
- 不适用于未经测试的生产环境自动化。

## 背景

raw 的学习重点包括 filesystem access、command approval、network boundaries 和 workspace isolation。提炼问题聚焦于默认审批姿态、危险命令识别以及 sandbox 例外记录。

## 核心要点

- 权限边界必须先于自动化能力定义。
- 文件系统、命令、网络和外部系统访问应分别审查。
- 破坏性命令和跨目录操作需要更严格审批。
- sandbox 例外必须有原因、范围和有效期。
- 自动化任务不应静默扩大权限。

## 推荐做法 / Checklist Items

- 明确默认 sandbox 模式和允许的工作目录。
- 标记读、写、删除、移动、递归操作、外部网络访问等权限级别。
- 对删除、覆盖、发布、凭据访问、跨仓库写入等操作要求人工确认。
- 记录每个 sandbox 例外的原因、目标路径、命令范围和审核人。
- 在运行长期任务前确认不会读取 `.env`、`private/`、`.kb/` 或 secret 文件。
- 对命令输出中可能包含敏感信息的步骤做额外检查。
- 在 disposable workspace 中验证高风险命令。
- 将危险命令策略写入 AGENTS.md 或项目规则前必须人工 review。

## 反例 / Anti-patterns

- 默认允许 Agent 递归删除、移动或覆盖文件。
- 把网络访问和本地文件访问混为一个权限级别。
- 因为命令在本机运行就跳过审批。
- 例外权限没有记录，后续无法审计。

## 对我的项目有什么影响

本知识库已经强调 search-before-open 和禁止全量读取。未来若加入自动维护或外部工具，需要继续保持最小权限和显式审批，避免 Agent 误读、误删或泄露内容。

## 可执行规则或检查项

- 任何超出当前工作区的写操作都必须被视为高风险。
- 任何可能删除、覆盖、移动大量文件的命令都需要人工确认。
- 任何会读取或暴露 secret/private 文件的操作都必须拒绝或隔离。
- sandbox 例外必须能在审计报告中追溯。

## 可给 Codex / Agent 使用的指令

未 promote 前仅可作为审查草案：执行命令前先识别文件系统、命令和网络边界；遇到删除、覆盖、跨目录、secret 或外部系统操作时必须停下来要求人工确认。

## 验证方式

- 对照官方 sandboxing 文档复核概念是否准确。
- 在临时目录测试安全命令和危险命令的边界。
- 检查 AGENTS.md 是否明确禁止 destructive fallback。
- 复核 CI/脚本是否不会访问被忽略的私有目录。

## 人工审核要求

- 高风险 AI Agent 权限内容必须经过人工安全审核。
- promote 前需补充实际 sandbox 配置、命令示例和拒绝示例。
- 审核人需确认规则不会与用户显式指令或系统权限策略冲突。

## 来源与备注

本卡片只基于 raw 摘要和提炼问题生成，未保存官方网页全文。未经审核不得进入正式规则层。
