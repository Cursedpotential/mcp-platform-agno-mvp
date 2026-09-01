---
scope: docker/n8n
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - docs/plans/N8N-BUILDER-AGENT-GUIDE.md
  - docs/runbooks/N8N-PIPELINE-GOLIVE-RUNBOOK.md
  - docs/reviews/2026-08-25-schema-audit/TEMPORAL-N8N-WORKFLOW-AND-GAPS.md
watches:
  - docker/n8n/**
  - engine/**
contains_secrets: false
---

# n8n Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

## Boundary

- n8n provides visual, business-visible mini-workflows used within the Temporal-controlled process.
- Temporal owns durability, retries, timers, signals, workflow identity, and resumable waits. n8n
  does not become the durable orchestrator merely because it invokes a stage.
- Custom Go, Python, JavaScript, TypeScript, and off-the-shelf extraction nodes are wrappers around
  the same Activity contracts and reference-only payload rules.
- Tika, metadata, EXIF, OCR, archive, file extraction, comparison, classification, splitting, and
  similar nodes are candidates; configuration acceptance is not proof. Validate with observed
  output before treating any community node as usable.
- One shared error workflow records a durable failure reference and receipt; it does not hide a
  failed stage or report completion.

## Human review

Preview and decision waits remain durable Temporal workflow state. Short-lived response caching may
improve the surface, but it cannot own approval state or canonical data.

<!-- freshness
watches_hash: def2987
last_verified: 2026-08-27
watches:
  - docker/n8n/**/*.json
  - engine/**/*.go
  - docs/plans/N8N-BUILDER-AGENT-GUIDE.md
-->
