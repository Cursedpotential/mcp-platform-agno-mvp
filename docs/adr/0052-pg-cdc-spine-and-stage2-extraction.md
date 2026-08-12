# ADR-0052: The PG-CDC spine, end-to-end AI-chat ingest with coverage-based engine split, and Stage-2 extraction (tools, not agents)

> _Byline: Claude Code · Opus 4.x (draft) · 2026-08-12; amended Kimi K3 · 2026-08-12 (owner rulings on all 8 open questions — format/size split replaced by coverage-based Go-primary)_

- Status: DRAFT — all 8 open questions RULED by owner 2026-08-12 (see "Owner rulings" below);
  awaiting final sign-off; no code until then
- Date: 2026-08-12 ~~(title said "size-based engine split")~~ **Corrected 2026-08-12, owner
  ruling Q3:** the engine axis is COVERAGE, not size — Go-primary wherever a Go decoder exists;
  Python only when no Go decoder exists for the format, or as failure-fallback (see Part 2).
- Hands off from: **ADR-0051 invariant 4** ("extraction is triggered by PG change-detection" —
  whose own Consequences defer the mechanism choice to "own ADR when chosen" — this is that ADR) ·
  ADR-0049 (engine-dynamic parsing, amended) · ADR-0050 (six-lane storage) · ADR-0043 (Semantica =
  governed extraction worker; PG canonical, Weaviate/Neo4j rebuildable projections) ·
  ADR-0045 §B (derivation/attestation disciplines) · ADR-0046 (dual-invocation / MCP exposure) ·
  ADR-0047 (audit ledger) · DECISION_LOG D-046..D-052.
- **Naming note:** DECISION_LOG entry **D-052** (archive-as-unit, `context_asset` +
  `context_archive`) is a decision-log id that happens to share this ADR's number. They are not the
  same artifact; references below say "D-052 (log)" where the log entry is meant.

## What is true TODAY (shipping, verified 2026-08-12) vs what this ADR PROPOSES

**Shipped (D-048..D-052, all verified in code/live DB 2026-08-12):**

- `working.context_record` is the PG source of truth for AI-chat context ingest (sql/0021, applied
  live; Option B — separate table, no evidence FK, the ADR-0044 boundary as an absence).
- Change-detection is **CDC-shaped but not the spine**: `sync_pending_context(sink)` polls rows
  `WHERE <sink>_synced_at IS NULL` and stamps them after projecting to Weaviate `platform_context` /
  Graphiti CASE lane. It is exposed as the registered tool `ingest.context-drain`
  (`server/tools/ingest/context_drain.py`) + CLI `scripts/drain_context.py`. The sql/0021 header
  (line ~36) says it outright: *"no outbox/trigger/cursor spine yet (that stays deferred,
  ADR-0051 / DEBT), but the seam is already CDC-shaped."*
- The parse step is **engine-dynamic** (D-049: `engine="auto"|"python"|"go"`, explicit override)
  with a **detect-once, Go-primary detection router** (D-051: `server/analysis/format_router.py`),
  a **ZIP-aware front door** (D-050: `server/analysis/chat_archive.py`), and **archive-as-unit
  materialization** (D-052 (log): `working.context_archive` + `working.context_asset`, sql/0022,
  R2-mount blob writes via `CONTEXT_BLOB_ROOT`).
- The evidence workflow (`server/evidence/workflows.py`) still writes its Weaviate insert **inline**;
  Semantica (`server/analysis/semantica_wiring.py`) is still **unwired** in any ingest flow.

**Proposed here (nothing below is built or authorized to be built):**

1. **The PG-CDC spine** — the full trigger/outbox/cursor mechanism ADR-0051 invariant 4 deferred:
   how `working.*` writes propagate to projections (Weaviate, Graphiti, extraction workers) as
   subscribers, for ALL ingest paths, replacing pending-row polling.
2. **End-to-end AI-chat ingest with a coverage-based engine split** — Task 10 of the 2026-08-12 TODO
   snapshot: ~~small/medium exports → Python; LARGE exports → Go~~ **corrected 2026-08-12 (owner
   ruling Q3):** Go SBV decoders parse EVERY format they cover, regardless of size; Python serves
   only uncovered formats or as logged failure-fallback (the D-046/ADR-0049 memory criterion: Go
   owns anything that must ingest unbounded input), same `NormalizedRecord`/`context_record`
   downstream either way.
3. **Stage-2 extraction** — Task 14: entities + relations + events + LEGAL FACT-CLAIMS (MCL 722.23
   factors, case/court/docket refs, parties, motions, allegations, dates) extracted from ingested
   records into candidate tables, with **materialization** of created works (generated
   documents/code written as FILES into document/code stores), built as **tools, not agents**
   (owner 2026-08-12). Langfuse is the eval/tracing layer (already present); DSPy is deferred until
   a classifier tool + tracing exist. Graphiti is an OPTIONAL downstream consumer, backfilled, never
   a hard dependency. ~~("LEGAL artifacts"~~ — **Corrected 2026-08-12, owner ruling Q6:** "artifact"
   was ambiguous; the owner reads *artifacts* as created works (AI-generated chats/documents). The
   extraction output row is renamed to **FACT-CLAIM**: `working.claim_candidate`, formerly named
   `working.artifact_candidate` everywhere in this draft.)

## Context

ADR-0051 locked the flow: one pipeline — parse+preview (SBV) → extract (Stage 2, TRIGGERED, not
called inline) → HITL verify — with custody tier the only evidence/context branch. Its invariant 4
named *what* must exist ("a PG change-detection monitor fires the fan-out") and explicitly left
*how* unchosen ("Postgres triggers vs LISTEN/NOTIFY vs logical replication vs polling. (Own ADR when
chosen.)"). D-048 then shipped the CDC-shaped pending-row consumer as the manual stand-in. The gap
that remains is precisely the spine:

- **Polling does not close the loop.** Today's drain runs inline after an ingest, or when an
  operator/agent invokes the tool. Nothing fires when a row lands. The evidence workflow still
  bypasses the pattern entirely with an inline Weaviate write. Until the spine exists, invariant 4
  is met by one path, on demand, only.
- **The two ingest paths cannot collapse without it.** ADR-0051's Consequences: "once it exists,
  Weaviate, Semantica, and Graphiti become subscribers instead of inline calls, and the two paths
  collapse." The spine is the highest-leverage missing piece.
- **Large real exports make the engine split urgent, not theoretical.** Real exports observed
  2026-08-12: a 61 MB Claude export, a 16 MB ChatGPT export, a Perplexity zip carrying 169 assets /
  34.5 MB. ADR-0049 verified nine Python parsers load whole files into memory and named the memory
  criterion as the owner-set rule: Go owns anything that can blow out a memory store. The router
  (D-051) already routes by format ~~; it does not yet route by SIZE~~ — **and per owner ruling
  2026-08-12 (Q3) it never will: format coverage IS the axis, not size.**
- **Extraction has no home.** Entities/artifacts/timeline are ADR-0051 Stage 2 and ADR-0043's
  Semantica role, but nothing is wired, and the owner's 2026-08-12 ruling pins the shape before
  anyone builds it wrong: extraction units are **TOOLS** — atomic, dual-invocation (CLI/API/MCP and
  workflow step, per ADR-0046 / the ADR-0049 Python dual-invocation contract), HITL-verified — not
  agents, and not Graphiti-dependent.

## Decision (proposed — three parts, one spine)

### Part 1 — The PG-CDC spine: transactional outbox + LISTEN/NOTIFY wakeup + per-sink cursors

**Recommended mechanism (for owner ruling against the alternatives below):**

- **Outbox tables — PER-TABLE (owner ruling 2026-08-12, Q2).** Every `working.*` table whose
  writes must propagate gets ITS OWN outbox table (e.g. `working.context_record_event`,
  `working.normalized_record_event`), written in the SAME transaction as the data row, so a commit
  either publishes the event or rolls back atomically — no lost, no phantom events. Per-table (not
  one shared `working.ingest_event`) keeps write hot-spots per lane; the worker reconstructs
  cross-table causal order from outbox row committed timestamps + ids. This is the change the
  polling columns (`*_synced_at`) already gesture at; the outbox generalizes them from two named
  sinks to any subscriber.
- **Trigger + NOTIFY as the wakeup, not the transport — FULL outbox row per insert,
  trigger-written (owner ruling 2026-08-12, Q4).** An `AFTER INSERT/UPDATE` trigger writes the
  complete outbox row per insert (not just a stamp; ~2× write amplification on ingest, accepted —
  at case-scale volumes this is noise, and a future 100k-row bulk re-ingest is the exception, not
  the norm) and emits a minimal `pg_notify` (aggregate id only — payload lives in the outbox row,
  never in the NOTIFY payload). Trigger-written, not writer-called: the DB enforces "no commit
  without its event" structurally, so no future ingest code path can forget to emit. NOTIFY is
  advisory: workers ALSO poll on a timer, so a worker that was down, or a notification lost because
  no one was listening, is healed by the next poll. The notification only buys latency; the
  outbox+cursor buys correctness.
- **Per-sink cursor.** Each subscriber (weaviate-context, graphiti-case, extraction-runner, …)
  holds its own durable cursor (a `working.cdc_cursor` row or the existing per-sink `*_synced_at`
  stamps generalized). A lane is rebuilt by resetting its cursor — the same rebuild semantic D-048
  established ("clear the stamp"), preserved.
- **One worker process, many sinks — standalone Coolify app (owner ruling 2026-08-12, Q8), NOT an
  agentos-api sidecar.** The always-on worker is its own Coolify application on the data tier
  (deploy-coupling per the Watch-Paths rule: set at app creation — the 2026-07-21 data-tier-restart
  incident). It wraps what `ingest.context-drain` does today: read pending events after cursor →
  dispatch to sink → stamp. The existing drain tool remains the manual/atomic invocation of the
  same code path (ADR-0046 dual invocation), now also run as a service.
- **Horizon fields ride the event.** Every propagated event carries `occurred_at`,
  `knowledge_time` (as the frozen audit clock only, per ADR-0045 §A), the asserted
  `disclosure_tier` hint, and (once the ADR-0045 derivation layer exists) the derived
  `visible_from`. A subscriber writes them into its projection so that per-agent horizon filters
  (dict filters on Weaviate — FilterExpr silently no-ops, AGENTS.md §WHY) have something to bind
  to. **The spine NEVER filters by horizon** — extraction is not analysis; the horizon discipline
  is a READ-side, agent-bound property (canon §1, ADR-0043). A spine that pre-filtered would bake
  one agent's horizon into every projection.

### Part 2 — End-to-end AI-chat ingest: coverage-based engine split (~~size-based~~ — owner ruling 2026-08-12, Q3)

The end-to-end shape (detect → parse → store-PG-first → spine fan-out → chunk+lane → extract →
HITL) is ADR-0051's; this part decides which ENGINE parses, per file:

- **Engine choice = f(coverage, fallback), operator-overridable — NO size axis (owner ruling
  2026-08-12, verbatim: "everything needs to go to the Go engine unless there's not a Go parser
  available or if for some reason the Go parser fails and we have a Python parser that functions").**
  The size-threshold design considered here is REJECTED: no byte threshold, no f(format,size). The
  D-049 `engine`/`format` explicit override stays the escape hatch at every surface (CLI/API now;
  SBV GUI selector later, ADR-0049). When no override is given, the router (D-051) decides:
  1. **Detect once** (format signatures, bounded head read) — as shipped.
  2. **Go-primary by coverage.** If a Go SBV decoder exists for the detected format, it parses —
     regardless of file size. Python serves only when (a) no Go decoder exists for the format, or
     (b) the Go parse FAILS and a Python parser that accepts the format exists (failure-fallback,
     logged loudly — a fallback is an event to see, not a silent hand-off).
  3. **Archive rule (unchanged):** the ZIP front door (D-050) and the archive stays one unit
     (D-052 (log)): assets materialize to the document/code stores regardless of which engine
     parsed the logs. (The extracted-vs-compressed size measurement is moot for engine choice now;
     it survives only as observability metadata on the archive row.)
- **Same downstream, whichever engine.** Go decoder output and Python parser output both land as
  `NormalizedRecord` → `working.context_record` (context tier) — owner invariant (D-049): "the
  destination doesn't change just how it gets parsed is changeable." Memory-safety coverage follows
  the ADR-0049 table: formats with a Go decoder get one (ChatGPT today, D-047/`4accbf2`; Claude/
  Perplexity/Gemini Go decoders remain Gap 2 work); formats without one carry the DEBT-item-0b
  caveat that their Python fallback must not balloon.
- **Chunking stays downstream of PG.** Record-grain in PG (sql/0021 header: "Chunking stays a
  property of the vector-population step"); the turn-aware + semantic hybrid chunker (Chonkie,
  D-046) runs in the projection/extraction stage, and its output — not the raw parse — is what the
  lane classifier routes (ADR-0051 invariant 5: one chat → many lanes).

### Part 3 — Stage-2 extraction: tools, not agents; candidates, materialization, eval

- **Unit of construction is the TOOL.** Each extractor is a registered capability
  (`server/tools/…`), invocable atomically (one call/one job, CLI/API/MCP — ADR-0046) AND as a
  workflow step (dual invocation). No extraction agent is built; agents may CALL the tools. Owner,
  2026-08-12: extraction tools are TOOLS, not agents.
- **Outputs are candidates in native PG stores — TWO tables (owner ruling 2026-08-12, Q6:**
  entities and fact-claims merge differently; entity references get dedup-merged, fact-claims
  accumulate and are NEVER merged/rewritten). Entities/relations/events →
  `working.entity_candidate`; legal fact-claims → `working.claim_candidate` (MCL 722.23 factors,
  case/court/docket references, parties, motions, allegations, dates — the first legal-extractor
  schema). ~~named `working.artifact_candidate` in the draft~~ — renamed per owner ruling Q6
  ("artifact" collides with created works / AI chats in the owner's usage). Candidates become
  canonical only through HITL (native `@approval`, ADR-0002; every decision to `ops.audit_ledger`,
  ADR-0047). This is ADR-0043's governed-worker contract (candidates + provenance, PG canonical)
  delivered as callable tools, with Semantica (pinned fork, ADR-0043) as the heavyweight multipass
  engine when wired — a lightweight callable extractor does NOT require the full Semantica workflow
  and must not block on it.
- **Extraction runs REGARDLESS of custody-approval state (owner ruling 2026-08-12, Q5: "always
  extract regardless").** Rationale: candidate rows are not evidence and not beliefs — extraction
  is not analysis (ADR-0043); an unapproved record's candidates sit in `working.*_candidate`,
  non-canonical, until the record itself is custody-approved and its claims promoted. **Horizon
  guard:** candidate rows carry the source record's `disclosure_tier` and custody-approval flag so
  no candidate from unapproved evidence-tier material can be promoted or surfaced without the
  approval — and the planted-future-fact test (invariant 3 / pre-mortem 5) covers candidate tables
  too. Trade-off accepted by owner: an agent (or the owner) CAN see candidates for unapproved
  evidence in the review queue; the horizon discipline binds at promotion/materialization and at
  agent retrieval, not at extraction time.
- **Materialization is first-class.** Generated documents, PDFs, and code snippets recognized in
  chat content are WRITTEN AS FILES into the document/code stores (the D-052 (log)
  `working.context_asset` + R2-mount blob index is the shipped substrate) — not left as chat text.
  Provenance links every materialized file back to its source record.
- **Graphiti is an optional consumer.** Entities may be backfilled into Graphiti/Neo4j as a
  subscriber of the spine; extraction never requires the graph to be up, and never writes to it
  inline.
- **Eval layer: Langfuse (already present).** Tracing/eval on every extraction call from day one.
  **DSPy is deferred** until (a) the segment→lane classifier tool exists and (b) tracing data
  exists to optimize against (owner 2026-08-12). Structured-output model choice follows the learned
  rule: schema-constrained extraction never on models that can't conform (glm-5.1 failure mode);
  nemotron-class guided-JSON or equivalent, verified empirically per model before wiring.

### The invariants

1. **PG is the only source of truth; every downstream is a rebuildable projection.** All ingest
   paths (evidence workflow, context path, future lanes) write `working.*` first. No sink is
   written inline by a parse path once the spine exists (ADR-0051 invariant 4, made concrete).
2. **Events are transactional with the data they describe.** No event without its commit; no
   commit (of a propagated row) without its event.
3. **The spine carries horizon fields but never filters by them.** `occurred_at` /
   `disclosure_tier` / derived `visible_from` are payload for read-side per-agent filters
   (canon §1). Extraction reads everything and forms no beliefs (ADR-0043). Contamination is
   silent — the planted-future-fact test (ADR-0043 Consequences) is the proof burden for every
   new subscriber.
4. **Subscribers hold their own cursors; any lane is rebuildable from PG** by cursor reset alone,
   with no schema change and no source re-ingest.
5. **Engine split is by FORMAT COVERAGE with failure-fallback and operator override; the parse
   engine never changes the destination** (D-049 invariant) or the record contract. ~~(format+size)~~
   — owner ruling 2026-08-12 (Q3): no size axis; Go parses anything it has a decoder for.
6. **Extraction units are tools** — atomic + workflow dual invocation, CLI/API/MCP — never agents,
   and candidates are never canonical without HITL approval (ADR-0002/0047).
7. **Unbounded input goes to Go** (the ADR-0049/D-046 memory criterion) — **strengthened 2026-08-12
   (owner Q3): ALL input goes to Go when a Go decoder exists, not just large input.** A Python
   fallback that can exhaust memory is a known-debt fallback, used only where no Go decoder exists
   or after a logged Go failure.
8. **The archive is the unit** (D-052 (log)): a zip exports' logs, metadata, and assets are
   ingested, classified, and accounted for together; nothing inside is silently dropped (D-050).

## Pre-mortem #1 (owner-referenced 2026-08-12)

It is six months later and the spine "works" but the delta is worthless / the data tier is on fire.
What killed it:

1. **NOTIFY treated as transport.** Worker down at the moment of a burst → backlog silently grows;
   nobody alarmed because polling fallback was never implemented. *Mitigation already in the
   design:* outbox+cursor is the correctness path; NOTIFY is latency-only. **Test:** kill the
   worker, ingest, restart, assert zero missed rows.
2. **Trigger overhead on the hot write path.** Per-row trigger + outbox insert measurably slows
   bulk ingest of a 7,007-record export; the "fix" becomes bypassing the trigger, and the spine
   quietly stops being the only path. *Mitigation:* measure before rollout; batch-aware outbox
   writes; inline bypass is forbidden code, not just forbidden config.
3. **Poison-pill rows.** One malformed row fails its sink forever, the retry loop hot-spins, the
   cursor never advances, every later row is stuck behind it. *Mitigation (confirmed owner ruling
   2026-08-12, Q7):* per-event retry budget → **dead-letter TABLE** (full payload retained — nothing
   is ever dropped, consistent with the never-trim rule) + cursor advances past dead letters +
   replay tool drains the table after a fix + **alert on dead-letter count > 0 is mandatory**
   (operator console cdc-status surface; without the alert the table is a black hole).
4. **Cursor drift between sinks.** Weaviate projects row N, Graphiti crashes at N−1; weeks later a
   "rebuild" resets only one sink. *Mitigation:* per-sink cursors + a `cdc-status` surface that
   reports per-sink lag; rebuild resets are audited (ADR-0047).
5. **Horizon leak through the spine.** A subscriber strips or ignores the horizon payload, and its
   projection serves future facts to the ignorant agent — silently, and the delta is quietly
   worthless (canon §1). *Mitigation:* planted-future-fact test per subscriber before the
   subscriber is considered live; the Weaviate dict-filter landmine (FilterExpr no-ops) re-verified
   per sink.
6. ~~**Size threshold mispredicts.** ...~~ **RETIRED 2026-08-12 (owner ruling Q3 — no size axis).**
   Replacement failure mode: **silent Python fallback.** A Go decoder regression routes EVERY file
   of that format to slow/memory-heavy Python parsers and nobody notices until ingest crawls.
   *Mitigation:* fallback events are logged loudly (per Part 2) and counted on the operator cdc-status
   surface; a format whose Go failure-rate exceeds a small threshold alerts.
7. **Extraction output becomes canonical by default.** A well-meaning change auto-promotes
   candidates (or an agent writes them directly) — the HITL gate evaporates and ADR-0043's
   "nothing automatic overwrites canonical data" is breached invisibly. *Mitigation:* candidates
   and canonical rows are different tables with different grants; promotion exists only inside the
   `@approval` flow.
8. **Structured-output model roulette.** An extractor is wired to a model that can't emit
   schema-conformant JSON; extraction yields nothing for weeks and nobody notices (the Graphiti
   2026-07 failure mode). *Mitigation:* Langfuse traces + a conformance check in the tool's own
   test suite per model before wiring.
9. **Asset double-materialization.** Spine replay + re-ingest race writes duplicate document/code
   files. *Mitigation:* `content_hash` UNIQUE (already in sql/0022) + content-addressed blob keys
   make replay idempotent; a replay test proves it.
10. **Test data becomes canonical during the build.** A dry-run extraction lands in the live
    candidate tables and survives. *Mitigation:* the 2026-08-02 ruling binds — design-phase ingests
    are disposable; controlled-write proofs are cleaned up in the same session (the D-052 (log)
    pattern).

## Migration / rollout path (from today's pending-row polling)

Sequenced so each phase is independently shippable and reversible (the ADR-0050 phased-plan
discipline; no big-bang):

- **Phase 0 — NOW (shipped).** Pending-row polling + the manual `ingest.context-drain` tool. This
  ADR changes nothing at Phase 0; it names what exists.
- **Phase 1 — Spine on the context path only.** Add the outbox + trigger + NOTIFY to
  `working.context_record` writes; the always-on worker wraps the SAME
  `sync_pending_context`/drain code, now driven by events with a timed poll fallback. The
  `*_synced_at` stamps dual-write (stay the rebuild authority) until cursors are proven, then fold
  into `cdc_cursor`. Rollback = stop the worker; the drain tool still drains.
- **Phase 2 — Evidence workflow converges.** `server/evidence/workflows.py`'s inline Weaviate
  insert moves behind the spine, closing ADR-0051's invariant 4 for the second path and collapsing
  the two-path split.
- **Phase 3 — Extraction subscribers.** The Stage-2 tools register as spine subscribers (entity /
  legal fact-claim extractors, chunker+lane router, materialization). HITL gate lands on candidate
  promotion in the same phase — the gate must exist before extraction runs, not after (ADR-0051
  invariant 6). (Extraction itself runs regardless of custody-approval per owner ruling Q5 — the
  gate binds PROMOTION of candidates to canonical, and materialization.)
- **Phase 4 — DSPy optimization**, only after the classifier tool + Langfuse traces exist.
- **Reversal story end-to-end:** every phase keeps the prior phase operable behind a config flag;
  the projections are rebuildable from PG, so a bad spine rollout at worst costs a cursor reset.

## Consequences

- ADR-0051 invariant 4 becomes implementable for ALL paths; the two ingest paths can finally
  collapse onto the one flow.
- The drain tool graduates from manual stand-in to the atomic front door of an always-on worker —
  no code fork between "run it now" and "it runs itself."
- Rebuild semantics stay uniform: any lane, any sink, one cursor reset — which is also the
  contamination-recovery story.
- New obligations: the outbox/cursor schema is new custom code (register in docs/DEBT.md as
  justified custom per the minimize-custom lock — no off-the-shelf CDC fits the PG-first,
  horizon-payload, dual-tier shape); trigger-function migrations join the numbered sql/ chain;
  the worker is a new always-on service to deploy (Coolify app, watch_paths set at creation per
  the standing rule) and to monitor (the operator console gains a cdc-status surface).
- The coverage-based split (owner Q3) makes Go decoders for Claude/Perplexity/Gemini (ADR-0049
  Gap 2) load-bearing for ALL exports of those formats, not nice-to-have — until they exist, those
  formats route to Python parsers with a known memory ceiling at every size, and the override is
  the only guard. Go-decoder coverage is now on the critical path.
- Extraction landing as tools with candidate tables gives ADR-0043's Semantica worker a concrete
  seam to take over heavyweight multipass extraction later without re-architecting the stage.

## Explicitly OUT of scope

- **Google Timeline / Takeout work** — parked (ADR-0048/0049).
- **The segment→lane classifier model/prompt itself** — this ADR fixes WHERE it runs (a Stage-2
  tool) and WHEN (post-chunk), not its content. Own decision when the tool is designed.
- **Semantica full wiring** — ADR-0043's build, on its own phase gates; Stage 2 here must work
  WITHOUT it.
- **Horizon derivation machinery** (`visible_from`, `realization_event`, pass materializations) —
  ADR-0045's. The spine carries the fields; it does not compute them.
- **Graphiti schema/group changes** — Graphiti is a downstream consumer here, nothing more.
- **DSPy** — deferred by name (Phase 4 precondition).
- **The SBV GUI engine/format selectors** — ADR-0049 GUI surface work; CLI/API overrides are the
  MVP mechanism (D-049 / TODO-15).

## Owner rulings (2026-08-12, AskUserQuestion — ALL 8 resolved; ADR awaits final sign-off)

1. **Mechanism — RULED: outbox + NOTIFY-wakeup + per-sink cursors is THE mechanism.** Polling is
   the fallback inside the worker; logical replication explicitly rejected (replication-slot disk
   risk too heavy for a single-owner platform).
2. **Outbox shape — RULED: PER-TABLE outbox tables** (owner overrode draft's leaned-shared option).
   Hot-spot per lane beats one global stream; cross-table causal order is the worker's problem to
   reconstruct, not a reason to serialize all writes through one table.
3. **Size threshold — RULED: NO SIZE AXIS at all.** Owner verbatim: "everything needs to go to the
   Go engine unless there's not a Go parser available or if for some reason the Go parser fails and
   we have a Python parser that functions." Engine split is coverage + failure-fallback (Part 2
   rewritten). The calibration numbers (16/61 MB exports) remain as sizing context only.
4. **Trigger cost — RULED: FULL outbox row per insert, trigger-written** (the strongest option).
   ~2× write amplification accepted; "no commit without its event" is enforced BY THE DATABASE,
   not by code-path convention.
5. **Extraction timing — RULED: ALWAYS EXTRACT, regardless of custody-approval** (carries ADR-0051's
   open question). Guard added in exchange: candidate rows carry the source record's
   `disclosure_tier` + custody-approval flag; horizon binds at promotion/materialization/retrieval,
   never at extraction. The review queue may contain candidates from unapproved evidence — accepted
   trade-off.
6. **Candidate tables — RULED: TWO tables**, with a rename: `working.entity_candidate` +
   `working.claim_candidate` (~~`working.artifact_candidate`~~). Owner: "artifact" reads as created
   works (AI chats / generated documents), not fact-claims; merge semantics differ (entities merge,
   claims accumulate, never rewritten).
7. **Dead-letter — RULED: dead-letter table + replay tool + mandatory alert** on count>0 (operator
   console cdc-status surface). Nothing is silently dropped; lane stays readable.
8. **Worker placement — RULED: standalone always-on Coolify app on the data tier** (not an
   agentos-api sidecar). Watch Paths set at app creation per the standing 2026-07-21 rule.

## Alternatives considered

- **Plain polling, upgraded** (keep D-048 as-is; add a cron/loop around the drain tool) —
  rejected: per-row triggers give transactional coupling (event and data commit or roll back
  together); polling-only leaves an unbounded latency window between write and propagation and
  makes "already sent" bookkeeping spread across per-sink stamp columns, which does not scale past
  two sinks. Polling survives here as the FALLBACK inside the worker, not as the design.
- **LISTEN/NOTIFY without an outbox** (payloads as the transport) — rejected: notifications to a
  down/absent listener are lost by construction; correctness cannot ride on an advisory channel.
- **Logical replication / WAL decoding** (wal2json, pg_logical slots, or an external CDC like
  Debezium) — rejected for now: operationally the heaviest option (replication slots pin WAL and
  can silently bloat the data tier; a new external service violates minimize-custom), and it
  carries schema-level change streams, not the lane-aware, horizon-payload events subscribers
  actually need. Revisit if row volume outgrows the outbox.
- **Trigger-free, writer-emitted events only** (each ingest code path inserts its own outbox row) —
  rejected as the SOLE mechanism: it makes the spine a convention every future writer can forget;
  the trigger is the enforcement. (Open question 4 leaves room to measure.)
- **Extraction as agents** (an "extraction agent" per kind) — rejected by owner ruling 2026-08-12:
  tools, not agents. An agent wrapper adds an uncontrollable decision layer over a unit that must
  be atomic, traceable, and dual-invocable.
- **DSPy-first extraction** (optimize prompts before tracing exists) — rejected by owner ruling:
  deferred until the classifier tool + Langfuse traces exist; optimizing against no trace data is
  how the glm-5.1 silent-empty-extraction failure happened.
- **Route large files by format allow-list instead of measured size** — rejected: format is a
  proxy for the real constraint (memory), and it would mis-route a small ChatGPT export to Go and
  a huge novel-format export to Python; the D-051 router already keys on format, so size is the
  missing axis, not a replacement one. **(Mooted 2026-08-12 by owner ruling Q3: the owner's
  coverage-based rule — Go parses everything it has a decoder for, Python is uncovered-format /
  failure-fallback — subsumes BOTH the size gate and this alternative; the D-051 router keys on
  format already, and coverage-based routing needs no new axis at all.)**
