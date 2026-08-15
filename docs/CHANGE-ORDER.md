# CHANGE-ORDER — Agno-MCP-Platform

> _Byline: Claude Code · Fable 5 · 2026-08-12; Codex · GPT-5 · 2026-08-13_
> Running, append-only ledger of executed changes (newest on top). Per the workspace
> memory contract: append the same turn as any executed change. Complements
> `DECISION_LOG.md` (the why) — this is the what/where/verified. Strike; never delete.

---

## 2026-08-14

### CH-11 — Wave-1 owner rulings D1–D4 (2026-08-14) — D1 RESOLVED by ADR-0053, D2 DEFERRED, D3 SPLIT, D4 DEFER

> _Owner rulings on the four Wave-1 review decisions, delivered 2026-08-14. These
> SUPERSEDE every prior D1 recommendation in the W1.1/W1.2/W1.3/W1.5 pre-mortems, the
> earlier CH-6…CH-10 open-item lines, and the WAVE1-review HTML. Per the doc-drift
> rule, those stale recs are visibly corrected in place (dated pointer to this entry),
> not silently deleted._

- **D1 — bundled-document `visible_from`: DISSOLVED by ADR-0053, not "answered."**
  The "bundle clock (`occurred_at_max`) vs per-record (`occurred_at`)" question was
  the WRONG frame — it assumed the Weaviate document = the conversation bundle
  (`store.py::horizon_axes` `group_by_conversation` + `occurred_at_max`). **ADR-0053
  (accepted 2026-08-13) already decides the document unit: chunk-first-then-classify**
  (ADR-0053 §3). `working.chat_chunk` (+ `chat_chunk_message` exact message provenance
  + `chat_chunk_lane` multi-label) is the unit — NOT the conversation bundle, NOT the
  raw record. One chat crosses several domains; a chunk is embedded once per embedder
  and the same vector is projected per-lane (no double-embed, no duplication). **The
  horizon is an AGENT-RETRIEVAL filter, never an extraction/storage lane** (ADR-0053
  §7: "The horizon remains an agent retrieval permission/filter, never an extraction
  lane"), applied as a Weaviate **dict pre-filter** (ADR-0053 §8) over the chunk's
  constituent-message clocks. So `visible_from` attaches at retrieval, derived from
  the chunk's message provenance — the per-record clock logic in
  `working.visible_from(record)` (`COALESCE(MIN approved realized_at, occurred_at)`,
  sql/0026) is correct and sufficient; **there is no "bundle clock" to pick.** The
  current `store.py` `group_by_conversation` + `occurred_at_max` is the pre-0053
  `context_record` model (explicitly superseded by ADR-0053 §3, which lists
  "classified before chunking" as the rejected approach) and must be conformed to the
  **chunk unit** — that is **Wave-3 projection work** (one vector per chunk, projected
  per-lane, horizon dict-filter at retrieval over per-message clocks), NOT a Wave-1
  bundle-clock ruling. **The prior rec "occurred_at_max + make the DB function
  bundle-aware" is SUPERSEDED — do not act on it.** Owner 2026-08-14 (verbatim intent):
  the chunk→classify→domain-tag pipeline (normalize → change-detection → classify AND
  chunk → route chunks to domains with tags) is the decided design and has been
  discussed repeatedly; stop re-litigating it.

- **D2 — connection model: DEFERRED. Interim = option (b); future target = (c).**
  Owner 2026-08-14: "go with B for now, I think C but I want to flesh it out, we're
  not working on it yet." **Interim = option (b)** (W1.4 pre-mortem P0, lines 94-96):
  keep the app as the `ai` SUPERUSER; 0029 grants stay advisory (inert for the
  superuser connection); the F13 app-side advisory lock + app-side post-filter
  (`retrieval.py` ADR-0050 §4) remain the **effective** §B sole-writer guard; the
  grants are a defense-in-depth schema contract only. **Future target = option (c)**
  (two/three connection pools: admin `ai`/su + `pass_refresher` LOGIN + `pass_reader`
  LOGIN) — to be fleshed out when we actually work on the connection model. **Do NOT
  implement the connection model now.** Consequence: the agent pass-corpus read
  rebinding (W1.5-A) + DB-enforced sole-writer WAIT for (c); under (b), agents keep
  reading via `working.vw_spine_horizon` (canonical), and §B is enforced app-side.

- **D3 — `walk_step_retrieval`: DECIDED = SPLIT the concept.** Engine records the
  visible-slice as provenance (`was_used=false` or a separate `walk_step_visible`
  table); the agent records its real retrievals with `rank`/`score`/`was_used`.
  Implement when the derivation read path lands (gated on D2=(c), deferred).

- **D4 — per-agent read scoping: DECIDED = DEFER.** Leave `pass_reader` whole-table
  SELECT for now; revisit RLS/app-layer scoping at scale or when (c) lands.

- **Cutover status (re-anchored):** Wave-1 **BUILD is complete** (all five sub-tasks
  built + verified in rollback). The **cutover is an owner-review item** — prod-apply
  of migrations waits for owner review (governing directive), and the owner will
  review all pre-mortems when back. Under D2=(b), the cutover slice that does NOT need
  the connection model = apply **0026/0027/0028** (clock + realization + derivation
  repoint) + wire the refresher fast-path (`refresh_visible_from`) + redeploy
  agentos-api; **0029 applies as inert contract** (harmless while superuser); agents
  stay on the spine. The DB-enforced sole-writer + pass-corpus read rebinding + F6
  run-level gate wait for (c). **Nothing applies until the owner reviews.**

- **Governing record:** ADR-0053 §3/§7/§8; ADR-0045 §A/§B; W1.4 pre-mortem P0 (b/c);
  plan §G Wave-1/Wave-3. Byline: Claude Code · glm-5.2:cloud · 2026-08-14.

### CH-10 — W1.5 agent lane bindings + derivation isolation pin (ADR-0045 §A.4/§B) — built (partial), NOT applied/pushed

- **What:** the final Wave-1 build pieces, both reversible + no owner-decision needed:
  (1) **P2 isolation pin** — `server/evidence/derivation.py` `_get_engine()` now
  `create_engine(..., isolation_level="REPEATABLE READ")` (closes the W1.3 pre-mortem
  P2 gap: a concurrent realization approval mid-walk could move `visible_from`
  between steps under READ COMMITTED, breaking §B reproducibility; REPEATABLE READ
  takes the snapshot at the txn's first statement = the `pg_advisory_xact_lock`,
  freezing the authored store for the walk). Module contract docstring gained a
  "Snapshot-stable (W1.5 / P2)" bullet (doc-drift rule, same turn). Callers passing
  `connection=` keep the caller's isolation (documented).
  (2) **Realization-tools lane binding** — `REALIZATION_TOOLS` registered in
  `providers.source_tools` (`providers.py:192`, the single append point); every
  platform agent gets the realization-event writer surface. `realization_propose`
  = plain `@tool` (inert: a `'proposed'` row `visible_from` never reads → free,
  bulk on all agents). `realization_approve`/`realization_supersede` =
  `@approval` + `requires_confirmation=True` → any call PAUSES for a recorded
  human (owner) approval. **The `@approval` gate IS the lane boundary** — tool
  placement ≠ enforcement. `realization_tools.py` header updated (was "NOT
  appended in W1.2" → "registered in W1.5").
- **Verified (zero net write / rollback):** `_wave1_validate_w15_isolation.py`
  3/3 PASS (derivation engine opens at `repeatable read` via SHOW; contrast
  unconfigured engine = `read committed`, proving the pin not the server default
  sets RR; lazy singleton); W1.3 derivation re-run 12/12 PASS (no regression from
  the pin); REALIZATION_TOOLS = 3 tools with correct gating (propose free;
  approve/supersede `requires_confirmation=True` + `@approval`); providers import
  clean (no cycle); full unit suite 688 passed / 24 skipped; ruff + mypy (derivation.py) clean.
- **NOT built (held for owner decisions — DESIGN only):**
  - derivation read path → agent retrieval (§B pass-corpus read): gated on W1.4
    #1 (connection model — app connects as `ai` SUPERUSER today, so 0029 grants
    stay inert) + W1.4 #3 (transition ordering). Not unilaterally rewired.
  - F3 live-Weaviate planted-fact dict-filter: **the Wave-3 gate, NOT Wave-1**
    (Wave-1 derivation gate met in W1.3 12/12; current horizon filter is app-side
    post-filter per `retrieval.py` ADR-0050 §4, not a store-side dict-filter; a
    real agno Weaviate round-trip is heavy — better in Wave 3). Weaviate IS up
    (`100.91.190.107:8081` HTTP 200).
  - F6 `@approval` run-level: code-level proven in W1.2; run-level (drive a live
    agno run through the pause) deferred to the runtime gate (agentos-api up at
    `100.72.169.40:8000` HTTP 200).
- **Files (all uncommitted):** edited `server/evidence/derivation.py`,
  `server/agents/providers.py`, `server/agents/tools/realization_tools.py`; new
  `scripts/_wave1_validate_w15_isolation.py`. No migration applied (0026/0027/0028/0029 still held).
- **Safety:** nothing to prod; nothing pushed to main (commit-only-when-asked).
  The realization tools go live only on agentos-api redeploy (env-literal render + restart).
- **OPEN owner decisions (the Wave-1 cutover hinge):** W1.4 #1 connection model
  (rec: non-superuser app role + SET ROLE per path — THE gate that turns 0029 +
  lane binding into DB-enforced §B); W1.4 #3 transition ordering; optional
  refinement = scope approve/supersede to `review_gatekeeper` only.
- **Governing record:** plan §G Wave-1; ADR-0045 §A.4 + §B; W1.5 pre-mortem
  `docs/plans/WAVE1-W1.5-pre-mortem-2026-08-14.md`. Byline: Claude Code · glm-5.2:cloud · 2026-08-14.

### CH-9 — W1.4 default-deny pass-grants (ADR-0045 §B / ADR-0052) — built, NOT applied/pushed

- **What:** the DB-layer schema contract for §B sole-writer / ADR-0052 default-deny isolation.
  - new `sql/0029_pass_grants.sql` — two NOLOGIN roles + schema USAGE + per-table grants:
    **`pass_refresher`** (sole writer of `working.walk_run/walk_step/walk_step_retrieval` +
    `record_visible_from`; SELECT on canonical `normalized_record`/`realization_event*` to compute
    `base_version`; INSERT `ops.audit_ledger` for attestation; EXECUTE `visible_from`/`horizon_visible`;
    NO DELETE — append-only) + **`pass_reader`** (SELECT pass corpus only; NO canonical — agents read
    the DERIVED pass corpus, not the raw store, per §B one-store-filtered-per-agent) + DEFAULT-DENY
    (`REVOKE ALL ... FROM PUBLIC` on the pass tables + `record_visible_from`).
  - new `scripts/_wave1_recon_w14_grants.py` — read-only recon that surfaced the decisive finding (below).
  - new `scripts/_wave1_validate_w14_grants.py` — live rollback validation incl. a real SET-ROLE
    enforcement proof (creates the roles + grants inside one rollback txn, SET ROLEs to each
    non-superuser role, observes what each can/cannot do — proving the grants are real enforcement,
    not just structure).
- **The decisive finding — grants are INERT while the app is superuser:** the agno app connects as
  the role `ai`, which is a SUPERUSER (verified live 2026-08-14: rolsuper=True, the only login role,
  owner of every working./ops. table). Superusers bypass ALL grants + BYPASSRLS. So 0029 is the
  **schema contract** for the target isolation — correct + validated as real enforcement *for a
  non-superuser role* (proven via SET ROLE) — but **INERT for the app's current superuser connection.**
  The grants become ENFORCING only when the derivation path connects as `pass_refresher` and agent
  reads as `pass_reader` — a **connection-model change** that is the owner's call, NOT made here. The
  F13 app-side advisory lock remains the sole *effective* sole-writer guard until then. (ADR-0036 is
  Neo4j/DozerDB RBAC, not Postgres — the `walk_ledger.postgres-draft.HOLD.sql` comment conflated the
  two; Postgres CREATE ROLE + GRANT both work here.)
- **Contract — PROVEN on live (rollback, 18/18 PASS):** roles exist NOLOGIN; default-deny PUBLIC=0;
  pass_refresher SELECT canonical/INSERT walk_step/UPDATE walk_run/INSERT audit_ledger; pass_reader
  SELECT walk_step/NO INSERT/NO canonical SELECT. **SET-ROLE enforcement:** as `pass_reader` SELECT
  walk_step succeeds, INSERT walk_step DENIED ("permission denied for table walk_step"), SELECT
  normalized_record DENIED; as `pass_refresher` INSERT walk_step succeeds, SELECT normalized_record
  succeeds, DELETE walk_run DENIED (append-only). Proven WITHOUT a committed live write (a txn sees
  its own DDL → CREATE ROLE + GRANT + SET ROLE all in one rollback txn).
- **Apply-order dependency:** 0026 → 0027 → **0028** → 0029. 0029 grants on
  `working.record_visible_from`, which 0028 (the horizon repoint) creates.
- **Open (owner review):** **#1 connection model** — introduce a non-superuser app role so the grants
  bite (the gate that turns the schema contract into enforcement; recommendation = yes, the §B
  sole-writer becomes real); **#2 per-agent scoping** — pass_reader SELECT exposes ALL runs not just
  the agent's own (needs RLS, also inert while superuser, or app-layer — deferred to W1.5);
  **#3 transition** — agents today read via `vw_spine_horizon` (needs canonical SELECT); 0029's target
  denies it, so rebind agents to the pass corpus (W1.5) BEFORE stripping canonical access.
- **Safety:** 0029 NOT applied to prod (held for the owner's connection-model ruling; applying it alone
  while the app stays superuser is harmless but pointless). Purely additive (CREATE ROLE + GRANT/REVOKE
  — does not touch the `ai` role or any existing privilege). Nothing pushed (commit-only-when-asked). All
  validation in rollback transactions on live — zero net write. Post-check: `pass_refresher` /
  `pass_reader` / pass-table grants all ABSENT on live (rollbacks left no trace).
- **Verified (re-run this turn):** `scripts/_wave1_validate_w14_grants.py` **18/18 PASS** (live rollback);
  `uv run pytest -q` **688 passed / 24 skipped** (no regressions); `ruff check server tests` clean;
  new scripts ruff-clean (mypy non-blocking — scripts outside the `mypy server` gate).
- **Governing record:** ADR-0045 §B + ADR-0052 (D-054); approved plan `cached-waddling-crayon.md`
  Wave 1 task #13; pre-mortem `docs/plans/WAVE1-W1.4-pre-mortem-2026-08-14.md`.

_Byline: Claude Code · glm-5.2:cloud · 2026-08-14._

### CH-8 — W1.3 derivation engine + horizon repoint (ADR-0045 §B + §A) — built, NOT applied/pushed

- **What:** the SOLE-writer checkpoint-derivation engine (ADR-0045 §B) + the live-spine
  visible_from repoint (ADR-0045 §A, the F1-resolution deferred from W1.1).
  - new `sql/0027_walk_ledger.sql` — purely-additive `working.walk_ledger`:
    `walk_run` (version-pinned: `base_version` content-hash + `genesis_hash` +
    `final_corpus_hash`), `walk_step` (chain-hashed: `corpus_hash` + `prev_hash`),
    `walk_step_retrieval` (provenance), + `vw_walk_contamination` (leak detector,
    on `visible_from` not `knowledge_time` — draft correction #3) + `vw_walk_delta`
    (the deliverable: believed-then vs actual + `realization_lag`). Reconciled from the
    SUPERSEDED `sql/drafts/walk_ledger.postgres-draft.HOLD.sql` with four corrections
    (documented in the header): `analysis.*`→`working.*`, FK→`working.normalized_record`
    (post schema split), contamination on `visible_from`, + the §B chain-hash/version-pin
    columns the draft lacked entirely.
  - new `server/evidence/derivation.py` — the SOLE-writer refresher engine:
    `derive_walk` (ignorant incremental walk over N horizons + hindsight on-prompt) +
    `verify_reproducibility` (the §B pre-binding gate). `pg_advisory_xact_lock(F13)`
    sole-writer; `base_version` = content-hash of the case's records + APPROVED
    realizations; `corpus_hash = sha256(prev_hash || canonical slice)`; each step
    hash-attested to `ops.audit_ledger` (atomic via `connection=`; `base_version` NOT
    passed — `audit_ledger.base_version` is BIGINT, the precise content-hash lives in
    `working.walk_run.base_version` TEXT + `payload_hash=corpus_hash`).
  - new `sql/0028_horizon_repoint.sql` — ⚠ **HELD FOR OWNER.** the F1-resolution:
    `vw_spine_horizon` filters on `visible_from(r.id) <= app.horizon` (not the superseded
    `knowledge_time`) WITH a materialized fast path (`working.record_visible_from` +
    `COALESCE` function fallback). NOT purely additive (CREATE OR REPLACE VIEW) — the
    live-behavior flip. Drafted + rollback-validated; F4-dependent.
  - new `scripts/_wave1_validate_w13_derivation.py` (12/12 PASS, live rollback) +
    `scripts/_wave1_validate_w13_repoint.py` (5/5 PASS, live rollback).
- **§B contract — PROVEN on live (rollback):** contamination guard (canon §1 — ignorant
  early step excludes a year-forward realized record; multi-step walk DISCOVERS it at the
  later step; hindsight includes); sole-writer lock F13 (2nd connection's
  `pg_try_advisory_xact_lock` returns False); version-pinned reproducibility
  (`verify_reproducibility` reproducible=True, 1-step + 2-step); chain integrity
  (each step `prev_hash` = prior `corpus_hash`); hash-attestation (audit_ledger
  `action_type='derivation'` rows). Repoint faithful: ignorant excludes / hindsight
  includes / fast-path consulted / late-horizon includes / structural (view body on
  `visible_from(r.id)`, not `knowledge_time <=`).
- **Safety:** 0026/0027/0028 NOT applied to prod. 0027 additive + safe but held for a
  single cutover; 0028 is the live flip — explicitly HELD FOR OWNER (F4 + fast-path-writer
  + W1.4 grants ordering). Nothing pushed (commit-only-when-asked). All validation in
  rollback transactions on live — zero net write. Post-check: `walk_run`/`walk_step`/
  `walk_step_retrieval`/`vw_walk_*`/`record_visible_from` all ABSENT on live (rollbacks
  left no trace).
- **Verified:** `_wave1_validate_w13_derivation.py` **12/12 PASS**;
  `_wave1_validate_w13_repoint.py` **5/5 PASS**; `uv run pytest -q` **688 passed / 24
  skipped** (no regressions); `ruff check` clean (auto-fixed 3 unused imports);
  `mypy` clean on `derivation.py`.
- **Open (owner review):** **F4** bundled-doc degenerate `visible_from`
  (occurred_at_max vs per-record — blocks 0028 apply; recommendation = occurred_at_max +
  bundle-aware function — ~~SUPERSEDED 2026-08-14 by CH-11 (D1): bundle-clock question dissolved by ADR-0053 §3 chunk unit; do not act on this rec~~); **P2** derivation isolation not pinned (concurrent realization
  approval breaks reproducibility — fix `SET TRANSACTION REPEATABLE READ` before W1.5);
  **P5** `walk_step_retrieval` semantics (visible-slice provenance vs agent retrieval —
  needs owner call); **P1** fast-path refresher not yet wired (0028 falls back to per-row
  function until `refresh_visible_from` lands); **P3** sole-writer DB-enforcement deferred
  to W1.4 grants.
- **Governing record:** ADR-0045 §B+§A (D-042); approved plan `cached-waddling-crayon.md`
  Wave 1 task #12; pre-mortem `docs/plans/WAVE1-W1.3-pre-mortem-2026-08-14.md`.

_Byline: Claude Code · glm-5.2:cloud · 2026-08-14._

### CH-7 — W1.2 realization writers (ADR-0045 §A.4) — built, NOT applied/pushed

- **What:** the realization-event WRITE side of the horizon clock.
  - new `server/evidence/realization.py` — `propose_realization` (inert `'proposed'` write
    + F5 app-side guard rejecting `realized_at < min(linked occurred_at)`), `approve_realizations`
    (batch `'proposed'→'approved'`, stamps `approved_at/by`), `supersede_realization` (sanctioned
    `approval_state→'superseded'` UPDATE). `connection=` kwarg for atomic-audit + rollback-testability
    (mirrors `audit.record(connection=)`). Rides the platform write engine, not an agent's read-only
    engine (ADR-0005).
  - new `server/agents/tools/realization_tools.py` — agno `@tool` wrappers: `realization_propose`
    (plain `@tool`, inert, no HITL), `realization_approve` + `realization_supersede`
    (`@approval` + `@tool(requires_confirmation=True)` — the HITL gate). Exports `REALIZATION_TOOLS`;
    **wiring into `providers.source_tools` deferred to W1.5** (lane binding).
  - new `tests/test_realization_writers.py` (11 DB-free unit tests) + new
    `scripts/_wave1_validate_w12_realization.py` (live rollback validation, SQLAlchemy engine path).
  - **edited `sql/0026_realization_event.sql`** (NOT applied to prod): revised the
    `realization_event_approved_iff_timestamp` CHECK constraint — old form
    `(approval_state='approved')=(approved_at IS NOT NULL)` BLOCKED supersede (a superseded row
    retains approved_at → CHECK violation, found by the live validation). New form: `approved_at/by`
    are NULL iff `'proposed'`, set once at approval, retained through `'superseded'` (append-only audit).
- **Two-gate design (F6):** DB-level `visible_from` reads only `'approved'` (fail-closed backstop);
  agno `@approval` run-pause gates the approve/supersede tool bodies (HITL). DB-level PROVEN live;
  `@approval` run-level deferred to the Wave gate.
- **Safety:** 0026 NOT applied to prod (held for owner review). Nothing pushed (commit-only-when-asked).
  All validation in rollback transactions on live — zero net write. Post-check: `realization_event` /
  `realization_event_record` / `visible_from()` all ABSENT on live (0026 unapplied; rollbacks left no trace).
- **Verified:** `scripts/_wave1_validate_w12_realization.py` **17/17 PASS** (4 F6 code-level + 13 DB-level);
  `scripts/_wave1_validate_0026.py` re-run **12/12 PASS** (no regression from the CHECK fix);
  `uv run pytest -q` **688 passed / 24 skipped**; `ruff check server tests` clean;
  `mypy` clean on new modules.
- **Open (owner review):** F4 bundled-doc degenerate `visible_from` (occurred_at_max vs per-record —
  needs canon §1/ADR-0045 §A ruling; recommendation = occurred_at_max + bundle-aware function — ~~SUPERSEDED 2026-08-14 by CH-11 (D1): dissolved by ADR-0053 §3 chunk unit; do not act on this rec~~);
  F6 `@approval` run-level Wave-gate test; F5 defensive DB trigger deferred.
- **Governing record:** ADR-0045 (D-042) §A.4; approved plan `cached-waddling-crayon.md` Wave 1 task #11;
  pre-mortem `docs/plans/WAVE1-W1.2-pre-mortem-2026-08-14.md`.

_Byline: Claude Code · glm-5.2:cloud · 2026-08-14._

### CH-6 — W1.1 horizon clock migration sql/0026 (ADR-0045 §A + §A.4) — built, NOT applied/pushed

- **What:** new `sql/0026_realization_event.sql` — purely-additive: `working.realization_event` +
  `working.realization_event_record` (one event reveals many records) + `working.visible_from(record_id)`
  STABLE function (`= COALESCE(MIN(realized_at) over approved linked events, occurred_at)`) +
  supersession COMMENT on `normalized_record.realized_at`. **Deferred (pre-mortem F1):** the
  `horizon_visible` + `vw_spine_horizon` repoint to `visible_from` is NOT in 0026 — it lands in W1.3
  alongside the materialized fast path (repointing the live spine view at per-row `visible_from(r.id)`
  before the fast path exists would put a slow correlated-subquery scan on every horizon query).
- **Safety:** purely additive (no DROP/REPLACE of any existing object); the live predicate + view stay
  on the superseded `knowledge_time` (zero behavior change). 0026 NOT applied to prod; nothing pushed.
  Validated in a rollback transaction on live — zero net write.
- **Verified:** `scripts/_wave1_validate_0026.py` **12/12 PASS** (objects created; horizon_visible +
  vw_spine_horizon UNCHANGED; degenerate==occurred_at; PROPOSED inert; APPROVED moves clock; horizon_visible
  regression denies/allows/NULL/hindsight). F8 transactional guards (strip BEGIN/COMMIT, assert
  autocommit=False, double rollback, no commit anywhere) verified — DDL did NOT persist.
- **Governing record:** ADR-0045 (D-042) §A + §A.4; approved plan `cached-waddling-crayon.md` Wave 1 task #7;
  pre-mortem `docs/plans/WAVE1-pre-mortem-2026-08-14.md` (F1/F5/F8 resolutions).

_Byline: Claude Code · glm-5.2:cloud · 2026-08-14._

### CH-5 — Wave 0 doc true-up to signed ADRs (no behavior change)

- **What:** conformed living docs to already-signed ADRs (0040/0045/0053) per the
  doc-drift rule (visible strike + dated correction, never silent delete). Edits:
  `PROJECT_CANON.md` (§1 visible_from/derived-passes, §2 + §8 transcript_miner+agno 2.8.7,
  §4+§6 Weaviate cutover-verified); `AGENTS.md` (topology + §1 ADR-0045 signed/§B sanction +
  FORBIDS parallel authored stores); `server/agents/factory.py` (docstring topology adds
  transcript_miner — **docstring+comment only, zero behavior change**); `06-semantica.md`
  (Milvus/bge-m3 → Weaviate/nv-embed-v1); `workbench/api/README.md` (Milvus → Weaviate,
  data-vector DOWN note + byline); `adr/README.md` + `adr/0040` (cutover VERIFIED D-042,
  data-vector DOWN since 2026-08-10, Case Bible memsearch lane carve-out); `adr/0032` (Milvus
  → Weaviate cell); `COORDINATION.md` (context_record → ADR-0053 supersession pointer);
  `INVENTORY-2026-08-09.md:39` (agno 2.8.0→2.8.7 dated note); `DEBT.md` (records the review
  report's two REFUTED claims: disclosure_tier-hardcode-is-CORRECT per ADR-0045 N3; derived-
  tables-ADR-already-signed per §B). Report `docs/reports/mcp-platform-agno-review.md` stays
  local/untracked; corrections folded into DEBT, not committed as a report.
- **Safety:** docs + one docstring/comment edit only. No schema, code-behavior, deploy,
  DB, ingest, or external-write change. No deletion (strike-through, never delete).
- **Verified:** `uv run ruff check server tests` clean; `uv run ruff format --check`
  clean (195 files); `uv run mypy server` clean (128 files, no issues); `uv run pytest -q`
  **677 passed / 24 skipped**. Fresh-schema restore + live inventory baseline deferred to
  task #4 (needs tailnet PG 100.91.190.107) — static gate green, DB gate pending.
- **Governing record:** ADR-0040 / ADR-0045 (D-042) / ADR-0053 (D-057); approved plan
  `cached-waddling-crayon.md` Wave 0.

_Byline: Claude Code · glm-5.2:cloud · 2026-08-14._

### CH-5b — agno venv 2.8.6 → 2.8.7 (align venv to the pin)

- **What:** `uv pip install agno==2.8.7`. The venv + untracked `uv.lock` had drifted to
  2.8.6 while git-tracked `requirements.txt:3` pins `agno==2.8.7`; upgraded the venv to
  match the source-of-truth pin (reversible; source intact). No code change.
- **Decision basis:** approved plan Wave 0 task #3 ("install 2.8.7 to match pin, or pin
  2.8.6; re-verify FilterExpr either way"). Chose to upgrade the venv — the pin is the
  declared truth, the venv/lock were the stale side.
- **Verified:** FilterExpr silent-drop landmine RE-VERIFIED present in 2.8.7 at
  `agno/vectordb/weaviate/weaviate.py:414-416` + `:441-443` + `:883-884` (`_build_filter_expression`)
  — identical to 2.8.6, so GAP-01 stays CONFIRMED and the repo's dict-filter defense
  (`store.py:364-366`, pinned by `test_horizon_axes.py:76-80`) remains mandatory. Gate
  re-run with 2.8.7: `ruff` clean, `mypy server` clean, `pytest -q` **677 passed /
  24 skipped**. AGENTS.md landmine note updated to record the 2.8.7 re-verification.
- **Safety:** dev-env change only; no schema/deploy/DB/ingest/external-write change.

_Byline: Claude Code · glm-5.2:cloud · 2026-08-14._

### CH-5c — Wave 0 live inventory baseline + fresh-schema restore gate

- **What:** read-only live inventory of tailnet PG `100.91.190.107:5432` db `ai` (PG 18.1)
  via `scripts/_wave0_inventory.py` (creds regex-parsed from `~/.secrets/Agno-MCP-Platform.env`,
  never sourced/printed). Captured: 8 schemas, extensions, per-table row counts, horizon-clock
  definition, ADR-0045/0052/0053 build-state. Persisted as
  `docs/INVENTORY-BASELINE-2026-08-14.md` (signed baseline before Wave 1+). Then ran the
  fresh-schema restore gate via `scripts/_wave0_fresh_restore.py` — created throwaway DB
  `_wave0_restore_test`, applied all 25 migrations from zero, DROPPED it (zero net write to
  the live `ai` DB).
- **Verified findings:**
  1. **horizon clock is the superseded `knowledge_time` (LIVE-CONFIRMED)** —
     `working.horizon_visible` filters on `row_knowledge_time <= p_horizon`, NOT ADR-0045 §A's
     `visible_from = COALESCE(realized_at, occurred_at)`. GAP-04/N1 confirmed against the
     running DB. Wave 1 replaces it.
  2. **ADR-0045 §A/§B unbuilt** — `realization_event`, `walk_ledger` NOT BUILT.
  3. **ADR-0053 schema BUILT but EMPTY** — `chat_conversation`/`message`/`chunk` exist, 0 rows;
     `context_record` still holds 1,741 rows (the superseded legacy data).
  4. **fresh-schema restore: migrations NOT from-zero** — `0008` fails (`evidence.source`
     not created by any migration; bootstrapped outside `sql/`). Verifies the documented
     "sql/ does NOT describe the live DB" divergence; pins the precise symptom. Wave 1+ builds
     against the LIVE schema; a true from-zero restore (Wave 5) needs the bootstrap DDL
     captured first (new DEBT item).
- **Safety:** read-only SELECTs + a throwaway DB created/dropped in a `finally` block. Zero
  net write to `ai`. No deletion (throwaway DB dropped is the intended cleanup; scripts kept
  as reusable tools, untracked).
- **Governing record:** approved plan `cached-waddling-crayon.md` Wave 0 task #4; ADR-0045
  (D-042) / ADR-0052 (D-054) / ADR-0053 (D-057).

_Byline: Claude Code · glm-5.2:cloud · 2026-08-14._

## 2026-08-13

### CH-4 — ADR-0053 five-lane chat-ingestion feature branch implemented

- **What:** additive migration 0024; explicit conversation/message/chunk tables;
  post-chunk multi-label classification; selective confidence review; embed-once lane
  projections; normalized tags; whole-archive multimodal assets + optional Docling;
  per-table outboxes/cursors/dead-letter; human investigation register; runtime five-lane
  alignment; new Gemini/custom-GPT Markdown parsers; visual HTML report; canon/ADRs true-up.
- **Safety:** no live database migration, deployment, bulk ingest, or external write was
  performed. Conflicting untracked utilities/reports were moved to `to_be_deleted`, never
  deleted.
- **Verified:** PostgreSQL parser accepts migration 0024 (43 statements); Ruff lint clean;
  focused mypy clean; HTML structure and JavaScript syntax clean; full pytest suite 644
  passed / 22 skipped. Global mypy still has unrelated pre-existing errors recorded in the
  handoff/reporting; repository-wide format check has unrelated historical drift.
- **Governing record:** ADR-0053 / D-057.

_Byline: Codex · GPT-5 · 2026-08-13._

## 2026-08-12

### CH-3 — `require_tracked_code` PreToolUse hook: `.py` extension false-positive fixed
- **What:** In `~/.claude/local-plugins/plugins/case-bible/hooks/require_tracked_code.py`,
  the `EXEC_TEMP` interpreter alternation `\b(?:python3?|py|bash|sh|node|pwsh|powershell)\b`
  matched the `py` in `.py` **file extensions** (`\b` matched because the preceding `.` is a
  non-word char). Any `.py` filename was treated as the `py` interpreter, so any later `/tmp/`
  path in the same command string false-blocked legitimate staging (e.g.
  `docker cp /tmp/x.py c:/app/y.py` paired with `ssh @100.`/`docker exec`).
- **Fix:** replaced the leading `\b` with `(?<![\w.])` — a negative lookbehind rejecting
  word-char and dot prefixes — so extensions cannot pose as interpreters. Real invocations
  (`python x.py`, `bash run.sh`, `py script.py`) still match.
- **Verified:** `scripts/_test_hook_regex_tmp.py` — blocked staging now ALLOWs; real
  `python /tmp/script.py` still BLOCKs; output-redirect INTO temp still ALLOWs.
- **Why now:** the false block was preventing the live Task-3 ops (hot-patch + wipe +
  re-ingest). Owner: "Fix that hook or that file or whatever the fuck is stopping."

### CH-2 — ADR-0045 OQ-8 / D-042 amended (AI-chat context lane reverses auto-assert hindsight)
- **What:** `docs/adr/0045-horizon-clocks-and-checkpoint-derivation.md` — struck the OQ-8
  clause ("the AI-chat context lane auto-asserts `hindsight` tier at write") with a dated
  2026-08-12 correction: the context lane asserts NO tier; the horizon is a query-level
  distinction derived from clocks + HITL realization events. `docs/DECISION_LOG.md` D-056
  appended (newest-on-top).
- **Scope:** context lane only; ADR-0045 Decision C (normalized_record keeps
  `disclosure_tier` as an asserted hint) unchanged.

### CH-1 — `working.context_record` drops `disclosure_tier` (context lane = just normalized data)
- **What:** `sql/0023_drop_context_record_disclosure_tier.sql` (idempotent `DROP COLUMN`,
  applied live 2026-08-12). `server/analysis/context_chat_ingest.py` (the ONLY reader/writer
  of `context_record`) hot-patched: INSERT and `load_pending_context` SELECT no longer
  reference the column.
- **Live ops (VPS, container agentos-api-…-194330527059):** column DROPPED → confirmed
  absent in `information_schema` → 1617 `source='claude-ai-export'` test rows wiped
  (124 other-source rows untouched) → re-ingested `data-2025-12-08-batch-0001.zip` with the
  hot-patched code → **1617 rows back, `disclosure_tier` column absent** (an INSERT
  referencing a dropped column would have errored, so the patch is provably live).
- **Open / deferred (separate, not this change):** R2 nexus blob upload still `dry_run`
  (assets_materialized.uploaded=0); companion files (users.json/projects.json/memories.json)
  not yet folded into context rows; baseline `sql/bootstrap/schema_baseline.sql` still does
  NOT contain `context_record` (0021/0022/0023 applied live but baseline never regenerated —
  pg_dump --schema-only regen is the follow-up).
