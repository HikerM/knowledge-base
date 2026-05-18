---
title: SQL Injection Prevention Checklist
category: security
type: checklist
status: active
confidence: high
source_type: official
source_url: "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html"
created_at: "2026-05-18T00:00:00"
last_reviewed: "2026-05-18"
reviewed_by: "benchmark"
valid_for: ["sql", "api", "backend"]
not_valid_for: []
project_scope: "search-quality"
supersedes: []
superseded_by: ""
risk_level: high
verification_method: "search quality fixture assertion"
review_required: false
reviewed_at: "2026-05-18T00:00:00"
promoted_from: "tests/benchmark_corpus/security-checklist.md"
---

# SQL Injection Prevention Checklist

Use this checklist before merging data access code that constructs SQL queries.

## 检查项

- Use parameterized queries or prepared statements for every untrusted input.
- Do not concatenate request parameters into SQL strings.
- Validate allowlisted identifiers for table names, column names, and sort directions.
- Add regression tests for SQL injection payloads around authentication and search endpoints.

## 验证方式

Run unit tests with malicious SQL injection payloads and inspect data access code paths.
