---
scope: server/timeline
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - server/timeline/AGENTS.md
  - timesketch-fork/AGENT_MEMORY.md
watches:
  - "server/timeline/**/*.py"
  - server/timeline/AGENTS.md
contains_secrets: false
---

# Timeline Projection Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- Timeline packets and projectors are governed projections from canonical PostgreSQL records.
- Preserve event time, source availability time, record identity, and raw lineage.
- Changes returning from Timesketch are provenance-bearing candidates that must be reconciled and
  re-reviewed; annotation does not directly mutate canonical evidence.
- Keep first-party and acquired-third-party source clocks and participant semantics distinct.

<!-- freshness
watches_hash: c85e5dd
last_verified: 2026-08-27
watches:
  - server/timeline/**/*.py
  - server/timeline/AGENTS.md
-->
