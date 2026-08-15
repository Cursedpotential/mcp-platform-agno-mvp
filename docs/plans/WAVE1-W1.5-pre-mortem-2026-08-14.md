# WAVE 1.5 Pre-Mortem — Agent Lane Bindings + Wave-1 Gate (ADR-0045 §A.4/§B)

> **R0 AUDIT BANNER 2026-08-15:** later replay found Wave 1 remains unsafe for
> product execution despite the focused checks below. Read
> `../HANDOFF-2026-08-15-R0-wave1-audit.md`; all migrations are unapplied and
> cutover is held. _Byline: Codex · GPT-5._


> _Byline: Claude Code · glm-5.2:cloud · 2026-08-14_
> Status: **PARTIAL BUILD — the two reversible, no-owner-decision pieces are built +
> verified (P2 isolation fix; realization-tools lane binding). The derivation read
> path is DESIGN-ONLY, held for the owner's connection-model + transition decisions.
> Nothing applied to prod; nothing pushed.** This is the final Wave-1 pre-mortem.
>
> ⚠ **CORRECTION 2026-08-14 (CH-11):** the owner ruled on the four Wave-1 review
> decisions. **D1** (bundled-doc `visible_from`): the bundle-clock question is
> **DISSOLVED by ADR-0053 §3** — the document unit is the classified **chunk**, not the
> conversation bundle; the horizon is an agent-retrieval dict-filter (§7/§8); the prior
> `occurred_at_max` rec is superseded. **D2** (connection model): **DEFERRED — interim
> = option (b)** (keep the app superuser; 0029 grants stay advisory; F13 lock + app
> post-filter = the effective §B guard); future target = (c), fleshed out later; **do
> not implement the connection model now.** **D3** = split `walk_step_retrieval`;
> **D4** = defer per-agent scoping. Cutover is an owner-review item (no migration
> applies until reviewed). Full ruling: `docs/CHANGE-ORDER.md` **CH-11**.

## The scenario

It is after Wave 1. The lane bindings shipped, and **either a concurrent
realization approval silently broke a derivation's reproducibility (the delta is
now timing-dependent), or an agent approved its own realization with no human in
the loop (the HITL gate was bypassed), or the "Wave-1 gate passed" claim was made
on a derivation-level test that never actually ran against the planted-fact.**
Explain why.

---

## What W1.5 actually built (the reversible pieces)

### 1. P2 — derivation engine pinned to REPEATABLE READ (the W1.3 carryover)
- **The gap (W1.3 pre-mortem P2):** `derive_walk` + `verify_reproducibility` opened
  their transactions at the DEFAULT isolation (READ COMMITTED). The §B contract
  requires that once a derivation pins `base_version`, the WHOLE walk sees one
  stable snapshot — otherwise a concurrent realization approval mid-walk moves
  `visible_from` for a record between step N and step N+1, making the chain
  dependent on approval timing and `verify_reproducibility` non-deterministic.
- **The fix:** `_get_engine()` now `isolation_level="REPEATABLE READ"`. Postgres
  takes the snapshot at the txn's first statement (the `pg_advisory_xact_lock`),
  freezing the authored store for the walk's duration; the append-only INSERTs
  don't conflict with the snapshot. Module docstring + a new "Snapshot-stable"
  contract bullet record it (doc-drift rule, same turn).
- **Verified live (zero net write, SHOW only):** `_wave1_validate_w15_isolation.py`
  3/3 PASS — the derivation engine's OWN `_get_engine()` opens at `repeatable read`
  (the production path `derive_walk` takes); a contrast engine on the same DB
  defaults to `read committed` (proves the pin, not the server default, sets RR);
  the engine is a lazy singleton. Verification standard: prove the CODE CHANGE
  (the isolation the engine opens at) by observing it; the snapshot-freeze
  BEHAVIOR is a documented Postgres REPEATABLE READ guarantee, trusted once the
  pin is shown — the same standard used for F13's `pg_advisory_xact_lock`.

### 2. Realization-tools lane binding (the W1.2-deferred W1.5 wiring)
- **What:** `REALIZATION_TOOLS` is now registered in `providers.source_tools`
  (`providers.py:178`, the single append point), so every platform agent gets the
  realization-event writer surface. `realization_tools.py` header updated (was
  "NOT appended in W1.2" → now "registered in W1.5").
- **Lane binding (the design):** `realization_propose` is a plain `@tool`,
  inert (a `'proposed'` row `visible_from` never reads) → every agent may propose
  freely, in bulk. `realization_approve` + `realization_supersede` are
  `@approval` + `requires_confirmation=True` → any call PAUSES for a recorded
  human (owner) approval before the body runs. **The `@approval` gate IS the
  lane boundary** — which agent holds the tool does not change enforcement: any
  approve/supersede call pauses for the owner. The DB-level backstop
  (`visible_from` reads only `'approved'`) catches any writer that bypasses the
  tool entirely.
- **Verified:** the 3 tools land with the right gating (`realization_propose`
  `requires_confirmation=None`; `realization_approve`/`realization_supersede`
  `requires_confirmation=True`, `@approval` present); `providers` imports clean
  (no cycle); 688 passed / 24 skipped (no regressions).

## What W1.5 did NOT build (held for owner decisions — DESIGN only)

### A. Derivation read path → agent retrieval (the §B pass-corpus read)
- **The §B contract:** agents read the DERIVED pass corpus (`working.walk_*`),
  not the canonical store directly (one-store-filtered-per-agent). Today no agent
  calls `derive_walk`; agents read via `working.vw_spine_horizon`.
- **Why held (two owner decisions, NOT made unilaterally):**
  - **W1.4 #1 — connection model.** Binding the read path to `pass_reader`
    requires the app to connect as a non-superuser role (the gate that turns the
    0029 grants from schema contract into enforcement). That is the owner's
    architecture fork (option a/b/c in the W1.4 pre-mortem). Rewiring the agent
    read path before that decision would either be inert (superuser, grants
    ignored) or risk breaking agent reads (stripping canonical SELECT before the
    pass corpus is wired — W1.4 #3 transition).
  - **W1.4 #3 — transition ordering.** Rebind agents to the pass corpus (W1.5)
    BEFORE stripping their canonical/spine access, or every agent read breaks.
- **What IS ready:** the derivation engine (`derive_walk` + `verify_reproducibility`,
  W1.3) + the §B pre-binding gate (`verify_reproducibility` returns
  `reproducible=True` before any agent binds). A read helper
  (`get_pass_corpus` → `verify_reproducibility` then return the visible slice) is
  the natural next building block, but it is only meaningful once the connection
  model is decided — building it now against the superuser connection would be
  speculative code that the owner's decision may reshape.

### B. F3 — live-Weaviate planted-fact dict-filter test
- **Clarification (important):** the **Wave-1 gate itself** (plan §G: "plant a
  2026 fact in a 2023 thread; ignorant walk returns no 2026 fact; hindsight does;
  re-derivation reproduces the hash") is the **derivation-level** planted-fact
  test — **already MET in W1.3 (12/12 PASS: contamination guard excludes the
  future-revealed record from the early ignorant step; the multi-step walk
  DISCOVERS it at the later horizon; hindsight includes it; reproducibility
  holds).**
- **F3 live-Weaviate is the Wave-3 gate** (plan §G Wave-3: "future fact excluded
  before top-k in PG + Weaviate + Neo4j; real dict-filter round-trip"). It is NOT
  a Wave-1 requirement. Pulling it forward now was considered and **declined**:
  - the platform's currently-exploited horizon filter is **app-side post-filter**
    (`server/evidence/retrieval.py` ADR-0050 §4), NOT a Weaviate store-side
    dict-filter (agno serializes metadata into one `meta_data` blob no store-side
    range filter can reach); the GAP-01 landmine (FilterExpr dropped, dict-only)
    is a latent risk for a future store-side path, not the live one;
  - a real round-trip through agno's Weaviate VectorDb needs a working embedder
    provider + navigation of several known agno×weaviate-client integration gaps
    (documented in `knowledge_vectordb.py`) — heavy setup unrelated to Wave 1's
    goal, better suited to Wave 3's "one shared filter compiler" work.
- **Weaviate IS up** (`100.91.190.107:8081` → HTTP 200 ready; the "data-vector
  DOWN since 2026-08-10" was Milvus, not Weaviate). So F3 is runnable, not blocked
  — it is correctly scheduled for Wave 3, not deferred due to outage.

### C. F6 — `@approval` run-level test
- The **code-level F6** (the `@approval` + `requires_confirmation` decorators are
  present on the approve/supersede tools; the DB-level `visible_from` reads only
  `'approved'`) was **proven in W1.2 (17/17 PASS, 4 F6 code-level + 13 DB-level).**
- The **run-level** F6 (drive a live agno run through the `@approval` pause and
  confirm it blocks until a human approves) needs a live `agentos-api` run write.
  `agentos-api` IS up (`100.72.169.40:8000` → HTTP 200; `/config` needs the
  `OS_SECURITY_KEY` bearer). W1.5 wired the tools (the precondition), so the
  run-level test is now closer — but driving a live run that pauses for approval
  is a runtime-gate validation, deferred to the Wave-1 cutover / runtime gate
  rather than this build task.

---

## Failure reasons (what could go wrong) — prioritized

### P0 — the connection model is never decided, so the §B sole-writer stays advisory
- **What could fail:** W1.4's grants + W1.5's lane binding ship, but the app
  keeps connecting as the `ai` superuser, so the DB-enforced sole-writer /
  default-deny never bites. The derivation read path stays on the spine
  (canonical), agents can still read/write `walk_*` freely, and "DB-enforced
  §B" is a claim that's only true for non-superuser roles. The whole Wave-1
  isolation story is "F13 advisory lock + app-side post-filter," not DB-enforced.
- **Mitigation (owner decision, NOT made):** decide W1.4 #1 (connection model).
  Recommendation: option (a) — a non-superuser app role (`pass_refresher` for
  derivation writes, `pass_reader` for agent reads, a third for spine/canonical
  reads), SET ROLE per path. This is THE gate that turns 0029 + the lane binding
  into enforcement. Everything else in Wave 1 is ready; this is the hinge.
- **Status:** **OPEN — the #1 owner decision.**

### P1 — agents approve their own realizations (no human in the loop)
- **What could fail:** because `realization_approve`/`realization_supersede` are
  now on EVERY agent (uniform `source_tools`), an autonomous agent run calls
  approve and... the `@approval` gate pauses for a human. So this is MITIGATED by
  the gate — but if `@approval` is misconfigured or bypassed (e.g., a run mode
  that auto-approves, or a future tool that calls `approve_realizations` directly
  without the decorator), an agent could approve its own realization, moving
  `visible_from` with no human. That would silently corrupt the delta.
- **Mitigation:** (i) the `@approval` gate (verified present); (ii) the DB-level
  backstop (`visible_from` reads only `'approved'` — but approve_realizations
  sets `'approved'`, so the backstop doesn't stop a self-approval, it stops
  UNAPPROVED writes); (iii) the real defense is the HITL pause + owner review of
  the approval queue. **OPEN refinement:** scope approve/supersede to the
  `review_gatekeeper` only (per-agent tool customization in `factory.py`, which
  today passes one uniform `source_tools`) — cosmetic tool-surface hygiene, not
  enforcement (the `@approval` gate is the enforcement either way).
- **Status:** **mitigated by @approval; gatekeeper-scoping is an open refinement.**

### P2 — REPEATABLE READ fix breaks under the `connection=` path
- **What could fail:** the isolation pin is on `_get_engine()` (the
  `connection=None` production path). A caller passing `connection=` (an outer
  txn) gets the CALLER's isolation, not REPEATABLE READ. If a production caller
  passes a READ COMMITTED outer txn for atomicity, the snapshot-stability
  guarantee is lost for that call.
- **Mitigation:** documented in `_get_engine`'s docstring — callers passing
  `connection=` are responsible for its isolation; the validation scripts pass a
  rollback `connection=` (single-threaded, no concurrency, acceptable). In
  practice the derivation should OWN its txn (the `connection=None` path), which
  IS pinned. No production caller passes `connection=` today.
- **Status:** **documented; no current production caller passes connection=.**

### P3 — the Wave-1 gate claim rests on W1.3, not a fresh W1.5 run
- **What could fail:** "Wave-1 gate met" is asserted by pointing at the W1.3
  validation (12/12). If the W1.5 changes (REPEATABLE READ, lane binding) had
  silently altered the derivation behavior, the W1.3 result might not hold —
  and re-asserting W1.3 without re-running it would be claiming off a stale signal.
- **Mitigation:** the W1.3 derivation validation was **re-run after the
  REPEATABLE READ change this session → still 12/12 PASS** (the isolation pin is
  additive to the walk; the contamination guard + reproducibility are unchanged).
  The lane binding (providers wiring) doesn't touch the derivation path at all.
- **Status:** **re-verified — W1.3 12/12 re-ran green post-change.**

### P4 — F3/F6 deferral reads as "gate passed" when they weren't run
- **What could fail:** the pre-mortem defers F3 (live-Weaviate) to Wave 3 and F6
  (run-level) to the runtime gate, but a reader infers "Wave-1 gate green =
  Weaviate + @approval run-level proven." They are NOT — F3 is a Wave-3 gate;
  F6 run-level is deferred. Only the derivation-level gate (W1.3) is met.
- **Mitigation:** stated explicitly above (F3 = Wave-3 gate, not Wave-1; F6
  code-level met in W1.2, run-level deferred). The Wave-1 gate (plan §G) is the
  derivation planted-fact test, which IS met.
- **Status:** **called out; no over-claim.**

---

## Resolutions — applied 2026-08-14

| Finding | Status | Evidence |
|---|---|---|
| P2 REPEATABLE READ isolation pin | **BUILT + PROVEN** | `_wave1_validate_w15_isolation.py` 3/3 PASS (SHOW transaction_isolation=repeatable read); W1.3 derivation re-run 12/12 PASS |
| Realization-tools lane binding | **BUILT + VERIFIED** | 3 tools in source_tools; propose free, approve/supersede requires_confirmation=True + @approval; 688 passed / 24 skipped |
| Derivation read path → agent retrieval | **DESIGN ONLY — held** | blocked on W1.4 #1 (connection model) + #3 (transition); not wired unilaterally |
| F3 live-Weaviate planted-fact | **Wave-3 gate — not Wave-1** | Wave-1 derivation gate met in W1.3 (12/12); F3 correctly scheduled for Wave 3 |
| F6 @approval run-level | **code-level met (W1.2); run-level deferred** | tools now wired (precondition); runtime-gate validation deferred |

## Validation evidence

```
W1.5 isolation (live, SHOW only, zero net write):  3/3 PASS
  - derivation _get_engine() opens at REPEATABLE READ
  - contrast engine defaults to READ COMMITTED (pin proven)
  - engine is a lazy singleton
W1.3 derivation (re-run post-P2, live rollback):    12/12 PASS  (no regression from the pin)
REALIZATION_TOOLS:                                  3 tools; propose free,
                                                    approve/supersede requires_confirmation=True + @approval
providers import:                                   OK (no cycle)
Full unit suite:                                    688 passed, 24 skipped  (no regressions)
ruff (edited files + project gate):                 clean
mypy (derivation.py):                               clean
Weaviate reachability:                              100.91.190.107:8081 → HTTP 200 (up; data-vector-DOWN was Milvus)
agentos-api reachability:                           100.72.169.40:8000 → HTTP 200 (up; /config needs OS_SECURITY_KEY bearer)
```

## Prod-apply / push status

- **Nothing applied to prod.** 0026/0027/0028/0029 all still NOT applied; the
  P2 isolation pin + the lane binding are code changes that take effect on the
  next deploy (not deployed). The realization tools becoming live in the agent
  runtime requires an agentos-api redeploy (env-literal rendering + restart).
- **Nothing pushed to main** (commit-only-when-asked). All W1.5 work uncommitted:
  - edited: `server/evidence/derivation.py` (REPEATABLE READ pin + docstring),
    `server/agents/providers.py` (REALIZATION_TOOLS wiring), `server/agents/tools/realization_tools.py` (header doc true-up)
  - new: `scripts/_wave1_validate_w15_isolation.py` (zero-net-write validation)

## What I would do differently next time

- **Probe the app's connection role BEFORE designing the grants/lane binding,
  not across W1.4→W1.5.** The superuser finding (W1.4) reshaped both W1.4 and
  W1.5; a 30-second `SELECT rolsuper` recon at Wave-1 start would have made the
  connection-model the explicit Wave-1 prerequisite from day one instead of a
  discovery that serializes the gates. (Same lesson as the W1.4 pre-mortem —
  the recon should be the first step of the wave, not a mid-wave finding.)
- **Decouple the F-level gate labels from the wave labels.** The task description
  bundled "F3 live-Weaviate" into W1.5, but F3 is the Wave-3 gate per plan §G.
  I spent real time confirming F3 wasn't a Wave-1 requirement before declining
  to pull it forward — a clearer wave↔gate mapping up front would have saved
  that. The Wave-1 gate is the derivation planted-fact test; the Weaviate/Neo4j
  planted-fact test is Wave-3.

## Review schedule — owner decisions that gate the Wave-1 cutover

> ⚠ **SUPERSEDED 2026-08-14 (CH-11):** the owner RULED on all four below. D1 dissolved
> by ADR-0053; **D2 = DEFERRED, interim option (b)** (NOT "decide option (a)" — the
> connection model is NOT being worked now; future target (c)); D3 = split; D4 = defer.
> The "Decide W1.4 #1 … Recommendation: option (a)" text immediately below is the
> PRE-ruling ask, kept for history. See `docs/CHANGE-ORDER.md` **CH-11** for the rulings.

- **Decide W1.4 #1 — the connection model** (the hinge). Until this is decided,
  the §B sole-writer + default-deny are advisory (F13 lock + app-side
  post-filter), not DB-enforced. Recommendation: option (a) non-superuser app
  role + SET ROLE per path. This unblocks the derivation read path (W1.5-A).
- **Decide W1.4 #3 — the transition ordering.** Rebind agents to the pass
  corpus before stripping canonical/spine access.
- **Optional refinement:** scope `realization_approve`/`realization_supersede`
  to the `review_gatekeeper` only (per-agent tools in `factory.py`). The
  `@approval` gate enforces HITL regardless; this is tool-surface hygiene.
- **Wave-1 cutover sequence (post-decision):** decide connection model → apply
  0026/0027/0028/0029 → build the derivation read path (W1.5-A) + rebind agents
  to the pass corpus → redeploy agentos-api → run the F6 run-level + the
  derivation planted-fact gate against the live stack.

## Wave 1 — overall status (all five sub-tasks)

| Sub-task | Built | Verified | Applied to prod | Pre-mortem |
|---|---|---|---|---|
| W1.1 clock migration (0026) | ✅ | 12/12 rollback | ❌ held | ✅ |
| W1.2 realization writers | ✅ | 17/17 rollback | ❌ held | ✅ |
| W1.3 derivation engine + repoint (0027/0028) | ✅ | 12/12 + 5/5 rollback | ❌ held | ✅ |
| W1.4 default-deny grants (0029) | ✅ | 18/18 rollback | ❌ held (superuser) | ✅ |
| W1.5 lane bindings (P2 + realization tools) | ✅ partial | 3/3 + 688 unit | ❌ held (connection model) | ✅ this |

**Wave 1 BUILD is complete; the cutover (apply + redeploy + bind read path) is
gated on the owner's connection-model decision (W1.4 #1).** All five pre-mortems
are the owner's review surface for that decision.
