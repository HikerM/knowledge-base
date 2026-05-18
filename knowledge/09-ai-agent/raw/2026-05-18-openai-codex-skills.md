---
title: "OpenAI Codex Agent Skills"
category: ai_agent
type: raw
status: experimental
confidence: high
source_type: official
source_url: "https://developers.openai.com/codex/skills"
created_at: "2026-05-18T14:23:21+08:00"
last_reviewed: ""
reviewed_by: ""
valid_for: []
not_valid_for: []
project_scope: "personal-knowledge-base/raw-batch-001"
supersedes: []
superseded_by: ""
risk_level: medium
verification_method: ""
review_required: true
short_summary: "Official Codex Skills documentation; useful for deciding when repeated workflows should become reusable skills instead of long prompts."
learn_focus: ["Codex Skills", "workflow packaging", "agent capability reuse"]
possible_output_targets: ["rule", "checklist", "codex-task"]
extraction_questions: ["When should a workflow become a skill?", "What files should a skill include?", "How should skills avoid embedding secrets or stale assumptions?"]
notes: "Raw intake only. Do not create a Skill from this source until reviewed."
content_not_fetched: false
---

# OpenAI Codex Agent Skills

## Short Summary

Official documentation for packaging repeatable Codex workflows as skills.

## Learn Focus

- Skill structure.
- When to use skills versus AGENTS.md.
- Safety and maintainability of reusable agent workflows.

## Possible Output Targets

- rule
- checklist
- codex-task

## Extraction Questions

- Which knowledge-base workflows are skill candidates?
- What minimum review checklist should a skill pass before use?
- How should skills reference docs without copying full pages?

## Notes

Raw only. Not reviewed. Do not use as a formal project rule.
