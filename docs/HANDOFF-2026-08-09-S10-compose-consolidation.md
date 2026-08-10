# HANDOFF S10 — Compose-file consolidation (for the Code-side agent)
> _2026-08-09 · repo @ a68fabd+working-tree · STATUS: READY · Owner-initiated ("why are there
> eighteen compose files, some stale, none in a deploy folder"). Independent of S6–S9._
> MANDATORY: read docs/PLAN-2026-08-09-completion-master.md §Standing constraints first.

## ⚠ THE LANDMINE — read before touching ANY compose file
**Coolify deploys directly from files and branches in this repo.** A compose file that looks
stale can be a LIVE deploy source on ovh-files/ovh2 — this is exactly how a prior cleanup nearly
broke production, and why the standing rule exists: *check Coolify deploy sources before merging
or deleting anything*. Renaming or moving a compose file that a Coolify application references
breaks that deployment silently on next deploy. VERIFY against the live Coolify config (owner has
access; coolify-mcp tooling exists — `compose.coolify-mcp.yaml`) before every single move.

## Current state (18 root-level compose files)
`compose.yaml` (core) · `compose.browser` · `compose.contextforge` · `compose.coolify-mcp` ·
`compose.data-graphiti-case` · `compose.data-graphiti` · `compose.data-neo4j` · `compose.data-pg` ·
`compose.data-surreal` · `compose.data-vector` · `compose.data` · `compose.desktop` ·
`compose.exec` · `compose.gateway` · `compose.librechat-mongo` · `compose.librechat` ·
`compose.nocodb` · `compose.platform-tools` · `compose.portkey` · `compose.sandbox` ·
`compose.ui` · `compose.workbench` — plus `deploy/data-weaviate.yaml` (already the pattern the
owner wants: single-app Coolify fragments under `deploy/`).

Known-stale candidates (verify, don't assume):
- `compose.data-surreal.yaml` — SurrealDB RETIRED (ADR-0043, D-042) but the container is
  deliberately PARKED on ovh-data, owner-gated deletion. The compose file likely must SURVIVE
  (documented as parked) even though the engine is retired. Do not delete; annotate.
- `compose.data-vector.yaml` (Milvus) — cutover to Weaviate ruled VERIFIED (D-042, OQ-10);
  Milvus was "sidelined-but-up". Confirm the Coolify app is stopped/removed before archiving.
- `compose.librechat*`/`compose.nocodb` — check whether still deployed at all.

## Task
1. Inventory: for each compose file, determine (a) referenced by Coolify? (b) referenced by
   docs/scripts/CI? (`grep -rn "compose\." docs/ scripts/ .github/ README.md AGENTS.md`)
   (c) services it defines still in canon §4's host table?
2. Propose (do not execute blind) a target layout: `deploy/` = one file per Coolify application
   (the `deploy/data-weaviate.yaml` pattern); repo root keeps ONLY `compose.yaml` + profiles
   used for local/dev (`docker compose --profile tools|desktop|analysis`). Present the mapping
   table to the owner for a yes/no before moving anything Coolify-referenced.
3. Execute approved moves; update every doc/script reference in the same commit; stale-but-
   parked files (surreal) get a header note, not a move, unless owner says otherwise.
4. Never delete — `_stale/` for anything truly dead, after Coolify verification.
5. Record the final layout in docs/REPO_STRUCTURE.md + a D-NNN DECISION_LOG entry.

## Acceptance
`ls compose.*.yaml | wc -l` at root is small and intentional; every moved file's old path is
referenced nowhere (`grep` clean); every live Coolify app still points at an existing file
(verified against Coolify, not assumed); REPO_STRUCTURE matches reality.
