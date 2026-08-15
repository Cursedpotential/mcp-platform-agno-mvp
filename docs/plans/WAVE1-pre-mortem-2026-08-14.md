# Pre-Mortem: Wave 1 (Temporal Truth + Horizon Enforcement)

> **R0 AUDIT BANNER 2026-08-15:** later independent replay found the Wave-1
> build is **not cutover-ready**. Migrations 0026–0029 remain unapplied; see
> `../HANDOFF-2026-08-15-R0-wave1-audit.md` for proposal-contamination,
> replay, content-path, and quarantine findings. Earlier rollback counts below
> remain historical evidence, not a release verdict. _Byline: Codex · GPT-5._


> _Byline: Claude Code · glm-5.2:cloud · 2026-08-14_
> Skill: `thinking-skills:thinking-pre-mortem` (Gary Klein prospective hindsight).
> Scope: Wave 1 of the end-to-end plan (executes ADR-0045 §A + §B) — the horizon
> clock, realization events, derivation engine, DB grants, agent lane bindings.
> Trigger: W1.1 validation failed live (PG rejects param-rename via `CREATE OR
> REPLACE FUNCTION`), owner paused W1.1, asked for a pre-mortem before more building.

> ⚠ **CORRECTION 2026-08-14 (CH-11 / D1):** the D1 "bundled-document `visible_from`"
> recommendation recorded below in F4/P1 (`occurred_at_max` + make the DB function
> bundle-aware) is **SUPERSEDED — do not act on it.** The bundle-clock question is
> dissolved by **ADR-0053 §3**: the document unit is the classified **chunk**
> (`working.chat_chunk` + `chat_chunk_message` + `chat_chunk_lane`), NOT the
> conversation bundle; a chunk is embedded once and projected per-lane; the horizon is
> an agent-retrieval **dict-filter** (ADR-0053 §7/§8), not a storage-time bundle clock.
> `working.visible_from(record)` per-record clock is correct as-is. The current
> `store.py` `group_by_conversation` + `occurred_at_max` is the pre-0053 `context_record`
> model, superseded — conforming it to the chunk unit is Wave-3 projection work. Full
> ruling: `docs/CHANGE-ORDER.md` **CH-11 (D1)**.

## The scenario

It is **2027-02-14**, six months on. Wave 1 "shipped." The ignorant/hindsight delta
was supposed to be the deliverable — the whole point of the platform (canon §1).
Instead the delta is **worthless**: the ignorant agent was quietly as smart as the
hindsight agent, or prod melted, or a reader bound early and admitted the whole
corpus. We are in the postmortem. Explain what went wrong.

Each finding below is tagged:
- **KNOWN** — a verified fact about the current state (this session / Wave 0
  re-verification / AGENTS.md).
- **RISK** — a prospective failure mode (the pre-mortem's actual job).
- **MINE** — a failure I (this agent) personally contributed in the W1.1 work.

---

## Failure reasons identified

### Technical — P0 (delta-worthless or prod-down)

**F1 — Per-row `visible_from()` in the LIVE view is the slow path, and W1.3's fast
path doesn't exist yet. [KNOWN + MINE]**
W1.1 repoints `working.vw_spine_horizon` to call `working.visible_from(r.id)` per
row. That function runs **two correlated subqueries per row** (realization_event
join + normalized_record fallback). Over the full spine that is O(rows × events)
— a sequential scan with a per-row function eval on every horizon-filtered query.
The migration's own comment admits "the hot read path is the §B DERIVED pass
corpus (W1.3)" — i.e. the fast path is **deferred to W1.3**, but the **slow path
goes live in W1.1**. Any reader bound to `vw_spine_horizon` between W1.1 and W1.3
hits the slow path. On a large corpus, prod queries become unusably slow.

**F2 — The build-order gate is procedural, not enforced. The project's #1 failure
mode is silent. [KNOWN]**
ADR-0045 §B's non-negotiable order (clock → writers → derivation → grants →
bindings) is a **convention**. Nothing in the migration, the grants, or the schema
prevents a future chat/PR from wiring an agent lane to the horizon view before W1.3
lands. If that happens, either the whole corpus is admitted (no derivation filter)
or the slow path melts prod — and **nothing errors**. AGENTS.md is blunt:
contamination is silent; one leaked future fact makes the ignorant agent merely
smarter and the delta quietly worthless. The gate that prevents the project's
defined worst-case outcome is a doc nobody is forced to read.

**F3 — The Wave 1 gate can pass while Weaviate leaks future facts. [KNOWN]**
The Wave 1 gate is "plant a 2026 fact in a 2023 thread; ignorant walk excludes it."
But there is **no live-Weaviate integration test** (GAP-01 reframed: only a
`_FakeKnowledge` post-filter + a Python `visible()` mirror unit test). agno's
Weaviate adapter **silently drops `FilterExpr` lists** and only applies dict
filters (verified in agno 2.8.6 and 2.8.7, `weaviate.py:414-416`). If the horizon
filter compiles to a FilterExpr on Weaviate, it applies ZERO filters, the future
fact scores exactly as similar as a contemporaneous one, and it leaks into the
ignorant agent's top-k — with no error. Wave 3 owns the shared filter compiler,
but **Wave 1's gate claims horizon enforcement without ever touching a live vector
store**, so a green Wave 1 gate does not prove the delta is clean. Embeddings have
no sense of time; this is the exact failure the project exists to prevent.

### Technical — P1 (correctness, silent)

**F4 — The in-memory and DB `visible_from` degenerates DIVERGE across stores.
[MINE]**
This session I made `store.horizon_axes` emit `visible_from = MAX(occurred_at)`
(occurred_at_max — the conservative bundle clock: a document is knowable when its
LAST message is). But `working.visible_from(record_id)` in the DB falls back to
that **record's own** `occurred_at`. For a multi-message document, the Weaviate
projection (occurred_at_max) and the PG per-row clock (per-record occurred_at) can
disagree — the **same fact is visible at different horizons across stores**. Since
Weaviate is the main leak vector (F3), an inconsistent clock across stores is a
contamination path, not a cosmetic difference. I introduced this and only flagged
the occurred_at_min→occurred_at_max behavior change for CHANGE-ORDER; the
cross-store divergence I did not flag at all.

**F5 — `realized_at >= occurred_at` is unenforced; the clock can go backwards.
[KNOWN + MINE]**
A cross-table CHECK is not expressible, so the migration enforces nothing. The
realization_event table has **no constraint** that `realized_at` >= the linked
records' `occurred_at`. `visible_from = COALESCE(MIN(realized_at), occurred_at)`;
if a W1.2 writer ever lets through a `realized_at < occurred_at`, the COALESCE
returns that early realized_at and the record becomes visible **before it
occurred**. My migration comment claims "a wrong-ordered event can only make a
record visible LATER, never before it occurred" — **that claim is false** unless
realized_at >= occurred_at, which is exactly the unenforced guard. The comment is
doc-drift in a file I just wrote.

**F6 — native `@approval` is assumed to gate `realization_event` but is unverified
on a custom table. [RISK — needs verification]**
ADR-0045 §A.4 + ADR-0002 lean on native `@approval` for HITL. The migration carries
a poor-man's `approval_state`/`approved_at` CHECK, but whether the `@approval`
hook actually fires on a brand-new custom table (`working.realization_event`) is
**unverified**. If it does not, any writer can flip `approval_state` proposed→
approved and the fail-closed gate is bypassed — proposed events become
visible_from-truth with no human in the loop. This must be proven before W1.2
relies on it.

### Operational — P1 (prod-safety)

**F7 — 0026 will be applied to live prod PG with no fresh backup. [KNOWN]**
GAP-06: no recurring backups (verified Wave 0). The validation is a rollback
**transaction**, not a backup. When 0026 is applied FOR REAL, it repoints the
spine view every horizon reader depends on. If that repoint breaks prod queries
(slow path, F1), there is **no rollback path** — no fresh backup to restore. A
rollback txn proves the DDL applies; it does not protect the live DB after a real
commit.

**F8 — The only validation path is live prod, and the desktop has no Docker.
[KNOWN + MINE]**
Migrations are not from-zero (Wave 0 finding), so 0026 is validated against live
`100.91.190.107` in a rollback txn. The **only** guard against an accidental real
write is `finally: conn.rollback()` and `autocommit=False` in the validation
script. A future validation script that forgets either, or a script bug that
commits, **writes to prod**. The validation method itself is a prod-safety risk,
repeated every migration round.

### People / process — P2 (drift, traps)

**F9 — The owner believes as-lived/hindsight is "already fixed" (2026-08-12).
[KNOWN]**
It is decided (ADR-0045 signed D-042) but unbuilt (N1/N2). If the owner — or a
future chat that inherits the belief — re-assumes it's done, W1.2–W1.5 get
skipped and agents bind to an unbuilt derivation. The belief itself is a failure
mode; surfacing the gap was Wave 1's first job and it is easy to lose.

**F10 — The refuted report still lives locally; its "disclosure_tier hardcode = bug"
claim invites a wrong fix. [KNOWN]**
The review's most-wrong claim was refuted (ADR-0045 Decision C: the hardcode is
CORRECT). But the report is local/untracked and still on disk. A future agent
reading it and "fixing" the hardcode breaks disclosure derivation and contradicts
the signed ADR.

**F11 — `knowledge_time` is "audit only" but written everywhere; the supersession
is a comment. [KNOWN + MINE]**
The predicate no longer reads knowledge_time, but `finalize()` still stamps it, the
column stands, and old code/tests reference it. The supersession lives in a
`COMMENT` and a docstring — easy to miss. Someone re-wires a filter to
knowledge_time, assumes it's the clock, contamination returns.

**F12 — The walk_ledger draft uses the superseded `knowledge_time` in its
contamination view. [KNOWN]**
`sql/drafts/walk_ledger.postgres-draft.HOLD.sql` is deferred to W1.3 with a
"reconcile-not-lift" note, but its contamination view still filters on
`knowledge_time`. A W1.3 agent that lifts without reconciling ships a walk ledger
whose own contamination check is wrong.

**F13 — Single-writer refresher (W1.3) is not enforced. [RISK]**
ADR-0045 §B makes the refresher the SOLE writer of pass corpora, hash-attested to
`ops.audit_ledger`. No advisory lock or leader-election is specified. A
redeploy overlap → two refreshers → double-writers; a crash mid-derivation → a
partial checkpoint that is hash-attested and looks valid.

**F14 — Append-only is a convention, not enforced. [KNOWN + MINE]**
"Never UPDATE an approved realization_event — supersede it" is a comment. The
schema allows DELETE of an approved event (CASCADE removes its links) and UPDATE
of approval_state. No trigger prevents it.

**F15 — `uuidv7()` default assumes PG ≥18. [KNOWN, low]**
Wave 0 inventory confirmed 18.1, so this is fine today — but it is a checkpoint,
not a guarantee, if the live DB version ever drifts.

---

## Priority risks and mitigations

### P0 — F1: slow live path before W1.3 fast path
- **Description:** repointing `vw_spine_horizon` at per-row `visible_from()` puts
  an O(rows × events) scan on every horizon query before the W1.3 materialized pass
  corpus exists.
- **Mitigation:** (a) Do NOT repoint the live `vw_spine_horizon` in W1.1. Ship the
  clock function + table only; keep the view on the old predicate until W1.3's
  materialized corpus is the read path. OR (b) add a `visible_from` expression
  index / materialized helper so the live view isn't a per-row function scan.
  Decide before 0026 is applied for real.
- **Owner checkpoint:** before the real-apply of 0026.

### P0 — F2: build-order gate is unenforced
- **Description:** nothing prevents an early agent-lane binding; contamination is
  silent.
- **Mitigation:** make the gate *structural*. Land W1.4 grants such that the
  horizon view/`visible_from` is **not selectable by agent roles until W1.3
  materialization exists** — revoke/default-deny, grant only after the derivation
  engine is live. Plus a CI lint forbidding agent code from importing
  `vw_spine_horizon`/`visible_from` until a feature flag (`HORIZON_DERIVATION_ENABLED`,
  default-off per the plan) flips.
- **Owner checkpoint:** W1.4 grant design.

### P0 — F3: Wave 1 gate passes while Weaviate leaks
- **Description:** no live-vector-store test; FilterExpr silent-drop = future fact
  leaks into top-k, no error.
- **Mitigation:** add ONE live-Weaviate planted-fact test to the Wave 1 gate (not
  Wave 3): plant a 2026 fact in a 2023 thread, embed, query the ignorant horizon
  with a **dict filter**, prove it is excluded **before top-k**. If the filter must
  be a FilterExpr to express it, the test must FAIL LOUDLY (the Wave 3 compiler's
  contract, pulled forward as a guard). Do not declare Wave 1 green without a real
  vector round-trip.
- **Owner checkpoint:** Wave 1 gate definition.

### P1 — F4: cross-store visible_from divergence [MINE]
- **Description:** Weaviate projection uses occurred_at_max; PG per-record uses
  occurred_at → same fact visible at different horizons across stores.
- **Mitigation:** make the degenerate clock ONE definition. Either the DB
  `visible_from` for a bundled document also uses occurred_at_max (requires the
  function to know the bundle — a doc-level not row-level clock), or the Weaviate
  projection stores per-record occurred_at and filters per-record. Pick one,
  document it in ADR-0045 §A as a clarification, and make the Weaviate projection
  and the DB function agree by construction.
- **Owner checkpoint:** before W1.3 (derivation engine is where both projections
  are cut from one base version).

### P1 — F5: realized_at < occurred_at can move the clock backwards [MINE]
- **Description:** no constraint; the migration comment over-claims.
- **Mitigation:** (a) fix the misleading comment in 0026 now; (b) W1.2 writers
  MUST reject/clamp realized_at < min(linked occurred_at) app-side, with a test;
  (c) consider a trigger that raises if an approved event's realized_at precedes
  any linked record's occurred_at (enforce at the DB, not just the app).
- **Owner checkpoint:** W1.2.

### P1 — F6: @approval unverified on realization_event
- **Description:** if the native hook doesn't fire on the custom table, the
  fail-closed gate is bypassable.
- **Mitigation:** verify @approval against `working.realization_event` on the live
  DB (rollback txn) BEFORE W1.2 — propose an event, attempt to approve without the
  hook, confirm the hook gates it (or confirm the CHECK + a trigger is the real
  gate and document that @approval is advisory here).
- **Owner checkpoint:** before W1.2.

### P1 — F7/F8: live-apply with no backup; live-only validation
- **Description:** no rollback path after the real apply; the validation method
  can write prod on a script bug.
- **Mitigation:** (a) take a fresh PG backup (pg_dump of at least the `working`
  schema) immediately before the real apply of 0026; (b) add a guard to every
  validation script: assert `conn.autocommit is False` and wrap the whole body in
  `try/finally: conn.rollback()` with a second `rollback()` in a `finally`; (c)
  never call `COMMIT` from a validation script — lint for it.
- **Owner checkpoint:** before real-apply of 0026.

### P2 — F9–F15: drift, traps, conventions
- **Mitigations:** (F9) keep "decided-not-built" as a standing banner in the
  subplan until W1.5 lands; (F10) add a dated strike-through to the report's
  hardcode claim and a pointer to ADR-0045 Decision C; (F11) grep for
  `knowledge_time` uses in filter code each wave; (F12) reconcile the walk_ledger
  draft's contamination view to `visible_from` as the first W1.3 task; (F13) add a
  `pg_advisory_lock` to the refresher; (F14) add a trigger preventing
  UPDATE/DELETE of approved realization_events; (F15) keep the version checkpoint
  in the Wave 1 gate.
- **Owner checkpoint:** folded into the relevant waves.

---

## What I personally contributed to the failure (the skill asks)

- **MINE — F1/F4/F5/F11/F14:** I wrote `sql/0026`, the `horizon_axes`
  occurred_at_max change, and the `finalize` docstring this session. The slow-path
  repoint (F1), the cross-store divergence (F4), the unenforced realized_at ordering
  + the over-claiming comment (F5), the knowledge_time supersession-as-comment
  (F11), and the append-only-as-convention (F14) are all in code I wrote. The
  pre-mortem is partly an audit of my own W1.1 draft.
- **MINE — F8:** I chose the live-only rollback-txn validation path (correctly,
  given not-from-zero) but did not add the backup or the autocommit-hardening
  guards before proposing to run it against prod.

## Plan updates (proposed, NOT executed — pending owner sign-off)

These are the changes to the Wave 1 sub-plan the pre-mortem implies. None are
applied; they are for your decision:

- [ ] **W1.1:** decide the live-view repoint (defer the `vw_spine_horizon` repoint
  to W1.3, OR keep it with a fast access path). F1.
- [ ] **W1.1:** fix the over-claiming `realized_at` comment in `sql/0026`; add the
  app-side ordering guard to W1.2's scope. F5.
- [ ] **W1.1:** add the autocommit + double-rollback guard to
  `scripts/_wave1_validate_0026.py` and any future validation script. F8.
- [ ] **W1.1 gate:** add ONE live-Weaviate planted-fact dict-filter test; do not
  declare green without a real vector round-trip. F3.
- [ ] **W1.2:** verify `@approval` on `realization_event` (rollback txn) before
  building writers. F6.
- [ ] **W1.4:** grant/default-deny so agent roles cannot select the horizon view
  until W1.3 materialization exists; CI lint + `HORIZON_DERIVATION_ENABLED`
  default-off. F2.
- [ ] **W1.3:** reconcile the walk_ledger draft's contamination view to
  `visible_from` as the first task; add a `pg_advisory_lock` to the refresher.
  F12/F13.
- [ ] **Pre-apply:** fresh `working`-schema pg_dump before the real apply of 0026.
  F7.
- [ ] **Cross-store clock (F4):** pick ONE degenerate-clock definition and make
  the Weaviate projection and the DB function agree by construction; record as an
  ADR-0045 §A clarification. Needs an owner ruling — see open question below.

## Open question for the owner (one)

**F4 needs a ruling:** should the degenerate `visible_from` for a bundled
document be the document's `occurred_at_max` (last message knowable — what the
in-memory projection now emits) or the per-record `occurred_at` (what the DB
function currently returns)? They diverge, and Weaviate (the main leak vector)
will follow whichever the projection stores. This changes what "the same fact is
visible at horizon H" means across stores and is a canon §1 / ADR-0045 §A
clarification, not a build detail. I recommend `occurred_at_max` for bundled
documents (the conservative, no-future-leak form) and making the DB function
doc/bundle-aware — but it is yours to call.

## Review schedule

- **Before real-apply of 0026:** resolve F1, F5, F7, F8.
- **W1.2 start:** resolve F6.
- **W1.3 start:** resolve F4 (owner ruling), F12, F13.
- **W1.4:** resolve F2.
- **Wave 1 gate:** F3 live-Weaviate test must pass.

---

## Resolutions — applied 2026-08-14 (owner: "continue the work, pre-mortem after each task")

The pre-mortem's "Plan updates (NOT executed)" checklist was acted on for the
**reversible** items; nothing has been applied to prod or pushed. Every change
below is uncommitted in the working tree, validated only in a rollback txn.

**F1 (P0) — RESOLVED by deferral.** `sql/0026` no longer repoints
`working.horizon_visible` or `working.vw_spine_horizon`. W1.1 now ships ONLY
the additive clock objects: `realization_event` + `realization_event_record`
+ `visible_from()` + the supersession COMMENT. The live predicate and spine
view stay on the (inert) `knowledge_time` predicate — **zero behavior change,
zero slow per-row path**. The predicate/view repoint moves to W1.3 together
with the materialized pass corpus (the sanctioned fast read path). Side
effect: the migration is now **purely additive** (no DROP/REPLACE of any
existing object), which also eliminated the PG `CREATE OR REPLACE FUNCTION`
param-rename failure that blocked the earlier validation run.

**F5 (P1) — RESOLVED.** The over-claiming `realized_at` comment is fixed
in-place: the migration now states explicitly that `realized_at >= occurred_at`
is **NOT** DB-enforced (cross-table CHECK not expressible), that the clock CAN
move backwards if a writer lets through an early `realized_at`, and that the
guard is **app-side** (W1.2). The `realized_at` COLUMN + TABLE COMMENTs carry
the same WARNING. The W1.2 app-side guard (reject/clamp `realized_at <
min(linked occurred_at)` + test) is added to W1.2 scope (task #11).

**F8 (P1) — MECHANISM CONFIRMED + FIXED.** Reading the validation script
found the *concrete* F8 mechanism the pre-mortem only gestured at:
`sql/0026` carried its own `BEGIN;`/`COMMIT;`, and with `autocommit=False`
that inner `COMMIT;` would have **committed the DDL to the live DB** — the
`finally: conn.rollback()` would have protected only the test rows, not the
DDL. The earlier run looked "zero-net-write" only because the migration
*errored* before reaching its `COMMIT;`; a *successful* run would have
applied 0026 to prod. Fixed in `scripts/_wave1_validate_0026.py`:
(1) `strip_txn_control()` removes the migration's leading `BEGIN;`/trailing
`COMMIT;` so the DDL runs inside our rollback transaction; (2) `assert
conn.autocommit is False` before any execute; (3) a second defensive
`conn.rollback()` after the cursor block; (4) rollback-in-`except` before
re-raise; (5) a source-grep guard at the top of `main()` that refuses to run
if the script contains a `conn.commit(` call. **Verified live:** after a green
run, a direct query confirmed `realization_event` / `realization_event_record`
/ `visible_from()` do NOT persist on the live DB — the rollback genuinely
held (not just the printed line).

**Validation — GREEN (rollback txn, zero net write verified by post-check).**
`uv run python scripts/_wave1_validate_0026.py` → 12/12 PASS: objects
created; live predicate + view UNCHANGED (F1 deferral proven — no slow path
introduced); degenerate `visible_from == occurred_at`; PROPOSED event is
fail-closed (no clock move); APPROVED event moves the clock to `realized_at`;
the untouched `horizon_visible` still denies/allows correctly (regression).
Post-run direct query confirmed nothing persisted.

### Still open — NEEDS OWNER (do not real-apply 0026 until reviewed)

- **F4 (P1) — OWNER RULING REQUIRED (the one open question).** The
  degenerate `visible_from` for a **bundled document** diverges across stores:
  the in-memory `store.horizon_axes` projection (Weaviate) emits
  `occurred_at_max` (last message knowable — the conservative no-future-leak
  form); the DB `working.visible_from(record_id)` is **per-record**
  `occurred_at`. They serve different granularities (doc-level vs
  record-level), but Weaviate is the main leak vector (F3), so an
  inconsistent cross-store clock is a contamination path, not cosmetic. This
  is a **canon §1 / ADR-0045 §A clarification**, not a build detail. My
  recommendation: `occurred_at_max` for bundled documents + make the DB
  function doc/bundle-aware so the projection and the DB function agree by
  construction — but it is yours to call. **Left unchanged; flagged here.**

- **F7 (P1) — pre-apply prerequisite.** No fresh `working`-schema `pg_dump`
  exists. Before the REAL apply of 0026, take one. Not done (no real-apply
  happening this session).

- **F3 (P0) — Wave 1 gate prerequisite.** No live-Weaviate planted-fact
  dict-filter test exists. Added to the W1.5 / Wave 1 final gate (task #14).
  Not done this wave.

### Deferred to their wave (unchanged, tracked in tasks #11–#14)

- F6 (verify native `@approval` fires on `working.realization_event`) →
  first W1.2 task (rollback txn).
- F12 (reconcile `walk_ledger` draft contamination view to `visible_from`) →
  first W1.3 task.
- F13 (`pg_advisory_lock` on the refresher) → W1.3.
- F2 (default-deny agent-role grants + CI lint + `HORIZON_DERIVATION_ENABLED`
  default-off) → W1.4.

### Prod-apply / push status

**None.** `sql/0026` is written + rollback-validated-green but NOT applied to
prod and NOT pushed. W1.2–W1.5 are blocked behind your review of this
pre-mortem's open items (F4 ruling especially), per "will review them all
when I get out of work." All W1.1 changes remain uncommitted in the working
tree (commit-only-when-asked).
