# SurrealDB Analytical Aggregation Surface

> _Byline: Claude Code · Sonnet (subagent) · 2026-09-01_

Handoff H-11. Docs-only design note. Grounds SurrealDB's current, governed role in this
platform in applied DDL and accepted ADRs, and records two open decisions (`opensearch`,
`sat_temporal`) that live in that same applied CHECK constraint with no design doc or ADR
behind them.

## 1. What the Surreal analytical aggregation surface is

SurrealDB is **not** a general-purpose database in this platform. It is a governed,
rebuildable **analytical projection** — one of several sinks that PostgreSQL fans content
out to after canonical writes land. Two accepted decisions establish this:

- **ADR-0032** (`docs/adr/0032-drop-pg-fdw-federation-surreal-is-analysis-sink.md`,
  Accepted 2026-06-26) established the shape of the pipeline: **PG → Surreal**, with
  Postgres as the processing/staging hub and Surreal as the downstream consolidation /
  analysis sink. That ADR's real subject is dropping the Multicorn2/FDW federation layer
  (query-time cross-source JOINs inside PG), but its premise — "processed data flows PG →
  Surreal, and analysis happens in Surreal" — is the founding statement of Surreal's role
  as sink, not source of truth.

- **ADR-0056** (`docs/adr/0056-surrealdb-governed-analytical-and-walk-memory-surface.md`,
  **Accepted**, Decision 10 later narrowed by ADR-0059) restated and hardened that role
  after SurrealDB had been pulled out of Agno's operational critical path by ADR-0043:

  > "PostgreSQL remains the canonical authority for evidence, custody, claims, approvals,
  > promotion decisions, and audit records." (Decision 1)
  >
  > "SurrealDB returns as a **governed, rebuildable analytical projection** and an
  > experimental tri-temporal memory/runtime for one as-lived walk agent. It is not the
  > Agno operational database and does not replace PostgreSQL." (Decision 2)

  ADR-0056 is what licenses SurrealDB to exist as live infrastructure again after ADR-0043
  retired it — see §5 for why that matters to the `deploy/` compose files.

- **`sql/0058_the_reckoning.sql`** (applied to the live database 2026-08-31, recorded in
  `ops.migration_ledger` per D-116 in `docs/DECISION_LOG.md`) is where this stopped being
  only a decision on paper. It created `working.content_chunk_projection`, the fresh-ingest
  chunk-projection tracking table, with this CHECK constraint (verbatim, `sql/0058_the_reckoning.sql:178`,
  confirmed live in `sql/bootstrap/schema_baseline_20260830.sql:5047`):

  ```sql
  sink TEXT NOT NULL CHECK (sink IN ('weaviate','semantica','sat_temporal','opensearch','surrealdb')),
  ```

  `surrealdb` is one of five values the applied schema accepts for `sink`. That is first-class
  status in real, currently-applied DDL — not a proposal, not a mockup, not a stale doc claim.

**Current implementation status, stated plainly:** the CHECK constraint accepts `surrealdb`,
but no code in `server/` currently writes rows into `working.content_chunk_projection` for
any sink (a repo-wide search found only the table's own DDL — `sql/0058_the_reckoning.sql`,
`sql/bootstrap/schema_baseline_20260830.sql`, and `docs/DECISION_LOG.md` D-116 reference it;
`server/ingest/service.py` reports `weaviate` projection results as a Python literal in its
`ProjectionResult` objects, not by reading this table). The schema is real and applied; the
Surreal projector that would populate it is not yet built. Do not describe SurrealDB
projection as "live" without separately verifying a projector process and observed rows —
the applied CHECK constraint proves the contract, not the pipeline.

## 2. SurrealDB is a rebuildable projection, never authority

This is the load-bearing constraint and it must not erode over time:

- ADR-0056 Decision 1 names PostgreSQL as canonical authority for evidence, custody,
  claims, approvals, promotion decisions, and audit records. Decision 2 names SurrealDB a
  **governed, rebuildable analytical projection** that "does not replace PostgreSQL."
- The platform's broader canon (`AGENTS.md`, repository root) states the same rule for
  every non-Postgres store: PostgreSQL 18 is "canonical source/control plane," and
  SurrealDB is "the governed final reconciled temporal-graph, walk, and analysis engine" —
  governed and reconciled against PG, not an independent origin of facts.
- ADR-0056 Decision 4 spells out what actually crosses the PG → Surreal boundary:
  "promoted manifests, normalized content, exact locators, chunks, embedding instances,
  graph relationships, temporal state, traces, and future TraceIQ projections." Original
  binaries stay in custody-controlled object storage, referenced by immutable hash — Surreal
  never becomes the custody store.

**What "a full rebuild from Postgres must be possible" requires at design level:**

1. **Every Surreal-resident fact must be derivable from a PG row plus a documented
   transform.** No hand-edited, agent-written, or walk-produced state may exist in Surreal
   without a PG-side origin (an approved `canon.change_proposal` per D-114, a promoted
   `evidence.evidence_item`, a sealed `working.content_chunk`, etc.) — otherwise a rebuild
   silently loses it. ADR-0056 Decision 11 already enforces a related discipline for walk
   beliefs: a walk cannot import candidates "produced under a broader horizon" — the same
   provenance discipline extends to the projection surface generally.
2. **A projection generation/version marker per Surreal record**, so a rebuild can detect
   whether a record reflects the current PG generation or a stale one. `working.content_chunk_projection`
   already carries `source_generation BIGINT` for exactly this purpose (though as noted
   in §1, no writer populates it yet).
3. **A rebuild procedure that is drop-and-repopulate, not incremental-only.** Because
   Surreal owns no independent facts, wiping a Surreal namespace/database and re-running
   the projector against PG's current state must be a supported, tested operation — not a
   theoretical one. ADR-0056's own risk section calls this out under "Projection drift":
   PostgreSQL IDs, custody hashes, projection revisions, and rebuild checkpoints must be
   carried so mismatches fail closed rather than silently diverge.
4. **Horizon/disclosure predicates travel with every Surreal write**, not just the initial
   projection. This is the platform's core mechanism (see `AGENTS.md` §"WHY THIS EXISTS")
   applied to a concrete store: a Surreal rebuild that drops the temporal/disclosure
   predicate on a re-projected node reintroduces the exact contamination risk ADR-0056's
   "Horizon contamination" mitigation exists to prevent.
5. **No irreversible action ever originates in Surreal.** Per ADR-0056 Decision 9 (post-parity)
   and the general canon rule, canonical control and approval metadata come from PostgreSQL;
   Surreal supplies retrieval, not authority, even after the as-lived walk retrieves
   exclusively through its Surreal projection.

Any future implementation plan for this surface should treat "can this be safely dropped
and rebuilt from PG with a verifiable diff of zero" as its primary acceptance test — that
property is the entire justification for letting Surreal exist as live infrastructure again
after ADR-0043 pulled it out.

## 3. The two undocumented sinks: `opensearch` and `sat_temporal`

The CHECK constraint quoted in §1 lists five sinks. `weaviate` and `surrealdb` are covered
by ADR-0040/ADR-0056 respectively. `semantica` is covered by ADR-0043 (governed extraction
worker). The remaining two — `opensearch` and `sat_temporal` — have **no ADR and no design
doc**, despite each having real, separately-documented history elsewhere in the repository.
This section reports what evidence actually exists for each and treats what it does not
cover as open decisions, per the task's own instruction not to invent intent.

### 3a. `opensearch` — real, but for a different projection than the one holding this CHECK

- **What it is:** OpenSearch is the search/event index backing the platform's Timesketch
  fork (personal-case timeline surface). **ADR-0060**
  (`docs/adr/0060-timesketch-personal-case-timeline-fork.md`) and **ADR-0061**
  (`docs/adr/0061-unified-operator-surface.md`) both describe it as a rebuildable,
  governed projection: ADR-0060 states "OpenSearch and Timesketch metadata are rebuildable
  serving state," and explicitly rejects making it canonical ("Make Timesketch/OpenSearch
  canonical: rejected because it would split authority, weaken custody..."). D-084 in
  `docs/DECISION_LOG.md` confirms this was owner-ruled 2026-08-26.
- **Where it is actually wired:** the **timeline** schema, not the content-chunk schema.
  `timeline.timeline_projection_member` (`sql/0035_timeline_projection.sql`, confirmed live
  in `sql/bootstrap/schema_baseline_20260830.sql`) carries `opensearch_doc_id` and
  `opensearch_index` columns, a `sink` column defaulting to `'timesketch_opensearch'`, and
  is backed by real projector code in `server/timeline/generation.py`, `server/timeline/receipts.py`,
  and `server/timeline/projector.py` (`server/timeline/AGENTS.md` documents the module).
  This is a live, real, ADR-governed pipeline — for **timeline events**, not for
  `working.content_chunk` rows.
- **The open decision:** `working.content_chunk_projection.sink` (the table this handoff
  is about, from `sql/0058`) accepts `'opensearch'` as a valid chunk-projection sink, but
  no code writes chunk-level rows there for any sink (§1), and nothing in ADR-0060/0061 or
  `server/timeline/` describes chunks being projected to OpenSearch — only timeline events
  are. Either (a) a future design intends content chunks to also land in OpenSearch as a
  full-text search projection distinct from the timeline pipeline, in which case it needs
  its own ADR describing what chunk-level OpenSearch indexing is for and how it differs
  from the timeline projection, or (b) `'opensearch'` was added to this CHECK by analogy
  with the timeline sink without a distinct design behind it and should be narrowed back
  out until one exists. **This design doc does not resolve which; it flags the gap.**

### 3b. `sat_temporal` — real and owner-ruled, with a recovery story worth preserving

- **What it is:** `sat_temporal` is the lane identifier for the platform-owned
  **SAT-RAG / legal SAT-Graph temporal lane** — a Neo4j/DozerDB graph database running
  alongside (never fused with) the Semantica extraction graph, for explicit side-by-side
  GraphRAG evaluation. **D-093** in `docs/DECISION_LOG.md` (owner-ruled 2026-08-27,
  "implementation pending") is the primary decision record:

  > "A platform-owned SATemporal GraphRAG lane and a pinned/decomposed Semantica lane run
  > concurrently for explicit side-by-side evaluation, never as parallel authorities... DozerDB
  > isolates the graph projections in named databases: existing `evidence` remains the
  > Semantica graph; new `sat_temporal` owns the custom legal SAT structure/version/action/text
  > model and temporal/rule-graph retrieval..."

  **D-106** (2026-08-29) corrects the literal Neo4j database name — DozerDB rejects
  underscores in database names, so the live Neo4j/DozerDB database is `sat-temporal`
  (hyphen), while `sat_temporal` (underscore) remains the internal lane id used throughout
  the SQL layer (`analysis.graph_lane` ENUM, `analysis.graphrag_lane_receipt`,
  `analysis.graphrag_comparison_join.sat_temporal_receipt_id`).

- **How it got into applied schema:** **D-112** (2026-08-30) records that the SAT/Semantica
  implementation was recovered from five orphaned `.pyc` files (compiled 2026-08-27, source
  never committed, would have been lost to a `git clean` or Python version bump). The
  recovered artifacts included the `GraphRagLane` discriminator (`semantica`/`sat_temporal`)
  and the SQL for the `analysis.graphrag_*` tables. They were preserved to `docs/recovered/`
  and reconstructed as real schema in `sql/0055_graph_lane_provenance_and_graphrag_recovery.sql`
  — including this repository's own comment explaining the naming split
  (`sql/0055_graph_lane_provenance_and_graphrag_recovery.sql:37-40`).

- **Its presence in the `content_chunk_projection.sink` CHECK:** `sql/0056_canon_change_spine.sql`
  independently uses `sat_temporal` as a `canon.recompute_queue` **recompute target**
  (`recompute_target TEXT NOT NULL, -- 'semantica' | 'sat_temporal' | 'vectors' | 'timeline' | ...`,
  `sql/0056_canon_change_spine.sql:153`), and `sql/0059_identity_trust_state.sql` uses it the
  same way for identity-reconciliation fan-out. So `sat_temporal` is a genuine, owner-ruled,
  actively-used fan-out target **elsewhere in the schema** (canon recompute), which is
  presumably why `sql/0058` also listed it as a valid `content_chunk_projection.sink` value —
  by analogy with its established role, not a fresh invention.

- **The open decision:** there is still no dedicated ADR for the SAT-RAG lane itself — D-093
  is a `docs/DECISION_LOG.md` entry ("owner-ruled... implementation pending"), not a signed
  ADR, and no `docs/adr/00NN-*.md` file currently exists for it (searched; none found — the
  closest ADRs are 0036 "DozerDB multi-db RBAC" and 0041 "Memgraph additive temporal GraphRAG
  layer," neither of which documents the SAT lane's `content_chunk_projection` sink role).
  As with `opensearch`, no code currently writes chunk-level projection rows with
  `sink='sat_temporal'` (§1). Recommend either: (a) write the SAT-RAG lane ADR that D-093
  implies is still owed, explicitly covering whether/how content chunks (not just
  extraction-time graph writes) are meant to project into the `sat-temporal` Neo4j database,
  or (b) if chunk-level projection to this lane was never actually intended and the CHECK
  value is inherited by analogy from the recompute-queue usage, narrow the CHECK and record
  that narrowing as a decision-log entry so the next reader does not re-open this question
  from zero.

**Neither `opensearch` nor `sat_temporal` is speculative noise — both trace to real,
owner-ruled, applied schema elsewhere in the platform.** What is missing in both cases is a
document that specifically justifies their presence as `working.content_chunk_projection`
sinks (as opposed to their well-documented roles in the timeline pipeline and the recompute
queue, respectively). This doc does not manufacture that justification; it names the gap as
an open decision per the task's instruction.

## 4. The two-mechanism fan-out split — do not merge these

`working.content_chunk_projection` (created in `sql/0058_the_reckoning.sql`) and
`canon.recompute_queue` (created in `sql/0056_canon_change_spine.sql`, referenced again in
`sql/0059_identity_trust_state.sql`) are **two deliberately separate processes with
overlapping-looking sink/target vocabularies.** This is stated explicitly in the migration
that created the successor table, and reaffirmed in the owner-reviewed decision log:

- `sql/0058_the_reckoning.sql:172-174` (comment directly above the table definition):

  > "Process carried over from `chat_chunk_projection` (deleted above): which chunk has
  > been projected to which sink, with retry/error state. **Fresh-ingest projection is THIS
  > table + the workers; `canon.recompute_queue` handles re-projection after approved
  > changes. Two processes, two tables, on purpose.**"

- `sql/0058_the_reckoning.sql:191-192` (table comment, same intent, shorter):

  > "Fresh-ingest projection state for `content_chunk`... Re-projection after an approved
  > canon change is `canon.recompute_queue`'s job — **deliberately separate processes**."

- **D-116** in `docs/DECISION_LOG.md` (2026-08-31, owner: "blueprint reviewed,
  method-confirmed") restates the same split as part of the applied reckoning migration:
  "`content_chunk_projection` created as successor for fresh-ingest projection state —
  **deliberately separate from `canon.recompute_queue`**, which handles re-projection after
  approved changes."

**Why they must stay separate, spelled out for anyone tempted to consolidate them later:**

| | `working.content_chunk_projection` | `canon.recompute_queue` |
|---|---|---|
| Trigger | A chunk is newly created (fresh ingest) | An approved `canon.change_proposal` is adopted (D-114) |
| Question it answers | "Has this brand-new chunk reached sink X yet?" | "What downstream derived work must recalculate because canon changed?" |
| Granularity | Per `(chunk_id, sink)` | Per recompute target, driven by `canon.change_proposal.recompute_targets` |
| Failure semantics | `pending` / `projected` / `failed` / `skipped` with `attempts`/`last_error` — a retryable per-chunk worker queue | Enqueued rows for downstream consumers to drain after a canon-changing event |
| Owner rationale (D-114) | N/A directly — this is the ingest-time half | "adoption snapshots prior values, bumps the table generation, and enqueues `canon.recompute_queue` rows so downstream derived work recalculates" — and explicitly: this "must not" repeat the fate of the 2026-08-24-era outbox tables, which "died consumer-less" |

A merge would conflate "this is new content that has never been projected" with "this
content already existed, was projected once, and now needs to be reprojected because
something upstream about it changed" — two different lifecycles with different retry
semantics, different triggers, and (per D-114) an explicit owner requirement that the
recompute path have a real consumer this time, unlike the 2026-08-24 outbox tables that
`sql/0058` itself deleted for having none (`working.chat_conversation_event`,
`working.chat_message_event`, etc. — "dead outbox (7) — `canon.recompute_queue` is the one
fan-out mechanism," `sql/0058_the_reckoning.sql:75`). **Do not simplify this into one
table.** If a future refactor proposes merging them, it should be treated as reopening a
question the owner has already closed twice (2026-08-31 migration comment + D-116), and
routed back to the owner rather than resolved unilaterally.

## 5. The rescinded v1-audit advice to relocate the `deploy/` Surreal compose files

**Current state (verified by reading the files):** `deploy/compose.data-surreal.yaml` and
`deploy/compose.surreal-phase1.yaml` both exist in the repository today, and neither was
touched by this handoff (docs-only; compose files are explicitly out of scope per this
task's constraints).

**Why an earlier audit lens flagged them as contradictory / candidates for removal:**
`deploy/compose.data-surreal.yaml`'s own file header still reads:

> "PARKED — DO NOT DEPLOY, DO NOT DELETE (S10 annotation, 2026-08-10) — SurrealDB is
> RETIRED (ADR-0043 d3, flatten executed 2026-08-04; D-042 OQ-7)."

That header was accurate when written — ADR-0043 (Accepted 2026-08-02) removed SurrealDB
from Agno's operational critical path, and the S10 consolidation on 2026-08-10 treated the
Surreal compose file as parked infrastructure worth keeping at the repo root only as a
historical record, "NOT moved to `deploy/` in the S10 consolidation because no Coolify app
references it." Reading that stance at face value, a subsequent audit pass flagged a live
contradiction: `docs/URGENT-TODO.md` item 14 (OWN-005 in
`docs/reviews/2026-08-23-cross-repo-evidence-audit/ISSUES-AND-TODO.md`) states —

> "SurrealDB is formally RETIRED (ADR-0043, owner ruling 2026-08-06) — yet
> `data-surreal-phase1-t0-r1` is live in Coolify production and was ordered promoted on
> 2026-08-20. These cannot both be current intent." — flagged **"Contradicts canon,"
> OWNER — BLOCKING.**

Separately, `docs/URGENT-TODO.md` (2026-08-24 entry) records the owner's own contemporaneous
impulse in the same direction: "owner personally moved `compose.data-surreal.yaml` +
`compose.surreal-phase1.yaml` out of the repo root same night ('they don't belong there')" —
though that note explicitly defers the corresponding deletion/relocation commit to the owner,
not an agent, and it was never carried out (both files remain in `deploy/` today).

**Why that advice is now rescinded:** the premise underneath both the audit flag and the
owner's same-night impulse — that SurrealDB is simply retired and any Surreal compose
artifact is dead weight — no longer holds, for two independently sufficient reasons:

1. **ADR-0056 (Accepted, 2026-08-15) narrows ADR-0043.** ADR-0056's own text is explicit
   about the scope of what it changes: "This supersedes ADR-0043 only where that ADR says
   SurrealDB has no future analytical/memory role. ADR-0043's PostgreSQL authority, Semantica
   candidate boundary, and removal of SurrealDB from Agno's operational critical path remain
   in force." SurrealDB is retired as the **Agno operational store** — that part of ADR-0043
   stands — but it is simultaneously and deliberately live again as a **governed analytical
   projection**, which is a different claim than "SurrealDB is retired" read without
   qualification.
2. **`sql/0058` (applied 2026-08-31) is not a proposal — it is proof.** The `'surrealdb'`
   value in the live, applied `working.content_chunk_projection.sink` CHECK constraint (§1)
   means the current production schema treats SurrealDB as a first-class projection target
   today, not a historical curiosity being wound down. An artifact that ships live SurrealDB
   infrastructure (`deploy/compose.surreal-phase1.yaml`, "Disposable synthetic-only Phase-1
   SurrealDB slice on ovh-files... Stop and quarantine; never delete the app, volume, or
   files automatically") is consistent with, not contradictory to, that applied schema.

**What follows for these two files, stated as documentation guidance and not as an action
taken here:** the `deploy/compose.data-surreal.yaml` header's "SurrealDB is RETIRED"
sentence is now stale relative to ADR-0056 and should eventually be corrected in place (to
something like "the legacy Agno operational Surreal adapter is retired; SurrealDB itself
returns as a governed analytical projection per ADR-0056") — but per this handoff's explicit
constraints, that edit is out of scope here and belongs to whoever next touches that file
with authorization to do so. The relocate/delete impulse that both the v1 audit and the
owner's 2026-08-24 note expressed is superseded by ADR-0056 + the applied `sql/0058` DDL and
should not be resurrected without re-reading both.

## Summary

- SurrealDB is a governed, rebuildable analytical projection (ADR-0032 origin, ADR-0056
  current governing decision), never authority; PostgreSQL is canonical (ADR-0056 D-1).
- `sql/0058_the_reckoning.sql` (applied 2026-08-31) proves this in live DDL: `'surrealdb'`
  is one of five values in `working.content_chunk_projection.sink`'s CHECK constraint. No
  code currently writes rows to that table for any sink — the contract is real, the
  projector is not yet built.
- A full rebuild-from-Postgres must be provably possible; §2 lists the five design-level
  requirements that make that true (provenance, generation markers, drop-and-repopulate
  support, traveling horizon predicates, no Surreal-originated authority).
- `opensearch` and `sat_temporal` are both real elsewhere in the schema (Timesketch/ADR-0060
  and the SAT-RAG lane/D-093 respectively) but neither has a design doc or ADR justifying
  its specific presence as a `content_chunk_projection` sink — flagged as open decisions,
  not invented intent.
- `content_chunk_projection` (fresh-ingest) and `canon.recompute_queue` (re-projection after
  canon changes) are two deliberately separate mechanisms per the 0058 migration comment and
  D-116 — do not merge them.
- The earlier audit-era impulse to relocate/remove the `deploy/` Surreal compose files is
  rescinded by ADR-0056 (Accepted) plus the applied `sql/0058` DDL; no file was touched by
  this handoff.
