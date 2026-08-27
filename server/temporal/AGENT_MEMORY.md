---
scope: server/temporal
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - engine/AGENT_MEMORY.md
  - docs/reviews/2026-08-25-schema-audit/TEMPORAL-N8N-WORKFLOW-AND-GAPS.md
watches:
  - "server/temporal/**/*.py"
  - "engine/**/*.go"
contains_secrets: false
---

# Python Temporal Adapter Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- Temporal owns durable sequencing and waits. Keep Activities atomic, reference-only, idempotent,
  and fail-closed.
- Healthy approval pauses are workflow state through Signals, Queries, and Timers, not worker memory
  or short-lived cache.
- This Python subtree is an adapter/compatibility boundary while the Go runtime becomes primary.
  Do not create a second orchestration contract.
- Worker registration success is not a durability exit test; prove restart/resume and receipts live.

<!-- freshness
watches_hash: 9152ddf
last_verified: 2026-08-27
watches:
  - server/temporal/**/*.py
  - engine/**/*.go
-->
