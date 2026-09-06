# Master application TODO — production resume ledger

> Byline: Codex · GPT-5 · 2026-08-18
> Byline amendment: Claude Code · Opus 5 · 2026-08-29
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

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

## SBV storage-free pipeline-preview cutover — active critical path

> _Added by Codex · GPT-5 · 2026-08-29 from the accepted ADR-0061 owner clarification._

- Compose the SBV React client inside the Workbench shell as `/evidence/preview`. Workbench owns
  fixed case context, navigation, and the authenticated boundary; SBV owns preview presentation
  for messages plus Go/Temporal/n8n pipeline progress and owns no canonical state.
- Remove SBV-specific SQLite storage/cache, local auth, synchronous ingest, search authority, and
  parser selection from the target architecture. Do not hard-delete them. Prove callers and data
  coverage, then move retired paths to repo-root `to_be_deleted` for owner review.
- Move SMS/MMS decoding behind the same Go-selected parser contract as every other format. Fix
  `convertMMSEntry` multi-attachment loss and the RCS group-name no-op during the port. Keep H1/H2/H3
  custody hashing in its separately versioned upstream activity; never fold it into parsing.
- Re-ingest retained source XML rather than migrating SQLite `media_data`: SQLite stored only the
  first MMS attachment, while retained XML contains the complete attachment set. Require source-level
  attachment completeness, platform read-path proof, and live preview proof; SQLite row-count parity
  is explicitly insufficient.
- Treat `workbench/design-mockups/unified-operator-surface` and its deployment as design history/donor,
  not a third production product. Quarantine the obsolete deployment definition only after the
  production Workbench+SBV cutover and rollback window are proven.
- Production exit: focused client/API/contract tests, exact current-revision Coolify deployments,
  Authentik/Traefik login and denial proof, no direct `:8020` bypass, live source preview/reject/approve,
  custody/run-event rendering, complete multi-attachment MMS re-ingest, and recorded rollback receipts.

## Derived-document ingest wiring — queued

> _Added by Claude Code · Opus 5 · 2026-08-29 from an owner directive._

- Documents that are AI-assistant **work products** (case chronologies, strategy memos, research
  guides — not chat transcripts, no role markers) **need no parse step at all** — they are already
  text, with no export format to decode. The defect is that nothing routes them accordingly:
  `.md` sits in `_TEXT_SUFFIXES` and is filed into the **transcript** branch, where it fails all
  16 `.md`-accepting parsers in turn and lands on the flat `transcripts.markdown` whole-file
  record by exhaustion. Structure preservation is therefore a **chunk-stage** requirement, not a
  parser gap. Once ingested they are also **not semantically searchable** — only `ILIKE` on
  `/v1/records`.
  _(Corrected 2026-08-29: an earlier revision of this bullet said these have "no parser that
  preserves structure," which framed a category error as a missing capability and contradicted
  the parse/extract/chunk taxonomy recorded later in the same section. Caught in reconciliation.)_
- Downstream is built and unwired: `timeline.event_candidate` (`sql/0035:62`) is purpose-built
  for this class (`source_system='ai_chat'`, D-082 lead-never-evidence, append-only) and has
  **no producer**; `server/timeline/` is CLI-only with **zero production callers**.
- Preferred tools are already vendored — Semantica `StructuralChunker` (a **chunk-stage** tool,
  not a parser) and its `parse/` modules (owner: "if one of the bundled semantica tools will work,
  we can call on those"). **Current-tree correction (2026-08-30):** the OCR Python dependencies,
  Tesseract, and Poppler are now baked into `platform-tools`; Docling remains declared but excluded
  from that image. Note the stage split: files that are already text need **no parse step** — the
  section-structure requirement is a chunk-stage concern.
- [ ] **Finish and prove the OCR/document-extraction surface (added 2026-08-30).** Add contract
  tests that execute the OCR capability through `platform-tools` REST and its ContextForge MCP
  publication (inventory **and invocation**, not documentation-only claims). Then prove the ingest
  path consumes addressable structural output — stable page/block IDs, reading order, coordinates,
  and source ranges — rather than flattening it to text before semantic chunking/tagging. Record an
  explicit Docling install-or-defer decision after the same corpus bake-off; do not treat its
  declaration in `pyproject.toml` as runtime availability.
- **HARD CONSTRAINT (owner 2026-08-29):** Semantica may be called **atomically as a tool** for
  document parse/chunk. Content may **NOT** flow through the **Semantica extraction lane** until
  change detection is ordered — Semantica is downstream of context creation and triggered by
  change detection. Running the lane early breaks D-069 context-first ordering and invalidates
  the `no-fusion` `semantica` vs `sat_temporal` comparison.
- **Multiple chunk-stage approaches required** (owner 2026-08-29), selected by the **Go
  coordinator's** declared `Quality` (`engine/parser`), not a Python flag pick.
  `Chonkie.from_recipe("markdown")` fails because `HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1` are
  set (no-local-models guard, not a Chonkie defect). ~~Preferred fix is inline `RecursiveLevel`
  delimiters.~~ **DISPROVED BY MEASUREMENT 2026-08-29** — inline heading delimiters produced
  *identical* heading alignment to the default (1 of 26 chunks starting at a heading) while
  creating more chunks (65 vs 46); `chunk_size` still dominates and re-splits across headings.
  **There is currently NO viable candidate:** default is verbatim-safe but structure-blind,
  inline delimiters change nothing, and Semantica `StructuralChunker` preserves structure (13/26)
  but **alters content** — 24 of 35 chunks not found verbatim in source, 176 chars missing, not
  whitespace. Reproducibility and hashes in the handoff. `format_router.py`'s Python selection
  mesh is **flagged for removal**, sequenced on
  Go adapter coverage per format; the Go↔Python bridge already exists (`platform-tools`, `:8090`).
- **n8n orchestrates, Temporal executes, a quality gate substitutes the method:** extraction runs
  as a Temporal activity invoked by n8n; a deterministic completeness check (byte-range
  reassembly) plus a model-backed quality score (via Portkey) — not a caught exception — select a
  different named Go adapter on failure/low confidence. Document-class markdown needs no parser
  at all (see "Ingest taxonomy" in the handoff) — only chunk + ingest.
- **Authored schemas exist** (2026-08-29, [`docs/schemas/`](schemas/)): class signature + variant
  registry [`document-markdown-v1.json`](schemas/document-markdown-v1.json) plus four
  self-contained modules under [`schemas/variants/`](schemas/variants/) — `chronology` (the only
  one emitting a timeline artifact), `research-report`, `statute-extract`, `strategy-memo`.
  Authored against the **measured** structure of the four real files, each with a sha256
  fingerprint. They record: stage routing (no parse step), the chunk contract (char offsets
  required, reassembly gate, verbatim requirement), extraction as a pass **separate from**
  chunking, and a four-tier date policy that defers unbounded dates to the relative-date
  subsystem rather than guessing. Draft/unapplied — the authored source that seeds the PG
  schema-manifest table, not the runtime store.
- Full analysis, verified-live state, owner decisions, and work packages WP-0, WP-1..WP-11
  (incl. WP-5b..WP-5f, WP-6a):
  [`HANDOFF-2026-08-29-derived-document-ingest-wiring.md`](HANDOFF-2026-08-29-derived-document-ingest-wiring.md).
- Queued behind the current unified Workbench/UIW release slice; recording it does not authorize
  work during that critical path.

## CRITICAL GAP — cross-medium conversation threads (`context_thread_id`) — SCHEMA BUILT; APPLICATION + PRODUCER REMAIN

> _Added by Claude Code · Opus 5 · 2026-08-29 from an owner directive. Owner: "one of the most
> critical things for this entire platform" — higher priority than, and broader than, the
> document-ingest wiring above; do not nest this under it._
>
> _**Status correction: Claude · Opus 5 · 2026-08-29 (owner-ordered reconciliation).** This section
> was written while the gap was open and was never updated when it closed. The schema landed the
> same day in `sql/0047_content_chunk_and_context_thread_foundation.sql` (commit `06702d9`), with
> the PG18 lifecycle proof in `860e925`. **The design questions below are settled and implemented;
> what remains is application and a producer, not design.** Do not read this section as an open
> design problem._

- ~~No schema anywhere represents a human conversation that hops platforms (SMS → Messenger →
  iMessage → email) as one thread — `context_thread_id` does not exist.~~ **SUPERSEDED 2026-08-29
  by `sql/0047`,** which creates `working.first_party_context_thread` and
  `working.third_party_context_thread`, their `_version` / `_message` / `_source` tables,
  `working.content_chunk`, the source-range locators, and the reassembly receipts. Contracts live
  in `server/contracts/context_thread.py`; coverage in
  `tests/test_0047_content_chunk_and_context_thread_foundation.py` and
  `tests/test_content_chunk_context_thread_contracts.py`. The rationale still stands and is why
  this was built first: in a custody matter whose evidence is largely messaging, **the
  cross-platform pattern is the evidence** (register R58, "nuance IS the abuse"); fragmenting by
  source file destroys it. Still gates R09 (parent-thread id on extraction chunks) and R15
  (chronology matrix `context_thread_id` column) **until the schema is applied and a producer
  exists** — the tables alone populate nothing.
- **Two populations, same shape, never mixed (owner 2026-08-29):** first-party threads
  (`working.message`, owner is a party) AND acquired third-party threads
  (`working.third_party_message`, owner is not) — **both platform-hop**. A thread is always one
  population or the other, so no thread has mixed authorization state. ~~**Recommended: separate
  tables, shared logic**~~ — **IMPLEMENTED AS SPECIFIED in `sql/0047`:** separate first-party and
  third-party thread tables, mirroring the precedent already set one layer down, where first- and
  third-party messages are separate tables each with a CHECK pinning `projection_kind`
  (`sql/0026:154,196`) rather than one table with a discriminator. Population separation is
  additionally enforced by a composite foreign key on `(thread_version_id, context_thread_id)`, so
  a thread version cannot adopt a message from the other population.

### What actually remains on this lane

1. **Apply `0047`** to `platform` — held with every other migration; not applied, not deployed.
2. **Build the producer.** Nothing writes threads yet. This is the same shape of gap as
   `timeline.event_candidate`, which has had a purpose-built table and zero producers since
   `sql/0035`. A table with no producer is not a delivered capability.
3. **Prerequisites are unchanged and still real:** party identity resolution across platforms
   (R17) and timestamp normalization to one timezone at ingest (R05). The schema does not remove
   this dependency — threading before those land produces confidently-wrong threads, which in an
   evidence context is worse than no threads.
- **Identity-resolution asymmetry — size the two separately:** a first-party thread is anchored by
  a known participant (the owner); a third-party thread has no anchor, so cross-platform matching
  is strictly harder and will need materially more human review.
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
