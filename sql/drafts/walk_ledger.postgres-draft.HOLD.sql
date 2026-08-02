-- ============================================================================
-- ON HOLD - WRONG ENGINE (parked 2026-08-02, was sql/0009_walk_ledger.sql)
-- ============================================================================
-- Its own commit (3f372dd) flagged this draft "0009 wrong engine": the walk
-- ledger records the ignorant agent's traversal + belief state, and the
-- 2026-08-02 owner ruling places the analysis graph (confirmed people/events/
-- timelines, walk ledger, native vectors, horizon-filtered retrieval) in
-- SURREALDB, not Postgres. Redesign as .surql under a SurrealKit database/
-- tree; SurrealDB row-level permissions per agent identity are how the
-- knowledge-horizon pre-filter gets enforced on that store. The Postgres
-- draft below is kept verbatim as design input. Do NOT apply.
-- ============================================================================

-- 0009_walk_ledger.sql — the walk ledger: how each agent experienced the record.
--
-- Byline: Claude Code · Opus 5 · 2026-08-01
--
-- WHY THIS EXISTS
-- ===============
-- Owner design, 2026-08-01: "creates a new table with foreign keys and the record
-- of its walk — so rather than appending the actual table we're just creating a
-- walk table as it does it."
--
-- PROJECT_CANON.md §1 (the killer mechanism): the platform reconstructs how a
-- person realizes they were abused, by running the same evidence past agents with
-- different KNOWLEDGE HORIZONS and diffing them.
--
--   ignorant agent   starts knowing nothing, walks forward living events as they
--                    were actually discovered; its horizon ADVANCES each step
--   hindsight agent  sees everything at once, including facts acquired years later
--
-- The DELTA between what those two agents experience IS the deceit, the
-- manipulation and the gaslighting. That delta is the deliverable.
--
-- A "pass" is therefore a retrieval filter bound to an agent — not a table, lane,
-- or destination. Owner: "ultimately it's just a permissions thing, and which
-- agents have hindsight." So nothing here partitions the evidence. Evidence stays
-- in analysis.normalized_record, written once, carrying all six clocks. This
-- schema records only WHAT EACH AGENT WAS SHOWN AND WHAT IT CONCLUDED.
--
-- DESIGN NOTES
-- ------------
-- * Additive. Creates new tables in `analysis` and touches nothing existing.
-- * APPEND-ONLY. A walk is a historical event: it happened, under a stated
--   horizon, over a recorded set. Never UPDATE a step. Re-running produces a NEW
--   walk_run, which is exactly what makes two walks diffable instead of one walk
--   silently degrading into the next.
-- * THE RETRIEVED SET IS RECORDED, NOT JUST THE CONCLUSION. Without it you cannot
--   prove the ignorant agent did not see something, and an unprovable delta is an
--   anecdote rather than evidence. It is also the only way to detect contamination
--   after the fact.
-- * Contamination is SILENT — one leaked future fact merely makes the ignorant
--   agent smarter; nothing errors. Postgres cannot prevent it (the check spans
--   tables), so vw_walk_contamination turns it into a query instead. Run that view
--   after every ignorant walk; a non-empty result invalidates the walk.
-- * uuidv7() (native in PG18) is time-ordered, so one run's steps cluster on disk —
--   which is the access pattern (replay a run in order).

BEGIN;

-- ---------------------------------------------------------------------------
-- walk_run — one row per walk. The unit of reproducibility.
-- ---------------------------------------------------------------------------
CREATE TABLE analysis.walk_run (
    id              UUID PRIMARY KEY DEFAULT uuidv7(),

    -- Which agent walked, and under what rule. horizon_policy is the pass:
    --   ignorant  — horizon advances stepwise; may see only what was knowable then
    --   hindsight — horizon is open; sees everything including late-acquired facts
    --   custom    — an intermediate horizon (canon allows more than two passes;
    --               how many is a workflow decision, so the vocabulary stays open)
    agent_id        TEXT NOT NULL CHECK (length(agent_id) > 0),
    horizon_policy  TEXT NOT NULL
                    CHECK (horizon_policy IN ('ignorant', 'hindsight', 'custom')),
    -- For 'hindsight' this is the as-of ceiling (usually now()); for 'ignorant' it
    -- is the far end of the walk. Per-step horizons live on walk_step.
    horizon_ceiling TIMESTAMPTZ,
    -- Which graph/store lane this agent was bound to. Access is enforced at the
    -- agent/tool layer, not by Neo4j roles — DozerDB RBAC is unavailable
    -- (ADR-0036: CREATE ROLE -> "Unsupported administration command", 2026-07-30).
    -- Recording it here is what makes the isolation auditable after the fact.
    bound_lane      TEXT NOT NULL DEFAULT 'analysis'
                    CHECK (bound_lane IN ('analysis', 'case', 'dev')),

    model_id        TEXT,
    prompt_version  TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'completed', 'failed', 'invalidated')),
    -- Set when vw_walk_contamination returns rows for this run, or a human voids it.
    invalidated_reason TEXT,
    notes           TEXT,
    attrs           JSONB NOT NULL DEFAULT '{}'
                    CHECK (jsonb_typeof(attrs) = 'object'),

    CONSTRAINT walk_run_finished_after_start
        CHECK (finished_at IS NULL OR finished_at >= started_at),
    CONSTRAINT walk_run_invalidated_has_reason
        CHECK (status <> 'invalidated' OR invalidated_reason IS NOT NULL)
);

CREATE INDEX walk_run_policy_idx  ON analysis.walk_run (horizon_policy, started_at DESC);
CREATE INDEX walk_run_agent_idx   ON analysis.walk_run (agent_id, started_at DESC);
CREATE INDEX walk_run_started_idx ON analysis.walk_run (started_at DESC);

COMMENT ON TABLE analysis.walk_run IS
  'One traversal of the evidence by one agent under one knowledge-horizon policy. '
  'Re-running creates a NEW run — never mutate an existing one, or the two walks '
  'stop being comparable.';

COMMENT ON COLUMN analysis.walk_run.horizon_policy IS
  'The pass. A pass is a retrieval filter bound to an agent (PROJECT_CANON §1), '
  'not a storage partition. More than two passes are allowed by design.';

-- ---------------------------------------------------------------------------
-- walk_step — ordered, append-only. One record, as experienced at one horizon.
-- ---------------------------------------------------------------------------
CREATE TABLE analysis.walk_step (
    id              UUID PRIMARY KEY DEFAULT uuidv7(),
    walk_run_id     UUID NOT NULL REFERENCES analysis.walk_run(id) ON DELETE CASCADE,
    step_no         INTEGER NOT NULL CHECK (step_no > 0),

    -- The as-of bound in force AT THIS STEP. For an ignorant walk this advances;
    -- for a hindsight walk it is constant. This is the whole mechanism in one
    -- column: it is what the retrieval layer must have filtered on.
    horizon_at      TIMESTAMPTZ NOT NULL,

    -- The record being walked. RESTRICT, not CASCADE: deleting evidence out from
    -- under a recorded walk would make the walk unprovable.
    record_id       UUID NOT NULL
                    REFERENCES analysis.normalized_record(id) ON DELETE RESTRICT,

    -- What the agent took away. `belief` is structured for diffing; `conclusion`
    -- is the human-readable form that ends up quoted.
    conclusion      TEXT,
    belief          JSONB NOT NULL DEFAULT '{}'
                    CHECK (jsonb_typeof(belief) = 'object'),
    -- How sure it was, and how it felt about the record — the ignorant agent
    -- believing something confidently and wrongly is precisely the finding.
    confidence      DOUBLE PRECISION CHECK (confidence >= 0 AND confidence <= 1),
    stance          TEXT CHECK (stance IN ('believed', 'doubted', 'confused',
                                           'contradicted', 'no_opinion')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT walk_step_unique_order UNIQUE (walk_run_id, step_no)
);

CREATE INDEX walk_step_run_idx     ON analysis.walk_step (walk_run_id, step_no);
CREATE INDEX walk_step_record_idx  ON analysis.walk_step (record_id);
CREATE INDEX walk_step_horizon_idx ON analysis.walk_step (horizon_at);
CREATE INDEX walk_step_belief_gin  ON analysis.walk_step USING GIN (belief);

COMMENT ON TABLE analysis.walk_step IS
  'Append-only. One evidence record as experienced by one agent at one horizon. '
  'Never UPDATE — a changed mind is a later step, or a later run.';

-- ---------------------------------------------------------------------------
-- walk_step_retrieval — WHAT THE AGENT WAS ACTUALLY SHOWN at this step.
-- ---------------------------------------------------------------------------
-- The load-bearing audit table. A conclusion without its retrieved set proves
-- nothing: you cannot show the ignorant agent did NOT see a record, and you
-- cannot detect a leak. Deliberately a relation, not a JSONB array, so
-- "prove it never saw X" is an indexed query rather than a document scan.
CREATE TABLE analysis.walk_step_retrieval (
    id              UUID PRIMARY KEY DEFAULT uuidv7(),
    walk_step_id    UUID NOT NULL REFERENCES analysis.walk_step(id) ON DELETE CASCADE,
    record_id       UUID NOT NULL
                    REFERENCES analysis.normalized_record(id) ON DELETE RESTRICT,

    -- Which store served it. Attribution matters: vector search is the likeliest
    -- leak path, because embeddings have no sense of time and a future document
    -- scores exactly as similar as a contemporaneous one.
    store           TEXT NOT NULL
                    CHECK (store IN ('postgres', 'weaviate', 'graphiti',
                                     'neo4j', 'surrealdb', 'other')),
    rank            INTEGER CHECK (rank > 0),
    score           DOUBLE PRECISION,
    -- Retrieved and shown is not the same as used. Both are recorded: a record
    -- the agent saw and ignored is still contamination.
    was_used        BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT walk_step_retrieval_unique UNIQUE (walk_step_id, record_id, store)
);

CREATE INDEX walk_step_retrieval_step_idx   ON analysis.walk_step_retrieval (walk_step_id);
CREATE INDEX walk_step_retrieval_record_idx ON analysis.walk_step_retrieval (record_id);
CREATE INDEX walk_step_retrieval_store_idx  ON analysis.walk_step_retrieval (store);

COMMENT ON TABLE analysis.walk_step_retrieval IS
  'Every record the agent was shown at a step, with the store that served it. '
  'This is what makes a delta provable and contamination detectable.';

-- ---------------------------------------------------------------------------
-- vw_walk_contamination — the leak detector. RUN AFTER EVERY IGNORANT WALK.
-- ---------------------------------------------------------------------------
-- Postgres cannot CHECK this: the rule spans walk_step and normalized_record.
-- So it becomes a query. Any row here means an agent was shown a record it could
-- not have known at that horizon — the walk is contaminated and its delta is
-- worthless. Non-empty result => set walk_run.status = 'invalidated'.
CREATE VIEW analysis.vw_walk_contamination AS
    SELECT r.id            AS walk_run_id,
           r.agent_id,
           r.horizon_policy,
           s.id            AS walk_step_id,
           s.step_no,
           s.horizon_at,
           ret.record_id,
           ret.store,
           ret.was_used,
           nr.knowledge_time,
           nr.disclosure_tier,
           nr.knowledge_time - s.horizon_at AS leaked_by
      FROM analysis.walk_run r
      JOIN analysis.walk_step s            ON s.walk_run_id = r.id
      JOIN analysis.walk_step_retrieval ret ON ret.walk_step_id = s.id
      JOIN analysis.normalized_record nr    ON nr.id = ret.record_id
     WHERE r.horizon_policy <> 'hindsight'
       AND nr.knowledge_time > s.horizon_at;

COMMENT ON VIEW analysis.vw_walk_contamination IS
  'Records shown to a horizon-bound agent that postdate its horizon. Contamination '
  'is silent — a leaked fact only makes the agent smarter, nothing errors — so this '
  'view is the ONLY signal. Empty is the required state for a valid ignorant walk.';

-- ---------------------------------------------------------------------------
-- vw_walk_delta — the deliverable.
-- ---------------------------------------------------------------------------
-- Same evidence record, two agents, different horizons. Where their conclusions
-- diverge is where the person was led to believe something other than the truth.
-- Invalidated runs are excluded: a contaminated walk must never feed a finding.
CREATE VIEW analysis.vw_walk_delta AS
    SELECT lived.record_id,
           lived.walk_run_id   AS lived_run_id,
           know.walk_run_id    AS hindsight_run_id,
           lived.horizon_at    AS believed_as_of,
           lived.conclusion    AS believed,
           lived.stance        AS believed_stance,
           lived.confidence    AS believed_confidence,
           know.conclusion     AS actual,
           know.stance         AS actual_stance,
           know.confidence     AS actual_confidence,
           nr.occurred_at,
           nr.knowledge_time,
           nr.realized_at,
           -- How long the gap between the event and understanding it ran.
           nr.realized_at - nr.occurred_at AS realization_lag
      FROM analysis.walk_step lived
      JOIN analysis.walk_run  lr ON lr.id = lived.walk_run_id
                                AND lr.horizon_policy <> 'hindsight'
                                AND lr.status = 'completed'
      JOIN analysis.walk_step know ON know.record_id = lived.record_id
      JOIN analysis.walk_run  kr ON kr.id = know.walk_run_id
                                AND kr.horizon_policy = 'hindsight'
                                AND kr.status = 'completed'
      JOIN analysis.normalized_record nr ON nr.id = lived.record_id
     WHERE lived.conclusion IS DISTINCT FROM know.conclusion
        OR lived.stance     IS DISTINCT FROM know.stance;

COMMENT ON VIEW analysis.vw_walk_delta IS
  'THE DELIVERABLE (PROJECT_CANON §1): what you were led to believe vs what was '
  'true vs when you found out. Only completed, non-invalidated runs contribute.';

COMMIT;
