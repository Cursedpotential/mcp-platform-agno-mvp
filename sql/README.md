# sql/ — Progressive Disclosure Map

> _Byline: Codex · GPT-5 · 2026-08-15 (entry-point bootstrap correction)_
> _2026-08-23 amendment: Claude Code · Opus 5 — the numbered chain is applied through `0030`
> as of tonight. Direct introspection of live PG18 (`100.91.190.107:5432`, db `ai`) showed
> `0026`–`0029` were already applied despite stale "HELD FOR OWNER / NOT APPLIED" banners
> (now restamped in the files themselves); `0030` was applied the same night on owner
> instruction. See `docs/CHANGE-ORDER.md` CH-15/CH-16. The replay-from-empty-database
> caveats below remain true and are unaffected by this note — do not replay the chain
> against an empty database; bootstrap from `sql/bootstrap/schema_baseline.sql`._
>
> PostgreSQL schema history and bootstrap artifacts. The numbered migrations
> are immutable history but **are not an empty-database bootstrap path** after
> 0007. Use `sql/bootstrap/schema_baseline.sql` for a fresh database, then apply
> only migrations newer than that baseline in reviewed numerical order.

## Directory Map

```
sql/
  bootstrap/schema_baseline.sql <- Captured structure baseline; see current-image caveat below.
  0001_init_extensions.sql     <- Historical extensions + rich domain types.
  0002_schema.sql              <- Dual-schema boundary + HITL audit tables (legacy).
  0003_normalized_records.sql  <- analysis.normalized_record (bitemporal substrate).
  0004_custom_types.sql        <- PG enums/domain types (entity_type, mcl_factor, event_type…).
```

## Schema Boundary

| Schema | Purpose | Access |
|---|---|---|
| `evidence` | Raw/source evidence | Append-only (custody.py); agents read via readonly engine |
| `analysis` | Derived artifacts | Write via approval-gated `@approval` tool |
| `public` | HITL audit + Agno-managed tables | Agno creates/owns |

## Convention

- **NEVER edit an applied migration.** Add a new `NNNN_*.sql` file.
- Do not replay the numbered chain against an empty database; it is incomplete
  by construction from 0008 onward. Bootstrap from the captured baseline.
- On existing `pgdata` volumes, apply new migrations manually:
  `psql -U "$DB_USER" -d "$DB_DATABASE" -f sql/NNNN_name.sql`

## Bootstrap contract (2026-08-02, Codex C-02; honesty pass 2026-08-09, handoff S3f)

Two artifacts, two jobs. The baseline is the structural starting point; the
current-image caveat below governs the additional ordering and migration work.

- **`sql/bootstrap/schema_baseline.sql`** — the captured structure baseline.
  It is a `pg_dump --schema-only` capture of the then-live schema. The
  2026-08-16 current-image replay caveat below means this file is presently a
  required bootstrap input, not a sufficient one-file bootstrap. Regenerate
  after any applied migration (see "Regenerating the baseline" below) — a
  stale baseline is worse than no baseline, because it looks trustworthy.
- **`sql/NNNN_*.sql`** — the historical, append-only chain. Never edit an
  applied file; future schema changes keep landing here. Read it for HISTORY
  and INTENT (every table's WHY is documented inline, the baseline has none
  of that). **Do NOT expect it to replay from an empty database — it does
  not, and has not since 0008.** See "Why the chain does not replay" below.

### Why the chain does not replay

Early custody/evidence DDL (`evidence.source`, `evidence.acquisition`'s
downstream consumers, `analysis.device`, `analysis.event_source_record`,
`analysis.entity`, `working.timeline_event`, `working.location`,
`working.location_assertion`, `working.time_assertion`, and more) was
applied directly to the live database and is captured only in
`sql/_manual/20260802_reconcile_evidence_ddl.sql` (a partial capture) and in
`sql/bootstrap/schema_baseline.sql` (the full one) — never in a numbered
migration. Every migration from 0008 onward references at least one of
these out-of-band objects, so a `psql -f 0001..0018` replay against an
empty database fails partway through. Verified by a scratch-container
replay, 2026-08-09 (evidence below is the exact failing statement per file;
"cascades" means the failure is a downstream consequence of an earlier one,
not a new missing object):

| Migration | Fails at | Cause |
|---|---|---|
| `0008_temporal_clocks_and_provenance.sql` | line 131 | `ALTER TABLE evidence.source ...` — `evidence.source` does not exist (out-of-band) |
| `0009_raw_layer_and_derivation.sql` | dynamic raw-table loop (~line 96) | the per-source `CREATE TABLE evidence.raw_<src>` template FKs to `evidence.source(id)` and `analysis.device(id)`, neither of which exist |
| `0010_extraction_candidate_and_acquisition_reconcile.sql` | line 85 | `CREATE TABLE analysis.extraction_candidate` FKs to `evidence.source(id)` |
| `0011_attestation_without_event.sql` | line 29 | `ALTER TABLE analysis.event_source_record ...` — the table does not exist (out-of-band) |
| `0012_pipeline_visibility.sql` | line 79 | `CREATE TABLE evidence.ingest_run` FKs to `evidence.source(id)` |
| `0013_raw_all_and_funnel_across_formats.sql` | line 54 | `evidence.vw_raw_all` unions the six `evidence.raw_*` tables, none of which exist (0009 never got to create them) |
| `0014_split_analysis_into_working_reference_ops.sql` | — | does NOT error; **silently no-ops instead** (see below) |
| `0015_layer_map_after_schema_split.sql` | line 72 | `evidence.vw_layer_map` reads `ops.workflow_run` / `ops.processing_run` / `ops.tool_call_ledger`, which 0014's no-op left uncreated |
| `0016_working_gate_layer.sql` | line 527 | `COMMENT ON TABLE working.extraction_candidate` — the table doesn't exist because 0014 no-op'd the move that was supposed to put it there |
| `0017_append_only_guards.sql` | line 36 | trigger on `working.source_provenance`, uncreated because 0016 already failed |
| `0018_retrieval_axes.sql` | line 85 | dynamic GIN-index loop over `working.*` tables that were never created |

**0014 does not fail — it silently no-ops.** Its three `DO $$` blocks move
tables/views/functions from `analysis` into the new `working` / `reference`
/ `ops` schemas, but every move is guarded by
`IF EXISTS (... WHERE table_schema='analysis' AND table_name=t)`. On the
LIVE database those tables exist in `analysis` (out-of-band history), so the
guard passes and the move runs. On a fresh chain-only replay none of those
tables were ever created in `analysis` in the first place (upstream
failures, or never created by the chain at all), so the guard is false for
every single entry, the loop body never executes, and `0014` commits
successfully having done nothing but create three empty schemas. Nothing in
`0014`'s own output distinguishes "moved 43 tables" from "moved zero
tables" — that is what "silently" means here.

**[F-B] cosmetic note, no action needed:** `0004:32` creates
`CREATE TYPE disclosure_tier AS ENUM (...)`, and `0008:548` runs
`DROP TYPE IF EXISTS public.disclosure_tier` as part of resolving a name
collision with `analysis.normalized_record.disclosure_tier` (a live TEXT
column, unrelated to the enum). On a full replay this means the type is
created by 0004 and then dropped six migrations later by 0008 — cosmetic
churn, not a defect, and 0008:515-548 documents the collision and the
resolution inline. No fix required.

**Bottom line:** the numbered chain is a truthful, append-only RECORD of
design decisions (read it for the "why"). It is not, and per the above
cannot currently be, a from-zero bootstrap path. Start a fresh dev/test
database from `sql/bootstrap/schema_baseline.sql`, then follow the
current-image extension-order and post-baseline migration caveat below.

### Regenerating the baseline

`scripts/capture_bootstrap_ddl.py` captures the baseline from the LIVE
database. It shells out to `pg_dump.exe` / `psql.exe` from a local
PostgreSQL 18 client install and is written to run from the owner's
workstation (not from inside a container — the platform's own containers
are Linux and do not carry a Windows PG client), reaching the live host
over the tailnet. It is NOT safely runnable from a sandboxed/CI environment
that cannot reach the production database.

**~~C1 PENDING~~ C1 DONE — executed against live 2026-08-10 (Claude Code · Fable 5).**
Ran from the owner's workstation over the tailnet: `verify: PASS — clean bootstrap
reproduces the live schema`. Per-schema table counts all matched (ai 23 · analysis 31 ·
evidence 19 · ops 5 · public 17 · reference 14 · working 47 = 156 tables); the
regenerated baseline carries `horizon_visible` (×5) and the
vw_spine_horizon/retrieval-axis/realization_event objects the stale baseline lacked.
**This also resolves the 2026-08-09 triage doc's UNVERIFIED #1: the live DB is fully
migrated — ops (audit ledger), working (0016 gate layer), and 0018 retrieval axes are
all present live.** The command, kept for the next regen:

> **2026-08-16 current-image re-verification (Codex · GPT-5):** Directly replaying the
> committed baseline into the isolated `horizon_scratch` target failed because the dump
> creates `pg_duckdb` before conventional extensions; later extension-script `GRANT`s were
> intercepted as MotherDuck operations. Pre-creating the conventional extensions before
> `pg_duckdb` allowed the structure-only restore. Source inspection also proved the committed
> baseline does **not** contain `ops.audit_ledger`; `0019`–`0020` and then `0021`–`0030` were
> required to reach the reviewed scratch state. Until a deterministic bootstrap wrapper or a
> regenerated, current-image-verified baseline lands, do not describe this file alone as a
> complete reproducible bootstrap. No production database was mutated during this proof.

```
# Prerequisites on the machine running this (NOT a container):
#   - Tailscale connected, so 100.91.190.107 (ovh-files, live Postgres host
#     per compose.exec.yaml's PG_HOST override) is reachable
#   - PostgreSQL 18 client tools installed at
#     C:\Program Files\PostgreSQL\18\bin  (pg_dump.exe / psql.exe — must be
#     v18 to match the server; scripts/capture_bootstrap_ddl.py:38 hardcodes
#     this path)
#   - Python env with `uv` and the repo's deps synced
#     (uv pip sync requirements.txt — pulls in psycopg[binary] + sqlalchemy,
#     already pinned there)
#   - Repo checked out locally, with .env (or exported env vars)
#     carrying DB_USER / DB_PASS / DB_DATABASE for the live database
#     (matching the credentials the data-pg-files Coolify app runs with)

cd <repo-root>
uv run python scripts/capture_bootstrap_ddl.py --host 100.91.190.107 --verify
```

`--verify` restores the fresh capture into a scratch database on the same
server, compares per-schema table counts against live, and drops the
scratch DB — no data ever moves, structure only. After it reports `PASS`:

```
grep -c horizon_visible sql/bootstrap/schema_baseline.sql   # expect > 0
```

(the current committed baseline predates `0018_retrieval_axes.sql` — verified
by git ancestry, `6ecb2de` @22:33 vs `71a4f53` @22:59 — and contains no
`horizon_visible` / `vw_spine_horizon` / retrieval-axis objects; this
command is how the owner/coordinator confirms the regenerated baseline
fixes that). This step could not be performed in this pass: it requires a
route to the live production database, which is unreachable from a sandbox
by design.
