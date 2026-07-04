--
-- PostgreSQL database dump
--

\restrict FsaauFYkVQKu4Rn6mKfC9HHVGENKdZWzCTYkNHm4pPvOa5UrRBNACO5rQcWjzHP

-- Dumped from database version 18.1 (Debian 18.1-1.pgdg12+2)
-- Dumped by pg_dump version 18.1 (Debian 18.1-1.pgdg12+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: ai; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ai;


--
-- Name: analysis; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA analysis;


--
-- Name: pg_duckdb; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_duckdb WITH SCHEMA public;


--
-- Name: EXTENSION pg_duckdb; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_duckdb IS 'DuckDB Embedded in Postgres';


--
-- Name: evidence; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA evidence;


--
-- Name: btree_gin; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gin WITH SCHEMA public;


--
-- Name: EXTENSION btree_gin; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION btree_gin IS 'support for indexing common datatypes in GIN';


--
-- Name: btree_gist; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;


--
-- Name: EXTENSION btree_gist; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION btree_gist IS 'support for indexing common datatypes in GiST';


--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA public;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: unaccent; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;


--
-- Name: EXTENSION unaccent; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION unaccent IS 'text search dictionary that removes accents';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: simple_s3_secret; Type: SERVER; Schema: -; Owner: -
--

CREATE SERVER simple_s3_secret TYPE 'S3' FOREIGN DATA WRAPPER duckdb OPTIONS (
    endpoint '1a7406c497493a52128bb282f499e7b8.r2.cloudflarestorage.com',
    region 'auto'
);


--
-- Name: USER MAPPING ai SERVER simple_s3_secret; Type: USER MAPPING; Schema: -; Owner: -
--

CREATE USER MAPPING FOR ai SERVER simple_s3_secret OPTIONS (
    key_id '9e9eb4a1f55d967f83c42dc041e37313',
    secret 'f64180b5668fedd0db791c2d2688154a5613b66c2ff1ac12fe7b27a6896e0878'
);


--
-- Name: simple_s3_secret_1; Type: SERVER; Schema: -; Owner: -
--

CREATE SERVER simple_s3_secret_1 TYPE 'S3' FOREIGN DATA WRAPPER duckdb OPTIONS (
    endpoint '1a7406c497493a52128bb282f499e7b8.r2.cloudflarestorage.com',
    region 'auto'
);


--
-- Name: USER MAPPING ai SERVER simple_s3_secret_1; Type: USER MAPPING; Schema: -; Owner: -
--

CREATE USER MAPPING FOR ai SERVER simple_s3_secret_1 OPTIONS (
    key_id '9e9eb4a1f55d967f83c42dc041e37313',
    secret 'f64180b5668fedd0db791c2d2688154a5613b66c2ff1ac12fe7b27a6896e0878'
);


--
-- Name: simple_s3_secret_2; Type: SERVER; Schema: -; Owner: -
--

CREATE SERVER simple_s3_secret_2 TYPE 'S3' FOREIGN DATA WRAPPER duckdb OPTIONS (
    endpoint '1a7406c497493a52128bb282f499e7b8.r2.cloudflarestorage.com',
    region 'auto'
);


--
-- Name: USER MAPPING ai SERVER simple_s3_secret_2; Type: USER MAPPING; Schema: -; Owner: -
--

CREATE USER MAPPING FOR ai SERVER simple_s3_secret_2 OPTIONS (
    key_id '9e9eb4a1f55d967f83c42dc041e37313',
    secret 'f64180b5668fedd0db791c2d2688154a5613b66c2ff1ac12fe7b27a6896e0878'
);


--
-- Name: simple_s3_secret_3; Type: SERVER; Schema: -; Owner: -
--

CREATE SERVER simple_s3_secret_3 TYPE 'S3' FOREIGN DATA WRAPPER duckdb OPTIONS (
    endpoint '1a7406c497493a52128bb282f499e7b8.r2.cloudflarestorage.com',
    region 'auto'
);


--
-- Name: USER MAPPING ai SERVER simple_s3_secret_3; Type: USER MAPPING; Schema: -; Owner: -
--

CREATE USER MAPPING FOR ai SERVER simple_s3_secret_3 OPTIONS (
    key_id '9e9eb4a1f55d967f83c42dc041e37313',
    secret 'f64180b5668fedd0db791c2d2688154a5613b66c2ff1ac12fe7b27a6896e0878'
);


--
-- Name: simple_s3_secret_4; Type: SERVER; Schema: -; Owner: -
--

CREATE SERVER simple_s3_secret_4 TYPE 'S3' FOREIGN DATA WRAPPER duckdb OPTIONS (
    endpoint '1a7406c497493a52128bb282f499e7b8.r2.cloudflarestorage.com',
    region 'auto'
);


--
-- Name: USER MAPPING ai SERVER simple_s3_secret_4; Type: USER MAPPING; Schema: -; Owner: -
--

CREATE USER MAPPING FOR ai SERVER simple_s3_secret_4 OPTIONS (
    key_id '9e9eb4a1f55d967f83c42dc041e37313',
    secret 'f64180b5668fedd0db791c2d2688154a5613b66c2ff1ac12fe7b27a6896e0878'
);


--
-- Name: simple_s3_secret_5; Type: SERVER; Schema: -; Owner: -
--

CREATE SERVER simple_s3_secret_5 TYPE 'S3' FOREIGN DATA WRAPPER duckdb OPTIONS (
    endpoint '1a7406c497493a52128bb282f499e7b8.r2.cloudflarestorage.com',
    region 'auto'
);


--
-- Name: USER MAPPING ai SERVER simple_s3_secret_5; Type: USER MAPPING; Schema: -; Owner: -
--

CREATE USER MAPPING FOR ai SERVER simple_s3_secret_5 OPTIONS (
    key_id '9e9eb4a1f55d967f83c42dc041e37313',
    secret 'f64180b5668fedd0db791c2d2688154a5613b66c2ff1ac12fe7b27a6896e0878'
);


--
-- Name: simple_s3_secret_6; Type: SERVER; Schema: -; Owner: -
--

CREATE SERVER simple_s3_secret_6 TYPE 'S3' FOREIGN DATA WRAPPER duckdb OPTIONS (
    endpoint '1a7406c497493a52128bb282f499e7b8.r2.cloudflarestorage.com',
    region 'auto'
);


--
-- Name: USER MAPPING ai SERVER simple_s3_secret_6; Type: USER MAPPING; Schema: -; Owner: -
--

CREATE USER MAPPING FOR ai SERVER simple_s3_secret_6 OPTIONS (
    key_id '9e9eb4a1f55d967f83c42dc041e37313',
    secret 'f64180b5668fedd0db791c2d2688154a5613b66c2ff1ac12fe7b27a6896e0878'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agno_approvals; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_approvals (
    id character varying NOT NULL,
    run_id character varying NOT NULL,
    session_id character varying NOT NULL,
    status character varying NOT NULL,
    source_type character varying NOT NULL,
    approval_type character varying,
    pause_type character varying NOT NULL,
    tool_name character varying,
    tool_args jsonb,
    expires_at bigint,
    agent_id character varying,
    team_id character varying,
    workflow_id character varying,
    user_id character varying,
    schedule_id character varying,
    schedule_run_id character varying,
    source_name character varying,
    requirements jsonb,
    context jsonb,
    resolution_data jsonb,
    resolved_by character varying,
    resolved_at bigint,
    created_at bigint NOT NULL,
    updated_at bigint,
    run_status character varying
);


--
-- Name: agno_component_configs; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_component_configs (
    component_id character varying NOT NULL,
    version integer NOT NULL,
    label character varying,
    stage character varying NOT NULL,
    config jsonb NOT NULL,
    notes text,
    created_at bigint NOT NULL,
    updated_at bigint,
    deleted_at bigint
);


--
-- Name: agno_component_links; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_component_links (
    parent_component_id character varying NOT NULL,
    parent_version integer NOT NULL,
    link_kind character varying NOT NULL,
    link_key character varying NOT NULL,
    child_component_id character varying NOT NULL,
    child_version integer,
    "position" integer NOT NULL,
    meta jsonb,
    created_at bigint,
    updated_at bigint
);


--
-- Name: agno_components; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_components (
    component_id character varying NOT NULL,
    component_type character varying NOT NULL,
    name character varying,
    description text,
    current_version integer,
    metadata jsonb,
    created_at bigint NOT NULL,
    updated_at bigint,
    deleted_at bigint
);


--
-- Name: agno_eval_runs; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_eval_runs (
    run_id character varying NOT NULL,
    eval_type character varying NOT NULL,
    eval_data jsonb NOT NULL,
    eval_input jsonb NOT NULL,
    name character varying,
    agent_id character varying,
    team_id character varying,
    workflow_id character varying,
    model_id character varying,
    model_provider character varying,
    evaluated_component_name character varying,
    created_at bigint NOT NULL,
    updated_at bigint
);


--
-- Name: agno_learnings; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_learnings (
    learning_id character varying NOT NULL,
    learning_type character varying NOT NULL,
    namespace character varying,
    user_id character varying,
    agent_id character varying,
    team_id character varying,
    workflow_id character varying,
    session_id character varying,
    entity_id character varying,
    entity_type character varying,
    content jsonb NOT NULL,
    metadata jsonb,
    created_at bigint NOT NULL,
    updated_at bigint
);


--
-- Name: agno_memories; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_memories (
    memory_id character varying NOT NULL,
    memory jsonb NOT NULL,
    feedback text,
    input text,
    agent_id character varying,
    team_id character varying,
    user_id character varying,
    topics jsonb,
    created_at bigint NOT NULL,
    updated_at bigint
);


--
-- Name: agno_metrics; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_metrics (
    id character varying NOT NULL,
    agent_runs_count bigint NOT NULL,
    team_runs_count bigint NOT NULL,
    workflow_runs_count bigint NOT NULL,
    agent_sessions_count bigint NOT NULL,
    team_sessions_count bigint NOT NULL,
    workflow_sessions_count bigint NOT NULL,
    users_count bigint NOT NULL,
    token_metrics jsonb NOT NULL,
    model_metrics jsonb NOT NULL,
    date date NOT NULL,
    aggregation_period character varying NOT NULL,
    created_at bigint NOT NULL,
    updated_at bigint,
    completed boolean NOT NULL
);


--
-- Name: agno_schedule_runs; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_schedule_runs (
    id character varying NOT NULL,
    schedule_id character varying NOT NULL,
    attempt bigint NOT NULL,
    triggered_at bigint,
    completed_at bigint,
    status character varying NOT NULL,
    status_code bigint,
    run_id character varying,
    session_id character varying,
    error text,
    input jsonb,
    output jsonb,
    requirements jsonb,
    created_at bigint NOT NULL
);


--
-- Name: agno_schedules; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_schedules (
    id character varying NOT NULL,
    name character varying NOT NULL,
    description text,
    method character varying NOT NULL,
    endpoint character varying NOT NULL,
    payload jsonb,
    cron_expr character varying NOT NULL,
    timezone character varying NOT NULL,
    timeout_seconds bigint NOT NULL,
    max_retries bigint NOT NULL,
    retry_delay_seconds bigint NOT NULL,
    enabled boolean NOT NULL,
    next_run_at bigint,
    locked_by character varying,
    locked_at bigint,
    created_at bigint NOT NULL,
    updated_at bigint
);


--
-- Name: agno_schema_versions; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_schema_versions (
    table_name character varying NOT NULL,
    version character varying NOT NULL,
    created_at character varying NOT NULL,
    updated_at character varying
);


--
-- Name: agno_sessions; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.agno_sessions (
    session_id character varying NOT NULL,
    session_type character varying NOT NULL,
    agent_id character varying,
    team_id character varying,
    workflow_id character varying,
    user_id character varying,
    session_data jsonb,
    agent_data jsonb,
    team_data jsonb,
    workflow_data jsonb,
    metadata jsonb,
    runs jsonb,
    summary jsonb,
    created_at bigint NOT NULL,
    updated_at bigint
);


--
-- Name: api_keys; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.api_keys (
    id bigint NOT NULL,
    key text NOT NULL,
    name text,
    scopes text[] DEFAULT ARRAY['mcp'::text] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone,
    revoked boolean DEFAULT false NOT NULL,
    last_used_at timestamp with time zone
);


--
-- Name: api_keys_id_seq; Type: SEQUENCE; Schema: ai; Owner: -
--

CREATE SEQUENCE ai.api_keys_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: api_keys_id_seq; Type: SEQUENCE OWNED BY; Schema: ai; Owner: -
--

ALTER SEQUENCE ai.api_keys_id_seq OWNED BY ai.api_keys.id;


--
-- Name: casebible_evidence_contents; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.casebible_evidence_contents (
    id character varying NOT NULL,
    name character varying NOT NULL,
    description text NOT NULL,
    metadata jsonb,
    type character varying,
    size bigint,
    linked_to character varying,
    access_count bigint,
    status character varying,
    status_message text,
    created_at bigint,
    updated_at bigint,
    external_id character varying
);


--
-- Name: casebible_evidence_test_contents; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.casebible_evidence_test_contents (
    id character varying NOT NULL,
    name character varying NOT NULL,
    description text NOT NULL,
    metadata jsonb,
    type character varying,
    size bigint,
    linked_to character varying,
    access_count bigint,
    status character varying,
    status_message text,
    created_at bigint,
    updated_at bigint,
    external_id character varying
);


--
-- Name: casebible_ingest_test2_contents; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.casebible_ingest_test2_contents (
    id character varying NOT NULL,
    name character varying NOT NULL,
    description text NOT NULL,
    metadata jsonb,
    type character varying,
    size bigint,
    linked_to character varying,
    access_count bigint,
    status character varying,
    status_message text,
    created_at bigint,
    updated_at bigint,
    external_id character varying
);


--
-- Name: casebible_ingest_test_contents; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.casebible_ingest_test_contents (
    id character varying NOT NULL,
    name character varying NOT NULL,
    description text NOT NULL,
    metadata jsonb,
    type character varying,
    size bigint,
    linked_to character varying,
    access_count bigint,
    status character varying,
    status_message text,
    created_at bigint,
    updated_at bigint,
    external_id character varying
);


--
-- Name: platform_knowledge_contents; Type: TABLE; Schema: ai; Owner: -
--

CREATE TABLE ai.platform_knowledge_contents (
    id character varying NOT NULL,
    name character varying NOT NULL,
    description text NOT NULL,
    metadata jsonb,
    type character varying,
    size bigint,
    linked_to character varying,
    access_count bigint,
    status character varying,
    status_message text,
    created_at bigint,
    updated_at bigint,
    external_id character varying
);


--
-- Name: normalized_record; Type: TABLE; Schema: analysis; Owner: -
--

CREATE TABLE analysis.normalized_record (
    id uuid DEFAULT uuidv7() NOT NULL,
    artifact_id uuid NOT NULL,
    record_type text NOT NULL,
    source text NOT NULL,
    conversation_id text,
    role text,
    participants jsonb DEFAULT '[]'::jsonb NOT NULL,
    content text DEFAULT ''::text NOT NULL,
    occurred_at timestamp with time zone,
    knowledge_time timestamp with time zone DEFAULT now() NOT NULL,
    disclosure_tier text DEFAULT 'contemporaneous'::text NOT NULL,
    attrs jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT normalized_record_disclosure_tier_check CHECK ((disclosure_tier = ANY (ARRAY['contemporaneous'::text, 'hindsight'::text, 'discovered'::text]))),
    CONSTRAINT normalized_record_record_type_check CHECK ((record_type = ANY (ARRAY['message'::text, 'call'::text, 'event'::text, 'media'::text])))
);


--
-- Name: evidence_hash; Type: TABLE; Schema: evidence; Owner: -
--

CREATE TABLE evidence.evidence_hash (
    id uuid DEFAULT uuidv7() NOT NULL,
    source_ref text NOT NULL,
    algo text DEFAULT 'sha256'::text NOT NULL,
    digest bytea NOT NULL,
    hashed_at timestamp with time zone DEFAULT now() NOT NULL,
    blob_key text,
    meta jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT evidence_hash_check CHECK (((algo <> 'sha256'::text) OR (octet_length(digest) = 32)))
);


--
-- Name: agent_run; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agent_run (
    id uuid DEFAULT uuidv7() NOT NULL,
    agent_name text NOT NULL,
    run_type text NOT NULL,
    status text NOT NULL,
    user_prompt text NOT NULL,
    summarized_plan text,
    approval_required boolean DEFAULT true NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    error_message text,
    CONSTRAINT agent_run_run_type_check CHECK ((run_type = ANY (ARRAY['platform'::text, 'builder'::text]))),
    CONSTRAINT agent_run_status_check CHECK ((status = ANY (ARRAY['queued'::text, 'running'::text, 'awaiting_approval'::text, 'completed'::text, 'failed'::text, 'cancelled'::text])))
);


--
-- Name: approval_request; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.approval_request (
    id uuid DEFAULT uuidv7() NOT NULL,
    agent_run_id uuid,
    run_id uuid,
    paused_tool text,
    requested_action text NOT NULL,
    requested_by_agent text NOT NULL,
    risk_level text NOT NULL,
    approval_status text DEFAULT 'pending'::text NOT NULL,
    requested_at timestamp with time zone DEFAULT now() NOT NULL,
    decided_at timestamp with time zone,
    decided_by text,
    decision_notes text,
    CONSTRAINT approval_request_approval_status_check CHECK ((approval_status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text, 'expired'::text]))),
    CONSTRAINT approval_request_risk_level_check CHECK ((risk_level = ANY (ARRAY['low'::text, 'medium'::text, 'high'::text, 'critical'::text])))
);


--
-- Name: transcript_insight; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transcript_insight (
    id uuid DEFAULT uuidv7() NOT NULL,
    source_file text NOT NULL,
    platform text,
    insight_type text NOT NULL,
    content text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    mined_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: api_keys id; Type: DEFAULT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.api_keys ALTER COLUMN id SET DEFAULT nextval('ai.api_keys_id_seq'::regclass);


--
-- Name: agno_approvals agno_approvals_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_approvals
    ADD CONSTRAINT agno_approvals_pkey PRIMARY KEY (id);


--
-- Name: agno_component_configs agno_component_configs_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_component_configs
    ADD CONSTRAINT agno_component_configs_pkey PRIMARY KEY (component_id, version);


--
-- Name: agno_component_links agno_component_links_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_component_links
    ADD CONSTRAINT agno_component_links_pkey PRIMARY KEY (parent_component_id, parent_version, link_kind, link_key);


--
-- Name: agno_components agno_components_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_components
    ADD CONSTRAINT agno_components_pkey PRIMARY KEY (component_id);


--
-- Name: agno_eval_runs agno_eval_runs_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_eval_runs
    ADD CONSTRAINT agno_eval_runs_pkey PRIMARY KEY (run_id);


--
-- Name: agno_learnings agno_learnings_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_learnings
    ADD CONSTRAINT agno_learnings_pkey PRIMARY KEY (learning_id);


--
-- Name: agno_memories agno_memories_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_memories
    ADD CONSTRAINT agno_memories_pkey PRIMARY KEY (memory_id);


--
-- Name: agno_metrics agno_metrics_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_metrics
    ADD CONSTRAINT agno_metrics_pkey PRIMARY KEY (id);


--
-- Name: agno_metrics agno_metrics_uq_metrics_date_period; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_metrics
    ADD CONSTRAINT agno_metrics_uq_metrics_date_period UNIQUE (date, aggregation_period);


--
-- Name: agno_schedule_runs agno_schedule_runs_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_schedule_runs
    ADD CONSTRAINT agno_schedule_runs_pkey PRIMARY KEY (id);


--
-- Name: agno_schedules agno_schedules_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_schedules
    ADD CONSTRAINT agno_schedules_pkey PRIMARY KEY (id);


--
-- Name: agno_schema_versions agno_schema_versions_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_schema_versions
    ADD CONSTRAINT agno_schema_versions_pkey PRIMARY KEY (table_name);


--
-- Name: agno_sessions agno_sessions_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_sessions
    ADD CONSTRAINT agno_sessions_pkey PRIMARY KEY (session_id);


--
-- Name: api_keys api_keys_key_key; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.api_keys
    ADD CONSTRAINT api_keys_key_key UNIQUE (key);


--
-- Name: api_keys api_keys_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);


--
-- Name: casebible_evidence_contents casebible_evidence_contents_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.casebible_evidence_contents
    ADD CONSTRAINT casebible_evidence_contents_pkey PRIMARY KEY (id);


--
-- Name: casebible_evidence_test_contents casebible_evidence_test_contents_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.casebible_evidence_test_contents
    ADD CONSTRAINT casebible_evidence_test_contents_pkey PRIMARY KEY (id);


--
-- Name: casebible_ingest_test2_contents casebible_ingest_test2_contents_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.casebible_ingest_test2_contents
    ADD CONSTRAINT casebible_ingest_test2_contents_pkey PRIMARY KEY (id);


--
-- Name: casebible_ingest_test_contents casebible_ingest_test_contents_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.casebible_ingest_test_contents
    ADD CONSTRAINT casebible_ingest_test_contents_pkey PRIMARY KEY (id);


--
-- Name: platform_knowledge_contents platform_knowledge_contents_pkey; Type: CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.platform_knowledge_contents
    ADD CONSTRAINT platform_knowledge_contents_pkey PRIMARY KEY (id);


--
-- Name: normalized_record normalized_record_pkey; Type: CONSTRAINT; Schema: analysis; Owner: -
--

ALTER TABLE ONLY analysis.normalized_record
    ADD CONSTRAINT normalized_record_pkey PRIMARY KEY (id);


--
-- Name: evidence_hash evidence_hash_pkey; Type: CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.evidence_hash
    ADD CONSTRAINT evidence_hash_pkey PRIMARY KEY (id);


--
-- Name: agent_run agent_run_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agent_run
    ADD CONSTRAINT agent_run_pkey PRIMARY KEY (id);


--
-- Name: approval_request approval_request_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approval_request
    ADD CONSTRAINT approval_request_pkey PRIMARY KEY (id);


--
-- Name: transcript_insight transcript_insight_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transcript_insight
    ADD CONSTRAINT transcript_insight_pkey PRIMARY KEY (id);


--
-- Name: idx_agno_approvals_agent_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_agent_id ON ai.agno_approvals USING btree (agent_id);


--
-- Name: idx_agno_approvals_approval_type; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_approval_type ON ai.agno_approvals USING btree (approval_type);


--
-- Name: idx_agno_approvals_created_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_created_at ON ai.agno_approvals USING btree (created_at);


--
-- Name: idx_agno_approvals_pause_type; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_pause_type ON ai.agno_approvals USING btree (pause_type);


--
-- Name: idx_agno_approvals_run_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_run_id ON ai.agno_approvals USING btree (run_id);


--
-- Name: idx_agno_approvals_run_status; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_run_status ON ai.agno_approvals USING btree (run_status);


--
-- Name: idx_agno_approvals_schedule_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_schedule_id ON ai.agno_approvals USING btree (schedule_id);


--
-- Name: idx_agno_approvals_schedule_run_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_schedule_run_id ON ai.agno_approvals USING btree (schedule_run_id);


--
-- Name: idx_agno_approvals_session_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_session_id ON ai.agno_approvals USING btree (session_id);


--
-- Name: idx_agno_approvals_source_type; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_source_type ON ai.agno_approvals USING btree (source_type);


--
-- Name: idx_agno_approvals_status; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_status ON ai.agno_approvals USING btree (status);


--
-- Name: idx_agno_approvals_team_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_team_id ON ai.agno_approvals USING btree (team_id);


--
-- Name: idx_agno_approvals_user_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_user_id ON ai.agno_approvals USING btree (user_id);


--
-- Name: idx_agno_approvals_workflow_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_approvals_workflow_id ON ai.agno_approvals USING btree (workflow_id);


--
-- Name: idx_agno_component_configs_created_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_component_configs_created_at ON ai.agno_component_configs USING btree (created_at);


--
-- Name: idx_agno_component_configs_stage; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_component_configs_stage ON ai.agno_component_configs USING btree (stage);


--
-- Name: idx_agno_component_links_created_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_component_links_created_at ON ai.agno_component_links USING btree (created_at);


--
-- Name: idx_agno_component_links_link_kind; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_component_links_link_kind ON ai.agno_component_links USING btree (link_kind);


--
-- Name: idx_agno_components_component_type; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_components_component_type ON ai.agno_components USING btree (component_type);


--
-- Name: idx_agno_components_created_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_components_created_at ON ai.agno_components USING btree (created_at);


--
-- Name: idx_agno_components_current_version; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_components_current_version ON ai.agno_components USING btree (current_version);


--
-- Name: idx_agno_components_name; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_components_name ON ai.agno_components USING btree (name);


--
-- Name: idx_agno_eval_runs_created_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_eval_runs_created_at ON ai.agno_eval_runs USING btree (created_at);


--
-- Name: idx_agno_learnings_agent_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_learnings_agent_id ON ai.agno_learnings USING btree (agent_id);


--
-- Name: idx_agno_learnings_created_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_learnings_created_at ON ai.agno_learnings USING btree (created_at);


--
-- Name: idx_agno_learnings_entity_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_learnings_entity_id ON ai.agno_learnings USING btree (entity_id);


--
-- Name: idx_agno_learnings_entity_type; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_learnings_entity_type ON ai.agno_learnings USING btree (entity_type);


--
-- Name: idx_agno_learnings_learning_type; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_learnings_learning_type ON ai.agno_learnings USING btree (learning_type);


--
-- Name: idx_agno_learnings_namespace; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_learnings_namespace ON ai.agno_learnings USING btree (namespace);


--
-- Name: idx_agno_learnings_session_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_learnings_session_id ON ai.agno_learnings USING btree (session_id);


--
-- Name: idx_agno_learnings_team_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_learnings_team_id ON ai.agno_learnings USING btree (team_id);


--
-- Name: idx_agno_learnings_user_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_learnings_user_id ON ai.agno_learnings USING btree (user_id);


--
-- Name: idx_agno_learnings_workflow_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_learnings_workflow_id ON ai.agno_learnings USING btree (workflow_id);


--
-- Name: idx_agno_memories_created_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_memories_created_at ON ai.agno_memories USING btree (created_at);


--
-- Name: idx_agno_memories_updated_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_memories_updated_at ON ai.agno_memories USING btree (updated_at);


--
-- Name: idx_agno_memories_user_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_memories_user_id ON ai.agno_memories USING btree (user_id);


--
-- Name: idx_agno_metrics_date; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_metrics_date ON ai.agno_metrics USING btree (date);


--
-- Name: idx_agno_schedule_runs_created_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_schedule_runs_created_at ON ai.agno_schedule_runs USING btree (created_at);


--
-- Name: idx_agno_schedule_runs_schedule_id; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_schedule_runs_schedule_id ON ai.agno_schedule_runs USING btree (schedule_id);


--
-- Name: idx_agno_schedule_runs_status; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_schedule_runs_status ON ai.agno_schedule_runs USING btree (status);


--
-- Name: idx_agno_schedules_created_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_schedules_created_at ON ai.agno_schedules USING btree (created_at);


--
-- Name: idx_agno_schedules_enabled_next_run_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_schedules_enabled_next_run_at ON ai.agno_schedules USING btree (enabled, next_run_at);


--
-- Name: idx_agno_schedules_name; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_schedules_name ON ai.agno_schedules USING btree (name);


--
-- Name: idx_agno_schedules_next_run_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_schedules_next_run_at ON ai.agno_schedules USING btree (next_run_at);


--
-- Name: idx_agno_schema_versions_created_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_schema_versions_created_at ON ai.agno_schema_versions USING btree (created_at);


--
-- Name: idx_agno_sessions_created_at; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_sessions_created_at ON ai.agno_sessions USING btree (created_at);


--
-- Name: idx_agno_sessions_session_type; Type: INDEX; Schema: ai; Owner: -
--

CREATE INDEX idx_agno_sessions_session_type ON ai.agno_sessions USING btree (session_type);


--
-- Name: idx_normrec_artifact; Type: INDEX; Schema: analysis; Owner: -
--

CREATE INDEX idx_normrec_artifact ON analysis.normalized_record USING btree (artifact_id);


--
-- Name: idx_normrec_conv; Type: INDEX; Schema: analysis; Owner: -
--

CREATE INDEX idx_normrec_conv ON analysis.normalized_record USING btree (source, conversation_id);


--
-- Name: idx_normrec_occurred; Type: INDEX; Schema: analysis; Owner: -
--

CREATE INDEX idx_normrec_occurred ON analysis.normalized_record USING btree (occurred_at);


--
-- Name: idx_evidence_hash_digest; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_evidence_hash_digest ON evidence.evidence_hash USING btree (digest);


--
-- Name: idx_agent_run_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_agent_run_status ON public.agent_run USING btree (status, started_at DESC);


--
-- Name: idx_approval_request_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_approval_request_status ON public.approval_request USING btree (approval_status, requested_at DESC);


--
-- Name: idx_transcript_insight_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transcript_insight_type ON public.transcript_insight USING btree (insight_type, mined_at DESC);


--
-- Name: agno_component_configs agno_component_configs_component_id_fkey; Type: FK CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_component_configs
    ADD CONSTRAINT agno_component_configs_component_id_fkey FOREIGN KEY (component_id) REFERENCES ai.agno_components(component_id);


--
-- Name: agno_component_links agno_component_links_child_component_id_fkey; Type: FK CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_component_links
    ADD CONSTRAINT agno_component_links_child_component_id_fkey FOREIGN KEY (child_component_id) REFERENCES ai.agno_components(component_id);


--
-- Name: agno_component_links agno_component_links_parent_component_id_parent_version_fkey; Type: FK CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_component_links
    ADD CONSTRAINT agno_component_links_parent_component_id_parent_version_fkey FOREIGN KEY (parent_component_id, parent_version) REFERENCES ai.agno_component_configs(component_id, version);


--
-- Name: agno_schedule_runs agno_schedule_runs_schedule_id_fkey; Type: FK CONSTRAINT; Schema: ai; Owner: -
--

ALTER TABLE ONLY ai.agno_schedule_runs
    ADD CONSTRAINT agno_schedule_runs_schedule_id_fkey FOREIGN KEY (schedule_id) REFERENCES ai.agno_schedules(id) ON DELETE CASCADE;


--
-- Name: normalized_record normalized_record_artifact_id_fkey; Type: FK CONSTRAINT; Schema: analysis; Owner: -
--

ALTER TABLE ONLY analysis.normalized_record
    ADD CONSTRAINT normalized_record_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES evidence.evidence_hash(id);


--
-- Name: approval_request approval_request_agent_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.approval_request
    ADD CONSTRAINT approval_request_agent_run_id_fkey FOREIGN KEY (agent_run_id) REFERENCES public.agent_run(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict FsaauFYkVQKu4Rn6mKfC9HHVGENKdZWzCTYkNHm4pPvOa5UrRBNACO5rQcWjzHP

