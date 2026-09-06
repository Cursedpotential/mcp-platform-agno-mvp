# Fresh `platform` baseline recovery — Matter/UIW prerequisite

> _Byline: Codex · GPT-5 · 2026-08-29._
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

STATUS: READ_ONLY_RECOVERY_COMPLETE  
LIVE_MUTATION: NONE  
RELEASE_GATE: HOLD UNTIL A PLATFORM-NATIVE MATTER FOUNDATION EXISTS

## Result

The fresh `platform` database is not missing migration 0043 by itself. It is missing the
**platform-native Matter/CourtCase prerequisite that 0043 references**.

`analysis.court_case` currently exists only in `sql/0030_matter_case_foundation.sql`. Migration 0030
belongs to the legacy `ai` chain and is not safe to replay on the context-only `platform` database:
it also alters or references `analysis.evidence_item`, `working.normalized_record`,
`evidence.evidence_hash`, `evidence.source`, `evidence.file_node`, and `ops.processing_run`. Those
objects are not supplied by `sql/bootstrap/platform_foundation.sql` or migration 0036.

Therefore:

- do **not** apply legacy migration 0030 to `platform`;
- do **not** restore `sql/bootstrap/schema_baseline.sql` into `platform` (it is a capture of legacy
  `ai` state and includes legacy schemas/framework tables);
- do **not** apply 0043 until the Matter/CourtCase parent tables, ownership, and runtime grants are
  present;
- do **not** rebuild or drop `platform` merely because it currently has no application data. An
  additive repair is smaller and preserves the verified 0036/0037/0038/0039/0042 receipts.

The reported Workbench `GET /api/matters` HTTP 500 is consistent with the missing
`analysis.matter` table because `server/case_management/repository.py` queries that table directly.
That is not yet a complete causal proof: a sanitized live application log and deployed database
target check must still prove that the spine serving `/v1/matters` is connected to `platform` and
that the database error is `undefined_table`, rather than a separate connectivity or authorization
failure.

## Expected migration sequence for the current UIW slice

The verified/recorded fresh-database sequence is:

1. `0000_platform_foundation` via `sql/bootstrap/platform_foundation.sql`;
2. `0036_context_import_foundation`;
3. `0037_platform_runtime_connect`;
4. `0038_platform_runtime_schema_version_probe`;
5. `0039_context_source_retention_lock`;
6. `0042_context_hash_bytea_slice`.

Migrations 0040 (GraphRAG evaluation) and 0041 (run events) are independent feature slices, not
prerequisites for Matter-bound UIW intake. The current durable status says 0041 is unapplied; the
live status of 0040 was not established in this lane and must be read from the ledger before any
release packet is assembled.

The missing continuation is:

7. a new, platform-native Matter/CourtCase foundation containing only the first-slice contract;
8. the current `0043_context_source_matter_binding.sql` behavior, after that prerequisite.

Because the current 0043 has not been applied and its columns/ledger receipt are absent, the clean
numerical repair is to reserve 0043 for the new Matter foundation and renumber the existing binding
to 0044 in one reviewed change. This is allowed only after a live recheck proves there is no active
0043 receipt, no 0043 columns, and no partially created constraint. If any of those exist, stop and
use a new forward migration instead; never rewrite an applied migration.

The platform-native Matter foundation required by the current API is narrower than legacy 0030:

- `analysis.matter`;
- `analysis.court_case`, including `UNIQUE (id, matter_id)`;
- `analysis.matter_knowledge_partition`;
- the case-management updated-at function/triggers and indexes used by those three tables;
- no seed/fake Matter or CourtCase row;
- no evidence promotion tables, evidence-table alterations, or legacy `ai` dependencies.

The owner-selected Matter/CourtCase should be created through the live Matter API after schema proof,
not invented in migration SQL.

## Role and apply contract

The target database is exactly `platform`. The legacy database `ai` remains read-only preservation
state and must not receive any DDL.

- The connection is made by an existing cluster administration identity authorized to assume the
  migration role; no credential or secret-bearing connection string is printed or persisted here.
- All application DDL and ledger writes execute under `SET LOCAL ROLE platform_admin` or a reviewed
  narrow object-owner role.
- `platform_admin` remains `NOLOGIN`; `platform_runtime` remains the ordinary `LOGIN` identity and
  receives no schema creation, DDL, role administration, superuser, database creation, replication,
  or RLS-bypass capability.
- Match the context-role pattern with narrow case-management roles (recommended names:
  `case_management_owner`, `case_management_writer`, `case_management_reader`). Make
  `platform_admin` a member of the owner role and `platform_runtime` a member of reader/writer.
  Grant only `USAGE` on `analysis`, required `SELECT`/`INSERT`/bounded `UPDATE` on the three Matter
  tables, and required function execution. Grant no `DELETE` and no direct DDL to runtime.
- Apply each migration and its SHA-256 `public.schema_version` receipt in one transaction under one
  advisory lock, then reconnect and verify independently.

The newest owner authentication ruling also means the existing database helpers must not be used
unchanged for this recovery: `bootstrap_platform_database.py`, `apply_0036_live.py`, and their
validators resolve database passwords from `.env`/environment files, while the current ruling
forbids introducing or relying on password environment variables. The execution packet must use an
already approved server-side authentication/secret mechanism, or pause for an owner-supplied
credential if PostgreSQL authentication actually requires one. It must not invent a password.

## Existing tooling assessment

| Tool/artifact | Safe target fence | What it can do | Recovery limitation |
|---|---|---|---|
| `scripts/bootstrap_platform_database.py` | Accepts only database `platform`; checks that `ai` exists but does not write to it | Creates the minimal database/roles/ledger foundation | Not a full application baseline; changes the runtime password and reads password material from env/file sources, contrary to the newest owner ruling |
| `scripts/apply_0036_live.py` + validator | Accept only `platform`, use advisory lock, role/shape/hash checks | Apply/verify the 20-table context foundation | Cannot create Matter/CourtCase; credential loading is env/file based |
| 0037/0038/0039/0042 apply + validate helpers | Accept only `platform`, ledger/hash guarded | Apply their narrow forward corrections | Do not supply Matter/CourtCase |
| 0040/0041/0043 | SQL/static tests only | Feature DDL | No guarded production apply helper; 0043 also lacks its parent table |
| `sql/bootstrap/schema_baseline.sql` | No fresh-`platform` target fence | Restores captured legacy structure | Must not be used for D-091 `platform`; it carries legacy `ai` structure and does not represent a reviewed consolidated replacement baseline |

Existing tooling can create the **minimal** fresh database without writing to legacy `ai`, but no
existing script can safely apply the complete baseline required by the current Matter-bound UIW
slice.

## Smallest safe recovery sequence

1. Re-read `platform` in a read-only transaction. Confirm exact database, session/effective role,
   owner, role attributes/memberships, active ledger rows/hashes, relation/constraint inventory, and
   row counts. Confirm `ai` separately only by database identity/presence; issue no query or DDL in it.
2. Confirm the current database is data-empty for the affected slice (`context.source`,
   `context.source_version`, and all prospective Matter tables). Data emptiness simplifies proof but
   does not authorize dropping the database.
3. Implement the narrow platform Matter foundation and a guarded rollback validator/apply helper.
   Renumber the unapplied binding to 0044 only if the live 0043-absence checks all pass.
4. Run static tests, then apply the new migrations inside an outer rollback against a disposable
   scratch database created from the **current platform foundation/current active migrations**, not
   from the legacy baseline.
5. Run a rollback-only rehearsal against live `platform`: advisory lock, prerequisite checks,
   migration execution, catalog/ACL/FK exercises, rollback, and exact before/after inventory equality.
6. Apply the Matter foundation and binding in reviewed numerical order, each with an atomic ledger
   receipt. Reconnect after each commit and prove its hash, owners, ACLs, constraints, and runtime
   behavior.
7. Confirm the deployed spine targets `platform` using `platform_runtime` through the approved secret
   mechanism. Prove `GET /v1/matters` and Workbench `GET /api/matters` return 200 with an empty list.
8. Create the real owner-selected Matter/CourtCase through the API, then live-prove list/detail and a
   bound UIW start. Do not seed placeholder case data in SQL.

## Proof queries

Run these as read-only/preflight queries with values redacted in receipts:

```sql
SELECT current_database(), session_user, current_user;
SELECT pg_get_userbyid(datdba) AS database_owner
FROM pg_database WHERE datname = 'platform';

SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
       rolreplication, rolbypassrls
FROM pg_roles
WHERE rolname IN ('platform_admin', 'platform_runtime',
                  'context_owner', 'context_import_writer', 'context_reader')
ORDER BY rolname;

SELECT migration_id, status, encode(ddl_hash, 'hex') AS ddl_hash
FROM public.schema_version
WHERE status = 'active'
ORDER BY migration_id;

SELECT to_regclass('context.source_version') AS source_version,
       to_regclass('analysis.matter') AS matter,
       to_regclass('analysis.court_case') AS court_case,
       to_regclass('analysis.matter_knowledge_partition') AS matter_partition;

SELECT count(*) AS source_count FROM context.source;
SELECT count(*) AS source_version_count FROM context.source_version;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'context' AND table_name = 'source_version'
  AND column_name IN ('matter_id', 'court_case_id')
ORDER BY column_name;

SELECT conname, contype, convalidated, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid IN (
  'analysis.court_case'::regclass,
  'analysis.matter_knowledge_partition'::regclass,
  'context.source_version'::regclass
)
ORDER BY conrelid::regclass::text, conname;
```

The final constraint query is post-apply only; preflight must use `to_regclass` guards instead of
casting an absent relation to `regclass`.

Post-apply also prove, under `SET LOCAL ROLE platform_runtime` in a rollback-only test transaction:

- all three Matter tables are readable;
- one complete Matter + primary CourtCase + partition can be inserted atomically;
- a cross-Matter `(court_case_id, matter_id)` binding is rejected;
- an unpaired Matter/CourtCase binding is rejected;
- `DELETE`, schema creation, table creation, role creation, and direct ledger access beyond the
  0038 column grant are rejected;
- rollback returns every affected row count to its pre-test value.

## Validation performed in this lane

No database or Coolify mutation was performed. Static/local contract validation passed:

```text
uv run pytest -q tests/test_platform_database_bootstrap.py
  tests/test_0036_context_import_foundation.py
  tests/test_0037_platform_runtime_connect.py
  tests/test_0038_platform_runtime_schema_version_probe.py
  tests/test_0039_context_source_retention_lock.py
  tests/test_0042_context_hash_bytea_slice.py
  tests/test_0043_context_source_matter_binding.py
  tests/test_matter_migration.py

131 passed in 3.81s
```

These tests validate repository contracts only. They do not prove the live database state, the
deployed spine database target, runtime privileges, migration apply, or Workbench behavior.

