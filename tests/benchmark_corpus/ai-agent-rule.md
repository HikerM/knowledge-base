---
title: Codex Context Retrieval Rule
category: ai_agent
type: rule
status: active
confidence: high
source_type: internal_practice
source_url: ""
created_at: "2026-05-18T00:00:00"
last_reviewed: "2026-05-18"
reviewed_by: "benchmark"
valid_for: ["codex", "agent-context", "knowledge-base"]
not_valid_for: []
project_scope: "search-quality"
supersedes: []
superseded_by: ""
risk_level: medium
verification_method: "search quality fixture assertion"
review_required: false
reviewed_at: "2026-05-18T00:00:00"
review_note: "Internal practice fixture for agent retrieval behavior."
promoted_from: "tests/benchmark_corpus/ai-agent-rule.md"
---

# Codex Context Retrieval Rule

Codex should search the formal knowledge index before opening full Markdown files for project decisions.

## 可执行规则

- Run `search` first to retrieve concise formal chunks from rules, checklists, and snippets.
- Open only the few documents needed for implementation context.
- Treat `research` results as unreviewed learning material unless the user explicitly promotes them.

## 验证方式

Inspect agent logs for search-before-open behavior and absence of full-directory reads.
