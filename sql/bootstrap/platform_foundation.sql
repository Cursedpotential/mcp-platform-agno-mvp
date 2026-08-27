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
-- builds on. sql/0036 now exists (Codex · GPT-5 · 2026-08-26, additive `context` schema for the
-- UniversalImportWorkflow) and, confirmed by reading it, declares ZERO `CREATE EXTENSION`
-- statements of its own — it relies on `uuidv7()` (native on PG18) and `digest()` (pgcrypto,
-- already shipped below). This file's minimal extension set already covers it; no extension list
-- change was needed. scripts/bootstrap_platform_database.py:discover_required_extensions() still
-- cross-checks 0036 live rather than trusting this note, so a future 0036 revision that adds an
-- extension is still caught and reported, not silently missed.
--
-- Roles: platform_admin / platform_runtime / context_owner. platform_admin owns the foundation
-- objects and is a member of context_owner (`GRANT context_owner TO platform_admin` below), so it
-- can administer the `context` schema sql/0036 creates without a separate ownership-transfer step.
-- platform_runtime is created LOGIN-less and with SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS
-- explicitly and permanently OFF (owner directive) — it is the eventual application runtime role
-- and must never hold cluster-wide or row-security-bypassing power, only whatever
-- context_import_writer/context_reader grants a later ACL-activation step adds once sql/0036's
-- write/read surface is stable. That later step (LOGIN + password + those two roles + grants) is
-- deliberately NOT done here, and no password is embedded in this git-tracked file.
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

-- Explicit, not merely default: SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS are stated OFF so intent
-- is grep-able in the DDL itself, not just implied by CREATE ROLE's unstated defaults.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'platform_runtime') THEN
        CREATE ROLE platform_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'context_owner') THEN
        CREATE ROLE context_owner NOLOGIN;
    END IF;
END $$;

-- Idempotent: re-granting an already-held role membership is a silent no-op in Postgres.
GRANT context_owner TO platform_admin;

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
