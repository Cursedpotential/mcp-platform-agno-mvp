# Migration 0036 — Context Import Foundation

> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

> Owner: Platform data plane  
> Target: fresh PostgreSQL 18 database `platform`  
> Migration: `sql/0036_context_import_foundation.sql`  
> Database status: **APPLIED AND VERIFIED** on 2026-08-27  
> Ingest status: **NOT YET LIVE-VERIFIED**  
> Legacy database `ai`: preservation source only; never apply 0036 there

## Table of contents

- [Purpose and authority boundary](#purpose-and-authority-boundary)
- [Completed production database work](#completed-production-database-work)
- [Verified bootstrap contract](#verified-bootstrap-contract)
- [Migration 0036 execution receipt](#migration-0036-execution-receipt)
- [Operator commands](#operator-commands)
- [Runtime secret handoff](#runtime-secret-handoff)
- [Failure and recovery rule](#failure-and-recovery-rule)
- [Verification boundary and remaining work](#verification-boundary-and-remaining-work)

## Purpose and authority boundary

Migration 0036 creates the context-only landing model for universal imports: retained source
objects, source versions, per-format raw records, metadata, normalized generations, exact
raw-to-normalized lineage, Activity receipts, bounded hash manifests, and reconciliation
receipts. It does not insert into or reference the custody-backed `evidence` schema, and it
cannot promote context into evidence.

## Completed production database work

The database foundation was completed against the live PostgreSQL 18 cluster on 2026-08-27:

1. The fresh database `platform` was provisioned.
2. The legacy database `ai` remained present and untouched.
3. The platform roles, memberships, database privileges, and rich migration ledger were created and
   re-read from the live cluster.
4. The rollback validator executed migration 0036 against `platform`, verified its database
   contract, rolled the transaction back, and confirmed that the preflight relation inventory was
   unchanged.
5. The apply helper committed migration 0036 to `platform`, reconnected, and independently verified
   the resulting schema, access-control contract, and migration ledger entry.

This is a database-foundation result. It does not establish that the n8n, Temporal, parser runtime,
human preview gate, or end-to-end ingest path has been deployed or live-tested.

## Verified bootstrap contract

The bootstrap apply completed with all invariants re-read after mutation. The verified contract is:

- `platform_admin`, `context_owner`, `context_import_writer`, and `context_reader` are `NOLOGIN`
  roles;
- `platform_runtime` is the dedicated `LOGIN` role;
- no platform role, including inherited runtime memberships, has `SUPERUSER`, `CREATEDB`,
  `CREATEROLE`, `REPLICATION`, or `BYPASSRLS`;
- `platform_admin` is a member of `context_owner`;
- `platform_runtime` is a member of the narrow writer and reader roles;
- `PUBLIC` does not retain `CONNECT` or `TEMPORARY` on `platform`; and
- `public.schema_version` has the rich ledger shape, its active-row uniqueness constraint, and the
  recorded platform-foundation entry.

The bootstrap tool refuses to proceed if `ai` is absent, the target is not exactly `platform`, a
runtime role or inherited membership has a dangerous attribute, or the recorded foundation hash
has drifted from the SQL file.

## Migration 0036 execution receipt

The live rollback-only validation completed successfully before the production apply:

```text
PASS: migration 0036 executed on live PostgreSQL and rolled back; 20 tables, dependencies, owners/ACLs, critical catalog objects, parent membership, and rollback inventory verified
```

The subsequent post-commit verification also completed successfully:

```text
APPLIED: migration 0036 independently verified after transaction end; context_tables=20; sha256=670ce6d6d6107fb304f922709ce5329e0ff52283600212ee5c64bde53a48a134
```

The active `public.schema_version` row for migration `0036` therefore records this committed SQL
SHA-256:

```text
670ce6d6d6107fb304f922709ce5329e0ff52283600212ee5c64bde53a48a134
```

## Operator commands

Both helpers are fail-closed to database `platform`. Use the rollback-only validator when
re-verification is required:

```powershell
uv run python scripts/validate_0036_live.py --database platform
```

The production apply command is idempotent only when the complete live schema and matching ledger
entry already exist. It refuses a partial schema or a hash mismatch:

```powershell
uv run python scripts/apply_0036_live.py --database platform --apply
```

Do not point either helper at `ai`. The scripts reject any database name other than `platform`.

## Runtime secret handoff

The password used to bootstrap `platform_runtime` was generated for that execution, kept ephemeral,
and never printed or persisted. It is not an operational deployment credential.

During Coolify configuration, generate a new runtime password and rotate `platform_runtime` in the
same controlled operation that stores the matching application secret in Coolify. Pass the value
through `PLATFORM_DATABASE_PASSWORD`; never place it in this runbook, source control, command output,
or a handoff. After rotation, verify a runtime connection with the narrow role before enabling any
ingest writer.

## Failure and recovery rule

- Before commit, any error rolls the entire migration back. Re-run the read-only inventory and
  rollback rehearsal after correcting the cause.
- After commit, do not edit 0036 and do not drop its objects as an improvised rollback. Production
  recovery is a new, reviewed forward migration (`0037` or later) that preserves any rows already
  written and records its own checksum.
- A mismatch between the live objects and the active `public.schema_version` hash is an integrity
  incident. Stop context-import writers and reconcile the mismatch before further ingestion.

## Verification boundary and remaining work

Completed database verification includes bootstrap invariants, dependency checks, exact 20-table
inventory, owners and ACLs, critical functions and triggers, same-source parent membership,
rollback cleanliness, post-commit shape, and ledger hash verification.

Still required before calling ingest functional:

1. rotate and configure the `platform_runtime` secret in Coolify without exposing it;
2. deploy the n8n, Temporal, and Go parser/runtime components;
3. verify the human preview approve/reject boundary;
4. run a live representative ingest through all required activities;
5. confirm sealed raw data, normalized publication, exact raw-to-normalized lineage, hashes, and
   reconciliation in `platform`; and
6. record the deployment revision and live integration receipts in the ingest handoff.

Migration 0036 is applied and verified at the database layer. The ingest system remains incomplete
until those production checks pass.
