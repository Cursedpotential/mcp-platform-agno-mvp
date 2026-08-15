# Live Inventory Baseline — 2026-08-14 (Wave 0)

> _Byline: Claude Code · glm-5.2:cloud · 2026-08-14_
> Signed read-only snapshot of the live tailnet PG **before** any Wave 1+ change.
> Source: `scripts/_wave0_inventory.py` + `scripts/_wave0_fresh_restore.py` run against
> `100.91.190.107:5432` db `ai` (PG 18.1). Credentials parsed by regex from
> `~/.secrets/Agno-MCP-Platform.env`; never sourced/printed. Read-only + throwaway-DB
> restore (dropped after); zero net write to the live `ai` DB.

## Server

- PostgreSQL 18.1 (Debian), x86_64.
- Schemas: `ai`, `analysis`, `duckdb`, `evidence`, `ops`, `public`, `reference`, `working`.
- Extensions: pg_duckdb 1.1.0, vector 0.8.6 (pgvector), postgis 3.6.4, pg_trgm, pgcrypto,
  btree_gin, btree_gist, citext, hstore, ltree, fuzzystrmatch, unaccent, pg_stat_statements.

## Headline finding — horizon clock is the superseded `knowledge_time` (LIVE-CONFIRMED)

`working.horizon_visible(row_case_id, row_knowledge_time, row_disclosure, row_actor, p_case_id, p_horizon, p_actor)`
filters on **`row_knowledge_time <= p_horizon`** — the **superseded** `knowledge_time`
clock, NOT ADR-0045 §A's `visible_from = COALESCE(realized_at, occurred_at)`. The horizon
predicate is therefore **inert** relative to the signed decision. This is GAP-04 / INVENTORY
N1, now confirmed against the **running DB** (not just source). Wave 1 replaces it.

Full definition (verbatim from `pg_get_functiondef`):

```sql
CREATE OR REPLACE FUNCTION working.horizon_visible(
  row_case_id text, row_knowledge_time timestamptz, row_disclosure text, row_actor text,
  p_case_id text, p_horizon timestamptz, p_actor text DEFAULT 'owner')
RETURNS boolean LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT row_case_id = p_case_id
     AND (
          p_horizon IS NULL                       -- hindsight: no cutoff
          OR (row_knowledge_time IS NOT NULL
              AND row_knowledge_time <= p_horizon
              AND row_actor = p_actor
              AND row_disclosure <> 'hindsight')  -- never leaks backwards
     );
$$
```

## Build-state vs signed ADRs (verified)

| Concern | Live state | ADR | Wave |
|---|---|---|---|
| `working.realization_event` (horizon clock) | **NOT BUILT** | ADR-0045 §A | Wave 1 |
| `working.walk_ledger` (derivation checkpoints) | **NOT BUILT** | ADR-0045 §B | Wave 1 |
| `working.entity_candidate` / `claim_candidate` | **NOT BUILT** | ADR-0052 Q6 | Wave 3 |
| legacy `candidate_entity`/`candidate_event`/`candidate_fact`/`extraction_candidate` | exist, 0 rows | (pre-0052) | Wave 3 supersede |
| `chat_conversation`/`chat_message`/`chat_chunk` (+lane/embedding/projection) | **BUILT, 0 rows** | ADR-0053 | populate (data in `context_record`) |
| `chat_cdc_cursor`, `chat_projection_dead_letter` | exist, 0 rows | ADR-0052/0053 outbox | Wave 2 |
| `working.context_record` | **1,741 rows** (ADR-0053-superseded) | ADR-0053 | migrate → chat_* tables |

## Data state (design-phase; test data disposable per owner ruling)

| Table | Rows | Note |
|---|---|---|
| `evidence.source` | 3 | evidence spine minimal |
| `evidence.evidence_hash` | 3 | |
| `working.normalized_record` | 11 | the one authored store |
| `analysis.human_label` | 1,918 | **PRECIOUS** curated labels |
| `analysis.human_label_gold` | 1,918 | **PRECIOUS** gold set |
| `ai.platform_context_contents` | 488 | context corpus |
| `ai.agno_spans` | 1,649 | operational telemetry |
| `ai.agno_traces` | 1,275 | operational telemetry |
| `ai.agno_learnings` | 4 | |
| `ops.audit_ledger` | 7 | ADR-0045 §B attestation target |
| `ops.workflow_run_stage` | 8 | |
| `evidence.raw_rejected` | 0 | GAP-02: zero writers (no reject accounting) |

`evidence.*` and most `working.*` raw/candidate tables are 0 rows — consistent with
the disposable-test-data design phase. Only `reference.*` + `analysis.human_label*` are
precious; never architect around preserving test rows.

## Fresh-schema restore gate — RESULT: migrations are NOT a from-zero build

Throwaway DB `_wave0_restore_test` created, 25 migrations (`sql/0001`–`0025`) applied
in order from zero:

- `0001`–`0007`: applied clean.
- **`0008_temporal_clocks_and_provenance.sql` FAILED: `relation "evidence.source" does not exist`.**
- Throwaway DB dropped (no net write to `ai`).

Root cause: **no migration in `sql/` CREATEs `evidence.source`** — `0008` only `ALTER`s
(line 130) and indexes (line 133) it, assuming a pre-existing base schema. `docker/postgres/`
contains only a `Dockerfile` (no init SQL), so the base schema is bootstrapped outside the
tracked migrations (runtime `docker-entrypoint-initdb.d` mount or one-off VPS DDL).

This freshly verifies the documented divergence (memory: *"sql/ does NOT describe the live
132-table DB"*) and pins a precise symptom: the numbered migrations **cannot rebuild the
schema from zero** without the missing bootstrap DDL.

**Implication for the plan:**
- Wave 1+ append-only migrations build against the **live** schema (the authority), not a
  fresh-from-`sql/` rebuild.
- A true from-zero restore (Wave 5 restore-drill gate) requires the bootstrap DDL to be
  captured into the repo first — currently a gap. Action: capture the live bootstrap schema
  (or the `docker-entrypoint-initdb.d` source) so `sql/` + bootstrap is a complete restore.
- This is a **DEBT** item, not a Wave 0 blocker — the live schema is intact and serves as
  the build base; only the reproducible-restore property is incomplete.

## Gate summary (Wave 0)

- Static gate: GREEN (ruff clean, mypy clean, pytest 677 passed / 24 skipped).
- Live inventory: captured (this doc).
- Fresh-schema restore: **migrations-not-from-zero** finding recorded (above); throwaway
  DB dropped, zero net write. Live `ai` DB untouched.

## Cleanup

- `scripts/_wave0_inventory.py` — reusable read-only inventory tool (kept).
- `scripts/_wave0_fresh_restore.py` — reusable migration-from-zero proof (kept; creates
  + drops a throwaway DB only).
- Both are untracked working files; not committed this session.