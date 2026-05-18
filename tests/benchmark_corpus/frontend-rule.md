---
title: React Hydration Boundary Rule
category: frontend
type: rule
status: active
confidence: high
source_type: official
source_url: "https://react.dev/reference/react-dom/client/hydrateRoot"
created_at: "2026-05-18T00:00:00"
last_reviewed: "2026-05-18"
reviewed_by: "benchmark"
valid_for: ["react", "ssr", "hydration"]
not_valid_for: []
project_scope: "search-quality"
supersedes: []
superseded_by: ""
risk_level: medium
verification_method: "search quality fixture assertion"
review_required: false
reviewed_at: "2026-05-18T00:00:00"
promoted_from: "tests/benchmark_corpus/frontend-rule.md"
---

# React Hydration Boundary Rule

React hydration work must keep server-rendered markup stable until `hydrateRoot` attaches client behavior.

## 可执行规则

- Do not render client-only timestamps, random IDs, or browser-only state before hydration completes.
- When a component needs client-only data, isolate it behind a hydration boundary and render deterministic fallback markup first.
- Treat hydration mismatch warnings as correctness bugs, not harmless console noise.

## 验证方式

Run SSR rendering tests and browser hydration checks for pages that use React hydration boundaries.
