# WAVE 1.2 Pre-Mortem — Realization Writers (ADR-0045 §A.4)

> **R0 AUDIT BANNER 2026-08-15:** rollback validation below does not establish
> Wave-1 cutover readiness. Read `../HANDOFF-2026-08-15-R0-wave1-audit.md`;
> migrations remain unapplied and product execution is held. _Byline: Codex · GPT-5._


> _Byline: Claude Code · glm-5.2:cloud · 2026-08-14_
> Status: **BUILD COMPLETE — validated in rollback on live; NOT applied to prod; NOT pushed.**
> Owner review surface: this is one of the per-task pre-mortems the owner asked for and will review together.

> ⚠ **CORRECTION 2026-08-14 (CH-11 / D1):** the F4 recommendation carried here
> (`occurred_at_max` for the bundle + make the DB `visible_from` bundle-aware) is
> **SUPERSEDED — do not act on it.** ADR-0053 §3 decides the document unit = the
> classified **chunk** (`working.chat_chunk` + provenance + `chat_chunk_lane`), not the
> conversation bundle; the horizon is an agent-retrieval dict-filter (§7/§8), not a
> storage-time bundle clock. `working.visible_from(record)` per-record clock stands.
> Full ruling: `docs/CHANGE-ORDER.md` **CH-11 (D1)**.

## The scenario

It is after the Wave 1 cutover. The realization writers shipped, the horizon
predicate was repointed at `visible_from`, and **the gaslighting delta is now
silently wrong.** Explain why.

---

## What W1.2 actually built

- `server/evidence/realization.py` — thin SQL writer (mirrors
  `store.py::store_records`): `propose_realization` (inert `'proposed'` write
  + the **F5 app-side guard** rejecting `realized_at < min(linked occurred_at)`),
  `approve_realizations` (batch `'proposed'→'approved'`, stamps
  `approved_at/by`), `supersede_realization` (the sanctioned
  `approval_state→'superseded'` UPDATE). Accepts `connection=` for atomic
  audit + rollback-testability (mirrors `audit.record(connection=)`).
- `server/agents/tools/realization_tools.py` — agno `@tool` wrappers:
  `realization_propose` (plain `@tool` — inert, no HITL),
  `realization_approve` + `realization_supersede` (`@approval` +
  `@tool(requires_confirmation=True)` — the HITL gate). Exports
  `REALIZATION_TOOLS`; **wiring into `providers.source_tools` is deferred to
  W1.5** (which agents may propose vs. approve is a lane binding).
- `tests/test_realization_writers.py` — 11 DB-free unit tests (stub conn):
  F5 guard, lifecycle SQL, idempotency, caller-connection honor.
- `scripts/_wave1_validate_w12_realization.py` — live rollback validation
  (SQLAlchemy engine + connection, same path as `store.py`): applies 0026 +
  runs propose/approve/supersede on a REAL record, then rolls back. Zero net
  write.
- `sql/0026_realization_event.sql` — **edited this task**: the
  `realization_event_approved_iff_timestamp` CHECK constraint was revised
  (see F15 below).

### The two-gate design (reconciles F6)

Two INDEPENDENT gates, neither trusting the other:

1. **DB-level (fail-closed, proven now):** `working.visible_from(record_id)`
   reads ONLY `approval_state='approved'` events. A `'proposed'` row changes
   NO record's clock regardless of how it was written — even a direct INSERT
   bypassing the tool is inert until approved.
2. **agno `@approval` (run-level, deferred to Wave gate):** the
   `realization_approve` / `realization_supersede` tool BODIES do not execute
   until a human resolves a pending approval row (`agno_approvals`, resolved
   via `POST /approvals/{id}/resolve`). This is the human-in-the-loop gate
   ADR-0045 §A.4 mandates.

The writer module is HITL-agnostic (thin inserter, like `store.py`); the human
gate lives on the `@approval`-decorated tool. The DB gate is the backstop that
catches any writer that bypasses the tool.

---

## Failure reasons (what could go wrong) — prioritized

### P0 — F6: the agno `@approval` gate is wired but UNVERIFIED at run level
- **What could fail:** the decorators are stacked (`@approval` + `requires_confirmation=True`)
  on the wrappers — asserted code-level (4/4 PASS). But a run-level
  verification (an agent calls `realization_approve`, the run PAUSES, a human
  resolves, the body runs) has NOT been done. If `@approval` is silently inert
  in this agno version (cf. the `EntityMemoryConfig(mode=PROPOSE)` precedent —
  accepted for months, did nothing), approve would run with NO human gate, and
  the ONLY protection is the DB-level backstop (which still holds the
  fail-closed clock, but the *human* approval is gone).
- **Mitigation:** Wave-gate test — run an agent that calls
  `realization_approve`; confirm the run pauses and a row appears in
  `agno_approvals`; resolve it; confirm the body ran. Do NOT bind the tool to
  agents (W1.5) until this is green.
- **Status:** **deferred to Wave gate** (requires a live agno run).

### P1 — F15: CHECK constraint blocked supersede (FOUND + FIXED this task)
- **What failed:** the first form of `realization_event_approved_iff_timestamp`
  was `CHECK ((approval_state='approved') = (approved_at IS NOT NULL))`.
  Supersede sets `approval_state='superseded'` but `approved_at` (stamped at
  approve) stays non-null → `(false)=(true)` → **CHECK violation**. The
  validation caught it live (rollback txn, so zero prod impact).
- **Fix applied (0026, not yet applied to prod):** relaxed to
  `CHECK ((approved_at IS NULL) = (approval_state='proposed') AND
  (approved_by IS NULL) = (approval_state='proposed'))` — i.e.
  `approved_at/by` are NULL exactly while proposed, set ONCE at approval, and
  **retained through supersede** (append-only audit: "when/by whom was this
  approved?" survives supersede). The writer needed no change (it already only
  flips `approval_state` on supersede).
- **Status:** **RESOLVED** — 0026 re-validated 12/12 (W1.1) + 17/17 (W1.2) on live.

### P2 — F5: the clock can move backwards if a bad realized_at leaks through
- **What could fail:** `realized_at >= min(linked occurred_at)` is NOT
  DB-enforceable (cross-table CHECK). A writer that skips the app-side guard
  lets `visible_from` return an early `realized_at` → a record visible BEFORE
  it occurred → the ignorant agent sees a future-tense fact early → the delta
  is silently corrupted.
- **Mitigation (in place):** `propose_realization` rejects (not clamps) any
  `realized_at < min(linked occurred_at)`. **PROVEN on live** (F5 raise + no
  row inserted). Guard is the ONLY path to insert (the `@tool` wrapper calls
  through it; a direct call bypasses `kind`/`proposer` validation but the
  writer's `_do` always runs the guard for non-empty `record_ids`).
- **Gap:** no defensive DB trigger (sql/0026 WARNING notes one is "considered
  for a later migration"). The guard is app-side only. If a future writer
  goes direct-to-INSERT bypassing this module, the guard is gone. **Defer the
  trigger to a later migration; for now the module is the sole sanctioned
  writer** (enforced by W1.4 grants — only the realization-writer role gets
  INSERT on `realization_event`).
- **Status:** **RESOLVED (app-side); trigger deferred.**

### P3 — F4: degenerate `visible_from` for a BUNDLED document (OWNER RULING NEEDED)
- **What could fail:** a realization that reveals a multi-record bundle (one
  export surfaces hundreds of records) — do ALL records get the SAME
  `visible_from` (= the bundle's `occurred_at_max`), or per-record
  `occurred_at` as the fallback? The DB function today does per-record
  `occurred_at` per record. Weaviate (`store.horizon_axes`) uses
  `occurred_at_max` per bundle. **They can disagree** → the same fact is
  visible in Postgres at one time and in Weaviate at another → the delta
  differs across stores → the delta itself is non-reproducible.
- **This is NOT resolved by W1.2** — it is a canon §1 / ADR-0045 §A
  clarification. My recommendation (recorded, not applied): **`occurred_at_max`
  for the bundle**, and make the DB `visible_from` bundle-aware. But this
  changes the W1.1 function and the cross-store contract — needs the owner.
- **Status:** **OPEN — needs owner ruling.** Flagged in the W1.1 pre-mortem
  too; carried forward. Held until owner review.

### P4 — wiring: tools are unwired (intentional, W1.5)
- **What could fail if wired wrong:** if `REALIZATION_TOOLS` is appended to
  `source_tools` naively, EVERY agent gets `realization_approve` — i.e. any
  agent could self-approve a realization (the `@approval` gate would still
  pause, but the *model* proposing AND approving is the wrong separation).
- **Mitigation:** NOT wired in W1.2. W1.5 binds propose → analysis/ingest
  lanes, approve → owner (via the `@approval` queue). Until then the tools are
  unreachable from agents (only importable + CLI-callable for validation).
- **Status:** **deferred to W1.5.**

### P5 — audit atomicity: propose is NOT atomic with audit.record
- **What could fail:** `propose_realization` writes the event + links but does
  not write an audit row in the same transaction. If a caller wants atomic
  audit, it must pass `connection=` and call `audit.record(connection=conn)`
  in the same txn. A caller that does NOT will have a realization with no
  audit trail (or an audit trail that can lag/diverge).
- **Mitigation (in place):** the `connection=` path exists and is the
  documented atomic pattern. The default path (`connection=None`) opens its
  own txn — fine for the propose-only case (inert). Approve/supersede (the
  truth-affecting ops) SHOULD be wrapped with audit by their callers; the
  `@approval` tool wrapper does not currently do this.
- **Status:** **acceptable for W1.2; audit-on-approve to be wired in W1.5**
  (the approve tool body can call `audit.record(connection=...)` alongside
  `approve_realizations`).

---

## Resolutions — applied 2026-08-14

| Finding | Status | Evidence |
|---|---|---|
| F5 app-side guard (realized_at >= occurred_at) | **RESOLVED (app-side)** | live: propose with realized_at<occurred_at raises ValueError, no row inserted |
| F6 DB-level gate (visible_from reads only 'approved') | **PROVEN** | live: proposed → visible_from unchanged; approve → moves; supersede → reverts (17/17) |
| F6 agno `@approval` run-level gate | **code-level PROVEN; run-level DEFERRED to Wave gate** | decorators stacked (4/4 code asserts); live agent run pending |
| F15 CHECK constraint blocked supersede | **FOUND + FIXED** | 0026 CHECK revised to NULL-iff-proposed (retains approved_at through supersede); re-validated 12/12 + 17/17 |
| F4 bundled-doc degenerate visible_from | **OPEN — needs owner** | carried from W1.1; recommendation = occurred_at_max + bundle-aware function |
| P4 wiring / P5 audit-on-approve | **deferred to W1.5** | by design |

## Validation evidence (live, rollback — zero net write)

```
W1.1 (0026 clock):        12/12 PASS  (re-run after F15 fix — no regression)
W1.2 (realization writers):17/17 PASS  (4 F6 code-level + 13 DB-level)
Full unit suite:           688 passed, 24 skipped
ruff check server tests:   clean
mypy (new modules):        clean
Post-check (live):         realization_event / _record / visible_from() all ABSENT
                           → 0026 NOT applied; rollback validations left no trace
```

## Prod-apply / push status

- **0026 NOT applied to prod.** Held for owner review of this pre-mortem's
  mitigations (F6 run-level, F4 ruling) per the owner's directive.
- **Nothing pushed to main** (commit-only-when-asked rule). All W1.2 work is
  uncommitted on the working tree:
  - new: `server/evidence/realization.py`,
    `server/agents/tools/realization_tools.py`,
    `tests/test_realization_writers.py`,
    `scripts/_wave1_validate_w12_realization.py`
  - edited: `sql/0026_realization_event.sql` (the F15 CHECK revision)

## What I would do differently next time

- **Write the lifecycle (propose→approve→supersede) test BEFORE finalizing the
  constraint.** The F15 failure was a constraint that encoded an invariant too
  strictly for the full lifecycle; a supersede-in-the-same-transaction test
  would have caught it at design time, not at first live run. (It WAS caught
  by the live validation before any prod write — the rollback discipline paid
  off — but earlier is cheaper.)
- **Decide F4 (bundle vs per-record degenerate) BEFORE W1.1 lands the
  function.** The function and the Weaviate projection now use different
  fallbacks; reconciling later means touching both. It is still cheap to fix
  now (0026 unapplied) — another reason to resolve F4 at this review.

## Review schedule

- **Owner review (this pre-mortem + W1.1 pre-mortem together):** decide F4
  (bundle degenerate), greenlight the 0026 prod-apply (post-F15), greenlight
  the F6 run-level Wave-gate test.
- **Wave gate (after W1.5):** live agent run proving the `@approval` pause +
  resolve; live-Weaviate planted-fact dict-filter test (F3); deterministic
  checkpoint re-derivation.
