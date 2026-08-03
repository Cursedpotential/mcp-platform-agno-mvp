# sql/ — Progressive Disclosure Map

> PostgreSQL migrations — numbered, immutable, run once on empty data dir.

## Directory Map

```
sql/
  0001_init_extensions.sql     <- Extensions + rich domain types (citext, ltree, hstore…).
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
- Files run in order via `/docker-entrypoint-initdb.d/` on first boot only.
- On existing `pgdata` volumes, apply new migrations manually:
  `psql -U "$DB_USER" -d "$DB_DATABASE" -f sql/NNNN_name.sql`

## Bootstrap contract (2026-08-02, Codex C-02)

Two artifacts, two jobs:

- **`sql/NNNN_*.sql`** — the historical, append-only chain. Never edit an
  applied file; future schema changes keep landing here. The chain is NOT
  guaranteed to replay from an empty database (early custody/analysis DDL was
  applied out-of-band and 0012/0015 reference it).
- **`sql/bootstrap/schema_baseline.sql`** — the reproducible bootstrap: a
  structure-only capture of the ENTIRE live schema. Apply this one file to an
  empty database to reproduce production (verified 2026-08-02: 156 tables
  across 7 schemas reproduce exactly). Regenerate after any applied migration:
  `uv run python scripts/capture_bootstrap_ddl.py --host <pg-host> --verify`
