---
title: "Codex GitHub Action Security Checklist"
category: ai_agent
type: checklist
status: experimental
confidence: medium
source_type: official
source_url: "https://developers.openai.com/codex/github-action"
source_file: "knowledge/09-ai-agent/raw/2026-05-18-openai-codex-github-action.md"
created_at: "2026-05-18T14:48:07+08:00"
last_reviewed: ""
reviewed_by: ""
reviewed_at: ""
review_required: true
valid_for: ["Codex GitHub Action evaluation", "CI agent automation review", "repository permission design"]
not_valid_for: ["automatic write access without review", "secret-bearing workflow experiments", "production CI rollout without security approval"]
project_scope: "personal-knowledge-base"
topic_id: "ai_agent.codex-github-action-security"
canonical_id: ""
source_hash: ""
content_hash: ""
risk_level: high
verification_method: "Not verified yet. Human reviewer must compare against official Codex GitHub Action documentation, inspect GitHub workflow permissions, and verify secret exposure controls before promotion."
review_cycle_days: 90
supersedes: []
superseded_by: ""
deprecated_reason: ""
rejected_reason: ""
quarantined_reason: ""
review_note: ""
---

# 一句话结论

Codex GitHub Action 应先按 CI/CD 安全边界审查触发条件、仓库权限和 secret 暴露面；本卡片未审核，不能作为正式项目规则。

## 来源

- source_url: https://developers.openai.com/codex/github-action
- source_file: knowledge/09-ai-agent/raw/2026-05-18-openai-codex-github-action.md
- source_type: official
- raw summary: Codex GitHub Action 与 CI/CD 自动化、仓库权限和安全执行相关。

## 适用场景

- 评估是否在 GitHub Actions 中运行 Codex。
- 设计最小权限 workflow。
- 审查 Agent 自动化是否可能修改仓库、读取 secret 或影响发布流程。

## 不适用场景

- 不适用于未审核的自动 merge、自动发布或自动部署。
- 不适用于把 secret 暴露给不可信任务上下文。
- 不适用于跳过本地和 CI 验收命令。

## 背景

raw 的学习重点包括 workflow triggers、repository permissions 和 safe automation boundaries。提炼问题集中在最小权限、CI secrets 保护、自动运行和人工审批边界。

## 核心要点

- GitHub Action 是仓库级自动化入口，风险高于本地一次性命令。
- 权限应按任务最小化，而不是默认写权限。
- secret 暴露面需要单独审查。
- 自动触发条件和人工审批条件必须明确。
- 自动化变更必须经过测试、audit 和 secret scan。

## 推荐做法 / Checklist Items

- 列出 workflow 触发方式，并区分 push、pull_request、manual dispatch 等风险。
- 明确 workflow 需要的最小仓库权限。
- 检查是否需要写权限；如果需要，说明具体写入对象和审批边界。
- 明确 Codex 是否能访问 secrets，以及哪些任务绝不能暴露 secrets。
- 对来自 fork、外部 PR 或不可信输入的场景设置更严格限制。
- 要求自动化变更先运行 smoke test、search quality test、audit 和 secret-scan。
- 对自动 commit、push、tag、release、deploy 等高影响动作设置人工确认。
- 保留 workflow 运行记录和失败日志，便于安全复盘。

## 反例 / Anti-patterns

- 以默认写权限运行所有 Codex workflow。
- 在未审查输入来源的 PR 上暴露 secrets。
- 让 Agent 在 CI 中自动修改仓库并直接发布。
- CI 失败时绕过测试继续推送。

## 对我的项目有什么影响

本仓库已经公开发布，任何 GitHub Action 自动化都必须保护 public repo 安全边界。未来若启用 Codex GitHub Action，应先以只读或受限验证流程开始。

## 可执行规则或检查项

- 未完成权限和 secret 审查前，不启用 Codex GitHub Action 写入能力。
- 所有 Agent 生成的 CI 变更必须通过现有验收命令。
- 任何 tag/release/push 自动化都必须有人工确认。
- workflow 权限应在 YAML 中显式声明，而不是依赖默认权限。

## 可给 Codex / Agent 使用的指令

未 promote 前仅可作为审查草案：设计 GitHub Action 时先列出触发器、权限、secret 暴露面、人工审批点和必须通过的验收命令；不要自动启用写入或发布流程。

## 验证方式

- 人工对照官方 Codex GitHub Action 文档复核。
- 检查 workflow permissions 是否最小化。
- 在测试仓库或受限分支验证触发条件。
- 运行 secret-scan 并确认没有 secret 暴露。

## 人工审核要求

- 必须由了解 GitHub Actions 权限和仓库安全的人审核。
- promote 前应补充实际 workflow 样例和权限矩阵。
- 高风险自动化必须记录 review_note 和回滚方式。

## 来源与备注

本卡片只基于 raw 中的官方来源摘要、学习重点和提炼问题生成，未保存网页全文。未经审核不得作为正式 CI/CD 规则。
