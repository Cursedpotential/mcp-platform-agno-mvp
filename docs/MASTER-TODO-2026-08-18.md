# Master application TODO — production resume ledger

> Byline: Codex · GPT-5 · 2026-08-18

## Completion rule

Mockups are never completion. Unless the owner explicitly asks for a mockup, every item
requires production implementation, Coolify deployment, and live verification.

## Status inventory (evidence-backed)

| Surface | Status | Remaining gate/evidence |
|---|---|---|
| Custody, ingest, parsers, normalized spine | IMPLEMENTED LOCAL ONLY | Run production path and verify custody/provenance; `server/evidence/`, `server/tools/`, `server/contracts/`; `AGENTS.md` |
| Conversations / acquired third-party approval | IMPLEMENTED LOCAL ONLY | Verify source clocks, actual participants, approval/review; `docs/adr/0059-*`, `server/evidence/message_projection.py` |
| Chunks / native Weaviate | IN PROGRESS | Complete migration/cutover and live prefilter proof; `docs/plans/WEAVIATE-NATIVE-EVIDENCE-CUTOVER-RUNBOOK-2026-08-18.md` |
| Knowledge / curated works | IN PROGRESS | Finish retrieval and agent wiring; `docs/COORDINATION.md` KB-STRUCTURE lane |
| Case/matter evidence desk | IMPLEMENTED LOCAL ONLY | Deploy and exercise drill-through; `workbench/`, `docs/HANDOFF-2026-08-18-evidence-operations-desk-mvp.md` |
| Human review | IMPLEMENTED LOCAL ONLY | Live verify review decisions persist and are visible in drill-through |
| Horizon walk | IN PROGRESS | Production activation and replay gates remain held; `AGENTS.md`, `docs/PROJECT_CANON.md` |
| Agents / Graphiti / Neo4j | IN PROGRESS | Verify production bindings and derived belief boundaries; `server/agents/`, `docs/COORDINATION.md` |
| Surreal experimental surface | HISTORICAL/MOCKUP ONLY | Parked/held; no activation; `docs/COORDINATION.md` R10/R11 |
| Workbench/API | IMPLEMENTED LOCAL ONLY | Current deployed `100.72.169.40:8020` is old; deploy current SHA and live verify |
| Backup / observability / security | IN PROGRESS | Run deploy/rollback, auth, health, logs, and backup receipts; `AGENTS.md` operational learnings |
| Deployment | BLOCKED | Current release app/commit and Coolify receipt not yet recorded in this handoff |

No item is classified DONE+LIVE VERIFIED from the evidence inspected here.

## Critical path

1. Inventory current SHA, dirty worktree, Coolify app, watch paths, environment, and old
   endpoint. 2. Reconcile contracts and tests for custody-to-review drill-through. 3. Run
   focused tests (`uv run pytest -q`, relevant Workbench tests; `uv run ruff check server tests`).
   4. Deploy through Coolify. 5. Verify health/auth and the complete operator drill-through
   against production. 6. Record SHA, timestamp, endpoints, observations, and rollback.

## Deploy, rollback, decisions

- Deploy only the identified Workbench Coolify app and release commit; honor scoped watch
  paths. Record the Coolify receipt before claiming live.
- Roll back to the last known-good deployed commit through the same Coolify app, then
  re-run health and drill-through verification; do not delete data or files.
- Owner decisions needed: target production Workbench app/URL if ambiguous; approval for
  any held migration or Horizon/Surreal activation; acceptance of unresolved blockers.

## Resume

**NOT COMPLETE. Start with the Evidence Desk handoff step 1.** Use the least-expensive
subagent capable of reliably completing each bounded check; root owns orchestration,
decisions, integration, and final live proof.

## Documentation lifecycle

Current documentation is indexed by `docs/INDEX.md`; historical material lives under
`docs/archive/`. ADRs and `DECISION_LOG.md` remain authoritative and append-only. On task
completion or supersession, update the active TODO/handoff and move the retired document to
the archive in the same change. Mockup/design history is never production truth.
