---
title: "Core Web Vitals Release Checklist"
category: frontend
type: checklist
status: experimental
confidence: medium
source_type: official
source_url: "https://web.dev/articles/vitals"
source_file: "knowledge/01-frontend/raw/2026-05-18-web-dev-core-web-vitals.md"
created_at: "2026-05-18T14:48:07+08:00"
last_reviewed: ""
reviewed_by: ""
reviewed_at: ""
review_required: true
valid_for: ["web frontend release review", "performance measurement planning", "user-perceived performance checklist"]
not_valid_for: ["non-web UI", "native mobile performance gates", "project-specific thresholds before calibration"]
project_scope: "personal-knowledge-base"
topic_id: "frontend.core-web-vitals-release"
canonical_id: ""
source_hash: ""
content_hash: ""
risk_level: medium
verification_method: "Not verified yet. Human reviewer must compare against web.dev Core Web Vitals guidance and define project-specific measurement tools and thresholds before promotion."
review_cycle_days: 180
supersedes: []
superseded_by: ""
deprecated_reason: ""
rejected_reason: ""
quarantined_reason: ""
review_note: ""
---

# 一句话结论

Web 前端发布前应检查 LCP、CLS、INP 和测量方式，但阈值和阻断策略必须经项目审核后才能成为正式规则。

## 来源

- source_url: https://web.dev/articles/vitals
- source_file: knowledge/01-frontend/raw/2026-05-18-web-dev-core-web-vitals.md
- source_type: official
- raw summary: web.dev Web Vitals / Core Web Vitals 与用户感知性能和发布检查相关。

## 适用场景

- Web 前端发布前性能检查。
- 设计性能预算和 release gate。
- 统一 lab 与 field measurement 的解释方式。

## 不适用场景

- 不适用于没有 Web 页面渲染的后端服务。
- 不适用于尚未定义目标用户、页面类型和设备范围的项目。
- 不适用于把未校准阈值直接作为发布阻断规则。

## 背景

raw 的学习重点包括 LCP、CLS、INP、performance measurement、lab versus field measurement。提炼问题关注哪些指标应成为 release-blocking、阈值如何因项目而异、测量工具如何标准化。

## 核心要点

- Core Web Vitals 应作为用户感知性能的核心检查入口。
- LCP、CLS、INP 需要分别跟踪，不能只看单一总分。
- lab 数据和 field 数据含义不同，需要分开记录。
- release gate 必须结合项目实际页面、用户设备和业务风险。
- 未审核前，本 checklist 只能作为性能审查草案。

## 推荐做法 / Checklist Items

- 发布前列出需要检查的关键页面或流程。
- 对每个关键页面记录 LCP、CLS、INP 的测量结果。
- 标注测量来源是 lab、field，还是两者都有。
- 记录使用的工具、环境、设备、网络条件和采样窗口。
- 对性能退化设置 review 阈值；正式阻断阈值需由项目审核确认。
- 对影响 LCP 的首屏资源、CLS 的布局稳定性、INP 的交互响应做专项排查。
- 发布后保留监控或复测计划，避免只在发布前一次性检查。
- 对性能问题关联具体改动、页面和责任人。

## 反例 / Anti-patterns

- 只看本地开发机 Lighthouse 分数就判定性能合格。
- 不区分实验室数据和真实用户数据。
- 对所有页面使用同一未校准阈值。
- 发现性能退化但没有记录原因和后续验证。

## 对我的项目有什么影响

如果未来本知识库或相关前端工具提供 Web UI，发布前应建立性能检查清单。正式阈值需要结合实际页面复杂度和用户设备后再 promote。

## 可执行规则或检查项

- 每个 Web release 至少记录关键页面的 LCP、CLS、INP 检查结果。
- lab 与 field 数据必须标注来源。
- 阈值未审核前，不应作为自动发布阻断条件。
- 性能问题必须关联页面、指标和后续验证方式。

## 可给 Codex / Agent 使用的指令

未 promote 前仅可作为审查草案：在 Web 发布检查中列出关键页面、LCP/CLS/INP、测量工具和环境；不要自动发明正式阈值。

## 验证方式

- 人工对照 web.dev Web Vitals 文档复核指标解释。
- 选择至少一个真实页面进行 lab measurement。
- 如果可用，补充 field data 来源和采样说明。
- 审核后再定义 release-blocking 阈值。

## 人工审核要求

- 前端或性能负责人需要确认适用页面、测量工具和阈值策略。
- promote 前必须补充项目级性能预算或明确暂不设置阻断阈值。
- 若指标定义或浏览器生态变化，应提前复查。

## 来源与备注

本卡片只基于 raw 中的官方来源摘要、学习重点和提炼问题生成，未保存网页全文。未经审核不得作为正式 frontend release checklist。
