---
scope: sql
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - sql/README.md
  - docs/HANDOFF-2026-08-24-ingest-testing.md
  - docs/DECISION_LOG.md
watches:
  - sql/**
  - docs/HANDOFF-2026-08-24-ingest-testing.md
contains_secrets: false
---

# SQL Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- Migrations are numbered and append-only; never edit an applied migration.
- The legacy `ai` database and `agno_app` role are preserved as dated state. New application schema
  work targets the fresh `platform` database only after its baseline and cutover gates pass.
- Migration 0036 must never be applied to `ai`; verify the latest handoff before any database write.
- Test data never becomes canonical. Preserve reference and hand-labeled gold data according to its
  controlling decision, and re-ingest disposable design data from originals.
- Schema validation claims are bounded until applied and queried against the intended live target.

<!-- freshness
watches_hash: a957fc6
last_verified: 2026-08-27
watches:
  - sql/**/*.sql
  - sql/README.md
  - docs/HANDOFF-2026-08-24-ingest-testing.md
-->
