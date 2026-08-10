# HANDOFF S3 — SQL & bootstrap hygiene
> _2026-08-09 · repo @ a68fabd · STATUS: READY · Depends: S2 (working image) · Blocks: S5, S6_
> Inventory items: FC, S1f, S2f, S3f, S4f, F-B(note).
> MANDATORY: read PLAN-2026-08-09-completion-master.md §Standing constraints before executing.

## Goal
A fresh database is buildable, contains the full horizon layer, and the sql/ directory tells the
truth about itself.

## Tasks
1. [FC] Regenerate `sql/bootstrap/schema_baseline.sql` — current baseline predates 0018 (verified
   by git ancestry: 6ecb2de @22:33 vs 71a4f53 @22:59) and contains NO horizon_visible /
   vw_spine_horizon / retrieval axes.
   `docker compose up -d agentos-db && docker compose run --rm agentos-api uv run python
   scripts/capture_bootstrap_ddl.py --host agentos-db --verify`
   Check: `grep -c horizon_visible sql/bootstrap/schema_baseline.sql` > 0; scratch restore can
   `EXPLAIN SELECT * FROM working.vw_spine_horizon`.
2. [S1f] sql/README.md honesty pass: numbered chain does NOT replay from empty — enumerate actual
   failures (0008–0013, 0015–0018 fail; **0014 silently no-ops** its conditional schema moves) and
   the out-of-band objects (evidence.source, analysis.device, analysis.event_source_record,
   analysis.entity, timeline_event, location, location_assertion, time_assertion). Baseline = the
   ONLY bootstrap path; numbered chain = append-only history. Add [F-B] note: 0004's colliding
   disclosure_tier enum is created-then-dropped by 0008 on replay — cosmetic, no action.
3. [S2f] New `sql/0019_reconcile_evidence_hash.sql`: idempotent `ADD COLUMN IF NOT EXISTS` bridging
   evidence.evidence_hash 5→15 columns, promoted from sql/_manual/20260802_reconcile_evidence_ddl.sql
   (cite it in the header). DDL only; evidence stays append-only; custody.py remains sole writer.
   NEVER edit 0002. Check: baseline-restored scratch DB + 0019 = 15-column table matching live.
4. [S3f] sql/validation/gen_validate_0008.py + validate_0008_working_schema.sql target
   `sql/0008_working_schema.sql`, renumbered to 0016 (per 0016:4). Retarget to 0016 if assertions
   hold, else move both to `_stale/` (never delete). Keep generic gen_validate.py.
   Check: every file under sql/validation/ references an existing migration.
5. [S4f] Rewrite `sql/drafts/walk_ledger.postgres-draft.HOLD.sql` header: the "wrong engine —
   SurrealDB" rationale is VOID (ADR-0043 retired SurrealDB). New status: superseded by ADR-0045
   Decision B — walk-ledger is the as-lived derivation log, Postgres `working.*`, built in S6.
   Keep the file as design history (do not delete; do not promote as-is).

## Acceptance
Fresh scratch DB from baseline + 0019 == live schema shape; sql/README's instructions succeed on
first attempt by a reader with no tribal knowledge; no validation/drafts file points at a
nonexistent target.

## Constraints
Standing constraints per PLAN master. NEVER edit an applied migration (0001–0018). All new SQL
files carry header citations (ADR-0045 where relevant; the _manual capture for 0019) per
traceability convention.
