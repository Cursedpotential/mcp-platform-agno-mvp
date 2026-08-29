# Master application TODO — production resume ledger

> Byline: Codex · GPT-5 · 2026-08-18
> Byline amendment: Claude Code · Opus 5 · 2026-08-29

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

## Feature-management infrastructure — queued

> _Added by Codex · GPT-5 · 2026-08-29 from an owner directive._

- Install and productionize [Unleash](https://github.com/Unleash/unleash) as the Platform's
  feature-management service, including persistent storage, backup, authentication, Traefik
  routing/middleware, least-privilege service credentials, Coolify deployment, and live proof.
- Adopt a standing implementation rule: side-by-side deployments, gated rollouts, optional
  advanced capabilities, experiments, and swappable implementations must use named feature
  flags rather than hard-coded branches or permanently exposed selectors.
- Define flag ownership, default state, environment scope, audit trail, rollback behavior,
  stale-flag retirement, and fail-closed behavior before connecting the service to production.
- Keep this queued behind the current unified Workbench/UIW release slice; recording it does
  not authorize a competing infrastructure deployment during that critical path.

## Derived-document ingest wiring — queued

> _Added by Claude Code · Opus 5 · 2026-08-29 from an owner directive._

- Documents that are AI-assistant **work products** (case chronologies, strategy memos, research
  guides — not chat transcripts, no role markers) currently have **no parser that preserves
  structure**: `format_router.SIGNATURES` holds 3 JSON signatures and none for markdown, so every
  `.md` skips routing and falls to the flat `transcripts.markdown` whole-file record. Once
  ingested they are **not semantically searchable** — only `ILIKE` on `/v1/records`.
- Downstream is built and unwired: `timeline.event_candidate` (`sql/0035:62`) is purpose-built
  for this class (`source_system='ai_chat'`, D-082 lead-never-evidence, append-only) and has
  **no producer**; `server/timeline/` is CLI-only with **zero production callers**.
- Preferred tools are already vendored — Semantica `StructuralChunker` and its `parse/` modules
  (owner: "if one of the bundled semantica tools will work, we can call on those"). Docling and
  the OCR tier are declared but **installed in no deploy image**.
- **HARD CONSTRAINT (owner 2026-08-29):** Semantica may be called **atomically as a tool** for
  document parse/chunk. Content may **NOT** flow through the **Semantica extraction lane** until
  change detection is ordered — Semantica is downstream of context creation and triggered by
  change detection. Running the lane early breaks D-069 context-first ordering and invalidates
  the `no-fusion` `semantica` vs `sat_temporal` comparison.
- **Multiple chunk-stage approaches required** (owner 2026-08-29), selected by the **Go
  coordinator's** declared `Quality` (`engine/parser`), not a Python flag pick.
  `Chonkie.from_recipe("markdown")` fails because `HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1` are
  set (no-local-models guard, not a Chonkie defect) — preferred fix is inline `RecursiveLevel`
  delimiters. `format_router.py`'s Python selection mesh is **flagged for removal**, sequenced on
  Go adapter coverage per format; the Go↔Python bridge already exists (`platform-tools`, `:8090`).
- **n8n orchestrates, Temporal executes, a quality gate substitutes the method:** extraction runs
  as a Temporal activity invoked by n8n; a deterministic completeness check (byte-range
  reassembly) plus a model-backed quality score (via Portkey) — not a caught exception — select a
  different named Go adapter on failure/low confidence. Document-class markdown needs no parser
  at all (see "Ingest taxonomy" in the handoff) — only chunk + ingest.
- Full analysis, verified-live state, owner decisions, and work packages WP-0, WP-1..WP-11
  (incl. WP-5b..WP-5f, WP-6a):
  [`HANDOFF-2026-08-29-derived-document-ingest-wiring.md`](HANDOFF-2026-08-29-derived-document-ingest-wiring.md).
- Queued behind the current unified Workbench/UIW release slice; recording it does not authorize
  work during that critical path.

## CRITICAL GAP — cross-medium conversation threads (`context_thread_id`) — queued

> _Added by Claude Code · Opus 5 · 2026-08-29 from an owner directive. Owner: "one of the most
> critical things for this entire platform" — higher priority than, and broader than, the
> document-ingest wiring above; do not nest this under it._

- No schema anywhere represents a human conversation that hops platforms (SMS → Messenger →
  iMessage → email) as one thread — `context_thread_id` does not exist. In a custody matter whose
  evidence is largely messaging, **the cross-platform pattern is the evidence** (register R58,
  "nuance IS the abuse"); fragmenting by source file destroys it. Blocks R09 (parent-thread id on
  extraction chunks) and R15 (chronology matrix `context_thread_id` column).
- Depends on two things that must land first or in parallel: party identity resolution across
  platforms (R17 — same human, different per-platform representations) and timestamp
  normalization to one timezone at ingest (R05) — attempting threading before these produces
  confidently-wrong threads, worse than no threads in an evidence context.
- Design sketch, the two-axis chunk-linkage distinction (reassembly vs. thread), and the
  recommendation for its own ADR/handoff: see "CRITICAL GAP" in
  [`HANDOFF-2026-08-29-derived-document-ingest-wiring.md`](HANDOFF-2026-08-29-derived-document-ingest-wiring.md).
- **Naming debt tracked, not yet actioned (owner 2026-08-29):** "chat" (`working.chat_*`) means
  AI-chat-only and "transcript" (`parse.transcript` / `parse.messages-transcript`) ambiguously
  covers both AI chats and human messaging — do not conflate them in any NEW name; renaming the
  live ones is a separate, later, explicitly-scheduled change. See "Glossary" in the handoff.

## Resume

**NOT COMPLETE. Start with the Evidence Desk handoff step 1.** Use the least-expensive
subagent capable of reliably completing each bounded check; root owns orchestration,
decisions, integration, and final live proof.

## Documentation lifecycle

Current documentation is indexed by `docs/INDEX.md`; historical material lives under
`docs/archive/`. ADRs and `DECISION_LOG.md` remain authoritative and append-only. On task
completion or supersession, update the active TODO/handoff and move the retired document to
the archive in the same change. Mockup/design history is never production truth.
