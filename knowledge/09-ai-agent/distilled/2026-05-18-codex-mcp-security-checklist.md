---
title: "Codex MCP Security Checklist"
category: ai_agent
type: checklist
status: experimental
confidence: medium
source_type: official
source_url: "https://developers.openai.com/codex/mcp"
source_file: "knowledge/09-ai-agent/raw/2026-05-18-openai-codex-mcp.md"
created_at: "2026-05-18T14:48:07+08:00"
last_reviewed: ""
reviewed_by: ""
reviewed_at: ""
review_required: true
valid_for: ["Codex MCP integration planning", "external tool access review", "agent context boundary review"]
not_valid_for: ["automatic MCP enablement", "unreviewed production automation", "rules for non-Codex agents without adaptation"]
project_scope: "personal-knowledge-base"
topic_id: "ai_agent.codex-mcp-security"
canonical_id: ""
source_hash: ""
content_hash: ""
risk_level: high
verification_method: "Not verified yet. Human reviewer must compare against the official Codex MCP documentation, threat-model the target MCP server, and test permission boundaries before promotion."
review_cycle_days: 90
supersedes: []
superseded_by: ""
deprecated_reason: ""
rejected_reason: ""
quarantined_reason: ""
review_note: ""
---

# 一句话结论

MCP 接入应先被当作外部工具信任边界问题处理；本卡片只是待审核 checklist，未 promote 前不能作为正式项目规则。

## 来源

- source_url: https://developers.openai.com/codex/mcp
- source_file: knowledge/09-ai-agent/raw/2026-05-18-openai-codex-mcp.md
- source_type: official
- raw summary: Codex MCP 文档与外部工具连接、权限、信任和上下文边界相关。

## 适用场景

- 评估是否为 Codex 启用新的 MCP server。
- 审查 MCP tool 是否会接触本地文件、网络、仓库、密钥或外部系统。
- 为 Agent 工具说明、权限边界和审计记录设计审核清单。

## 不适用场景

- 不适用于未经人工复核就启用 MCP server。
- 不适用于把任何 MCP tool 直接加入正式项目工作流。
- 不适用于保存或复述 MCP 文档全文。

## 背景

raw 记录指出 MCP 会改变 Codex 与外部系统的连接方式，并可能影响安全边界。raw 的提炼问题集中在：启用 MCP server 前需要哪些安全检查、哪些能力需要显式审批、如何记录和审计 MCP 使用。

## 核心要点

- MCP 是外部工具边界，不是普通知识来源。
- 每个 MCP server 都需要明确数据访问范围。
- Tool 描述应帮助 Agent 正确选择工具，同时不能掩盖风险。
- 需要区分只读、写入、执行命令、网络访问和敏感数据访问能力。
- 审计要求应在启用前确定，而不是事故后补充。

## 推荐做法 / Checklist Items

- 记录 MCP server 的来源、维护者、用途和启用理由。
- 列出 MCP server 暴露的每个 tool，以及它可能读取、写入或发送的数据。
- 标注 tool 是否可能访问仓库、文件系统、网络、外部账号或私有数据。
- 对写入、删除、执行、发布、发送请求等高影响能力设置人工审批要求。
- 明确哪些数据不得传入 MCP tool，包括密钥、token、客户隐私和未公开业务数据。
- 为 MCP 使用保留日志或任务记录，便于后续 audit。
- 为 Agent 写清楚何时允许调用 MCP，以及何时必须先向用户确认。
- 在正式使用前用低风险测试任务验证权限边界。

## 反例 / Anti-patterns

- 因为来源是官方文档就默认启用所有 MCP server。
- MCP tool 描述模糊，导致 Agent 无法判断能力边界。
- 允许 MCP tool 默认访问敏感目录或私有凭据。
- 缺少审计记录，无法复盘 Agent 调用了哪些外部能力。

## 对我的项目有什么影响

如果未来为本知识库或其他项目接入 MCP，应把 MCP 视为高风险扩展点。相关规则必须先进入 distilled，经过人工审核和安全复核后才可 promote。

## 可执行规则或检查项

- 未完成 tool 权限表前，不启用 MCP server。
- 未确认敏感数据边界前，不允许 Agent 把项目上下文传入 MCP tool。
- 高影响 MCP tool 必须有显式审批策略。
- 每次新增或更新 MCP server 后，应重新运行 security review。

## 可给 Codex / Agent 使用的指令

未 promote 前仅可作为审查草案：在评估 MCP 接入时，先列出工具能力、数据边界、审批要求和审计方式；不要把本卡片当作正式项目规则。

## 验证方式

- 人工对照官方 Codex MCP 文档复核 checklist 是否准确。
- 对目标 MCP server 做最小权限测试。
- 检查是否能阻止敏感文件、secret 和私有数据外泄。
- 复核 Agent 工具说明是否足够具体，能支持正确工具选择。

## 人工审核要求

- 必须由熟悉 Codex 权限模型和项目安全边界的人审核。
- promote 前必须补充具体 MCP server 示例和验证记录。
- 高风险项需要记录 review_note。

## 来源与备注

本卡片只基于 raw 中的 short_summary、learn_focus、possible_output_targets、extraction_questions 和 notes 提炼；未抓取或保存网页全文。未经审核不得进入 rules、snippets 或 checklists。
