---
title: "Maintenance 2026-05"
type: maintenance
status: active
source_type: internal_practice
created_at: "2026-05-18T18:42:53"
review_required: false
---

# Maintenance 2026-05

本报告是长期运维快照。默认只运行检查和报告，不会 promote，不会删除，不会修改 raw/distilled/rules。`VACUUM` 只有在显式传入 `--vacuum` 时运行。

## Summary

```json
{
  "month": "2026-05",
  "index": {
    "indexed": 0,
    "updated": 0,
    "deleted": 0,
    "skipped": 30,
    "hashed": 0,
    "elapsed_ms": 13
  },
  "lint_errors": 0,
  "lint_warnings": 0,
  "audit": {
    "documents": 30,
    "formal_missing_source_count": 0,
    "missing_formal_review_count": 0,
    "stale_active_count": 0,
    "raw_in_formal_layer_count": 0
  },
  "dedupe_groups": 8,
  "conflicts": 0,
  "stale": 0,
  "secret_findings": 0,
  "high_risk_secret_findings": 0,
  "stats": {
    "documents": 30,
    "chunks": 228,
    "by_category": {
      "ai_agent": 14,
      "frontend": 8,
      "ui_ux": 8
    },
    "by_layer": {
      "distilled": 5,
      "raw": 24,
      "rules": 1
    },
    "by_status": {
      "active": 1,
      "experimental": 29
    },
    "index_size_bytes": 245760,
    "last_indexed_at": "2026-05-18T18:32:01",
    "elapsed_ms": 1
  },
  "vacuum": null
}
```

## Index

```json
{
  "indexed": 0,
  "updated": 0,
  "deleted": 0,
  "skipped": 30,
  "hashed": 0,
  "elapsed_ms": 13
}
```

## Lint

```json
{
  "files_checked": 30,
  "error_count": 0,
  "warning_count": 0,
  "issues": [],
  "truncated": false
}
```

## Audit

```json
{
  "documents": 30,
  "by_category": {
    "ai_agent": 14,
    "frontend": 8,
    "ui_ux": 8
  },
  "by_layer": {
    "distilled": 5,
    "raw": 24,
    "rules": 1
  },
  "by_status": {
    "active": 1,
    "experimental": 29
  },
  "missing_source_count": 0,
  "formal_missing_source_count": 0,
  "missing_formal_review_count": 0,
  "stale_active_count": 0,
  "low_confidence_rules_count": 0,
  "raw_in_formal_layer_count": 0,
  "missing_source": [],
  "formal_missing_source": [],
  "missing_formal_review": [],
  "stale_active": [],
  "raw_in_formal_layer": []
}
```

## Dedupe

```json
{
  "count": 8,
  "groups": [
    {
      "kind": "content_hash",
      "key": "628fb9d9e0063a67e89e46d3882ecc15dd37de48388bdb1a82b3c977fe44b345",
      "duplicate_group": [
        {
          "id": 17,
          "path": "knowledge/09-ai-agent/distilled/2026-05-18-agents-md-project-guidance-rule.md",
          "title": "AGENTS.md Project Guidance Rule",
          "category": "ai_agent",
          "layer": "distilled",
          "status": "experimental",
          "type": "rule",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "ai_agent.agents-md-guidance",
          "canonical_id": ""
        },
        {
          "id": 30,
          "path": "knowledge/09-ai-agent/rules/agentsmd-project-guidance-rule.md",
          "title": "AGENTS.md Project Guidance Rule",
          "category": "ai_agent",
          "layer": "rules",
          "status": "active",
          "type": "rule",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "ai_agent.agents-md-guidance",
          "canonical_id": ""
        }
      ],
      "recommended_canonical_file": {
        "id": 30,
        "path": "knowledge/09-ai-agent/rules/agentsmd-project-guidance-rule.md",
        "title": "AGENTS.md Project Guidance Rule",
        "category": "ai_agent",
        "layer": "rules",
        "status": "active",
        "type": "rule",
        "confidence": "medium",
        "source_type": "official",
        "topic_id": "ai_agent.agents-md-guidance",
        "canonical_id": ""
      },
      "suggested_action": "merge",
      "evidence": {
        "content_hash": "628fb9d9e0063a67e89e46d3882ecc15dd37de48388bdb1a82b3c977fe44b345"
      }
    },
    {
      "kind": "normalized_title",
      "key": "ai_agent:agents md project guidance rule",
      "duplicate_group": [
        {
          "id": 17,
          "path": "knowledge/09-ai-agent/distilled/2026-05-18-agents-md-project-guidance-rule.md",
          "title": "AGENTS.md Project Guidance Rule",
          "category": "ai_agent",
          "layer": "distilled",
          "status": "experimental",
          "type": "rule",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "ai_agent.agents-md-guidance",
          "canonical_id": ""
        },
        {
          "id": 30,
          "path": "knowledge/09-ai-agent/rules/agentsmd-project-guidance-rule.md",
          "title": "AGENTS.md Project Guidance Rule",
          "category": "ai_agent",
          "layer": "rules",
          "status": "active",
          "type": "rule",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "ai_agent.agents-md-guidance",
          "canonical_id": ""
        }
      ],
      "recommended_canonical_file": {
        "id": 30,
        "path": "knowledge/09-ai-agent/rules/agentsmd-project-guidance-rule.md",
        "title": "AGENTS.md Project Guidance Rule",
        "category": "ai_agent",
        "layer": "rules",
        "status": "active",
        "type": "rule",
        "confidence": "medium",
        "source_type": "official",
        "topic_id": "ai_agent.agents-md-guidance",
        "canonical_id": ""
      },
      "suggested_action": "merge",
      "evidence": {
        "category": "ai_agent",
        "normalized_title": "agents md project guidance rule"
      }
    },
    {
      "kind": "source_url",
      "key": "https://developers.openai.com/codex/concepts/sandboxing",
      "duplicate_group": [
        {
          "id": 20,
          "path": "knowledge/09-ai-agent/distilled/2026-05-18-codex-sandboxing-permission-boundary-checklist.md",
          "title": "Codex Sandboxing Permission Boundary Checklist",
          "category": "ai_agent",
          "layer": "distilled",
          "status": "experimental",
          "type": "checklist",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "ai_agent.codex-sandboxing",
          "canonical_id": ""
        },
        {
          "id": 26,
          "path": "knowledge/09-ai-agent/raw/2026-05-18-openai-codex-sandboxing.md",
          "title": "OpenAI Codex Sandboxing",
          "category": "ai_agent",
          "layer": "raw",
          "status": "experimental",
          "type": "raw",
          "confidence": "high",
          "source_type": "official",
          "topic_id": "",
          "canonical_id": ""
        }
      ],
      "recommended_canonical_file": {
        "id": 20,
        "path": "knowledge/09-ai-agent/distilled/2026-05-18-codex-sandboxing-permission-boundary-checklist.md",
        "title": "Codex Sandboxing Permission Boundary Checklist",
        "category": "ai_agent",
        "layer": "distilled",
        "status": "experimental",
        "type": "checklist",
        "confidence": "medium",
        "source_type": "official",
        "topic_id": "ai_agent.codex-sandboxing",
        "canonical_id": ""
      },
      "suggested_action": "keep",
      "evidence": {
        "source_url": "https://developers.openai.com/codex/concepts/sandboxing"
      }
    },
    {
      "kind": "source_url",
      "key": "https://developers.openai.com/codex/github-action",
      "duplicate_group": [
        {
          "id": 18,
          "path": "knowledge/09-ai-agent/distilled/2026-05-18-codex-github-action-security-checklist.md",
          "title": "Codex GitHub Action Security Checklist",
          "category": "ai_agent",
          "layer": "distilled",
          "status": "experimental",
          "type": "checklist",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "ai_agent.codex-github-action-security",
          "canonical_id": ""
        },
        {
          "id": 23,
          "path": "knowledge/09-ai-agent/raw/2026-05-18-openai-codex-github-action.md",
          "title": "OpenAI Codex GitHub Action",
          "category": "ai_agent",
          "layer": "raw",
          "status": "experimental",
          "type": "raw",
          "confidence": "high",
          "source_type": "official",
          "topic_id": "",
          "canonical_id": ""
        }
      ],
      "recommended_canonical_file": {
        "id": 18,
        "path": "knowledge/09-ai-agent/distilled/2026-05-18-codex-github-action-security-checklist.md",
        "title": "Codex GitHub Action Security Checklist",
        "category": "ai_agent",
        "layer": "distilled",
        "status": "experimental",
        "type": "checklist",
        "confidence": "medium",
        "source_type": "official",
        "topic_id": "ai_agent.codex-github-action-security",
        "canonical_id": ""
      },
      "suggested_action": "keep",
      "evidence": {
        "source_url": "https://developers.openai.com/codex/github-action"
      }
    },
    {
      "kind": "source_url",
      "key": "https://developers.openai.com/codex/guides/agents-md",
      "duplicate_group": [
        {
          "id": 17,
          "path": "knowledge/09-ai-agent/distilled/2026-05-18-agents-md-project-guidance-rule.md",
          "title": "AGENTS.md Project Guidance Rule",
          "category": "ai_agent",
          "layer": "distilled",
          "status": "experimental",
          "type": "rule",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "ai_agent.agents-md-guidance",
          "canonical_id": ""
        },
        {
          "id": 22,
          "path": "knowledge/09-ai-agent/raw/2026-05-18-openai-codex-agents-md.md",
          "title": "OpenAI Codex AGENTS.md Guidance",
          "category": "ai_agent",
          "layer": "raw",
          "status": "experimental",
          "type": "raw",
          "confidence": "high",
          "source_type": "official",
          "topic_id": "",
          "canonical_id": ""
        },
        {
          "id": 30,
          "path": "knowledge/09-ai-agent/rules/agentsmd-project-guidance-rule.md",
          "title": "AGENTS.md Project Guidance Rule",
          "category": "ai_agent",
          "layer": "rules",
          "status": "active",
          "type": "rule",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "ai_agent.agents-md-guidance",
          "canonical_id": ""
        }
      ],
      "recommended_canonical_file": {
        "id": 30,
        "path": "knowledge/09-ai-agent/rules/agentsmd-project-guidance-rule.md",
        "title": "AGENTS.md Project Guidance Rule",
        "category": "ai_agent",
        "layer": "rules",
        "status": "active",
        "type": "rule",
        "confidence": "medium",
        "source_type": "official",
        "topic_id": "ai_agent.agents-md-guidance",
        "canonical_id": ""
      },
      "suggested_action": "merge",
      "evidence": {
        "source_url": "https://developers.openai.com/codex/guides/agents-md"
      }
    },
    {
      "kind": "source_url",
      "key": "https://developers.openai.com/codex/mcp",
      "duplicate_group": [
        {
          "id": 19,
          "path": "knowledge/09-ai-agent/distilled/2026-05-18-codex-mcp-security-checklist.md",
          "title": "Codex MCP Security Checklist",
          "category": "ai_agent",
          "layer": "distilled",
          "status": "experimental",
          "type": "checklist",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "ai_agent.codex-mcp-security",
          "canonical_id": ""
        },
        {
          "id": 24,
          "path": "knowledge/09-ai-agent/raw/2026-05-18-openai-codex-mcp.md",
          "title": "OpenAI Codex MCP Integration",
          "category": "ai_agent",
          "layer": "raw",
          "status": "experimental",
          "type": "raw",
          "confidence": "high",
          "source_type": "official",
          "topic_id": "",
          "canonical_id": ""
        }
      ],
      "recommended_canonical_file": {
        "id": 19,
        "path": "knowledge/09-ai-agent/distilled/2026-05-18-codex-mcp-security-checklist.md",
        "title": "Codex MCP Security Checklist",
        "category": "ai_agent",
        "layer": "distilled",
        "status": "experimental",
        "type": "checklist",
        "confidence": "medium",
        "source_type": "official",
        "topic_id": "ai_agent.codex-mcp-security",
        "canonical_id": ""
      },
      "suggested_action": "keep",
      "evidence": {
        "source_url": "https://developers.openai.com/codex/mcp"
      }
    },
    {
      "kind": "source_url",
      "key": "https://web.dev/articles/vitals",
      "duplicate_group": [
        {
          "id": 1,
          "path": "knowledge/01-frontend/distilled/2026-05-18-core-web-vitals-release-checklist.md",
          "title": "Core Web Vitals Release Checklist",
          "category": "frontend",
          "layer": "distilled",
          "status": "experimental",
          "type": "checklist",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "frontend.core-web-vitals-release",
          "canonical_id": ""
        },
        {
          "id": 8,
          "path": "knowledge/01-frontend/raw/2026-05-18-web-dev-core-web-vitals.md",
          "title": "web.dev Core Web Vitals",
          "category": "frontend",
          "layer": "raw",
          "status": "experimental",
          "type": "raw",
          "confidence": "high",
          "source_type": "official",
          "topic_id": "",
          "canonical_id": ""
        }
      ],
      "recommended_canonical_file": {
        "id": 1,
        "path": "knowledge/01-frontend/distilled/2026-05-18-core-web-vitals-release-checklist.md",
        "title": "Core Web Vitals Release Checklist",
        "category": "frontend",
        "layer": "distilled",
        "status": "experimental",
        "type": "checklist",
        "confidence": "medium",
        "source_type": "official",
        "topic_id": "frontend.core-web-vitals-release",
        "canonical_id": ""
      },
      "suggested_action": "keep",
      "evidence": {
        "source_url": "https://web.dev/articles/vitals"
      }
    },
    {
      "kind": "topic_id",
      "key": "ai_agent:ai_agent.agents-md-guidance",
      "duplicate_group": [
        {
          "id": 17,
          "path": "knowledge/09-ai-agent/distilled/2026-05-18-agents-md-project-guidance-rule.md",
          "title": "AGENTS.md Project Guidance Rule",
          "category": "ai_agent",
          "layer": "distilled",
          "status": "experimental",
          "type": "rule",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "ai_agent.agents-md-guidance",
          "canonical_id": ""
        },
        {
          "id": 30,
          "path": "knowledge/09-ai-agent/rules/agentsmd-project-guidance-rule.md",
          "title": "AGENTS.md Project Guidance Rule",
          "category": "ai_agent",
          "layer": "rules",
          "status": "active",
          "type": "rule",
          "confidence": "medium",
          "source_type": "official",
          "topic_id": "ai_agent.agents-md-guidance",
          "canonical_id": ""
        }
      ],
      "recommended_canonical_file": {
        "id": 30,
        "path": "knowledge/09-ai-agent/rules/agentsmd-project-guidance-rule.md",
        "title": "AGENTS.md Project Guidance Rule",
        "category": "ai_agent",
        "layer": "rules",
        "status": "active",
        "type": "rule",
        "confidence": "medium",
        "source_type": "official",
        "topic_id": "ai_agent.agents-md-guidance",
        "canonical_id": ""
      },
      "suggested_action": "merge",
      "evidence": {
        "category": "ai_agent",
        "topic_id": "ai_agent.agents-md-guidance"
      }
    }
  ]
}
```

## Conflicts

```json
{
  "count": 0,
  "results": []
}
```

## Stale

```json
{
  "days": 180,
  "count": 0,
  "results": []
}
```

## Secret Scan

```json
{
  "scanned_files": 89,
  "findings_count": 0,
  "high_risk_count": 0,
  "findings": [],
  "truncated": false,
  "allow_marker": "TEST_ONLY_SECRET_PATTERN",
  "elapsed_ms": 159
}
```

## Stats

```json
{
  "documents": 30,
  "chunks": 228,
  "by_category": {
    "ai_agent": 14,
    "frontend": 8,
    "ui_ux": 8
  },
  "by_layer": {
    "distilled": 5,
    "raw": 24,
    "rules": 1
  },
  "by_status": {
    "active": 1,
    "experimental": 29
  },
  "index_size_bytes": 245760,
  "last_indexed_at": "2026-05-18T18:32:01",
  "elapsed_ms": 1
}
```

## Vacuum

```json
{
  "requested": false,
  "result": null,
  "post_vacuum_stats": null
}
```
