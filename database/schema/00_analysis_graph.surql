-- 00_analysis_graph.surql — the SurrealDB analysis graph + walk ledger. DRAFT.
--
-- Byline: Claude Code · Fable 5 · 2026-08-02
-- STATUS: DRAFT — never applied anywhere. Managed by SurrealKit
--         (`surrealkit sync` on a dev instance only; `rollout` for shared).
-- Replaces the parked Postgres draft sql/drafts/walk_ledger.postgres-draft.HOLD.sql
-- ("0009 wrong engine"). Owner rulings implemented here:
--   2026-08-01 "a pass is a permissions thing, and which agents have hindsight"
--   2026-08-02 "creating a walk table as it does it ... different agents can
--               have different access"
--   Canon §1: enforce the horizon as a PRE-filter in every store; vector
--   search is the main leak.
--
-- THE MECHANISM, in schema form: the horizon is not a query convention an
-- agent is asked to follow — it is row-level PERMISSIONS bound to the agent
-- record that signed in. An ignorant agent CANNOT read past its horizon,
-- because the store refuses, not because the prompt says so.

-- ---------------------------------------------------------------------------
-- Agents and their horizons. $auth resolves to a row here via record access.
-- ---------------------------------------------------------------------------
DEFINE TABLE agent SCHEMAFULL
    PERMISSIONS FOR select WHERE id = $auth.id OR $auth.hindsight = true
                FOR create, update, delete NONE;  -- root/ops manages agents
DEFINE FIELD name       ON agent TYPE string;
DEFINE FIELD hindsight  ON agent TYPE bool DEFAULT false;
-- The ignorant agent's advancing knowledge cutoff. Root advances it between
-- walk steps; the agent itself can never widen its own horizon.
DEFINE FIELD horizon    ON agent TYPE option<datetime>;

-- ---------------------------------------------------------------------------
-- Core nodes. Every row carries the platform's clock triple, mirrored from
-- the Postgres spine at promotion time (working.promotion, lane-labelled).
-- knowledge_time = when this became KNOWABLE to the person — the horizon
-- filter runs on it, never on occurred_at.
-- ---------------------------------------------------------------------------
DEFINE TABLE entity SCHEMAFULL
    PERMISSIONS FOR select WHERE $auth.hindsight = true
                              OR knowledge_time <= $auth.horizon
                FOR create, update, delete NONE;  -- writes cross the PG gate only
DEFINE FIELD kind            ON entity TYPE string
    ASSERT $value IN ['person','organization','location','device','account','other'];
DEFINE FIELD name            ON entity TYPE string;
DEFINE FIELD normalized_name ON entity TYPE string;
DEFINE FIELD occurred_at     ON entity TYPE option<datetime>;  -- first true appearance
DEFINE FIELD knowledge_time  ON entity TYPE datetime;
DEFINE FIELD disclosure_tier ON entity TYPE string DEFAULT 'contemporaneous'
    ASSERT $value IN ['contemporaneous','hindsight','discovered'];
DEFINE FIELD promoted_from   ON entity TYPE string;            -- working.candidate_* UUID
DEFINE FIELD recorded_at     ON entity TYPE datetime DEFAULT time::now(); -- transaction time
DEFINE FIELD attrs           ON entity FLEXIBLE TYPE object DEFAULT {};
DEFINE INDEX entity_normalized ON entity FIELDS normalized_name;
DEFINE INDEX entity_ktime      ON entity FIELDS knowledge_time;

DEFINE TABLE event SCHEMAFULL
    PERMISSIONS FOR select WHERE $auth.hindsight = true
                              OR knowledge_time <= $auth.horizon
                FOR create, update, delete NONE;
DEFINE FIELD event_type      ON event TYPE string;
DEFINE FIELD summary         ON event TYPE string;
DEFINE FIELD occurred_at     ON event TYPE option<datetime>;
DEFINE FIELD validity_from   ON event TYPE option<datetime>;   -- honest range when vague
DEFINE FIELD validity_to     ON event TYPE option<datetime>;
DEFINE FIELD knowledge_time  ON event TYPE datetime;
DEFINE FIELD disclosure_tier ON event TYPE string DEFAULT 'contemporaneous'
    ASSERT $value IN ['contemporaneous','hindsight','discovered'];
DEFINE FIELD promoted_from   ON event TYPE string;
DEFINE FIELD recorded_at     ON event TYPE datetime DEFAULT time::now(); -- transaction time
DEFINE FIELD attrs           ON event FLEXIBLE TYPE object DEFAULT {};
DEFINE INDEX event_occurred ON event FIELDS occurred_at;
DEFINE INDEX event_ktime    ON event FIELDS knowledge_time;

DEFINE TABLE fact SCHEMAFULL
    PERMISSIONS FOR select WHERE $auth.hindsight = true
                              OR knowledge_time <= $auth.horizon
                FOR create, update, delete NONE;
DEFINE FIELD predicate       ON fact TYPE string;
DEFINE FIELD statement       ON fact TYPE string;
DEFINE FIELD evidence_quote  ON fact TYPE option<string>;
DEFINE FIELD occurred_at     ON fact TYPE option<datetime>;
DEFINE FIELD knowledge_time  ON fact TYPE datetime;
DEFINE FIELD disclosure_tier ON fact TYPE string DEFAULT 'contemporaneous'
    ASSERT $value IN ['contemporaneous','hindsight','discovered'];
DEFINE FIELD promoted_from   ON fact TYPE string;
DEFINE FIELD recorded_at     ON fact TYPE datetime DEFAULT time::now(); -- transaction time
DEFINE FIELD attrs           ON fact FLEXIBLE TYPE object DEFAULT {};
-- Platform embedder is nvidia/nv-embed-v1 (4096-d). Changing embedder =
-- re-embed the store; mixed dims hard-error.
DEFINE FIELD embedding       ON fact TYPE option<array<float>>;
DEFINE INDEX fact_ktime ON fact FIELDS knowledge_time;
DEFINE INDEX fact_embedding_hnsw ON fact
    FIELDS embedding HNSW DIMENSION 4096 DIST COSINE;
-- !! VALIDATION ITEM (canon: "vector search is the main leak"): before any
-- agent uses KNN here, PROVE with a two-agent test that HNSW results are
-- permission-filtered BEFORE ranking (an ignorant agent must get k results
-- from within its horizon, not top-k-then-filtered-to-fewer). If SurrealDB
-- filters post-index, KNN must be wrapped in a root-side function that
-- pre-filters on knowledge_time. Do not skip this test.

-- Edges (graph-first: direction follows the common query).
DEFINE TABLE involves TYPE RELATION FROM event TO entity
    PERMISSIONS FOR select WHERE $auth.hindsight = true
                              OR in.knowledge_time <= $auth.horizon
                FOR create, update, delete NONE;
DEFINE TABLE about TYPE RELATION FROM fact TO entity
    PERMISSIONS FOR select WHERE $auth.hindsight = true
                              OR in.knowledge_time <= $auth.horizon
                FOR create, update, delete NONE;
DEFINE TABLE evidences TYPE RELATION FROM fact TO event
    PERMISSIONS FOR select WHERE $auth.hindsight = true
                              OR in.knowledge_time <= $auth.horizon
                FOR create, update, delete NONE;

-- ---------------------------------------------------------------------------
-- THE WALK LEDGER — owner design 2026-08-02: "rather than appending the
-- actual table we're just creating a walk table as it does it."
-- The ignorant agent's traversal is DATA: one run, N steps, each step at an
-- advanced horizon, each belief formed/superseded recorded — so the delta
-- against hindsight is computable per step, and the walk is replayable.
-- ---------------------------------------------------------------------------
DEFINE TABLE walk_run SCHEMAFULL
    PERMISSIONS FOR select WHERE agent = $auth.id OR $auth.hindsight = true
                FOR create, update, delete NONE;   -- orchestrator (root) writes
DEFINE FIELD agent         ON walk_run TYPE record<agent>;
DEFINE FIELD started_at    ON walk_run TYPE datetime DEFAULT time::now();
DEFINE FIELD finished_at   ON walk_run TYPE option<datetime>;
DEFINE FIELD horizon_start ON walk_run TYPE datetime;
DEFINE FIELD horizon_end   ON walk_run TYPE option<datetime>;
DEFINE FIELD status        ON walk_run TYPE string DEFAULT 'running'
    ASSERT $value IN ['running','completed','aborted'];
DEFINE FIELD config        ON walk_run FLEXIBLE TYPE object DEFAULT {};

DEFINE TABLE walk_step SCHEMAFULL
    PERMISSIONS FOR select WHERE run.agent = $auth.id OR $auth.hindsight = true
                FOR create, update, delete NONE;
DEFINE FIELD run        ON walk_step TYPE record<walk_run>;
DEFINE FIELD seq        ON walk_step TYPE int ASSERT $value >= 0;
DEFINE FIELD horizon_at ON walk_step TYPE datetime;  -- the cutoff THIS step ran under
DEFINE FIELD summary    ON walk_step TYPE option<string>;
DEFINE FIELD stats      ON walk_step FLEXIBLE TYPE object DEFAULT {};
DEFINE INDEX walk_step_run_seq ON walk_step FIELDS run, seq UNIQUE;

-- What a step actually read (audit: proves no over-horizon access happened).
DEFINE TABLE observed TYPE RELATION FROM walk_step TO event | fact
    PERMISSIONS FOR select WHERE in.run.agent = $auth.id OR $auth.hindsight = true
                FOR create, update, delete NONE;

-- The ignorant agent's accumulating belief state, version-chained
-- (graphrag-temporal: version chain, never in-place edits). Graphiti holds
-- the conversational form; THIS is the queryable, diffable form.
DEFINE TABLE belief SCHEMAFULL
    PERMISSIONS FOR select WHERE run.agent = $auth.id OR $auth.hindsight = true
                FOR create, update, delete NONE;
DEFINE FIELD run            ON belief TYPE record<walk_run>;
DEFINE FIELD formed_at_step ON belief TYPE record<walk_step>;
DEFINE FIELD statement      ON belief TYPE string;
DEFINE FIELD confidence     ON belief TYPE option<float>
    ASSERT $value = NONE OR ($value >= 0.0 AND $value <= 1.0);
-- Bitemporal bounds (graphrag-temporal). held_from = the horizon at which the
-- belief formed (valid time); held_to uses a FAR-FUTURE SENTINEL, never NULL,
-- so "current beliefs" is a plain indexed range hit, not a null-scan.
-- recorded_at = transaction time. Supersession SETS held_to + superseded_by;
-- it never deletes — the invalidated belief IS the evidence of manipulation.
DEFINE FIELD held_from      ON belief TYPE datetime;
DEFINE FIELD held_to        ON belief TYPE datetime DEFAULT d'9999-12-31T00:00:00Z';
DEFINE FIELD recorded_at    ON belief TYPE datetime DEFAULT time::now();
DEFINE FIELD superseded_by  ON belief TYPE option<record<belief>>; -- set with held_to
DEFINE FIELD based_on       ON belief TYPE option<array<record>>;  -- events/facts cited
DEFINE INDEX belief_run ON belief FIELDS run;
-- Current state per run: WHERE run = $run AND held_to = d'9999-12-31T00:00:00Z'.
-- Belief-state as of horizon T: WHERE run = $run AND held_from <= T AND held_to > T.
DEFINE INDEX belief_run_held ON belief FIELDS run, held_to;

-- The deliverable is the DELTA: current beliefs of a completed ignorant run
-- vs the hindsight facts over the same span. Computed by a hindsight-side
-- query joining belief (superseded_by = NONE) against fact/event where
-- knowledge_time > the run's horizon_at for that belief's step. Deliberately
-- NOT materialized here yet — the first real walk decides its shape.
