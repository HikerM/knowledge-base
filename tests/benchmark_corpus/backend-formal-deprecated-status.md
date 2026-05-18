---
title: Formal Deprecated Status Rule
category: backend
type: rule
status: deprecated
confidence: medium
source_type: internal_practice
source_url: ""
created_at: "2026-05-18T00:00:00"
last_reviewed: "2026-05-18"
reviewed_by: "benchmark"
valid_for: ["backend-cache"]
not_valid_for: []
project_scope: "search-quality"
supersedes: []
superseded_by: "backend-active-cache-rule.md"
risk_level: medium
verification_method: "search deprecated status fixture assertion"
review_required: false
reviewed_at: "2026-05-18T00:00:00"
deprecation_reason: "Deprecated status fixture should not appear in default search even from a formal layer."
---

# Formal Deprecated Status Rule

This formal deprecated sentinel cache marker lives in a rules layer fixture but has status deprecated.

## Historical Guidance

The formal deprecated sentinel cache marker should only appear when search is run with explicit deprecated inclusion.
