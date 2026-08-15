-- 0028_horizon_repoint.sql — repoint the LIVE horizon predicate to visible_from (W1.3 F1-resolution).
--
-- Byline: Claude Code . glm-5.2:cloud . 2026-08-14
--
-- ⚠ HELD FOR OWNER — DRAFTED + ROLLBACK-VALIDATED 2026-08-14, NOT APPLIED TO PROD.
-- ⚠ This is the LIVE-BEHAVIOR FLIP (the cutover from the superseded knowledge_time
--   predicate to the ADR-0045 §A visible_from clock). It DEPENDS on the F4 ruling
--   (bundled-doc degenerate visible_from: per-record occurred_at vs occurred_at_max).
--   The draft uses the CURRENT per-record working.visible_from() function; if F4
--   rules occurred_at_max, the function becomes bundle-aware BEFORE this applies.
--
-- WHAT THIS IS
-- ============
-- Wave 1.3 — the F1-resolution. The W1.1 pre-mortem (F1) deferred the
-- working.horizon_visible + working.vw_spine_horizon repoint from 0026 to W1.3,
-- "alongside the materialized pass corpus," because repointing the LIVE spine
-- view at per-row visible_from(r.id) (two correlated subqueries per row) BEFORE a
-- fast read path existed would put a slow correlated scan on every horizon query
-- and risk a prod meltdown if any reader bound early. The pass corpus
-- (working.walk_ledger, 0027) + the derivation engine now exist, so the
-- materialized fast path this migration ships is safe to bind.
--
-- The repoint: the spine view filters on `working.visible_from(r.id) <=
-- app.horizon` (the §A clock) instead of the superseded `r.knowledge_time <=
-- app.horizon` (0008:247 — records row-WRITE time, never a horizon input, ADR-0045
-- §A). `app.horizon` unset/empty = hindsight (whole case, including
-- hindsight-tagged rows); set = ignorant agent at that cutoff.
--
-- THE FAST PATH
-- =============
-- working.record_visible_from (record_id PK, visible_from, refreshed_at) is the
-- materialized projection of visible_from, maintained by the derivation engine's
-- refresher (sole writer, W1.4 grants). The repointed view LEFT JOINs to it and
-- uses COALESCE(rvf.visible_from, working.visible_from(r.id)) — FAST when the
-- refresher has materialized (an indexed equality lookup), CORRECT (function
-- fallback) when it has not. So correctness never depends on the refresh having
-- run; only speed does. This is the F1 mitigation: the slow per-row function
-- scan is the fallback, not the only path.
--
-- SAFETY (when eventually applied)
-- ===============================
-- This migration DOES replace an existing object (CREATE OR REPLACE VIEW
-- working.vw_spine_horizon) — it is the live-behavior change, NOT purely
-- additive. The old knowledge_time predicate is RETAINED on the
-- working.horizon_visible FUNCTION (left intact for any direct caller); only the
-- spine VIEW flips. Applied to LIVE only after (a) the F4 ruling, (b) owner
-- sign-off on this pre-mortem, (c) the refresher is wired to maintain
-- record_visible_from, (d) backup-before-apply. Validated inside a rollback
-- transaction on live before it is applied for real.

BEGIN;

-- ---------------------------------------------------------------------------
-- working.record_visible_from — the materialized fast path (sole-writer: refresher).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS working.record_visible_from (
    record_id    UUID PRIMARY KEY REFERENCES working.normalized_record(id) ON DELETE CASCADE,
    visible_from TIMESTAMPTZ NOT NULL,
    refreshed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE working.record_visible_from IS
  'Materialized projection of working.visible_from (ADR-0045 §A) — the FAST path '
  'for the spine view. Sole writer = the derivation-engine refresher (W1.4 grants; '
  'pg_advisory_lock F13). The view COALESCEs to working.visible_from(r.id) when a '
  'row is absent, so correctness never depends on the refresh having run — only '
  'speed does (F1 mitigation). ';

-- ---------------------------------------------------------------------------
-- Repoint working.vw_spine_horizon to the visible_from clock + fast path.
-- ---------------------------------------------------------------------------
-- OLD (superseded, 0018): filtered on r.knowledge_time <= app.horizon.
-- NEW (ADR-0045 §A): filters on visible_from(r) <= app.horizon, via the
-- materialized fast path with a function fallback. app.horizon unset/empty =
-- hindsight (whole case incl. hindsight-tagged); set = ignorant (excludes
-- hindsight-tagged + anything whose visible_from is after the cutoff).
CREATE OR REPLACE VIEW working.vw_spine_horizon AS
SELECT r.*
  FROM working.normalized_record r
  LEFT JOIN working.record_visible_from rvf ON rvf.record_id = r.id
 WHERE r.case_id = coalesce(nullif(current_setting('app.case_id', true), ''), 'primary')
   AND (
        nullif(current_setting('app.horizon', true), '') IS NULL
        OR coalesce(rvf.visible_from, working.visible_from(r.id))
             <= nullif(current_setting('app.horizon', true), '')::timestamptz
   )
   AND (
        nullif(current_setting('app.horizon', true), '') IS NULL
        OR r.disclosure_tier <> 'hindsight'
   );

COMMENT ON VIEW working.vw_spine_horizon IS
  'Spine filtered by the ADR-0045 §A horizon clock (visible_from), NOT the '
  'superseded knowledge_time. SET app.case_id / app.horizon / app.actor first. '
  'app.horizon unset/empty = hindsight (whole case incl. hindsight-tagged rows); '
  'set = ignorant agent at that cutoff (excludes hindsight-tagged + anything '
  'whose visible_from is after the cutoff). Uses the materialized fast path '
  'working.record_visible_from with a working.visible_from(r.id) fallback (F1). '
  'Repointed 2026-08-14 (0028); old knowledge_time predicate retired from the view.';

COMMIT;