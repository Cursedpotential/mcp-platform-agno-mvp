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
