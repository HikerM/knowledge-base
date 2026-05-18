---
title: AGENTS.md Project Guidance Rule
category: ai_agent
type: rule
status: active
confidence: medium
source_type: official
source_url: "https://developers.openai.com/codex/guides/agents-md"
source_file: knowledge/09-ai-agent/raw/2026-05-18-openai-codex-agents-md.md
created_at: "2026-05-18T14:48:07+08:00"
last_reviewed: 2026-05-18
reviewed_by: linfenghiker
reviewed_at: "2026-05-18T18:31:54"
review_required: false
valid_for: ["personal-knowledge-base AGENTS.md maintenance", "repository-level Codex instruction governance", "agent knowledge-source boundary rules"]
not_valid_for: ["overriding user instructions", "encoding unreviewed raw as formal project policy", "generic agent rules without repository scope"]
project_scope: personal-knowledge-base
topic_id: ai_agent.agents-md-guidance
canonical_id: ""
source_hash: ""
content_hash: ""
risk_level: medium
verification_method: Checked required frontmatter and body sections; compared with current AGENTS.md governance rules; spot-checked against official OpenAI AGENTS.md guidance; ran kb lint, audit, review-queue, secret-scan, and search.
review_cycle_days: 180
supersedes: []
superseded_by: ""
deprecated_reason: ""
rejected_reason: ""
quarantined_reason: ""
review_note: Promote as a medium-risk repository instruction governance rule. Scope is AGENTS.md maintenance and Codex behavior boundaries only; it must not authorize raw/distilled content as formal rules without human promote.
promoted_from: knowledge/09-ai-agent/distilled/2026-05-18-agents-md-project-guidance-rule.md
---

# 一句话结论

AGENTS.md 应只保存经过项目确认的长期约束、工作流和安全边界；本卡片是待审核规则草案，不是正式 AGENTS.md 规范。

## 来源

- source_url: https://developers.openai.com/codex/guides/agents-md
- source_file: knowledge/09-ai-agent/raw/2026-05-18-openai-codex-agents-md.md
- source_type: official
- raw summary: 官方 AGENTS.md guidance 与仓库级 Codex 指令、scope、precedence 和可维护约定相关。

## 适用场景

- 为新仓库设计 AGENTS.md。
- 维护现有仓库的 Codex 工作方式、安全约束和验收流程。
- 规范 Agent 如何读取知识库、执行命令和处理未审核内容。

## 不适用场景

- 不适用于把临时任务要求写成永久规则。
- 不适用于将 raw/distilled 未审核内容写入正式 AGENTS.md。
- 不适用于覆盖用户在当前任务中的明确指令。

## 背景

raw 的学习重点包括 project-level instruction design、scope、precedence 和维护 practices。提炼问题关注每个 AGENTS.md 应包含什么、如何避免冲突和 Agent drift、修改后应运行哪些检查。

## 核心要点

- AGENTS.md 面向长期项目行为，不应塞入临时偏好。
- 指令应有明确适用范围和优先级边界。
- 安全约束、测试命令和禁止事项应具体可执行。
- 修改 AGENTS.md 后应有验证流程。
- AGENTS.md 不应把未审核 raw 当作正式规则。

## 推荐做法 / Checklist Items

- 写清仓库用途、事实来源和生成物边界。
- 写清 Codex 默认信任哪些层级的知识。
- 写清搜索知识库时必须先 search，再按需 open 少量文件。
- 写清禁止读取、提交或暴露 secret/private 数据。
- 写清代码修改、测试、CI、commit、push 的项目约定。
- 写清 raw/research/distilled 结果必须标注未审核。
- 保持指令短而具体，避免泛泛的质量口号。
- 修改 AGENTS.md 后运行 smoke test、audit 或相关项目验收。

## 反例 / Anti-patterns

- 把外部文章摘要直接写成 AGENTS.md 正式规则。
- 写入无法执行或无法验证的抽象原则。
- 同一仓库多个指令文件互相矛盾。
- 忽略用户当前明确指令，机械套用仓库规则。

## 对我的项目有什么影响

本知识库的 AGENTS.md 是防污染边界的一部分。它应继续明确 Markdown 是事实来源、SQLite 是索引层、raw/distilled 不可作为正式规则，以及 Codex 必须先 search 后 open。

## 可执行规则或检查项

- AGENTS.md 中的正式规则必须来自 rules、checklists 或 snippets，或来自用户明确要求。
- AGENTS.md 不应引用 raw 作为项目决策依据。
- 每次修改 AGENTS.md 后应运行 `python scripts/kb.py audit` 和相关测试。
- 如果指令冲突，以用户当前明确指令和更高优先级系统规则为准。

## 可给 Codex / Agent 使用的指令

未 promote 前仅可作为审查草案：维护 AGENTS.md 时，只写长期、可执行、可验证的仓库约束；不要把 raw 或 distilled 内容写成正式项目规则。

## 验证方式

- 人工对照官方 AGENTS.md guidance 复核。
- 检查 AGENTS.md 是否包含事实来源、信任层级、安全边界和测试命令。
- 用一个真实任务验证 Agent 是否能按 AGENTS.md 执行 search-before-open。
- 运行 audit，确认没有 raw 进入正式层。

## 人工审核要求

- 审核人需确认本规则不与现有 AGENTS.md 和用户指令优先级冲突。
- promote 前应补充一个 AGENTS.md 最小模板或 checklist。
- 如果用于多个项目，需要明确哪些规则可复用、哪些是本仓库专用。

## 来源与备注

本卡片只基于 raw 摘要和提炼问题生成，未保存网页全文。它是待审核规则草案，未 promote 前不能作为正式 Codex/Agent 项目规则。