---
scope: docs
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - docs/INDEX.md
  - docs/PROJECT_CANON.md
  - docs/DECISION_LOG.md
  - docs/HANDOFFS.md
  - docs/MEMORY_ARCHITECTURE.md
watches:
  - docs/INDEX.md
  - docs/PROJECT_CANON.md
  - docs/DECISION_LOG.md
  - docs/HANDOFFS.md
contains_secrets: false
---

# Documentation Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

## Durable local rules

- **Verified:** `docs/INDEX.md` routes current truth. A document merely existing under `docs/`
  does not make it current.
- **Owner directive:** material findings and verification must be persisted, with a byline and an
  honest validation boundary.
- ADRs and `docs/DECISION_LOG.md` remain in place. Superseded ordinary documentation moves under
  `docs/archive/`; pending-review material is explicitly unverified.
- Keep historical corrections visible and dated. Never silently rewrite history into apparent
  contemporaneous truth.
- Complex architecture reports should include a viewable HTML or diagram when it improves owner
  comprehension; Markdown remains the durable source.

## Failure modes to prevent

- Do not treat a stale handoff instruction as current when its header or later note supersedes it.
- Do not copy canon into memory. Link to the controlling section or decision ID.
- Do not claim live completion from local/static checks.

Format: `docs/agent-memory/README.md`.

<!-- freshness
watches_hash: 8b31043
last_verified: 2026-08-27
watches:
  - docs/INDEX.md
  - docs/PROJECT_CANON.md
  - docs/DECISION_LOG.md
  - docs/HANDOFFS.md
-->
