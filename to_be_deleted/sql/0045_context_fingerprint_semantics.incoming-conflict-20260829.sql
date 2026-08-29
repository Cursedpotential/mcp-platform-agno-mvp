-- 0045_context_fingerprint_semantics.sql
--
-- Guarded supersession marker for the abandoned first draft of migration 0045.
-- The draft was never applied. It targeted registry tables and column names
-- that do not exist in the migration-0036 context schema, so executing it
-- would make the numbered platform migration sequence unreachable.
--
-- The byte-for-byte historical draft is preserved, not deleted, at:
--   to_be_deleted/sql/0045_context_fingerprint_semantics.broken-historical-20260829.sql
-- Only the owner may delete anything under to_be_deleted.
--
-- Migration 0048 is the governed fix-forward that installs the context
-- fingerprint vocabulary against the actual 0036 relations. This slot does
-- not mutate data or schema. It fails closed unless it is running on the
-- intended platform database after the exact 0036 foundation and before any
-- incompatible draft objects have appeared.
--
-- Byline: Codex · GPT-5 · 2026-08-29.

BEGIN;

DO $supersession_guard$
DECLARE
    v_column TEXT;
BEGIN
    IF current_database() <> 'platform' THEN
        RAISE EXCEPTION 'migration 0045 may run only in database platform, not %', current_database();
    END IF;

    IF to_regclass('context.hash_receipt') IS NULL
       OR to_regclass('context.raw_generation') IS NULL
       OR to_regclass('context.activity_execution') IS NULL THEN
        RAISE EXCEPTION 'migration 0045 requires the migration-0036 context foundation';
    END IF;

    FOREACH v_column IN ARRAY ARRAY[
        'hash_kind', 'construction', 'computed_by', 'source_version_id',
        'raw_record_id', 'raw_generation_id'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'context'
              AND table_name = 'hash_receipt'
              AND column_name = v_column
        ) THEN
            RAISE EXCEPTION 'migration 0045 requires context.hash_receipt.% from migration 0036', v_column;
        END IF;
    END LOOP;

    -- The abandoned draft invented these objects. Their presence means the
    -- database is not at the governed 0036 boundary and must be reconciled
    -- explicitly rather than pretending this no-op can repair partial state.
    IF to_regclass('context.hash_kind') IS NOT NULL
       OR to_regclass('context.hash_canon') IS NOT NULL
       OR to_regclass('context.receipt_kind') IS NOT NULL
       OR to_regclass('context.custody_chain') IS NOT NULL THEN
        RAISE EXCEPTION 'migration 0045 found incompatible abandoned-draft objects; reconcile before continuing';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'context'
          AND table_name = 'hash_receipt'
          AND column_name IN ('kind', 'canon')
    ) THEN
        RAISE EXCEPTION 'migration 0045 found abandoned-draft hash_receipt columns';
    END IF;
END
$supersession_guard$;

COMMIT;
