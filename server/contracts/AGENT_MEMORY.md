---
scope: server/contracts
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - server/contracts/AGENTS.md
  - docs/CONVENTIONS.md
watches:
  - "server/contracts/**/*.py"
  - server/contracts/AGENTS.md
contains_secrets: false
---

# Python Contract Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- This package stays import-light and framework-neutral because parsers and facade containers import
  it without the full application dependency graph.
- `NormalizedRecord` remains the canonical Python record contract for its governed lane. Do not add
  database sessions, AgentOS objects, or runtime side effects here.
- Use typed Pydantic schemas and explicit validators/default factories. Preserve versioned wire
  semantics when bridging to root cross-language contracts.
- Horizon meaning is derived above normalized source data; do not casually turn access labels or
  write-audit time into knowledge-horizon predicates.

<!-- freshness
watches_hash: 56f2a20
last_verified: 2026-08-27
watches:
  - server/contracts/**/*.py
  - server/contracts/AGENTS.md
-->
