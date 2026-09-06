---
scope: engine
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - engine/README.md
  - docs/reviews/2026-08-25-schema-audit/SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html
  - docs/reviews/2026-08-25-schema-audit/TEMPORAL-N8N-WORKFLOW-AND-GAPS.md
watches:
  - engine/**
contains_secrets: false
---

# Go Runtime Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

## Owner-directed boundary

- The main orchestration runtime is Go-based for parallelism, speed, and memory safety.
- Temporal owns durable sequencing, retries, timers, workflow identity, and human approval waits.
- Every stage is an atomic Activity. Hashing, acquisition, parsing, raw persistence,
  normalization, lineage, comparison, and verification remain separate responsibilities.
- Parsers only parse. All parsers obey the same versioned contract, destination, workflow, and
  accounting rules regardless of implementation language.
- Workflow and Activity payloads carry durable references, not evidence bodies or large parser
  output. PostgreSQL receipts reconcile each boundary.
- Safe fan-out is goal-based and bounded; deterministic fan-in occurs before governed transitions.

## D-140 rename (2026-09-06)

- Ingest lane renamed: `uiw` package -> `proffer`, `uiwworker` -> `profferworker`,
  renamed `UniversalImportWorkflow` -> `ProfferWorkflow`. Module path is now
  `github.com/Cursedpotential/probata/engine` (D-137..D-141). n8n webhook path
  segments and `N8N_PROFFER_*` env var names (formerly `N8N_UNIVERSAL_IMPORT_*`) were renamed on 2026-09-06 together with the deploy lane; this note previously said they were left unchanged pending
  coordinated rename with the deploy/n8n lane.

## Verification caution

Go unit/build success is necessary but does not prove Temporal, n8n, PostgreSQL, object storage,
or Coolify integration. Link a dated live receipt before calling an integrated path complete.

<!-- freshness
watches_hash: b554291
last_verified: 2026-08-27
watches:
  - engine/**/*.go
  - engine/go.mod
  - engine/go.sum
  - engine/README.md
-->
