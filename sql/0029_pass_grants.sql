-- 0029_pass_grants.sql — default-deny grants for the pass-corpora derivation lane (ADR-0045 §B / ADR-0052).
--
-- Byline: Claude Code . glm-5.2:cloud . 2026-08-14
--
-- ⚠ HELD FOR OWNER — DRAFTED + ROLLBACK-VALIDATED 2026-08-14, NOT APPLIED TO PROD.
-- ⚠ INERT WHILE SUPERUSER (the decisive finding): the agno app connects as the role
--   `ai`, which is a SUPERUSER (verified live 2026-08-14: rolsuper=True,
--   rolcreaterole=True; the only login role; owner of every working./ops. table).
--   Superusers bypass ALL grants and BYPASSRLS. These grants are therefore the SCHEMA
--   CONTRACT for the target isolation, NOT an enforcing guard under the current
--   connection model. They become ENFORCING only when the app's derivation path
--   connects as `pass_refresher` and agent read-paths as `pass_reader` (a
--   connection-model change that belongs to W1.5 / agent lane bindings). Until then
--   the F13 app-side advisory lock is the sole EFFECTIVE sole-writer guard.
--
-- WHAT THIS IS
-- ============
-- ADR-0045 §B makes the derivation engine the SOLE writer of pass corpora; ADR-0052
-- is default-deny. This migration expresses that at the DB layer:
--   * pass_refresher (NOLOGIN) — sole writer of working.walk_* + record_visible_from;
--     reads the canonical store to compute base_version; attests each step to
--     ops.audit_ledger. (the §B refresher)
--   * pass_reader (NOLOGIN) — agent read of the pass corpus only
--     (working.walk_run/walk_step/walk_step_retrieval). NO grant on canonical base
--     tables (working.normalized_record etc.) — agents read the DERIVED pass corpus,
--     not the raw canonical store (the §B one-store-filtered-per-agent discipline).
--   * DEFAULT-DENY: REVOKE ALL on the pass tables from PUBLIC so a bare role gets
--     nothing; access flows only through the two roles above.
--
-- OPEN — owner decisions (do NOT treat as resolved; see W1.4 pre-mortem):
--   1. Connection model: introduce a non-superuser app role so these grants bite?
--      (the superuser finding above). This is the gate that turns the schema contract
--      into enforcement.
--   2. Per-agent scoping: pass_reader SELECT on walk_run/walk_step exposes ALL runs,
--      not just the agent's own. True per-agent scoping needs RLS (also inert while
--      superuser) or app-layer filtering — deferred to W1.5.
--   3. Transition: agents today read via working.vw_spine_horizon (needs
--      normalized_record SELECT). The target state (agents read pass corpus only,
--      no canonical SELECT) lands with W1.5's rebind. 0029 expresses the TARGET.
--
-- SAFETY (when eventually applied)
-- ===============================
-- Purely additive DDL (CREATE ROLE + GRANT/REVOKE). Does not touch the app's `ai`
-- superuser role or any existing privilege — the new NOLOGIN roles are inert until
-- something assumes them. Applying to LIVE only after (a) the owner rules on the
-- connection-model question, (b) owner sign-off on the W1.4 pre-mortem, (c) backup.
-- Validated inside a rollback transaction on live before it is applied for real.
--
-- APPLY ORDER: 0026 → 0027 → 0028 → 0029. 0029 grants on working.record_visible_from,
-- which 0028 (the horizon repoint) creates — so 0029 applies AFTER 0028.

BEGIN;

-- ---------------------------------------------------------------------------
-- Roles (NOLOGIN — assumed via SET ROLE or a dedicated non-superuser connection,
-- never logged into directly).
-- ---------------------------------------------------------------------------
CREATE ROLE pass_refresher NOLOGIN;

COMMENT ON ROLE pass_refresher IS
  'Sole writer of pass corpora (ADR-0045 §B refresher). Owns INSERT/UPDATE '
  'on working.walk_* + record_visible_from; reads canonical to compute '
  'base_version; attests each step to ops.audit_ledger. INERT while the app '
  'connects as the `ai` superuser — see 0029 header + W1.4 pre-mortem.';

CREATE ROLE pass_reader NOLOGIN;

COMMENT ON ROLE pass_reader IS
  'Agent read of the DERIVED pass corpus only (working.walk_run/walk_step/'
  'walk_step_retrieval). NO grant on canonical base tables — agents do not '
  'read working.normalized_record directly in the target state. INERT while '
  'the app connects as the `ai` superuser — see 0029 header + W1.4 pre-mortem.';

-- ---------------------------------------------------------------------------
-- Schema USAGE — without it, table-level grants are unreachable (a role must
-- have USAGE on a schema to access ANY object inside it). This is the
-- commonly-missed grant that makes the table grants below actually exercise.
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA working, ops TO pass_refresher;  -- refresher reaches ops.audit_ledger
GRANT USAGE ON SCHEMA working TO pass_reader;          -- reader reaches only the pass corpus

-- ---------------------------------------------------------------------------
-- DEFAULT-DENY on the pass tables: PUBLIC gets nothing.
-- ---------------------------------------------------------------------------
REVOKE ALL ON TABLE
  working.walk_run, working.walk_step, working.walk_step_retrieval
  FROM PUBLIC;
REVOKE ALL ON TABLE working.record_visible_from FROM PUBLIC;

-- ---------------------------------------------------------------------------
-- pass_refresher — the §B sole writer.
-- ---------------------------------------------------------------------------
-- Read the canonical store to compute base_version (records + approved realizations).
GRANT SELECT ON TABLE
  working.normalized_record,
  working.realization_event,
  working.realization_event_record
  TO pass_refresher;
-- Sole writer of the pass corpus + the visible_from fast path.
GRANT SELECT, INSERT, UPDATE ON TABLE
  working.walk_run, working.walk_step, working.walk_step_retrieval
  TO pass_refresher;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE working.record_visible_from
  TO pass_refresher;
-- Attest each step to ops.audit_ledger (INSERT) + read the prior entry's prev_hash (SELECT).
-- The derivation engine calls audit.record(connection=...) inside its sole-writer txn,
-- so the refresher role must be able to append the attestation atomically.
GRANT SELECT, INSERT ON TABLE ops.audit_ledger TO pass_refresher;
-- Execute the visible_from / horizon_visible functions used in the slice SQL.
-- (Functions default to PUBLIC EXECUTE; stated explicitly so a future PUBLIC REVOKE
--  on the schema does not silently break the refresher.)
GRANT EXECUTE ON FUNCTION
  working.visible_from(UUID),
  working.horizon_visible(TEXT, TIMESTAMPTZ, TEXT, TEXT, TEXT, TIMESTAMPTZ, TEXT)
  TO pass_refresher;

-- ---------------------------------------------------------------------------
-- pass_reader — agent read of own pass corpus only.
-- ---------------------------------------------------------------------------
-- NOTE (open #2): without RLS this exposes ALL runs, not just the agent's own.
-- Per-agent scoping is app-layer until RLS is activated (also inert while superuser).
GRANT SELECT ON TABLE
  working.walk_run, working.walk_step, working.walk_step_retrieval
  TO pass_reader;
-- Readers do NOT get record_visible_from (refresher-maintained projection), canonical
-- base tables, or ops.audit_ledger. They read the pass corpus the refresher produced.

COMMIT;