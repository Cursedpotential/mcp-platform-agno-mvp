# ADR-0045 — Horizon clocks (visible_from) and the checkpoint-derivation architecture

> _Byline: Claude (Cowork) · Fable 5 · 2026-08-09_

- **Status:** **Accepted** (owner signed 2026-08-09 — Option A, WITH the A.4 realization-events amendment; recorded as D-042)
- **Context sources:** 2026-08-09 full-repo audit (findings N1, N2, N3, FA, F-E, FC); owner
  rulings 2026-08-09 (checkpoint-derivation architecture, audit-everything, never multi-case);
  `docs/COMPACT-SUMMARY-2026-08-01.md` (six-clock design conversation — ratified here);
  ADR-0018 (bitemporal memory), ADR-0043 (PG canonical; Neo4j/Weaviate = rebuildable projections).
- **Ratifies:** the 2026-08-01 six-clock ruling (previously recorded only in a compact summary —
  finding FA). DECISION_LOG: D-039.

## Context

The knowledge-horizon mechanism is the platform's core deliverable (canon §1): agents with
different knowledge horizons read the same evidence, and the delta between the ignorant walk and
hindsight IS the case. The audit found the mechanism structurally unsound as built:

- **N1 — inert predicate.** `working.horizon_visible()` (sql/0018:115) filters on
  `knowledge_time`, which sql/0008:247 declared SUPERSEDED ("records row-write time, NOT when the
  party learned — do not use for 'when did you know' questions"), and which
  `server/contracts/records.py::finalize()` stamps `now()` on every record. Every row's knowledge
  time ≡ ingest wall-clock: historical horizons exclude everything; post-ingest horizons admit
  everything. The same value feeds the Weaviate horizon axes (`store.py`).
- **N2 — clocks unwritten.** Nothing writes `realized_at` / `acquired_at` / `realized_evidence` /
  `acquisition_id`; the "authoritative" derived-tier view returns NULL for every row.
- **N3 — tier hardcoded.** Every writer emits `disclosure_tier='contemporaneous'`; the anti-leak
  guards can never fire. (The parser hardcoding is itself CORRECT — extraction cannot know
  better; the defect is that no derivation layer exists above it.)
- **F-E — predicate duplicated.** The rule exists twice (SQL + a test mirror) with no shared
  source.

Additionally, the owner ruled (2026-08-09) that pass corpora may be materialized as separate
tables/collections — a pattern canon §1 currently forbids outright ("do NOT design parallel
as-lived/hindsight stores") — provided both are derived from the canonical factual layer.

## Decision

### A. The horizon clock is `visible_from = COALESCE(realized_at, occurred_at)`

- **Semantics:** the time the party knew the fact. A contemporaneous message was known when it
  occurred (you know your own messages) → `occurred_at`. A later-discovered fact was known when
  the discovery was HITL-confirmed → `realized_at`.
- **`acquired_at` is custody metadata only** and is NEVER a horizon input. Failure case that
  rules it out: bulk ingestion in 2026 of a 2023 export stamps `acquired_at=2026`; a 2023 horizon
  would then exclude the party's own 2023 messages — the same inert-filter failure as
  `knowledge_time`, in a different column.
- **`knowledge_time` is frozen** as the row-write audit clock (per 0008's own comment). It is
  never repurposed and never consulted by any horizon predicate.
- **Form (Option A, recommended):** predicate-computed `COALESCE(realized_at, occurred_at)` with
  an expression index. Option B (a materialized `visible_from` column) buys `EXPLAIN` legibility
  at the cost of one more writable, driftable field. Owner picks A or B at signature.
- `realized_at` is HITL-confirmed only, via the native `@approval` flow (ADR-0002; never a custom
  approval table). `acquired_at` is set by ingest (machine-knowable). Parsers keep emitting
  `disclosure_tier` as an ASSERTED HINT; the authoritative tier derives from the clocks + HITL.

**A.4 — Realization events table (owner amendment, signed 2026-08-09).** Found-out knowledge
lives in its OWN table, `working.realization_event`, not as columns updated on evidence rows:

- A realization is an event with its own provenance: what was realized, when, HOW (kind:
  `contradiction` | `export_read` | `told_by_person` | `manual` | …), the trigger record (e.g.
  the later conversation that contradicts an earlier assertion), evidence pointer, proposer
  (`algorithm` | `owner`), and approval status. One event may cover MANY records
  (`realization_event_record` link table — reading one export reveals hundreds at once).
- **The evidence spine is never modified.** `working.normalized_record` stays append-only;
  knowledge about the evidence accumulates alongside it. (0008's `realized_at` column on the
  record is superseded as source of truth; the predicate reads the events table.)
- **`visible_from` therefore = COALESCE(earliest APPROVED realization event for the record,
  occurred_at)** — still Option A, computed live, sourced from the events table via the one
  derivation function.
- **Contradiction events double as the lie register**: an approved `contradiction` row carries
  both the assertion date and the found-out date — the courtroom artifact, catalogued for free.
- **Workflow**: algorithm (Part 2 analysis, later) or any ingest lane PROPOSES events; the owner
  approves in batches through the native `@approval` queue. Nothing becomes visible-from-truth
  unapproved. ~~Per the OQ-8 ruling (D-042): HITL-only, with ONE exception — the AI-chat context
  lane auto-asserts `hindsight` tier at write (it is retrospective by nature); everything else
  waits for the owner.~~ **REVISED 2026-08-12 (D-056, owner correction): OQ-8 is REVERSED for the
  AI-chat context lane — it asserts NO tier at write. `working.context_record` carries no
  `disclosure_tier` column at all (migration `sql/0023`, applied live 2026-08-12); the context
  lane writes ONLY normalized data (`occurred_at` / `role` / `content` / `participants`). The
  as-lived / how-I-saw-it / discovered / hindsight horizon is a QUERY-level distinction derived
  from the clocks + HITL realization events — this ADR's A.4 `working.realization_event` + the
  derived `vw_record_disclosure` view — never a stamp on the normalized row: not `contemporaneous`
  (the old hardcode, which made every row a false as-lived assertion) and not `hindsight` (which
  would re-introduce horizon logic at the ingest layer). `working.normalized_record` (the
  evidence spine) KEEPS `disclosure_tier` as an asserted hint per Decision C — that is unchanged.
  Owner verbatim (2026-08-12): "Normalized data just normalized fucking data … all that stuff
  is a different fucking table just add the normalized fucking data ingest the fucking data."**

### B. Checkpoint-derivation architecture (amends canon §1)

**What stays forbidden:** parallel AUTHORED stores — two independently-written corpora whose
drift would corrupt the delta.

**What is sanctioned:** version-pinned, DERIVED pass materializations. One canonical factual
layer (ingestion + Semantica candidates, per ADR-0043) is the only authored store. Pass corpora
are cut from it by ONE derivation function under two schedules:

- **As-lived (incremental):** at each walk step, the refresher appends the newly-visible slice
  (`visible_from` in the step's horizon window) to the pass corpus, chain-hashing each step
  against the previous (`prev_hash`). These step records ARE the walk-ledger
  (`working.walk_ledger`) — **this closes OQ-1** and supersedes the SurrealDB rationale on
  `sql/drafts/walk_ledger.postgres-draft.HOLD.sql`.
- **Hindsight (on-prompt):** full materialization on demand.

**Four conditions, all mandatory:**
1. The refresher is the SOLE writer of pass tables/collections (grant-enforced INSERT; agents
   hold SELECT on their own pass corpus only, and NO grant on the canonical base tables).
2. Every checkpoint records the canonical-store base version it was cut from; a walk pins its
   base version at start — mid-walk ingestion lands in the NEXT run. Runs are citable objects:
   (pass, run_no, base_version).
3. Every derivation is hash-attested to `ops.audit_ledger` (ADR-0047): corpus hash + parameters.
   Re-derivation at the same base version MUST reproduce the identical hash.
4. Cross-lane checkpoints (Postgres + Weaviate) cut from the SAME base version in one operation.
   Per-pass Weaviate collections copy stored vectors — no re-embedding.

One predicate implementation serves both schedules AND the tests (resolves F-E). Graphiti is
unaffected: per-(case, pass) belief groups are the agents' own accumulating belief state
(ADR-0043), not an evidence copy. Analysis/observation tables append with
(pass_id, run_no, base_version) attribution.

### C. `disclosure_tier` type on `working.normalized_record`

TEXT + CHECK (as built) stands; the `ai.disclosure_horizon` enum remains where it lives
(`analysis.time_assertion`, `analysis.timeline_event`). AGENTS.md's contrary claim was corrected
2026-08-09 (finding FA). No type migration.

## Consequences

- S6 (horizon spine) becomes implementable: clock migration, writers, derivation engine, grants,
  lane bindings — in that order. Binding readers before A lands would admit the whole corpus
  while appearing correct; the ordering is non-negotiable.
- A pass corpus becomes a frozen, hashable, court-citable artifact; the Pass-1-vs-final delta is
  a diff between two attested artifacts, reproducible from (base_version, parameters).
- The bootstrap baseline must carry the horizon layer (finding FC — regenerated in S3) or fresh
  environments silently lack the mechanism this ADR defines.
- Enforcement simplifies: pass-table grants replace most runtime-RLS machinery; the residual
  fail-closed rule stays (missing HorizonContext → zero rows AND a raised error; hindsight is an
  explicit grant, never a default).
- The derivation engine is new custom code — registered as justified custom in docs/DEBT.md
  (no Agno-native equivalent; genuinely situation-specific per the minimize-custom lock).

## Alternatives considered

- **Repoint the predicate at `acquired_at`** — rejected: bulk-acquisition failure case above.
- **A new `learned_at` column** — rejected: a 7th clock duplicating what
  `COALESCE(realized_at, occurred_at)` already expresses; more writer surface, no new semantics.
- **Keep `knowledge_time` and re-teach writers to set it correctly** — rejected: 0008 already
  ruled the column means row-write time; repurposing a column against its own DDL comment is how
  N1 happened in the first place.
- **Parallel authored as-lived/hindsight stores** — remains forbidden (drift corrupts the delta).
- **Post-hoc filtering after top-k** — remains forbidden (silently shrinks k; leak invisible to
  count-based tests; per sql/0018's own comment).
- **Extraction-layer filtering** — remains forbidden (Semantica reads everything, forms no
  beliefs — ADR-0043; the horizon discipline is an agent-layer property).
