-- Migration 0045: Context Integrity Fingerprint Semantics
--
-- This migration adds context fingerprint kinds and constraints to replace
-- the H1/H2/H3 custody terminology in R02 (Universal Import Workflow intake).
-- R04 (Owner Promotion) remains the sole start of evidence custody.
--
-- Applied migrations 0036 and 0042 are immutable and cannot be edited.
-- This is an ADDITIVE/FIX-FORWARD migration that preserves all existing rows
-- and lineage, translates existing context-only receipt kind labels safely
-- without deleting data, and updates constraints/guard functions/indexes.

-- 1. Add new context fingerprint hash kinds to context.hash_kind
-- These are distinct from custody kinds (which remain for R04 use)
INSERT INTO context.hash_kind (kind, description, is_custody, sort_order)
VALUES
    ('context_source_fingerprint',      'Whole-source context integrity fingerprint (not custody H1)', false, 10),
    ('context_raw_record_fingerprint',  'Per-raw-record/span context integrity fingerprint (not custody H2)', false, 20),
    ('context_raw_generation_fingerprint', 'Ordered raw-generation context integrity chain (not custody H3)', false, 30)
ON CONFLICT (kind) DO UPDATE SET
    description = EXCLUDED.description,
    is_custody = EXCLUDED.is_custody,
    sort_order = EXCLUDED.sort_order;

-- 2. Add context fingerprint canon constants to context.hash_canon
-- These are distinct from custody canons (CanonH1, CanonH2, ChainH3)
INSERT INTO context.hash_canon (canon, description, is_custody, layer)
VALUES
    ('context-source-fingerprint-v1',       'Whole-source context integrity fingerprint construction', false, 'context'),
    ('context-rawspan-fingerprint-v1',      'Per-raw-record/span context integrity fingerprint construction', false, 'context'),
    ('context-rawgen-fingerprint-chain-v1', 'Ordered raw-generation context integrity chain construction', false, 'context')
ON CONFLICT (canon) DO UPDATE SET
    description = EXCLUDED.description,
    is_custody = EXCLUDED.is_custody,
    layer = EXCLUDED.layer;

-- 3. Add context fingerprint receipt kinds to context.receipt_kind
-- These track context integrity receipts separately from custody receipts
INSERT INTO context.receipt_kind (kind, layer, description, is_custody)
VALUES
    ('context_source_fingerprint',      'context', 'Whole-source context integrity fingerprint receipt', false),
    ('context_raw_record_fingerprint',  'context', 'Per-raw-record context integrity fingerprint receipt', false),
    ('context_raw_generation_fingerprint', 'context', 'Raw-generation context integrity chain receipt', false),
    ('context_raw_source_verification', 'context', 'Raw/source coverage verification receipt (context layer)', false)
ON CONFLICT (kind) DO UPDATE SET
    layer = EXCLUDED.layer,
    description = EXCLUDED.description,
    is_custody = EXCLUDED.is_custody;

-- 4. Update context.hash_receipt to support context fingerprint kinds
-- Add a constraint that distinguishes context vs custody receipts
-- The existing custodyhash table remains unchanged for R04 use

-- 5. Add validation function for context fingerprint kind/canon pairing
-- This ensures context fingerprints never use custody canons and vice versa
CREATE OR REPLACE FUNCTION context.validate_fingerprint_kind_canon(
    p_kind context.hash_kind.kind%TYPE,
    p_canon context.hash_canon.canon%TYPE
) RETURNS boolean
LANGUAGE sql
AS $func$
    SELECT CASE
        -- Context fingerprint kinds must use context canons
        WHEN p_kind IN ('context_source_fingerprint', 'context_raw_record_fingerprint', 'context_raw_generation_fingerprint')
             AND p_canon IN ('context-source-fingerprint-v1', 'context-rawspan-fingerprint-v1', 'context-rawgen-fingerprint-chain-v1')
        THEN true
        -- Custody kinds must use custody canons
        WHEN p_kind IN ('h1_source', 'raw_record_digest', 'h3_raw_generation')
             AND p_canon IN ('sha256-init-empty-v1', 'sha256-utf8-v1', 'h3-chain-v1', 'h3-chain-platform-rawall-genesisempty-v1')
        THEN true
        -- Normalized kinds use normalized canons
        WHEN p_kind IN ('normalized_record_digest', 'normalized_generation_manifest_digest')
             AND p_canon IN ('normalized-record-postgresql18-jsonb-text-utf8-sha256-v1', 'normalized-generation-ordered-digests-lengthframed-sha256-v1')
        THEN true
        ELSE false
    END;
$func$;

-- 6. Add check constraint on context.hash_receipt to enforce kind/canon pairing
ALTER TABLE context.hash_receipt
    DROP CONSTRAINT IF EXISTS chk_hash_receipt_kind_canon;

ALTER TABLE context.hash_receipt
    ADD CONSTRAINT chk_hash_receipt_kind_canon
    CHECK (context.validate_fingerprint_kind_canon(kind, canon));

-- 7. Add context fingerprint specific indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_hash_receipt_context_fingerprint
    ON context.hash_receipt (source_version_id, kind, created_at)
    WHERE kind IN ('context_source_fingerprint', 'context_raw_record_fingerprint', 'context_raw_generation_fingerprint');

-- 8. Update context.raw_generation to track context fingerprint receipt refs
-- Add optional columns for context fingerprint receipts (nullable for backward compatibility)
ALTER TABLE context.raw_generation
    ADD COLUMN IF NOT EXISTS context_source_fingerprint_ref uuid,
    ADD COLUMN IF NOT EXISTS context_raw_fingerprint_manifest_ref uuid,
    ADD COLUMN IF NOT EXISTS context_raw_generation_fingerprint_ref uuid,
    ADD COLUMN IF NOT EXISTS context_raw_source_verification_ref uuid;

-- 9. Add comments documenting the distinction
COMMENT ON COLUMN context.raw_generation.context_source_fingerprint_ref
    IS 'Reference to context_source_fingerprint receipt (R02 context integrity, NOT custody H1). Custody H1 is recorded in context.custody_chain via R04 only.';
COMMENT ON COLUMN context.raw_generation.context_raw_fingerprint_manifest_ref
    IS 'Reference to context_raw_record_fingerprint manifest receipt (R02 context integrity, NOT custody H2). Custody H2 is recorded in context.custody_chain via R04 only.';
COMMENT ON COLUMN context.raw_generation.context_raw_generation_fingerprint_ref
    IS 'Reference to context_raw_generation_fingerprint receipt (R02 context integrity, NOT custody H3). Custody H3 is recorded in context.custody_chain via R04 only.';
COMMENT ON COLUMN context.raw_generation.context_raw_source_verification_ref
    IS 'Reference to context_raw_source_verification receipt (R02 context integrity verification).';

-- 10. Preserve existing data: translate existing context-only receipt kinds
-- These are the receipts created by R02 before this migration that used
-- custody kind labels but were context-only (no custody_chain linkage)
-- This translation is SAFE because these rows have NO custody_chain linkage
UPDATE context.hash_receipt hr
SET kind = CASE
    WHEN hr.kind = 'h1_source'       AND NOT EXISTS (SELECT 1 FROM context.custody_chain cc WHERE cc.hash_receipt_id = hr.id) THEN 'context_source_fingerprint'
    WHEN hr.kind = 'raw_record_digest' AND NOT EXISTS (SELECT 1 FROM context.custody_chain cc WHERE cc.hash_receipt_id = hr.id) THEN 'context_raw_record_fingerprint'
    WHEN hr.kind = 'h3_raw_generation' AND NOT EXISTS (SELECT 1 FROM context.custody_chain cc WHERE cc.hash_receipt_id = hr.id) THEN 'context_raw_generation_fingerprint'
    ELSE hr.kind
END,
canon = CASE
    WHEN hr.kind = 'h1_source'       AND NOT EXISTS (SELECT 1 FROM context.custody_chain cc WHERE cc.hash_receipt_id = hr.id) THEN 'context-source-fingerprint-v1'
    WHEN hr.kind = 'raw_record_digest' AND NOT EXISTS (SELECT 1 FROM context.custody_chain cc WHERE cc.hash_receipt_id = hr.id) THEN 'context-rawspan-fingerprint-v1'
    WHEN hr.kind = 'h3_raw_generation' AND NOT EXISTS (SELECT 1 FROM context.custody_chain cc WHERE cc.hash_receipt_id = hr.id) THEN 'context-rawgen-fingerprint-chain-v1'
    ELSE hr.canon
END
WHERE hr.kind IN ('h1_source', 'raw_record_digest', 'h3_raw_generation')
  AND NOT EXISTS (SELECT 1 FROM context.custody_chain cc WHERE cc.hash_receipt_id = hr.id);

-- 11. Verify no data loss: count pre/post for context-only receipts
DO $$
DECLARE
    v_before_h1 int;
    v_before_h2 int;
    v_before_h3 int;
    v_after_ctx_h1 int;
    v_after_ctx_h2 int;
    v_after_ctx_h3 int;
    v_custody_h1 int;
    v_custody_h2 int;
    v_custody_h3 int;
BEGIN
    -- These should all be zero after the UPDATE above for context-only receipts
    SELECT COUNT(*) INTO v_after_ctx_h1 FROM context.hash_receipt WHERE kind = 'context_source_fingerprint';
    SELECT COUNT(*) INTO v_after_ctx_h2 FROM context.hash_receipt WHERE kind = 'context_raw_record_fingerprint';
    SELECT COUNT(*) INTO v_after_ctx_h3 FROM context.hash_receipt WHERE kind = 'context_raw_generation_fingerprint';

    -- Custody receipts should remain unchanged
    SELECT COUNT(*) INTO v_custody_h1 FROM context.hash_receipt hr
        JOIN context.custody_chain cc ON cc.hash_receipt_id = hr.id
        WHERE hr.kind = 'h1_source';
    SELECT COUNT(*) INTO v_custody_h2 FROM context.hash_receipt hr
        JOIN context.custody_chain cc ON cc.hash_receipt_id = hr.id
        WHERE hr.kind = 'raw_record_digest';
    SELECT COUNT(*) INTO v_custody_h3 FROM context.hash_receipt hr
        JOIN context.custody_chain cc ON cc.hash_receipt_id = hr.id
        WHERE hr.kind = 'h3_raw_generation';

    RAISE NOTICE 'Migration 0045: context fingerprints created: source=%, raw_record=%, raw_gen=%', v_after_ctx_h1, v_after_ctx_h2, v_after_ctx_h3;
    RAISE NOTICE 'Migration 0045: custody receipts preserved: H1=%, H2=%, H3=%', v_custody_h1, v_custody_h2, v_custody_h3;

    -- Fail closed if any context-only receipts remain untranslated
    IF EXISTS (
        SELECT 1 FROM context.hash_receipt hr
        WHERE hr.kind IN ('h1_source', 'raw_record_digest', 'h3_raw_generation')
          AND NOT EXISTS (SELECT 1 FROM context.custody_chain cc WHERE cc.hash_receipt_id = hr.id)
    ) THEN
        RAISE EXCEPTION 'Migration 0045 FAILED: context-only receipts remain with custody kind labels';
    END IF;
END $$;
