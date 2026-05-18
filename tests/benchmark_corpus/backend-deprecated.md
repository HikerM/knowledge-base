---
title: Legacy Cache Timeout Rule
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
superseded_by: "modern-cache-expiration-rule.md"
risk_level: medium
verification_method: "search quality fixture assertion"
review_required: false
reviewed_at: "2026-05-18T00:00:00"
deprecation_reason: "Deprecated fixture should not appear in default search."
---

# Legacy Cache Timeout Rule

This legacy cache timeout marker is deprecated and should be excluded from default search results.

## 历史说明

Old guidance suggested a fixed cache timeout for every backend endpoint. It was replaced by endpoint-specific cache expiration rules.
