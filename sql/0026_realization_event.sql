-- 0026_realization_event.sql — the horizon CLOCK definition lands (ADR-0045 §A + §A.4).
--
-- Byline: Claude Code . glm-5.2:cloud . 2026-08-14
--
-- ⚠ HELD FOR OWNER — COMMITTED + ROLLBACK-VALIDATED, NOT APPLIED TO PROD.
-- Apply only through the reviewed 0026-0030 release sequence.
--
-- WHAT THIS IS
-- ============
-- Wave 1.1 — the first slice of ADR-0045 (signed D-042, Option A + the A.4
-- amendment). It lands the AUTHORITATIVE horizon clock definition and the
-- realization-event tables that feed it. Until now working.horizon_visible
-- filtered on `row_knowledge_time <= p_horizon`, and knowledge_time is
-- SUPERSEDED (0008:247: it records ROW-WRITE time, not when the party learned
-- the fact). The predicate was therefore inert relative to the signed
-- decision — GAP-04 / INVENTORY N1, confirmed against the running DB on
-- 2026-08-14 (docs/INVENTORY-BASELINE-2026-08-14.md).
--
-- ADR-0045 §A mandates ONE clock:
--
--     visible_from = COALESCE(earliest APPROVED realization_event, occurred_at)
--
-- computed per record (predicate-computed, NOT a stored column), and the
-- realization events live in their OWN table (§A.4 — one event can reveal many
-- records at once, e.g. reading one export). Events are HITL-confirmed via the
-- native @approval mechanism (ADR-0002); nothing becomes visible-from-truth
-- unapproved. This migration creates the table and the per-record clock
-- function.
--
-- SCOPE BOUNDARY — what this migration does NOT do (PRE-MORTEM F1, 2026-08-14)
-- ===========================================================================
-- * It does NOT repoint working.horizon_visible or working.vw_spine_horizon at
--   visible_from. The pre-mortem (docs/plans/WAVE1-pre-mortem-2026-08-14.md F1)
--   found that repointing the LIVE spine view at per-row visible_from(r.id)
--   (two correlated subqueries per row = O(rows x events)) BEFORE the W1.3
--   fast materialized read path exists would put a slow per-row function scan
--   on every horizon query and risk a prod meltdown if any reader bound early.
--   W1.1 therefore ships the clock DEFINITION only; the predicate + view
--   repoint lands in W1.3 together with the materialized pass corpus that is
--   the sanctioned fast read path. The live view stays on the (inert)
--   knowledge_time predicate in the meantime — zero behavior change, zero slow
--   path. This also makes the migration purely additive (no DROP/REPLACE of
--   any existing object) — see SAFETY.
-- * It does NOT build working.walk_ledger. ADR-0045 §B makes the derivation/
--   refresher engine the SOLE writer of the walk ledger; that lands in W1.3
--   (see sql/drafts/walk_ledger.postgres-draft.HOLD.sql, to be reconciled
--   against the refresher contract, not lifted as-is).
-- * It does NOT build realization writers (propose/approve) — W1.2.
-- * It does NOT touch the parser disclosure_tier hardcode (ADR-0045 Decision C:
--   the hardcode is CORRECT) nor the ai.disclosure_horizon enum (§C).
-- * It does NOT remove the on-row realized_at column (0008) — A.4 supersedes
--   it as the HORIZON-CLOCK source of truth only; it is retained for the
--   disclosure_tier derivation (analysis.vw_record_disclosure) and audit. This
--   migration marks that supersession in a COMMENT (doc-drift rule).
--
-- SAFETY
-- ======
-- Pure additive: two CREATE TABLE IF NOT EXISTS, one CREATE FUNCTION
-- (visible_from — new, no existing object of that name), two CREATE INDEX IF
-- NOT EXISTS, and COMMENTs. NO DROP, NO REPLACE of any EXISTING object — the
-- live working.horizon_visible predicate and working.vw_spine_horizon view are
-- untouched (pre-mortem F1 deferral). Never deletes a row, never edits the
-- evidence spine. Idempotent. Applied to the LIVE schema (the authority — sql/
-- alone is not from-zero per the Wave 0 fresh-restore finding). Validated
-- inside a rollback transaction on live before it is applied for real. Never
-- edit after apply — add 0027.

BEGIN;

-- ---------------------------------------------------------------------------
-- working.realization_event — append-only. One discovery, provenanced.
-- ---------------------------------------------------------------------------
-- One event can reveal MANY records (reading one export surfaces hundreds),
-- so the records are a link table below, not columns here. Append-only: never
-- UPDATE an approved row — supersede it with a new event. realized_at is the
-- moment the party understood the significance (the "found out" time); it is
-- the clock that pushes those records' visible_from past their occurred_at.
CREATE TABLE IF NOT EXISTS working.realization_event (
    id              UUID PRIMARY KEY DEFAULT uuidv7(),

    case_id         TEXT NOT NULL DEFAULT 'primary'
                    CHECK (length(case_id) > 0),

    -- What kind of discovery this records. Vocabulary is open: the canon says a
    -- pass is a workflow decision, and so are its realization kinds. Extend by
    -- ALTER CONSTRAINT, never by silently reusing a value.
    kind            TEXT NOT NULL
                    CHECK (kind IN ('contradiction', 'export_read',
                                    'told_by_person', 'manual')),

    -- When the party understood it. NOT NULL: a realization without a time is
    -- not a realization. realized_at can be EARLIER than a linked record's
    -- occurred_at; a cross-table CHECK (realized_at >= occurred_at) is NOT
    -- expressible, so the clock CAN move backwards if a writer lets through a
    -- realized_at < occurred_at (visible_from = COALESCE(MIN(realized_at),
    -- occurred_at) would then return that early realized_at and make the record
    -- visible BEFORE it occurred). The guard is therefore APP-SIDE: W1.2
    -- writers MUST reject/clamp realized_at < min(linked occurred_at),
    -- enforced with a test, and a defensive trigger is considered for a later
    -- migration. Do NOT assume the DB enforces ordering.
    realized_at     TIMESTAMPTZ NOT NULL,

    -- The single record that triggered the realization, if any. A 'told by
    -- person' or 'manual' realization may have no single trigger. RESTRICT:
    -- never delete evidence out from under a recorded realization.
    trigger_record_id UUID REFERENCES working.normalized_record(id)
                    ON DELETE RESTRICT,

    -- Provenance of the realization: the contradicting later record, the
    -- export it was found in, the person who said it, a free-form quote.
    -- Structured so the export manifest and the delta can cite it.
    evidence_pointer JSONB NOT NULL DEFAULT '{}'
                    CHECK (jsonb_typeof(evidence_pointer) = 'object'),

    -- Who proposed it. 'algorithm' = the analysis layer matched it against the
    -- corpus; 'owner' = a human entered it directly. Either way it is inert
    -- until approved (HITL gate, ADR-0045 §A.4 + native @approval, ADR-0002).
    proposer        TEXT NOT NULL CHECK (proposer IN ('algorithm', 'owner')),

    approval_state  TEXT NOT NULL DEFAULT 'proposed'
                    CHECK (approval_state IN ('proposed', 'approved', 'superseded')),

    proposed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at     TIMESTAMPTZ,
    approved_by     TEXT,
    notes           TEXT,

    -- Append-only audit invariant. approved_at/approved_by are NULL exactly
    -- while the row is 'proposed', and set ONCE at approval; they are RETAINED
    -- through 'superseded' (they answer "when/by whom was this approved?"
    -- forever — clearing them on supersede would destroy audit history).
    -- This is the fail-closed gate: visible_from only reads APPROVED events,
    -- so a 'proposed' row changes no record's clock. (Revised 2026-08-14
    -- during W1.2 validation: the first form `(approval_state='approved') =
    -- (approved_at IS NOT NULL)` blocked supersede — a superseded row keeps
    -- approved_at, so the strict iff violated. The NULL-iff-proposed form
    -- below permits the full propose->approve->supersede lifecycle.)
    CONSTRAINT realization_event_approved_iff_timestamp
        CHECK ((approved_at IS NULL) = (approval_state = 'proposed')
               AND (approved_by IS NULL) = (approval_state = 'proposed'))
);

CREATE INDEX IF NOT EXISTS idx_realiz_event_case_state_realized
    ON working.realization_event (case_id, approval_state, realized_at);
CREATE INDEX IF NOT EXISTS idx_realiz_event_trigger
    ON working.realization_event (trigger_record_id)
    WHERE trigger_record_id IS NOT NULL;

COMMENT ON TABLE working.realization_event IS
  'The horizon CLOCK source of truth (ADR-0045 §A.4). One discovery that can '
  'reveal many records at once (via realization_event_record). Append-only; '
  'never UPDATE an approved row — supersede it. Inert until approval_state is '
  'approved (HITL via native @approval, ADR-0002); visible_from reads approved '
  'events only, so a proposed event changes no record clock. realized_at is '
  'the found-out time that pushes visible_from past occurred_at. WARNING: '
  'realized_at >= occurred_at is NOT DB-enforced (cross-table CHECK not '
  'expressible); W1.2 writers must reject/clamp realized_at < linked '
  'occurred_at, or the clock can move backwards.';

COMMENT ON COLUMN working.realization_event.realized_at IS
  'When the party understood the significance of the linked records. This is '
  'the CLOCK: visible_from(record) = COALESCE(MIN(realized_at) over approved '
  'linked events, occurred_at). NOT DB-constrained to be >= linked occurred_at; '
  'W1.2 enforces ordering app-side.';

-- ---------------------------------------------------------------------------
-- working.realization_event_record — one event reveals many records.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS working.realization_event_record (
    realization_event_id UUID NOT NULL
                          REFERENCES working.realization_event(id) ON DELETE CASCADE,
    normalized_record_id  UUID NOT NULL
                          REFERENCES working.normalized_record(id) ON DELETE RESTRICT,
    case_id               TEXT NOT NULL DEFAULT 'primary',
    PRIMARY KEY (realization_event_id, normalized_record_id)
);

-- The hot path: given a record, find its approved realizations' realized_at.
CREATE INDEX IF NOT EXISTS idx_realiz_event_record_record
    ON working.realization_event_record (normalized_record_id);

COMMENT ON TABLE working.realization_event_record IS
  'Many-to-many: one realization_event can reveal many normalized_records at '
  'once (reading one export surfaces hundreds). visible_from joins through '
  'here. RESTRICT on the record side: a realization cannot outlive its evidence.';

-- ---------------------------------------------------------------------------
-- working.visible_from(record_id) — THE per-record horizon clock (ADR-0045 §A).
-- ---------------------------------------------------------------------------
-- Predicate-computed, NOT a stored column. Returns the earliest APPROVED
-- realization's realized_at for the record, falling back to occurred_at when
-- there is none (the honest degenerate: until a discovery is recorded, the
-- record is knowable when it occurred).
--
-- STABLE, not IMMUTABLE: it reads realization_event, so it cannot be a single
-- expression index. The supporting access path is the join-key indexes above;
-- the hot read path is the §B DERIVED pass corpus (W1.3 derivation engine),
-- which materializes per-pass visible_from and is the sanctioned substitute
-- for a stored clock. This function is the AUTHORITATIVE definition that the
-- W1.3 repoint (working.horizon_visible + working.vw_spine_horizon) and the
-- Weaviate projection (store.horizon_axes) must agree with.
--
-- NOTE: this function has NO CALLER yet by design (pre-mortem F1 deferral) —
-- the live horizon predicate and spine view still filter on the superseded
-- knowledge_time. W1.3 wires it in alongside the materialized fast path.
CREATE OR REPLACE FUNCTION working.visible_from(p_record_id uuid)
RETURNS timestamptz
LANGUAGE sql STABLE PARALLEL SAFE AS
$$
    SELECT COALESCE(
        (SELECT MIN(e.realized_at)
           FROM working.realization_event e
           JOIN working.realization_event_record l
             ON l.realization_event_id = e.id
          WHERE l.normalized_record_id = p_record_id
            AND e.approval_state = 'approved'),
        (SELECT occurred_at FROM working.normalized_record WHERE id = p_record_id)
    );
$$;

COMMENT ON FUNCTION working.visible_from(uuid) IS
  'THE horizon clock (ADR-0045 §A): visible_from = COALESCE(earliest APPROVED '
  'realization, occurred_at). Authoritative per-record definition; the W1.3 '
  'predicate/view repoint, the Weaviate projection (store.horizon_axes), and '
  'the derivation engine (W1.3) all derive from this. Degenerate-but-correct: '
  'zero approved events => occurred_at (the record is knowable when it '
  'happened). No caller until W1.3 (pre-mortem F1 deferral).';

-- ---------------------------------------------------------------------------
-- Mark the on-row realized_at column as superseded as the HORIZON-CLOCK SoT.
-- ---------------------------------------------------------------------------
-- ADR-0045 §A.4: the horizon clock now reads realization_event, not this
-- column. It is RETAINED — analysis.vw_record_disclosure still derives
-- disclosure_tier from it (a separate analytical concern, untouched here),
-- and it remains an audit field. This COMMENT records the supersession so the
-- old column is never mistaken for the clock again (doc-drift rule).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema='working' AND table_name='normalized_record'
           AND column_name='realized_at'
    ) THEN
        COMMENT ON COLUMN working.normalized_record.realized_at IS
          'SUPERSEDED 2026-08-14 by working.realization_event as the HORIZON-CLOCK '
          'source of truth (ADR-0045 §A.4). visible_from(record_id) now reads the '
          'events table, not this column. RETAINED because analysis.vw_record_disclosure '
          'still derives disclosure_tier from it (an analytical concern, separate from '
          'the horizon clock) and as an audit field. Do not use for horizon queries — '
          'use working.visible_from(id).';
    END IF;
END $$;

COMMIT;
