# Wave 1 Sub-Plan — Temporal truth + horizon enforcement

> **ADR-0059 supersession addendum (2026-08-18, Codex · GPT-5):** This is a historical plan.
> Replace universal realization/occurrence visibility with source-class availability; keep actual
> third-party participants with owner absent, plural realization links, and derived chunks. Add
> healthy same-walk checkpoint/resume separately from terminal seal/linked rewalk. Nothing here is
> newly authorized for deployment or live migration.

> **STATUS CORRECTION 2026-08-15:** code and migrations 0026–0029 now exist in
> the dirty tree, but the independent R0 replay found cutover-blocking defects.
> They remain uncommitted, unapplied, and quarantined from product execution.
> Read `../HANDOFF-2026-08-15-R0-wave1-audit.md` before this historical plan.
> _Correction byline: Codex · GPT-5 · 2026-08-15._


> _Byline: Claude Code · glm-5.2:cloud · 2026-08-14_
> Executes **ADR-0045** (signed D-042, Option A + A.4 amendment) + the §B checkpoint-derivation
> architecture. This is THE core wave — the knowledge-horizon mechanism the project exists to build.
> ~~**Status: DRAFT for owner sign-off — no code/migration written yet.**~~
> Superseded by the correction above.

## Governing rules (non-negotiable, from ADR-0045)

- **Horizon clock:** `visible_from = COALESCE(earliest APPROVED realization_event for the record, occurred_at)`.
  Option A (predicate-computed + expression index, NOT a stored column).
- `knowledge_time` = row-write audit only (never a horizon input). `acquired_at` = custody metadata
  only (NEVER a horizon input). `disclosure_tier` = asserted hint (parser hardcode STAYS — Decision C).
- **Build order (ADR-0045 Consequences, "non-negotiable"):** clock migration → realization writers →
  derivation engine → DB grants → agent lane bindings. **Do NOT bind readers before the derivation
  lands** (admits the whole corpus while appearing correct).
- Realizations are HITL-confirmed via agno native `@approval` (ADR-0002) — same mechanism as
  `apply_db_modification` in `server/agents/factory.py`. Nothing becomes visible-from-truth unapproved.
- Fail-closed: missing case/actor/horizon/approval/clock context → zero rows + raised error;
  hindsight is an explicit grant, never a default.
- Evidence spine is NEVER modified. `normalized_record` stays append-only; knowledge accumulates
  alongside it in the events table.
- Migration is append-only (after `0025`); validated inside a rollback transaction on the live DB
  (proves it applies to the real schema, per the Wave 0 finding that `sql/` alone isn't from-zero);
  backup-before-apply; bootstrap regenerated to carry the horizon layer (ADR-0045 FC).

## Code reality (verified this session)

- `working.horizon_visible()` (live) filters on `row_knowledge_time <= p_horizon` → **inert** (N1).
- `server/contracts/records.py::finalize()` stamps `knowledge_time = now()` for every unset record → N1 root cause in code.
- `server/evidence/store.py::horizon_axes()` emits `knowledge_time` (MAX) + `occurred_at_min/max` into Weaviate metadata → N1 propagated to the vector store. Emits NO `visible_from`.
- `server/evidence/retrieval.py::evidence_search()` **already reads `visible_from`** from metadata (falls back to `occurred_at_min`) — the READ seam is built; only the WRITE side is missing.
- `normalized_record` already has a `realized_at` column (0008:232) — superseded as SoT by the events table per A.4 (becomes audit-only; migration adds the supersession COMMENT).

## Gated sub-steps

### W1.1 — Clock migration `sql/0026_realization_event.sql`

Append-only; applied to the **live** schema (the authority — `sql/` is not from-zero, per Wave 0 finding).

- **`working.realization_event`** (append-only; no UPDATE of approved rows — supersede by a new event):
  `id UUID PK`, `case_id TEXT DEFAULT 'primary'`, `kind TEXT NOT NULL` (CHECK: `contradiction |
  export_read | told_by_person | manual` + extensible), `realized_at TIMESTAMPTZ NOT NULL`,
  `trigger_record_id UUID NULL REFERENCES working.normalized_record(id)`,
  `evidence_pointer JSONB` (the contradicting later record / export reference), `proposer TEXT NOT NULL`
  (CHECK: `algorithm | owner`), `approval_state TEXT NOT NULL DEFAULT 'proposed'` (CHECK: `proposed |
  approved | superseded`), `proposed_at TIMESTAMPTZ DEFAULT now()`, `approved_at TIMESTAMPTZ NULL`,
  `approved_by TEXT NULL`. Indexes on `(case_id, approval_state, realized_at)` and `(trigger_record_id)`.
- **`working.realization_event_record`** (link table, one event → many records):
  `realization_event_id UUID FK`, `normalized_record_id UUID FK working.normalized_record(id)`,
  `case_id TEXT`, PK `(realization_event_id, normalized_record_id)`.
- **Repoint `working.horizon_visible()`** to the events table: a SQL function/view
  `working.visible_from(record_id)` = `COALESCE(MIN(realized_at) FROM realization_event r JOIN
  realization_event_record l WHERE r.approval_state='approved' AND l.normalized_record_id=record_id,
  (SELECT occurred_at FROM normalized_record WHERE id=record_id))`; predicate changes to
  `visible_from <= p_horizon` (keep the `actor` + `disclosure_tier <> 'hindsight'` guards).
  Expression index on `visible_from`.
- **`working.walk_ledger`** (§B as-lived checkpoints) — **DEFERRED to W1.3.** ADR-0045 §B makes the
  derivation/refresher engine the SOLE writer of the walk ledger, and
  `sql/drafts/walk_ledger.postgres-draft.HOLD.sql` (walk_run + walk_step + walk_step_retrieval + 2
  views) must be *reconciled against the refresher contract, not lifted unmodified* (per the draft's
  own supersession header). The clock migration (W1.1) therefore stops at the horizon CLOCK;
  the walk ledger lands with the engine that writes it (W1.3). Its contamination view must use
  `working.visible_from(record_id) > horizon_at`, not the draft's superseded `knowledge_time`.
- COMMENT the on-row `realized_at` column (0008) as superseded-by-events-table (audit-only) — doc-drift rule.
- Keep `knowledge_time` (already commented SUPERSEDED); do NOT touch `disclosure_tier` or the parser hardcode.

**W1.1 gate:** migration applies inside a rollback transaction on live; `working.visible_from()`
returns `occurred_at` for records with no approved realization (degenerate-but-correct: zero events
→ everything visible at its occurrence date, which is the as-lived truth before any discovery);
returns `realized_at` only when an approved event exists.

### W1.2 — Realization writers (propose) + native @approval

- A registered capability `realization.propose` (CLI/API/MCP-composable tool, per ADR-0052 tool-not-agent
  pattern): algorithm (Part 2 analysis, later) or any ingest lane PROPOSES events + record links.
- Owner approves in batches through the agno `@approval` queue (ADR-0002). `contradiction` events
  double as the lie register (assertion date + found-out date in one approved row).
- Unapproved events change `visible_from` for NO record (fail-closed).

### W1.3 — Derivation engine (justified custom — new DEBT row)

- The SOLE writer of pass corpora. One predicate implementation serves both schedules + tests (resolves F-E).
- **As-lived (incremental):** per walk step, append the newly-visible slice (`visible_from` in the step's
  horizon window) to the pass corpus; chain-hash each step (`prev_hash`) → these step records ARE
  `working.walk_ledger`.
- **Hindsight (on-prompt):** full materialization against the same pinned base_version.
- Every checkpoint records `base_version`, parameters, `corpus_hash`, `prev_hash`, and hash-attests to
  `ops.audit_ledger`. Re-derivation at the same base_version MUST reproduce the identical hash before
  any agent binds.
- Update `store.py::horizon_axes()` to emit `visible_from` (COALESCE of earliest approved realization,
  occurred_at_min) into Weaviate metadata; keep `knowledge_time` as audit-only. `retrieval.py` needs
  no change (already consumes `visible_from`).
- `records.py::finalize()`: keep stamping `knowledge_time=now()` for audit; add a note that it is no
  longer a horizon input (doc-drift).

### W1.4 — DB grants

- Refresher role = SOLE writer of pass tables/collections (grant-enforced INSERT on `walk_ledger` + pass
  corpus tables). Agents hold SELECT on their OWN pass corpus only, and NO grant on canonical base
  tables (`normalized_record`, `realization_event`).

### W1.5 — Agent lane bindings — ONLY after W1.3 lands

- Wire agent readers to the derivation (pass corpora), never to the canonical base. Graphiti stays
  separate as the ignorant agent's accumulating belief state (per-(case, pass) groups). Analysis/
  observation tables append with `(pass_id, run_no, base_version)`.

## Wave 1 gate (adversarial, per approved plan)

- Historical message visible at its occurrence date (degenerate path: no realization → `visible_from=occurred_at`).
- Later-discovered fact HIDDEN until an approved realization event exists; visible after.
- Unapproved realization event changes NO `visible_from`.
- A planted future fact never enters an earlier as-lived checkpoint (pre-top-k, in PG + the walk).
- Re-derivation at the same base_version reproduces the identical hash.
- Missing HorizonContext → zero rows AND a raised error (fail-closed).
- Deployment flag `HORIZON_DERIVATION_ENABLED` default-OFF until the gate passes.

## Scope / sequencing note

W1.1 (migration + horizon_visible repoint + store.py/records.py) is a coherent, testable first slice
that closes N1 at the predicate level and makes the read/write seam consistent — it can land and
gate before W1.2-W1.5. W1.2-W1.5 build the derivation + grants + bindings on top. Recommend building
**W1.1 first, gate it, then continue** — so the core clock is correct before any realization writers
or derivation engine are added. (Owner's "build underway (Wave 1)" framing in canon §1 refers to the
whole wave; this sub-plan sequences it.)

## What I will NOT do

- Remove the parser `disclosure_tier` hardcode (ADR-0045 Decision C — it is correct).
- Touch the `ai.disclosure_horizon` enum or `analysis.time_assertion`/`timeline_event` (§C — no type migration).
- Design parallel AUTHORED as-lived/hindsight stores (§B — forbidden; only DERIVED materializations).
- Bind agent readers before W1.3 (admits the whole corpus while appearing correct).
- Filter by horizon at the extraction layer (Semantica reads everything — ADR-0043).
