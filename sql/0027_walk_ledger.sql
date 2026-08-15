-- 0027_walk_ledger.sql — ADR-0045 §B DERIVED pass materialization lands (W1.3).
--
-- Byline: Claude Code . glm-5.2:cloud . 2026-08-14
--
-- WHAT THIS IS
-- ============
-- Wave 1.3 — the checkpoint-derivation ledger. ADR-0045 §B (signed D-042)
-- sanctions version-pinned DERIVED pass materializations and FORBIDS parallel
-- authored as-lived/hindsight stores: there is ONE authored store
-- (working.normalized_record + working.realization_event), and the derivation
-- engine (server/evidence/derivation.py, W1.3) is its SOLE writer of the pass
-- corpora. This migration creates the ledger tables those corpora + checkpoints
-- live in, plus two diagnostic views (contamination + delta).
--
-- This is a DERIVED store, never authored by hand. The refresher is the only
-- writer (enforced app-side by pg_advisory_lock F13 here, DB-side by W1.4
-- grants). Re-derivation at the same base_version MUST reproduce the identical
-- hash chain (proven by the W1.3 validation script before any agent binds).
--
-- RECONCILED FROM sql/drafts/walk_ledger.postgres-draft.HOLD.sql (SUPERSEDED)
-- ========================================================================
-- The draft was design input, NOT a lift-as-is. It was reconciled against the
-- ADR-0045 §B refresher contract. Four corrections (the draft predates the
-- working/analysis schema split and ADR-0045 §B's signing):
--   1. schema analysis.* -> working.* — ADR-0045 §B names working.walk_ledger.
--   2. FK -> working.normalized_record (the draft referenced analysis.normalized_record,
--      the pre-split location; canonical evidence is working.normalized_record).
--   3. contamination view: working.visible_from(record_id) > horizon_at (NOT the
--      draft's nr.knowledge_time > s.horizon_at — knowledge_time is SUPERSEDED,
--      ADR-0045 §A / 0008:247; the horizon clock is visible_from).
--   4. §B chain-hash + version-pin columns the draft had NONE of: walk_run gains
--      base_version + parameters + genesis_hash + final_corpus_hash; walk_step
--      gains corpus_hash + prev_hash. The draft's step rows were unhashed — they
--      could not prove reproducibility. The §B contract requires every checkpoint
--      to record base_version, parameters, corpus_hash, prev_hash and to
--      hash-attest to ops.audit_ledger.
--
-- SCOPE BOUNDARY — what this migration does NOT do
-- =================================================
-- * It does NOT repoint working.horizon_visible / working.vw_spine_horizon at
--   visible_from. That is the F1-resolution repoint, a SEPARATE migration
--   (0028, drafted + rollback-validated in W1.3, held for owner — it is the
--   live-behavior flip and depends on the F4 bundled-doc degenerate ruling).
--   This migration is purely additive (new tables + new views; no DROP/REPLACE).
-- * It does NOT create the refresher engine — that is server/evidence/derivation.py
--   (W1.3 code). The tables are empty until the engine writes them.
-- * It does NOT grant roles — W1.4 (default-deny, refresher = sole writer).
-- * It does NOT bind agents — W1.5 (only after W1.3 + W1.4 land).
--
-- SAFETY
-- ======
-- Pure additive: three CREATE TABLE IF NOT EXISTS, two CREATE OR REPLACE VIEW
-- (new names — no existing object of these names), indexes, COMMENTs. NO DROP,
-- NO REPLACE of any EXISTING object. Never edits the evidence spine. Idempotent.
-- Applied to the LIVE schema (the authority). Validated inside a rollback
-- transaction on live before it is applied for real. Never edit after apply — add 0028.

BEGIN;

-- ---------------------------------------------------------------------------
-- working.walk_run — one horizon walk (an agent running a pass over a case).
-- ---------------------------------------------------------------------------
-- A "pass" is a knowledge horizon bound to an agent (canon §1) — NOT a table.
-- A walk_run is the DERIVED record of one agent executing one pass: the
-- version-pinned base it was derived against, the schedule, and the final hash.
-- horizon_policy:
--   ignorant  — walks forward, horizon advances each step (the gaslightable agent)
--   hindsight — sees the whole case at once (horizon_at IS NULL = no cutoff)
--   custom    — a caller-supplied ceiling (horizon_ceiling)
-- base_version: the pinned DB content-version the walk was derived against. The
-- refresher pins a base_version at the start; re-deriving at the SAME base_version
-- MUST reproduce the identical hash chain (§B). Moving the base forward produces
-- a NEW run, never mutates an old one (append-only).
CREATE TABLE IF NOT EXISTS working.walk_run (
    id              UUID PRIMARY KEY DEFAULT uuidv7(),

    case_id         TEXT NOT NULL DEFAULT 'primary'
                    CHECK (length(case_id) > 0),

    agent_id        TEXT NOT NULL,
    bound_lane      TEXT,                       -- the pass/lane binding (W1.5)

    horizon_policy  TEXT NOT NULL
                    CHECK (horizon_policy IN ('ignorant', 'hindsight', 'custom')),
    horizon_ceiling TIMESTAMPTZ,                 -- custom policy only; NULL = no ceiling

    -- Provenance of the walk itself (for reproducibility + court export).
    model_id        TEXT,
    prompt_version  TEXT,

    -- §B version-pinning. base_version is the content-hash of the authored store
    -- at derivation time; genesis_hash = sha256(base_version || canonical
    -- parameters) is the prev_hash of step 1. The refresher computes these; the
    -- DB only stores them. final_corpus_hash is stamped when the run completes.
    base_version    TEXT NOT NULL,
    parameters      JSONB NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(parameters) = 'object'),
    genesis_hash    TEXT NOT NULL,
    final_corpus_hash TEXT,

    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'completed', 'failed',
                                      'invalidated')),
    invalidated_reason TEXT,

    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    notes           TEXT,

    CHECK (horizon_policy <> 'custom' OR horizon_ceiling IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_walk_run_case_status
    ON working.walk_run (case_id, status);
CREATE INDEX IF NOT EXISTS idx_walk_run_base_version
    ON working.walk_run (base_version);

COMMENT ON TABLE working.walk_run IS
  'ADR-0045 §B DERIVED pass materialization: one agent executing one pass over '
  'a case at a pinned base_version. A pass is a knowledge horizon bound to an '
  'agent (canon §1), not a table. DERIVED — never hand-authored; the refresher '
  '(server/evidence/derivation.py) is the SOLE writer (pg_advisory_lock F13 + '
  'W1.4 grants). Re-derivation at the same base_version MUST reproduce the '
  'identical hash chain. Append-only: a new base_version is a NEW run.';

COMMENT ON COLUMN working.walk_run.base_version IS
  'The content-version of the authored store (normalized_record + '
  'realization_event) this walk was derived against. genesis_hash = '
  'sha256(base_version || canonical parameters). Re-deriving at this same '
  'base_version reproduces the identical corpus_hash chain (§B reproducibility).';

-- ---------------------------------------------------------------------------
-- working.walk_step — one checkpoint in the walk (the chain-hashed unit).
-- ---------------------------------------------------------------------------
-- As-lived (ignorant) walks advance the horizon one step at a time; each step
-- appends the newly-visible slice and chain-hashes it. These step records ARE
-- working.walk_ledger (ADR-0045 §B): prev_hash chains to the prior step's
-- corpus_hash (step 1's prev_hash = run.genesis_hash). corpus_hash is the hash
-- of the canonical visible slice at this step. Hindsight walks are a single
-- step (horizon_at NULL = no cutoff).
--
-- record_id is the FOCAL record of the step (the event the agent is reacting
-- to), if any — NOT the whole visible slice (the slice is hashed into
-- corpus_hash, not stored row-by-row, to keep the ledger compact + reproducible).
CREATE TABLE IF NOT EXISTS working.walk_step (
    id              UUID PRIMARY KEY DEFAULT uuidv7(),

    walk_run_id     UUID NOT NULL
                    REFERENCES working.walk_run(id) ON DELETE CASCADE,

    step_no         INT NOT NULL,

    -- The knowledge horizon for this step. NULL = hindsight (no cutoff — the
    -- whole case is visible). For an ignorant walk this ADVANCES each step;
    -- that advance is the point (canon §1 — the agent lives events as discovered).
    horizon_at      TIMESTAMPTZ,

    -- The focal record the agent is reacting to at this step, if any.
    record_id       UUID REFERENCES working.normalized_record(id) ON DELETE RESTRICT,

    -- The agent's output + state at this step (analysis layer writes these).
    conclusion      TEXT,
    belief          JSONB CHECK (belief IS NULL OR jsonb_typeof(belief) = 'object'),
    confidence      REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    stance          TEXT,

    -- §B chain-hash. corpus_hash = sha256(canonical visible slice at this step);
    -- prev_hash = the prior step's corpus_hash (step 1 = run.genesis_hash).
    -- The refresher computes these; re-derivation at the same base_version
    -- reproduces them exactly. These are the reproducibility attestation.
    corpus_hash    TEXT NOT NULL,
    prev_hash      TEXT NOT NULL,

    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (walk_run_id, step_no)
);

CREATE INDEX IF NOT EXISTS idx_walk_step_run_step
    ON working.walk_step (walk_run_id, step_no);
CREATE INDEX IF NOT EXISTS idx_walk_step_record
    ON working.walk_step (record_id) WHERE record_id IS NOT NULL;

COMMENT ON TABLE working.walk_step IS
  'ADR-0045 §B: one checkpoint in a walk_run. As-lived walks append the '
  'newly-visible slice per step and chain-hash it (prev_hash -> prior corpus_hash; '
  'step 1 prev_hash = run.genesis_hash). corpus_hash attests to the visible slice; '
  'the chain proves the walk was not tampered with. Re-derivation at the same '
  'base_version reproduces the identical chain. DERIVED — refresher is sole writer.';

COMMENT ON COLUMN working.walk_step.corpus_hash IS
  'sha256 of the canonical visible slice at this step (the records visible in '
  'the horizon window, deterministically serialized). The chain link: this step''s '
  'corpus_hash is the next step''s prev_hash. Reproducibility attestation.';

-- ---------------------------------------------------------------------------
-- working.walk_step_retrieval — what the agent retrieved at each step.
-- ---------------------------------------------------------------------------
-- Provenance for the delta + contamination views: which records were retrieved
-- from which store, at what rank/score, and whether the agent actually used
-- them. was_used=false is a retrieved-but-discarded record (a contamination
-- signal if its visible_from > step horizon_at).
CREATE TABLE IF NOT EXISTS working.walk_step_retrieval (
    id              UUID PRIMARY KEY DEFAULT uuidv7(),

    walk_step_id    UUID NOT NULL
                    REFERENCES working.walk_step(id) ON DELETE CASCADE,

    record_id       UUID NOT NULL
                    REFERENCES working.normalized_record(id) ON DELETE RESTRICT,

    store           TEXT NOT NULL
                    CHECK (store IN ('postgres', 'weaviate', 'graphiti',
                                     'neo4j', 'other')),
    rank            INT,
    score           REAL,
    was_used        BOOLEAN NOT NULL DEFAULT false,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (walk_step_id, record_id, store)
);

CREATE INDEX IF NOT EXISTS idx_walk_step_retrieval_record
    ON working.walk_step_retrieval (record_id);

COMMENT ON TABLE working.walk_step_retrieval IS
  'What a walk_step retrieved: record, store, rank, score, and whether the agent '
  'used it. Feeds vw_walk_contamination (retrieved a record whose visible_from > '
  'the step horizon) and the delta provenance. DERIVED — refresher is sole writer.';

-- ---------------------------------------------------------------------------
-- working.vw_walk_contamination — the silent-leak detector (ADR-0045 §A).
-- ---------------------------------------------------------------------------
-- A row here means a record was retrieved/used at a step whose visible_from is
-- AFTER the step's horizon_at — i.e. the ignorant agent saw a fact it should not
-- have known yet. This is the contamination that silently corrupts the delta.
-- Uses working.visible_from(record_id) (the §A clock), NOT the superseded
-- knowledge_time (correction #3 from the draft).
CREATE OR REPLACE VIEW working.vw_walk_contamination AS
SELECT s.walk_run_id,
       s.step_no,
       s.horizon_at,
       ret.record_id,
       ret.store,
       ret.was_used,
       working.visible_from(ret.record_id) AS visible_from
  FROM working.walk_step s
  JOIN working.walk_step_retrieval ret
    ON ret.walk_step_id = s.id
 WHERE s.horizon_at IS NOT NULL
   AND working.visible_from(ret.record_id) > s.horizon_at;

COMMENT ON VIEW working.vw_walk_contamination IS
  'ADR-0045 §A contamination detector: a record retrieved at a step whose '
  'visible_from(record_id) > the step horizon_at was knowable only later — the '
  'ignorant agent saw a future fact. Non-empty here = the delta is silently '
  'corrupted. Uses visible_from (the §A clock), NOT the superseded knowledge_time.';

-- ---------------------------------------------------------------------------
-- working.vw_walk_delta — THE deliverable: believed-then vs actual (canon §1).
-- ---------------------------------------------------------------------------
-- The delta between what the ignorant agent believed at each step (conclusion)
-- and what was actually true (the focal record's content + when it was really
-- knowable). realization_lag = visible_from - occurred_at: how long after the
-- event the party discovered it. This is the gaslighting/manipulation signal —
-- "what you were led to believe vs what was true vs when you found out."
CREATE OR REPLACE VIEW working.vw_walk_delta AS
SELECT s.walk_run_id,
       s.step_no,
       s.horizon_at,
       s.record_id       AS focal_record_id,
       s.conclusion      AS believed_then,
       nr.content        AS actual,
       nr.occurred_at    AS occurred_at,
       working.visible_from(s.record_id) AS actual_known_from,
       CASE WHEN working.visible_from(s.record_id) IS NOT NULL
                 AND nr.occurred_at IS NOT NULL
            THEN working.visible_from(s.record_id) - nr.occurred_at
            END               AS realization_lag
  FROM working.walk_step s
  JOIN working.normalized_record nr ON nr.id = s.record_id
 WHERE s.record_id IS NOT NULL;

COMMENT ON VIEW working.vw_walk_delta IS
  'THE deliverable (canon §1): what the ignorant agent believed at each step '
  '(believed_then) vs what was actually true (actual), with realization_lag = '
  'visible_from - occurred_at (how long after the event the party found out). '
  'The delta between this and the hindsight walk IS the gaslighting/manipulation.';

COMMIT;