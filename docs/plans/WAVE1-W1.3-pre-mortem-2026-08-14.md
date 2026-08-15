# WAVE 1.3 Pre-Mortem — Derivation Engine + Horizon Repoint (ADR-0045 §B + §A)

> **R0 AUDIT BANNER 2026-08-15:** rollback validation below does not establish
> Wave-1 cutover readiness. Read `../HANDOFF-2026-08-15-R0-wave1-audit.md`;
> migrations remain unapplied and product execution is held. _Byline: Codex · GPT-5._


> _Byline: Claude Code · glm-5.2:cloud · 2026-08-14_
> Status: **BUILD COMPLETE — validated in rollback on live; NOT applied to prod; NOT pushed.**
> Owner review surface: one of the per-task pre-mortems the owner asked for and will review together.

> ⚠ **CORRECTION 2026-08-14 (CH-11 / D1):** the F4 recommendation carried here
> (`occurred_at_max` for the bundle + make the DB `visible_from` bundle-aware, "blocks
> 0028 apply") is **SUPERSEDED — do not act on it.** ADR-0053 §3 decides the document
> unit = the classified **chunk** (`working.chat_chunk` + `chat_chunk_message` +
> `chat_chunk_lane`), not the conversation bundle; the horizon is an agent-retrieval
> dict-filter (§7/§8), not a storage-time bundle clock. `working.visible_from(record)`
> per-record clock stands; 0028 is NOT blocked by a bundle-clock choice. Conforming the
> Weaviate projection to the chunk unit is Wave-3 work. Full ruling:
> `docs/CHANGE-ORDER.md` **CH-11 (D1)**.

## The scenario

It is after the Wave 1 cutover. The derivation engine shipped, the live spine
view was repointed at `visible_from`, and **the gaslighting delta is silently
wrong** — or the spine melts down, or the delta won't reproduce. Explain why.

---

## What W1.3 actually built

- **`sql/0027_walk_ledger.sql`** — `working.walk_ledger`: `walk_run` (version-pinned,
  `base_version` content-hash + `genesis_hash` + `final_corpus_hash`), `walk_step`
  (chain-hashed: `corpus_hash` + `prev_hash`), `walk_step_retrieval` (provenance),
  + two diagnostic views. Reconciled from the SUPERSEDED
  `sql/drafts/walk_ledger.postgres-draft.HOLD.sql` with four corrections: `analysis.*`
  → `working.*` (§B), FK → `working.normalized_record` (post schema split),
  contamination on `visible_from` not `knowledge_time`, + the §B chain-hash /
  version-pin columns the draft lacked entirely. Purely additive. NOT applied.
- **`server/evidence/derivation.py`** — the SOLE-writer refresher engine:
  `derive_walk` (ignorant incremental + hindsight on-prompt), `verify_reproducibility`
  (the §B pre-binding gate). `pg_advisory_xact_lock` (F13) sole-writer;
  `base_version` = content-hash of the case's records + APPROVED realizations;
  `corpus_hash = sha256(prev_hash || canonical slice)`; every step hash-attested
  to `ops.audit_ledger` (atomic via `connection=`).
- **`sql/0028_horizon_repoint.sql`** — ⚠ **HELD FOR OWNER.** The F1-resolution
  repoint: `vw_spine_horizon` filters on `visible_from(r.id) <= app.horizon` (not
  `knowledge_time`) WITH a materialized fast path (`working.record_visible_from` +
  `COALESCE` function fallback). Replaces a LIVE view — drafted + rollback-validated,
  NOT applied. Depends on the F4 ruling.
- **`scripts/_wave1_validate_w13_derivation.py`** (12/12 PASS) + **`scripts/_wave1_validate_w13_repoint.py`** (5/5 PASS) — live rollback validations.
- `store.py::horizon_axes` already emits `visible_from` (W1.1 task #8) — no edit
  needed this task; the refresher maintaining the Weaviate projection is inert
  while `data-vector` is DOWN (deliberate).

## The §B contract — what was PROVEN on live (rollback)

| Contract item | Evidence |
|---|---|
| **Contamination guard** (canon §1 — the point) | a realization pushing `visible_from` a year forward: ignorant step at an early horizon EXCLUDES the record (`retrieved=0`); a multi-step ignorant walk DISCOVERS it at the later step (`step1=0, step2=1`); hindsight INCLUDES it |
| **Sole-writer lock (F13)** | while the derivation txn holds the lock, a 2nd connection's `pg_try_advisory_xact_lock` returns False |
| **Version-pinned reproducibility** | `verify_reproducibility` returns `reproducible=True` for both 1-step and 2-step walks at the recorded base_version |
| **Chain integrity** | each step's `prev_hash` = prior step's `corpus_hash` |
| **Hash-attestation** | every step attested to `ops.audit_ledger` (`action_type='derivation'`, `payload_hash=corpus_hash`) |
| **Repoint faithful (0028)** | ignorant excludes / hindsight includes / fast-path consulted / late-horizon includes / view body filters on `visible_from(r.id)` not `knowledge_time <=` |

---

## Failure reasons (what could go wrong) — prioritized

### P0 — F4: bundled-doc degenerate `visible_from` — STILL OPEN, blocks the 0028 live-apply
- **What could fail:** the DB `visible_from(record_id)` uses **per-record** `occurred_at`
  as the degenerate fallback; `store.py::horizon_axes` uses **bundle** `occurred_at_max`.
  The 0028 repoint wires the live spine to the per-record function. If F4 rules
  `occurred_at_max`, the function must become bundle-aware BEFORE 0028 applies —
  or the spine (per-record) and Weaviate (bundle) disagree → the delta is
  non-reproducible across stores (a fact visible in Postgres at one time and in
  Weaviate at another).
- **Status:** **OPEN — needs owner ruling.** Carried from W1.1/W1.2. 0028 is
  drafted against the current per-record function and explicitly F4-dependent;
  it does NOT apply until F4 is decided.

### P1 — the refresher does not yet MAINTAIN the fast path (0028's mitigation is incomplete)
- **What could fail:** 0028 ships `working.record_visible_from` (the fast path) but
  the derivation engine does not yet write to it. So if 0028 applies now, the view
  falls back to per-row `working.visible_from(r.id)` (two correlated subqueries per
  row) on EVERY spine query — the slow scan the W1.1 F1 pre-mortem warned about.
  Correctness holds (COALESCE falls back), but the F1 performance mitigation is
  absent until the refresher maintains the table.
- **Mitigation:** a `refresh_visible_from(case_id)` function in the engine that
  re-materializes `record_visible_from` from `working.visible_from()` (incremental
  on changed records). Wire it BEFORE 0028 applies, or apply 0028 only when the
  corpus is small enough that the function scan is tolerable. NOT built this task.
- **Status:** **deferred — fast-path writer not yet wired.** Flagged so the owner
  does not read "0028 has a fast path" as "0028 is fast now."

### P2 — isolation: a realization approved MID-DERIVATION breaks reproducibility
- **What could fail:** `derive_walk` computes `base_version`, then writes steps.
  If a realization is APPROVED between those two statements (concurrent writer —
  the F13 lock serializes *derivations*, not *realization writes*), the visible
  slices the steps hash no longer match the recorded `base_version` →
  `verify_reproducibility` fails (the chain was built against moving data). The
  engine runs in the caller's txn isolation (default READ COMMITTED), so each
  statement sees a new snapshot.
- **Mitigation:** the derivation must run in a single snapshot — `SET
  TRANSACTION ISOLATION LEVEL REPEATABLE READ` (or SERIALIZABLE) on the
  derivation connection, so `base_version` and every step's slice read the same
  snapshot. NOT yet set in the engine. (The validation passes because it's
  single-threaded; the gap is concurrent realization approvals.)
- **Status:** **OPEN — isolation not pinned.** Low risk now (no concurrent
  realization writer wired), real risk once W1.5 binds the approve tool. Fix
  before agent binding.

### P3 — sole-writer is app-side ONLY until W1.4 grants land
- **What could fail:** the F13 advisory lock stops two *refresher* runs from
  interleaving, but it does NOT stop a *different* writer (an agent, a script, a
  direct INSERT) from writing `working.walk_*` — that enforcement is W1.4's
  default-deny grants. Until W1.4, the "sole writer" claim is app-convention, not
  DB-enforced. A bad writer could inject a step with a forged `corpus_hash`.
- **Mitigation:** W1.4 (next task) — only the refresher role gets INSERT on
  `walk_*`; everyone else SELECT-only. The `verify_reproducibility` gate also
  catches a forged chain (re-derive ≠ stored hash). But the grants are the
  hard backstop.
- **Status:** **deferred to W1.4 (next).** No risk now (tables empty + unapplied).

### P4 — 0028 replaces a LIVE view (the cutover itself)
- **What could fail:** 0028 is `CREATE OR REPLACE VIEW working.vw_spine_horizon`
  — a live-behavior flip, not additive. Applied before (a) F4 ruled, (b) the
  fast-path refresher wired, (c) backup taken, it could slow the spine to a
  correlated-subquery crawl AND diverge from Weaviate. This is the highest-blast-
  radius change in Wave 1.
- **Mitigation:** 0028 is drafted + rollback-validated but NOT applied; it is
  explicitly HELD FOR OWNER. The apply order is: F4 ruling → fast-path refresher
  wired → W1.4 grants → backup → apply 0028 → monitor the spine.
- **Status:** **HELD FOR OWNER.** No apply until the owner signs off.

### P5 — `walk_step_retrieval` semantics: "visible slice" vs "agent retrieval"
- **What could fail:** the engine writes the ENTIRE visible slice to
  `walk_step_retrieval` with `was_used=true`, `store='postgres'`, no rank/score.
  But the table's columns (`rank`, `score`, `was_used`) are named for an AGENT's
  actual retrievals (what the model retrieved from which store, at what rank).
  Conflating "what was visible" with "what the agent retrieved" makes
  `vw_walk_contamination` and the delta provenance ambiguous — is a row there
  because it was visible-but-ignored, or retrieved-and-used?
- **Mitigation:** split the concept. The engine should record the VISIBLE slice
  as provenance (e.g. `was_used=false`, or a separate `walk_step_visible` table),
  and the AGENT (W1.5) records its actual retrievals with rank/score/was_used.
  OR rename the intent in the docstring. NOT resolved this task.
- **Status:** **OPEN — design tension, needs owner call.** Does not block the
  §B contract (the contamination view works either way), but blocks the delta's
  provenance clarity.

### P6 — `base_version` recomputes the WHOLE case on every derive
- **What could fail:** `_compute_base_version` scans the case's records + approved
  events on every `derive_walk`. For a large case + many walks, that is O(case) per
  derivation. Fine for the current small disposable corpus; a scaling concern at
  thousands of records × frequent rederivations.
- **Mitigation:** cache `base_version` per (case, content) or compute it
  incrementally. Deferred — the corpus is disposable per the owner's "test data
  must never become canonical" rule, so premature optimization now.
- **Status:** **acceptable for now; flagged for scale.**

---

## Resolutions — applied 2026-08-14

| Finding | Status | Evidence |
|---|---|---|
| §B contamination guard (future fact excluded before top-k) | **PROVEN** | live: ignorant early step excludes the realized record; multi-step discovers it at the later step |
| §B sole-writer lock (F13) | **PROVEN (app-side)** | 2nd connection's `pg_try_advisory_xact_lock` returns False |
| §B version-pinned reproducibility | **PROVEN** | `verify_reproducibility` reproducible=True (1-step + 2-step) |
| §B chain-hash + hash-attestation | **PROVEN** | chain integrity + audit_ledger derivation rows |
| 0028 repoint faithfulness | **PROVEN (SQL)** | 5/5 live rollback checks; NOT applied |
| F4 bundled-doc degenerate visible_from | **OPEN — needs owner** | blocks 0028 apply; recommendation = occurred_at_max |
| P1 fast-path refresher not wired | **deferred** | 0028 falls back to per-row function until wired |
| P2 isolation not pinned (REPEATABLE READ) | **OPEN** | concurrent realization approval breaks reproducibility; fix before W1.5 |
| P3 sole-writer DB-enforcement | **deferred to W1.4** | grants are the hard backstop |
| P5 walk_step_retrieval semantics | **OPEN — needs owner** | visible-slice vs agent-retrieval conflation |

## Validation evidence (live, rollback — zero net write)

```
W1.3 derivation engine:  12/12 PASS  (contamination, multi-step discovery, sole-writer lock, reproducibility, attestation, chain)
W1.3 repoint (0028):      5/5 PASS  (exclude/include/hindsight/fast-path/structural)
Full unit suite:          688 passed, 24 skipped  (no regressions)
ruff check (new modules): clean
mypy (derivation.py):    clean
Post-check (live):        walk_run / walk_step / walk_step_retrieval / vw_walk_* /
                          record_visible_from all ABSENT → 0026+0027+0028 NOT applied;
                          rollback validations left no trace
```

## Prod-apply / push status

- **0026, 0027, 0028 NOT applied to prod.** 0027 (walk_ledger) is additive + safe
  but held with the wave for a single cutover. 0028 (repoint) is the live flip —
  explicitly HELD FOR OWNER (F4 + fast-path + W1.4 ordering).
- **Nothing pushed to main** (commit-only-when-asked rule). All W1.3 work is
  uncommitted on the working tree:
  - new: `sql/0027_walk_ledger.sql`, `sql/0028_horizon_repoint.sql`,
    `server/evidence/derivation.py`, `scripts/_wave1_validate_w13_derivation.py`,
    `scripts/_wave1_validate_w13_repoint.py`
  - edited: none (store.py already emitted visible_from in W1.1)

## What I would do differently next time

- **Pin the transaction isolation in the engine BEFORE the first validation.**
  The P2 isolation gap (concurrent realization approval) is invisible to a
  single-threaded validation — it passes cleanly and hides the race. A
  REPEATABLE READ derivation connection is a one-liner that should have been in
  the engine from the start; flagging it now means a future concurrent-writer
  test must re-prove it.
- **Decide walk_step_retrieval semantics before writing the engine.** I built the
  table (from the draft) then populated it with the visible slice, only to
  realize the columns (`rank`/`score`/`was_used`) describe agent retrievals, not
  visibility. The conflation is in the draft too; reconciling the draft's schema
  against the §B contract should have caught the column-intent mismatch before
  the engine wired it.
- **Wire the fast-path refresher IN THE SAME TASK as the repoint.** Shipping 0028
  with a fast-path TABLE but no fast-path WRITER means the F1 mitigation is
  half-built. The honest statement is "0028 is correct but slow until the
  refresher maintains record_visible_from" — I'd rather have made that
  impossible by building the maintainer alongside.

## Review schedule

- **Owner review (this + W1.1 + W1.2 pre-mortems together):**
  - **Decide F4** (bundle `occurred_at_max` vs per-record) — unblocks 0028 + the
    cross-store clock contract.
  - **Decide walk_step_retrieval semantics** (P5) — visible-slice provenance vs
    agent retrieval.
  - Greenlight the apply ORDER: 0027 (additive) → fast-path refresher → W1.4
    grants → 0028 (live flip) → monitor.
- **Before agent binding (W1.5):** fix P2 (REPEATABLE READ derivation), confirm
  W1.4 grants enforce sole-writer, run the F3 live-Weaviate planted-fact dict-filter
  test, the F6 `@approval` run-level test, and a CONCURRENT-realization-approval
  reproducibility test (the P2 race, for real this time).
