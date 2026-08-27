-- sql/bootstrap/platform_foundation.sql — minimal foundation for the NEW `platform` database.
--
-- Applied by scripts/bootstrap_platform_database.py --apply, against the `platform` database
-- ONLY (never against `ai`). Every statement here is idempotent — safe to re-run against a
-- database that already has some or all of this applied.
--
-- This file is NOT part of the numbered sql/NNNN chain (that chain governs the existing `ai`
-- database only — see docs/CONVENTIONS.md "SQL / migrations"). It is a standalone bootstrap
-- artifact, mirroring the existing sql/bootstrap/schema_baseline.sql convention
-- (scripts/capture_bootstrap_ddl.py): sql/bootstrap/ holds reproducible-from-empty snapshots,
-- not historical migration steps.
--
-- Scope: the smallest extension + ledger foundation that sql/0036_context_import_foundation.sql
-- is expected to build on (per this file's authoring instructions). sql/0036 is owned by a
-- different work lane and had not landed in this checkout as of authoring (2026-08-27) — rather
-- than guess its full extension list, this file ships only what a bootstrap ledger itself needs
-- (pgcrypto, for the checksum/digest machinery scripts/bootstrap_platform_database.py uses).
-- scripts/bootstrap_platform_database.py:discover_required_extensions() reads
-- sql/0036_context_import_foundation.sql's own `CREATE EXTENSION` statements once that file
-- exists and REPORTS (never silently applies) any extension it needs beyond what is bootstrapped
-- here — see that function's docstring. Extend the list below only once 0036 is real and its
-- requirements are read, not guessed.
--
-- Roles: platform_admin / platform_runtime are created here as NOLOGIN placeholders. This
-- bootstrap only reserves the names and establishes platform_admin as the owner of the
-- foundation objects, so later ACL activation (context_owner / context_import_writer /
-- context_reader grants, once sql/0036 defines their shape) has a stable ownership boundary to
-- GRANT/REVOKE against instead of needing an ownership-transfer step first. Turning
-- platform_runtime into a connectable application role (LOGIN + password + those grants) is a
-- deliberate later step — not done here, and no password is embedded in this git-tracked file.
--
-- Byline: Claude Code · Sonnet 5 · 2026-08-27

-- uuidv7() is native on PG18 (see sql/0001_init_extensions.sql) — no extension needed for it.
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- digest()/hmac() for checksum + custody-style hashing

-- Cluster-wide roles. CREATE ROLE has no native IF NOT EXISTS, and roles are cluster-scoped
-- (not database-local), so these are guarded existence checks rather than a CREATE DATABASE-style
-- clause. Running this file against any database in the cluster has the same effect.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'platform_admin') THEN
        CREATE ROLE platform_admin NOLOGIN;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'platform_runtime') THEN
        CREATE ROLE platform_runtime NOLOGIN;
    END IF;
END $$;

-- Bootstrap/migration ledger for the `platform` database. One row per applied foundation unit;
-- the checksum column lets scripts/bootstrap_platform_database.py detect drift (a bootstrap file
-- that changed on disk after its row was recorded) and refuse to proceed rather than silently
-- re-applying or overwriting. Scoped to public because sql/0036 is expected to read/extend this
-- table directly (per this file's authoring instructions) — moving it later needs a real
-- migration, not a silent rename.
CREATE TABLE IF NOT EXISTS public.schema_version (
    version      TEXT PRIMARY KEY,
    description  TEXT NOT NULL,
    checksum     TEXT NOT NULL,
    applied_by   TEXT NOT NULL DEFAULT current_user,
    applied_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.schema_version IS
    'Bootstrap/migration ledger for the platform database. One row per applied foundation unit; '
    'checksum guards against silently re-applying a changed file. Populated by '
    'scripts/bootstrap_platform_database.py.';

ALTER TABLE public.schema_version OWNER TO platform_admin;
