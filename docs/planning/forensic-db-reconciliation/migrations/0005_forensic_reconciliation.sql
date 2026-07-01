-- =====================================================================================
-- 0005_forensic_reconciliation.sql — live-DB reconciliation migration (IDEMPOTENT)
-- Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30
-- =====================================================================================
--  TARGET: live PG18 `agno-postgres:18-duckdb`, DB `ai`, role `ai`, on ovh3-data.
--  BASELINE: live introspection 2026-06-30 (live-introspection/). Live forensic objects =
--    schemas evidence/analysis/public; tables evidence.evidence_hash, analysis.normalized_record,
--    public.{agent_run,approval_request,transcript_insight}; everything else is GREENFIELD.
--  VERDICT: additive / low-risk. No destructive DROPs (the "competing" tables the design
--    deprecates — analysis.provenance, evidence.ingestion_run, D3 raw_timeline_segment, etc. —
--    never existed live, confirmed by PG_live_summary.txt; nothing to drop).
--
--  !!! TRANSACTION CAUTION — DO NOT wrap this whole file in one BEGIN/COMMIT. !!!
--    STEP 1 contains CREATE TYPE / ALTER TYPE ... ADD VALUE. A new enum value cannot be
--    USED in the same txn that adds it, and ADD VALUE cannot run inside a multi-statement
--    txn block on older PG. Run STEP 0 + STEP 1 as standalone statements FIRST (psql default
--    autocommit), THEN run STEP 2..16. Re-runnable: every object is guarded.
--
--  RUN BY HAND on the live (non-empty) volume — NOT via docker-entrypoint-initdb.d
--    (that fires ONLY on an empty pgdata; the live volume already has 0001-0003 applied).
--
--  Search 'TODO(human):' for every decision needing owner sign-off before court reliance.
-- =====================================================================================


-- =====================================================================================
-- STEP 0 — EXTENSIONS  (CORRECTIVE ITEM A: install the 4 drifted contrib extensions)
--   Live has: pg_duckdb, postgis, vector, pgcrypto, pg_trgm, btree_gin, btree_gist,
--             unaccent, pg_stat_statements (per PG_live_summary.txt).
--   DRIFT (declared in sql/0001, NOT installed live): citext, ltree, hstore, fuzzystrmatch.
--   All four are STANDARD contrib — present in the postgres:18 base layer of the
--   agno-postgres:18-duckdb image (sql/0001 comment: "all contrib — ship with the base
--   image, no apt"). If any CREATE EXTENSION below fails with "could not open extension
--   control file", the contrib package is missing from the image → STOP and rebuild the
--   image; do NOT proceed (fuzzystrmatch/citext are load-bearing for entity resolution).
-- =====================================================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;        -- LIVE (re-assert)
CREATE EXTENSION IF NOT EXISTS pg_trgm;         -- LIVE (re-assert)
CREATE EXTENSION IF NOT EXISTS btree_gin;       -- LIVE (re-assert)
CREATE EXTENSION IF NOT EXISTS btree_gist;      -- LIVE (re-assert)
CREATE EXTENSION IF NOT EXISTS unaccent;        -- LIVE (re-assert)
CREATE EXTENSION IF NOT EXISTS vector;          -- LIVE (re-assert; LEGACY — vectors live in Milvus, ADR-0027)
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;   -- [DRIFT → INSTALL] soundex/levenshtein/dmetaphone (id resolution)
CREATE EXTENSION IF NOT EXISTS citext;          -- [DRIFT → INSTALL] case-insensitive text (names/emails/handles)
CREATE EXTENSION IF NOT EXISTS ltree;           -- [DRIFT → INSTALL] hierarchical labels (file_node.node_path)
CREATE EXTENSION IF NOT EXISTS hstore;          -- [DRIFT → INSTALL] key-value attribute bags
-- Guarded (custom-image only; already LIVE per introspection):
DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS postgis;  EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'postgis skipped'; END $$;
DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS pg_duckdb; EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'pg_duckdb skipped'; END $$;
-- BM25/pg_textsearch intentionally ABSENT (STAGED-not-baked; Milvus owns hybrid/BM25 — ADR-0027).
-- Native PG18 uuidv7() required (live confirms: evidence_hash/normalized_record DEFAULT uuidv7()).


-- =====================================================================================
-- STEP 1 — SCHEMAS + CUSTOM TYPES  (CORRECTIVE ITEM B: apply sql/0004 + disclosure_tier fix)
--   Live drift: sql/0004 NOT applied (no entity_type/event_type/temporal_class/mcl_factor/
--   source_system/match_method enums; no confidence/canonical_id/geo_point domains; no
--   source_ref composite — per PG_live_types.txt + summary). This step bakes 0004 in-line
--   (idempotent) so the migration is self-contained; running sql/0004_custom_types.sql first
--   is equivalent and also safe.
--   !! RUN STEP 1 OUTSIDE A TRANSACTION (autocommit). ALTER TYPE ADD VALUE at 1.4 cannot be
--      used in the same txn it is added in.
-- =====================================================================================

CREATE SCHEMA IF NOT EXISTS evidence;   -- LIVE (re-assert)
CREATE SCHEMA IF NOT EXISTS analysis;   -- LIVE (re-assert)
-- schema `public` already exists (LIVE). schema `ai` (Agno) + `duckdb` (pg_duckdb) untouched.

-- 1.0  sql/0004 base types (idempotent inline; the live volume is missing ALL of these).
DO $$ BEGIN CREATE TYPE entity_type AS ENUM
  ('person','org','project','tech','location','concept');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE temporal_class AS ENUM ('historical','current','future');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE event_type AS ENUM
  ('milestone','decision','meeting','incident','change','memory','upcoming');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE mcl_factor AS ENUM ('a','b','c','d','e','f','g','h','i','j','k','l');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE source_system AS ENUM ('postgres','neo4j','milvus','surrealdb');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE match_method AS ENUM ('exact','resolved','manual');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN confidence AS numeric(4,3)
  CHECK (VALUE IS NULL OR (VALUE >= 0 AND VALUE <= 1));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN canonical_id AS uuid;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN geo_point AS geography(Point, 4326);
EXCEPTION WHEN duplicate_object THEN NULL;
         WHEN undefined_object THEN RAISE NOTICE 'postgis geography absent — geo_point skipped'; END $$;
DO $$ BEGIN CREATE TYPE source_ref AS (system source_system, native_id text, locator text);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- 1.1  disclosure_tier double-definition FIX (E1 §5.1). The 0004 ENUM disclosure_tier
--      (public|restricted|sealed = ACCESS classification) collides in name with the
--      as-built analysis.normalized_record.disclosure_tier TEXT CHECK column
--      (contemporaneous|hindsight|discovered = KNOWLEDGE horizon, from 0003 — the survivor,
--      verified live: normalized_record_disclosure_tier_check). Rename the access ENUM to
--      sensitivity_tier so the two concepts stop colliding. Idempotent.
DO $$ BEGIN
    ALTER TYPE disclosure_tier RENAME TO sensitivity_tier;
EXCEPTION
    WHEN undefined_object THEN NULL;   -- 0004 enum never created (live case) OR already renamed
    WHEN duplicate_object THEN NULL;   -- sensitivity_tier already exists
END $$;
-- Live volume never had the 0004 enum, so create the access enum fresh under the fixed name:
DO $$ BEGIN
    CREATE TYPE sensitivity_tier AS ENUM ('public','restricted','sealed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- 1.2  NEW shared cross-domain enums (created once; consolidate per-domain duplicates).
DO $$ BEGIN CREATE TYPE evidence_tier AS ENUM
  ('raw','extracted','inferred','analytical','legal_conclusion');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE assertion_type AS ENUM
  ('raw_evidence','extracted_fact','inferred_fact','analytical_finding','legal_conclusion');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE precision_class AS ENUM ('exact','approximate','inferred','uncertain');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE strength_class AS ENUM ('none','weak','moderate','strong','conclusive');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE review_state AS ENUM
  ('unreviewed','in_review','approved','rejected','needs_more_evidence');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE conduct_party AS ENUM
  ('user','partner','child','mutual','third_party','institution','unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE cycle_phase AS ENUM
  ('calm','tension_building','conflict','repair','reconciliation',
   'love_bombing','withdrawal','escalation','de_escalation','unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE disclosure_horizon AS ENUM
  ('contemporaneous','hindsight','discovered');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE temporal_relation AS ENUM
  ('preceded','meets','overlaps','during','same_day','equals','caused_hypothesis');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE anchor_kind AS ENUM
  ('docketed_event','recurring_holiday','life_event','derived');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE assertion_source AS ENUM
  ('gps','claimed_text','exif','ip_geo','cell_tower','wifi','witness','geocode','manual');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE geocode_provider AS ENUM
  ('google','radar','nominatim','osm','manual');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE pattern_match_type AS ENUM ('literal','regex');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE category_polarity AS ENUM
  ('negative','positive','neutral','linguistic_marker');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE detection_method AS ENUM
  ('literal','regex','priority_screener','semantic_similarity','model','human','imported');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- TODO(human): the surviving bitemporal column analysis.normalized_record.disclosure_tier
--   stays AS-BUILT (TEXT CHECK contemporaneous|hindsight|discovered) — non-destructive, and
--   verified live. The cross-store docs (S2/S3) call this concept `knowledge_horizon`. Decide
--   ONCE whether to (a) leave the column name `disclosure_tier`, or (b) rename it to
--   `knowledge_horizon` and retype to the disclosure_horizon enum (a coordinated records-domain
--   migration). Until decided, NEW tables use the disclosure_horizon enum with the SAME
--   vocabulary; the existing column is the canonical source. (integrity review A5)

-- 1.4  ADAPT (never redefine) the 0004 entity_type + event_type via ADD VALUE.
--      !! RUN OUTSIDE A TRANSACTION, BEFORE the table DDL — new values aren't usable in the
--      txn that adds them. IF NOT EXISTS makes each re-runnable.
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'phone';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'email';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'handle';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'device';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'account';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'vehicle';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'address';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'court';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'attorney';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'school';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'doctor';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'institution';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'platform';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'ai_system';
ALTER TYPE event_type  ADD VALUE IF NOT EXISTS 'presence';
ALTER TYPE event_type  ADD VALUE IF NOT EXISTS 'communication';
ALTER TYPE event_type  ADD VALUE IF NOT EXISTS 'observation';

-- =====================================================================================
-- ============  EVERYTHING BELOW (STEP 2..16) IS SAFE IN A SINGLE TRANSACTION  =========
-- ============  (no CREATE TYPE / ADD VALUE past this line). Optionally wrap in   =======
-- ============  BEGIN; ... COMMIT; for all-or-nothing table creation.            =======
-- =====================================================================================

-- =====================================================================================
-- STEP 2 — SHARED GUARD FUNCTIONS (append-only / write-once)
-- =====================================================================================
CREATE OR REPLACE FUNCTION evidence.forbid_mutation() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'evidence.% is immutable (originals/append-only): % blocked (never-delete -> _stale)',
    TG_TABLE_NAME, TG_OP;
END $$;
CREATE OR REPLACE FUNCTION analysis.forbid_mutation() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'analysis.% is append-only: % blocked (never-delete -> _stale)',
    TG_TABLE_NAME, TG_OP;
END $$;
CREATE OR REPLACE FUNCTION public.forbid_mutation() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'public.% is append-only: % blocked', TG_TABLE_NAME, TG_OP;
END $$;
CREATE OR REPLACE FUNCTION analysis.reject_mutation() RETURNS trigger
  LANGUAGE plpgsql AS $$ BEGIN
    RAISE EXCEPTION 'append-only table %.% — % not allowed', TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP; END $$;


-- =====================================================================================
-- STEP 3 — REFERENCE TABLES (seeded)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS analysis.custody_factor (
    factor          mcl_factor PRIMARY KEY,
    code_display    text NOT NULL,
    name            text NOT NULL,
    statutory_text  text,            -- TODO(human): paste verbatim MCL 722.23(x) at apply time
    is_key_factor   boolean NOT NULL DEFAULT false,
    notes           text
);
INSERT INTO analysis.custody_factor (factor, code_display, name, is_key_factor) VALUES
  ('a','A','Love, affection & emotional ties',                 false),
  ('b','B','Capacity & disposition to give love/guidance',     false),
  ('c','C','Capacity to provide food, clothing, medical care', false),
  ('d','D','Length of time in a stable environment',           false),
  ('e','E','Permanence as a family unit',                      false),
  ('f','F','Moral fitness',                                    false),
  ('g','G','Mental & physical health',                         false),
  ('h','H','Home, school & community record',                  false),
  ('i','I','Reasonable preference of the child',               false),
  ('j','J','Willingness to facilitate the other relationship', true),
  ('k','K','Domestic violence',                                true),
  ('l','L','Any other relevant factor',                        false)
ON CONFLICT (factor) DO NOTHING;


-- =====================================================================================
-- STEP 4 — EVIDENCE SCHEMA (raw/source + custody; agents READ-ONLY; append-only)
-- =====================================================================================

-- 4.1  Raw source registry (write-once original-of-record).
CREATE TABLE IF NOT EXISTS evidence.source (
    id                  uuid PRIMARY KEY DEFAULT uuidv7(),
    sha256              bytea NOT NULL,
    md5_prefilter       bytea,
    byte_size           bigint NOT NULL,
    mime_type           text,
    original_filename   text,
    source_type         text NOT NULL
                        CHECK (source_type IN ('device_dump','chat_export','screenshot',
                          'call_log','pdf','media','takeout','social_export','document','other')),
    source_platform     text,
    custodian           text NOT NULL DEFAULT 'Matt Salem',
    acquisition_source  text NOT NULL,
    acquisition_method  text CHECK (acquisition_method IS NULL OR acquisition_method IN
                          ('forensic_image','manual_export','cloud_pull','photograph','scan','backup')),
    origin_device_id    uuid,
    origin_account      uuid,
    acquired_at_raw     text,
    acquired_at_utc     timestamptz,
    acquired_tz_offset  text,
    acquired_certainty  precision_class NOT NULL DEFAULT 'exact',
    provenance_tier     text NOT NULL DEFAULT 'r2_canonical'
                        CHECK (provenance_tier IN ('r2_canonical','backup_corroborating')),
    r2_bucket           text,
    r2_key              text,
    local_path          text,
    hash_canon_version  text NOT NULL DEFAULT 'h1-rawbytes-v1',
    sensitivity_tier    sensitivity_tier NOT NULL DEFAULT 'restricted',
    legal_sensitivity   text NOT NULL DEFAULT 'none'
                        CHECK (legal_sensitivity IN ('none','privileged','confidential','in_camera')),
    privacy_sensitivity text NOT NULL DEFAULT 'none'
                        CHECK (privacy_sensitivity IN ('none','pii','minor','sensitive_pii')),
    supersedes_source_id uuid REFERENCES evidence.source(id),
    custody_status      text NOT NULL DEFAULT 'collected'
                        CHECK (custody_status IN ('collected','sealed','in_processing','verified','disputed','released')),
    extraction_status   text NOT NULL DEFAULT 'pending'
                        CHECK (extraction_status IN ('pending','running','done','failed','n/a')),
    processing_status   text NOT NULL DEFAULT 'pending'
                        CHECK (processing_status IN ('pending','enriched','analyzed','failed')),
    review_status       text NOT NULL DEFAULT 'not_reviewed'
                        CHECK (review_status IN ('not_reviewed','in_review','reviewed','flagged')),
    export_status       text NOT NULL DEFAULT 'not_exported'
                        CHECK (export_status IN ('not_exported','in_package','exported','withdrawn')),
    verified_by         text,
    verified_at         timestamptz,
    original_metadata   jsonb NOT NULL DEFAULT '{}',
    derived_metadata    jsonb NOT NULL DEFAULT '{}',
    ingested_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT source_sha256_len  CHECK (octet_length(sha256) = 32),
    CONSTRAINT source_sha256_uniq UNIQUE (sha256)
);
CREATE INDEX IF NOT EXISTS idx_source_custody       ON evidence.source (custody_status);
CREATE INDEX IF NOT EXISTS idx_source_platform      ON evidence.source (source_platform, source_type);
CREATE INDEX IF NOT EXISTS idx_source_filename_trgm ON evidence.source USING gin (original_filename gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_source_orig_meta     ON evidence.source USING gin (original_metadata);
CREATE INDEX IF NOT EXISTS idx_source_supersedes    ON evidence.source (supersedes_source_id);

CREATE OR REPLACE FUNCTION evidence.source_immutable_core() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'evidence.source is write-once: DELETE blocked (never-delete -> _stale)';
    END IF;
    IF  NEW.sha256 IS DISTINCT FROM OLD.sha256
     OR NEW.md5_prefilter IS DISTINCT FROM OLD.md5_prefilter
     OR NEW.byte_size IS DISTINCT FROM OLD.byte_size
     OR NEW.mime_type IS DISTINCT FROM OLD.mime_type
     OR NEW.original_filename IS DISTINCT FROM OLD.original_filename
     OR NEW.source_type IS DISTINCT FROM OLD.source_type
     OR NEW.custodian IS DISTINCT FROM OLD.custodian
     OR NEW.acquisition_source IS DISTINCT FROM OLD.acquisition_source
     OR NEW.r2_bucket IS DISTINCT FROM OLD.r2_bucket
     OR NEW.r2_key IS DISTINCT FROM OLD.r2_key
     OR NEW.provenance_tier IS DISTINCT FROM OLD.provenance_tier
     OR NEW.hash_canon_version IS DISTINCT FROM OLD.hash_canon_version
     OR NEW.supersedes_source_id IS DISTINCT FROM OLD.supersedes_source_id
     OR NEW.original_metadata IS DISTINCT FROM OLD.original_metadata
     OR NEW.ingested_at IS DISTINCT FROM OLD.ingested_at THEN
        RAISE EXCEPTION 'evidence.source core/identity columns immutable (only lifecycle status may change)';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS source_immutable ON evidence.source;
CREATE TRIGGER source_immutable BEFORE UPDATE OR DELETE ON evidence.source
  FOR EACH ROW EXECUTE FUNCTION evidence.source_immutable_core();

-- 4.2  Recursive file decomposition.
CREATE TABLE IF NOT EXISTS evidence.file_node (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    source_id       uuid NOT NULL REFERENCES evidence.source(id),
    parent_node_id  uuid REFERENCES evidence.file_node(id),
    node_kind       text NOT NULL CHECK (node_kind IN ('file','archive_member','page','frame','region',
                      'screenshot','ocr_block','attachment','message_unit','event_unit')),
    node_path       ltree,
    ordinal         int,
    sha256          bytea,
    byte_span_start bigint,
    byte_span_end   bigint,
    locator         jsonb NOT NULL DEFAULT '{}',
    mime_type       text,
    extraction_confidence confidence,
    attrs           jsonb NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT file_node_sha_len CHECK (sha256 IS NULL OR octet_length(sha256) = 32)
);
CREATE INDEX IF NOT EXISTS idx_filenode_source ON evidence.file_node (source_id);
CREATE INDEX IF NOT EXISTS idx_filenode_parent ON evidence.file_node (parent_node_id);
CREATE INDEX IF NOT EXISTS idx_filenode_path   ON evidence.file_node USING gist (node_path);
CREATE INDEX IF NOT EXISTS idx_filenode_sha    ON evidence.file_node (sha256);
DROP TRIGGER IF EXISTS filenode_immutable ON evidence.file_node;
CREATE TRIGGER filenode_immutable BEFORE UPDATE OR DELETE ON evidence.file_node
  FOR EACH ROW EXECUTE FUNCTION evidence.forbid_mutation();

-- 4.3  EXTEND the as-built evidence.evidence_hash  [EXISTS-NEEDS-ALTER].
--      LIVE as-built cols (verified PG_live_schema.sql): id, source_ref, algo, digest,
--      hashed_at, blob_key, meta + CHECK(algo<>'sha256' OR octet_length(digest)=32) +
--      idx_evidence_hash_digest. All PRESERVED; new columns are purely additive.
ALTER TABLE evidence.evidence_hash
  ADD COLUMN IF NOT EXISTS level           text NOT NULL DEFAULT 'H1'
                          CHECK (level IN ('H1','H2','H3')),
  ADD COLUMN IF NOT EXISTS source_id       uuid REFERENCES evidence.source(id),
  ADD COLUMN IF NOT EXISTS file_node_id    uuid REFERENCES evidence.file_node(id),
  ADD COLUMN IF NOT EXISTS md5_prefilter   bytea,
  ADD COLUMN IF NOT EXISTS record_locator  jsonb,
  ADD COLUMN IF NOT EXISTS member_hash_ids uuid[],
  ADD COLUMN IF NOT EXISTS canon_version   text NOT NULL DEFAULT 'h1-rawbytes-v1',
  ADD COLUMN IF NOT EXISTS computed_by     text;
DO $$ BEGIN
  ALTER TABLE evidence.evidence_hash
    ADD CONSTRAINT evidence_hash_subject_ck CHECK (
      level = 'H3' OR source_id IS NOT NULL OR file_node_id IS NOT NULL) NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_evhash_level_source ON evidence.evidence_hash (level, source_id);
CREATE INDEX IF NOT EXISTS idx_evhash_filenode     ON evidence.evidence_hash (file_node_id);
CREATE INDEX IF NOT EXISTS idx_evhash_meta         ON evidence.evidence_hash USING gin (meta);
-- TODO(human): add the immutability trigger AFTER the one-time backfill of level/source_id
--   on legacy rows (the trigger blocks UPDATE). Until backfilled, leave it off:
-- CREATE TRIGGER evidence_hash_immutable BEFORE UPDATE OR DELETE ON evidence.evidence_hash
--   FOR EACH ROW EXECUTE FUNCTION evidence.forbid_mutation();

-- 4.4  Chain-of-custody event log (append-only, pgcrypto sha256 hash-chained).
CREATE TABLE IF NOT EXISTS evidence.custody_event (
    seq             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id              uuid NOT NULL DEFAULT uuidv7() UNIQUE,
    source_id       uuid NOT NULL REFERENCES evidence.source(id),
    file_node_id    uuid REFERENCES evidence.file_node(id),
    evidence_hash_id uuid REFERENCES evidence.evidence_hash(id),
    event_type      text NOT NULL CHECK (event_type IN ('collected','sealed','in_processing','verified',
                      'disputed','released','re_hashed','integrity_violation','superseded','accessed')),
    actor           text NOT NULL,
    occurred_at     timestamptz NOT NULL DEFAULT now(),
    occurred_certainty precision_class NOT NULL DEFAULT 'exact',
    detail          jsonb NOT NULL DEFAULT '{}',
    prev_event_digest bytea,
    event_digest      bytea NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_custody_source ON evidence.custody_event (source_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_custody_type   ON evidence.custody_event (event_type, occurred_at DESC);
CREATE OR REPLACE FUNCTION evidence.chain_custody_event() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.source_id::text, 0));
    SELECT ce.event_digest INTO NEW.prev_event_digest
      FROM evidence.custody_event ce
     WHERE ce.source_id = NEW.source_id ORDER BY ce.seq DESC LIMIT 1;
    NEW.event_digest := digest(convert_to(
        coalesce(NEW.source_id::text,'') || '|' || coalesce(NEW.file_node_id::text,'') || '|' ||
        coalesce(NEW.evidence_hash_id::text,'') || '|' || NEW.event_type || '|' || NEW.actor || '|' ||
        to_char(NEW.occurred_at,'YYYY-MM-DD"T"HH24:MI:SS.US TZH:TZM') || '|' ||
        coalesce(NEW.detail::text,'{}') || '|' || coalesce(encode(NEW.prev_event_digest,'hex'),''),
      'UTF8'), 'sha256');
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS custody_event_chain ON evidence.custody_event;
CREATE TRIGGER custody_event_chain BEFORE INSERT ON evidence.custody_event
  FOR EACH ROW EXECUTE FUNCTION evidence.chain_custody_event();
DROP TRIGGER IF EXISTS custody_event_immutable ON evidence.custody_event;
CREATE TRIGGER custody_event_immutable BEFORE UPDATE OR DELETE ON evidence.custody_event
  FOR EACH ROW EXECUTE FUNCTION evidence.forbid_mutation();

-- 4.5  RAW GEO / TIMELINE (D5 canonical). Order raw points by sequence/serial, never by ts.
CREATE TABLE IF NOT EXISTS evidence.gps_point (
    id             uuid PRIMARY KEY DEFAULT uuidv7(),
    source_id      uuid NOT NULL REFERENCES evidence.source(id),
    file_node_id   uuid REFERENCES evidence.file_node(id),
    device_id      uuid,
    geog           geo_point NOT NULL,
    captured_at    timestamptz,
    captured_raw   text,
    ts_precision   precision_class NOT NULL DEFAULT 'exact',
    accuracy_m     numeric(8,2),
    point_sequence bigint,
    ingest_run_id  uuid,
    raw_data       jsonb NOT NULL DEFAULT '{}'::jsonb,
    data_tier      evidence_tier NOT NULL DEFAULT 'raw' CHECK (data_tier = 'raw'),
    ingested_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gps_point_geog    ON evidence.gps_point USING gist (geog);
CREATE INDEX IF NOT EXISTS idx_gps_point_devtime ON evidence.gps_point (device_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_gps_point_seq     ON evidence.gps_point (source_id, point_sequence);
CREATE INDEX IF NOT EXISTS idx_gps_point_raw     ON evidence.gps_point USING gin (raw_data);

CREATE TABLE IF NOT EXISTS evidence.raw_visit (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    source_id       uuid NOT NULL REFERENCES evidence.source(id),
    file_node_id    uuid REFERENCES evidence.file_node(id),
    event_serial    bigint,
    hierarchy_level int,
    start_raw       text, end_raw text,
    start_utc       timestamptz, end_utc timestamptz,
    tz_offset_min   int,
    duration_s      bigint,
    detection_probability confidence,
    semantic_type   text,
    semantic_probability confidence,
    place_id        text,
    geog            geo_point,
    parent_id       uuid REFERENCES evidence.raw_visit(id),
    memory_id       uuid,
    ingest_run_id   uuid,
    raw_data        jsonb NOT NULL DEFAULT '{}'::jsonb,
    data_tier       evidence_tier NOT NULL DEFAULT 'raw' CHECK (data_tier = 'raw'),
    ingested_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_raw_visit_source ON evidence.raw_visit (source_id);
CREATE INDEX IF NOT EXISTS idx_raw_visit_geog   ON evidence.raw_visit USING gist (geog);
CREATE INDEX IF NOT EXISTS idx_raw_visit_utc    ON evidence.raw_visit (start_utc);

CREATE TABLE IF NOT EXISTS evidence.raw_activity (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    source_id       uuid NOT NULL REFERENCES evidence.source(id),
    file_node_id    uuid REFERENCES evidence.file_node(id),
    event_serial    bigint,
    start_raw       text, end_raw text,
    start_utc       timestamptz, end_utc timestamptz,
    tz_offset_min   int,
    duration_s      bigint,
    activity_type   text,
    activity_probability confidence,
    distance_m      numeric(12,2),
    start_geog      geo_point,
    end_geog        geo_point,
    place_id_start  text, place_id_end text,
    parent_id       uuid,
    memory_id       uuid,
    ingest_run_id   uuid,
    raw_data        jsonb NOT NULL DEFAULT '{}'::jsonb,
    data_tier       evidence_tier NOT NULL DEFAULT 'raw' CHECK (data_tier = 'raw'),
    ingested_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_raw_activity_source ON evidence.raw_activity (source_id);
CREATE INDEX IF NOT EXISTS idx_raw_activity_start  ON evidence.raw_activity USING gist (start_geog);
CREATE INDEX IF NOT EXISTS idx_raw_activity_utc    ON evidence.raw_activity (start_utc);

CREATE TABLE IF NOT EXISTS evidence.raw_path (
    id                 uuid PRIMARY KEY DEFAULT uuidv7(),
    source_id          uuid NOT NULL REFERENCES evidence.source(id),
    file_node_id       uuid REFERENCES evidence.file_node(id),
    path_serial        bigint,
    point_sequence     bigint NOT NULL,
    point_geog         geo_point NOT NULL,
    point_ts_raw       text,
    point_ts_utc       timestamptz,
    tz_offset_min      int,
    aligned_activity_id uuid REFERENCES evidence.raw_activity(id),
    parent_id          uuid REFERENCES evidence.raw_path(id),
    ingest_run_id      uuid,
    raw_data           jsonb NOT NULL DEFAULT '{}'::jsonb,
    data_tier          evidence_tier NOT NULL DEFAULT 'raw' CHECK (data_tier = 'raw'),
    ingested_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_raw_path_source ON evidence.raw_path (source_id, path_serial, point_sequence);
CREATE INDEX IF NOT EXISTS idx_raw_path_geog   ON evidence.raw_path USING gist (point_geog);

CREATE TABLE IF NOT EXISTS evidence.raw_trip (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    source_id       uuid NOT NULL REFERENCES evidence.source(id),
    file_node_id    uuid REFERENCES evidence.file_node(id),
    event_serial    bigint,
    start_raw       text, end_raw text,
    start_utc       timestamptz, end_utc timestamptz,
    tz_offset_min   int,
    duration_s      bigint,
    distance_from_origin_km numeric(12,3),
    destination_place_ids text[],
    parent_id       uuid REFERENCES evidence.raw_trip(id),
    ingest_run_id   uuid,
    raw_data        jsonb NOT NULL DEFAULT '{}'::jsonb,
    data_tier       evidence_tier NOT NULL DEFAULT 'raw' CHECK (data_tier = 'raw'),
    ingested_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_raw_trip_source ON evidence.raw_trip (source_id);
CREATE INDEX IF NOT EXISTS idx_raw_trip_utc    ON evidence.raw_trip (start_utc);


-- =====================================================================================
-- STEP 5 — PUBLIC: CONTEXT VERSION REGISTRIES (run-anchor prerequisites)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS public.prompt_registry (
    prompt_id            uuid PRIMARY KEY DEFAULT uuidv7(),
    prompt_name          text NOT NULL,
    prompt_version       text NOT NULL,
    prompt_type          text NOT NULL CHECK (prompt_type IN
        ('extraction','classification','summary','agent_instruction','tone_style','review','export')),
    full_prompt_text     text NOT NULL,
    body_sha256          bytea NOT NULL,
    purpose              text, inputs_expected text, outputs_expected text,
    known_limitations    text, safety_constraints text,
    human_approval_required boolean NOT NULL DEFAULT false,
    superseded_by        uuid REFERENCES public.prompt_registry(prompt_id),
    status               text NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded','deprecated')),
    created_by           text NOT NULL,
    created_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (prompt_name, prompt_version)
);
CREATE TABLE IF NOT EXISTS public.model_version (
    model_version_id  uuid PRIMARY KEY DEFAULT uuidv7(),
    provider          text,
    model_id          text NOT NULL,
    role              text NOT NULL CHECK (role IN ('llm','embedder','reranker','ocr','asr')),
    version           text, dims int,
    ran_local_capable boolean NOT NULL DEFAULT false,
    params            jsonb NOT NULL DEFAULT '{}',
    created_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (model_id, role, version)
);
CREATE TABLE IF NOT EXISTS public.schema_version (
    schema_version_id uuid PRIMARY KEY DEFAULT uuidv7(),
    version_label text NOT NULL, applies_to text NOT NULL,
    ddl_uri text, ddl_hash bytea, migration_id text,
    supersedes uuid REFERENCES public.schema_version(schema_version_id),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded','deprecated')),
    notes text, created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version_label, applies_to)
);
CREATE TABLE IF NOT EXISTS public.ontology_version (
    ontology_version_id uuid PRIMARY KEY DEFAULT uuidv7(),
    version_label text NOT NULL, source text NOT NULL,
    definition_uri text, definition_hash bytea,
    node_types jsonb NOT NULL DEFAULT '[]', edge_types jsonb NOT NULL DEFAULT '[]',
    supersedes uuid REFERENCES public.ontology_version(ontology_version_id),
    review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
    notes text, created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version_label, source)
);
CREATE TABLE IF NOT EXISTS public.classification_version (
    classification_version_id uuid PRIMARY KEY DEFAULT uuidv7(),
    version_label text NOT NULL, scheme text NOT NULL,
    label_set jsonb NOT NULL DEFAULT '[]', source text NOT NULL,
    definition_uri text, definition_hash bytea,
    supersedes uuid REFERENCES public.classification_version(classification_version_id),
    review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
    notes text, created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version_label, scheme)
);


-- =====================================================================================
-- STEP 6 — ANALYSIS: PROVENANCE / LINEAGE  (processing_run = THE single run anchor)
-- =====================================================================================
CREATE TABLE IF NOT EXISTS analysis.processing_run (
    run_id            uuid PRIMARY KEY DEFAULT uuidv7(),
    run_type          text NOT NULL CHECK (run_type IN
        ('acquisition','file_scan','repository_scan','evidence_ingestion','extraction','ingestion',
         'ocr','transcription','message_parsing','entity_extraction','temporal_extraction',
         'location_extraction','gps_processing','embedding','graph_projection','surreal_consolidation',
         'ontology_merge','schema_generation','classification','pattern_analysis','legal_issue_mapping',
         'scoring','model_analysis','evidence_task_generation','redaction','export','review')),
    run_purpose       text,
    status            text NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued','running','ok','failed','partial','cancelled','superseded')),
    actor             text NOT NULL,
    tool_or_model     text, code_version text,
    prompt_version_id         uuid REFERENCES public.prompt_registry(prompt_id),
    model_version_id          uuid REFERENCES public.model_version(model_version_id),
    schema_version_id         uuid REFERENCES public.schema_version(schema_version_id),
    ontology_version_id       uuid REFERENCES public.ontology_version(ontology_version_id),
    classification_version_id uuid REFERENCES public.classification_version(classification_version_id),
    input_evidence_ids uuid[]  NOT NULL DEFAULT '{}',
    input_artifact_ids uuid[]  NOT NULL DEFAULT '{}',
    output_artifact_ids uuid[] NOT NULL DEFAULT '{}',
    input_digest      jsonb NOT NULL DEFAULT '[]',
    inputs_hash       bytea,
    params            jsonb NOT NULL DEFAULT '{}',
    ran_local_only    boolean NOT NULL DEFAULT false,
    cloud_exposure    boolean NOT NULL DEFAULT false,
    counts_processed  int, counts_failed int,
    confidence_summary jsonb,
    human_review_requirement boolean NOT NULL DEFAULT false,
    replayable        boolean NOT NULL DEFAULT false,
    error_message     text, summary text,
    supersedes_run    uuid REFERENCES analysis.processing_run(run_id),
    started_at        timestamptz, finished_at timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_run_type_status ON analysis.processing_run (run_type, status);
CREATE INDEX IF NOT EXISTS idx_run_started     ON analysis.processing_run (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_inputs_gin  ON analysis.processing_run USING gin (input_evidence_ids);

CREATE TABLE IF NOT EXISTS analysis.tool_call_ledger (
    tool_call_id      uuid PRIMARY KEY DEFAULT uuidv7(),
    run_id            uuid REFERENCES analysis.processing_run(run_id),
    tool_name         text NOT NULL,
    tool_category     text NOT NULL CHECK (tool_category IN ('read','analysis','write','transfer','deploy','llm','mcp')),
    requested_by      text, input_summary text,
    input_payload_uri text, input_hash bytea,
    output_summary    text, output_payload_uri text, output_hash bytea,
    created_artifact_ids uuid[] NOT NULL DEFAULT '{}',
    updated_record_refs  jsonb  NOT NULL DEFAULT '[]',
    runtime_ms int, cost_estimate numeric(12,4),
    human_approval_status text NOT NULL DEFAULT 'n/a' CHECK (human_approval_status IN ('n/a','pending','approved','denied')),
    safety_flags jsonb NOT NULL DEFAULT '[]',
    replayability_status text NOT NULL DEFAULT 'replayable'
        CHECK (replayability_status IN ('replayable','inputs_lost','nondeterministic')),
    errors text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tcl_run ON analysis.tool_call_ledger (run_id);
DROP TRIGGER IF EXISTS tcl_append_only ON analysis.tool_call_ledger;
CREATE TRIGGER tcl_append_only BEFORE UPDATE OR DELETE ON analysis.tool_call_ledger
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();

CREATE TABLE IF NOT EXISTS analysis.artifact_registry (
    artifact_id       uuid PRIMARY KEY DEFAULT uuidv7(),
    artifact_kind     text NOT NULL,
    title text, format text,
    sha256            bytea NOT NULL,
    path_or_uri text, byte_size bigint, content_inline text,
    assertion_type    assertion_type NOT NULL,
    confidence        confidence,
    evidence_strength strength_class,
    timestamp_certainty precision_class,
    is_sensitive      boolean NOT NULL DEFAULT false,
    sensitivity_tier  sensitivity_tier,
    producing_run     uuid REFERENCES analysis.processing_run(run_id),
    parent_artifact_id uuid REFERENCES analysis.artifact_registry(artifact_id),
    derived_from_artifact_ids uuid[] NOT NULL DEFAULT '{}',
    related_source_evidence   uuid[] NOT NULL DEFAULT '{}',
    status            text NOT NULL DEFAULT 'draft' CHECK (status IN
        ('draft','needs_review','active','approved','promoted','rejected','superseded','archived')),
    review_status     review_state NOT NULL DEFAULT 'unreviewed',
    superseded_by     uuid REFERENCES analysis.artifact_registry(artifact_id),
    archive_reason    text, summary_md text,
    metadata_json     jsonb NOT NULL DEFAULT '{}',
    created_by        text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (status <> 'archived' OR archive_reason IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_art_kind_status ON analysis.artifact_registry (artifact_kind, status);
CREATE INDEX IF NOT EXISTS idx_art_sha256      ON analysis.artifact_registry (sha256);
CREATE INDEX IF NOT EXISTS idx_art_evid_gin    ON analysis.artifact_registry USING gin (related_source_evidence);

CREATE TABLE IF NOT EXISTS analysis.lineage_edge (
    edge_id           uuid PRIMARY KEY DEFAULT uuidv7(),
    child_artifact    uuid NOT NULL REFERENCES analysis.artifact_registry(artifact_id),
    parent_artifact   uuid REFERENCES analysis.artifact_registry(artifact_id),
    parent_source     uuid REFERENCES evidence.evidence_hash(id),
    producing_run     uuid REFERENCES analysis.processing_run(run_id),
    role              text NOT NULL CHECK (role IN ('derived_from','supersedes','corroborates','contradicts')),
    note text, created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (parent_artifact IS NOT NULL OR parent_source IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_edge_child ON analysis.lineage_edge (child_artifact);
DROP TRIGGER IF EXISTS edge_append_only ON analysis.lineage_edge;
CREATE TRIGGER edge_append_only BEFORE UPDATE OR DELETE ON analysis.lineage_edge
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();

CREATE TABLE IF NOT EXISTS analysis.score_band_config (
    config_version  text PRIMARY KEY,
    bands           jsonb NOT NULL,
    effective_from  timestamptz NOT NULL DEFAULT now(),
    changed_by      text NOT NULL, rationale text NOT NULL
);
CREATE TABLE IF NOT EXISTS analysis.score (
    score_id        uuid PRIMARY KEY DEFAULT uuidv7(),
    target_kind     text NOT NULL, target_id uuid NOT NULL,
    score_type      text NOT NULL CHECK (score_type IN
        ('extraction','temporal','identity','location','evidence_strength','legal_relevance',
         'abuse_pattern','corroboration','contradiction','court_readiness')),
    value           confidence NOT NULL,
    band            text NOT NULL CHECK (band IN ('very_low','low','medium','high','very_high')),
    method          text NOT NULL CHECK (method IN ('rule','model','human','hybrid')),
    method_detail   jsonb NOT NULL DEFAULT '{}',
    rationale       text NOT NULL,
    evidence_refs   uuid[] NOT NULL DEFAULT '{}',
    assertion_type  assertion_type NOT NULL,
    config_version  text REFERENCES analysis.score_band_config(config_version),
    scoring_run_id  uuid NOT NULL REFERENCES analysis.processing_run(run_id),
    recheck_after   timestamptz, stale boolean NOT NULL DEFAULT false,
    valid_from      timestamptz NOT NULL DEFAULT now(), valid_to timestamptz,
    superseded_by   uuid REFERENCES analysis.score(score_id),
    created_by      text NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_score_target  ON analysis.score (target_kind, target_id);
CREATE INDEX IF NOT EXISTS idx_score_current ON analysis.score (score_type) WHERE valid_to IS NULL;


-- =====================================================================================
-- STEP 7 — ANALYSIS: ENTITIES & IDENTITY RESOLUTION
-- =====================================================================================
CREATE TABLE IF NOT EXISTS analysis.entity (
    id                  uuid PRIMARY KEY DEFAULT uuidv7(),
    entity_type         entity_type NOT NULL,
    display_name        citext, canonical_name citext, normalized_name citext,
    sensitivity_tier    sensitivity_tier,
    is_party            boolean NOT NULL DEFAULT false,
    data_tier           evidence_tier NOT NULL DEFAULT 'inferred',
    evidence_confidence confidence,
    provenance          source_ref[] NOT NULL DEFAULT '{}',
    requires_human_review boolean NOT NULL DEFAULT false,
    review_status       review_state NOT NULL DEFAULT 'unreviewed',
    safe_for_legal_use  boolean NOT NULL DEFAULT false,
    merged_into_id      uuid REFERENCES analysis.entity(id),
    first_seen_at timestamptz, last_seen_at timestamptz,
    sys_period          tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT entity_not_self_merge CHECK (merged_into_id IS DISTINCT FROM id)
);
CREATE INDEX IF NOT EXISTS idx_entity_type          ON analysis.entity (entity_type);
CREATE INDEX IF NOT EXISTS idx_entity_live          ON analysis.entity (id) WHERE merged_into_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_entity_dispname_trgm ON analysis.entity USING gin ((display_name::text) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_entity_normname_trgm ON analysis.entity USING gin ((normalized_name::text) gin_trgm_ops);
CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_norm    ON analysis.entity (entity_type, normalized_name)
    WHERE normalized_name IS NOT NULL AND merged_into_id IS NULL;

CREATE TABLE IF NOT EXISTS analysis.person (
    id uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    relationship_type text,
    connection_to text CHECK (connection_to IN ('petitioner','respondent','child','mutual','third_party','unknown')),
    role_in_case  text CHECK (role_in_case IN ('user','partner','child','witness','evaluator','attorney','third_party','neutral','unknown')),
    gender text, is_minor boolean NOT NULL DEFAULT false, is_flagged boolean NOT NULL DEFAULT false, notes text
);
CREATE TABLE IF NOT EXISTS analysis.organization (
    id uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    org_type text, legal_name citext, jurisdiction text
);
CREATE TABLE IF NOT EXISTS analysis.phone (
    id uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    e164 citext, raw_number text, owner_entity_id uuid REFERENCES analysis.entity(id),
    is_blocked boolean NOT NULL DEFAULT false,
    validity tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),
    EXCLUDE USING gist ((e164::text) WITH =, validity WITH &&) WHERE (e164 IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_phone_owner ON analysis.phone (owner_entity_id);
CREATE INDEX IF NOT EXISTS idx_phone_e164  ON analysis.phone ((e164::text));
CREATE TABLE IF NOT EXISTS analysis.email (
    id uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    address citext, owner_entity_id uuid REFERENCES analysis.entity(id),
    validity tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),
    EXCLUDE USING gist ((address::text) WITH =, validity WITH &&) WHERE (address IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_email_owner ON analysis.email (owner_entity_id);
CREATE TABLE IF NOT EXISTS analysis.handle (
    id uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    platform text NOT NULL, handle citext NOT NULL, owner_entity_id uuid REFERENCES analysis.entity(id),
    is_blocked boolean NOT NULL DEFAULT false,
    validity tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),
    EXCLUDE USING gist (platform WITH =, (handle::text) WITH =, validity WITH &&)
);
CREATE INDEX IF NOT EXISTS idx_handle_owner ON analysis.handle (owner_entity_id);
CREATE INDEX IF NOT EXISTS idx_handle_trgm  ON analysis.handle USING gin ((handle::text) gin_trgm_ops);
CREATE TABLE IF NOT EXISTS analysis.device (
    id uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    make_model text, os text, imei_or_serial citext, owner_entity_id uuid REFERENCES analysis.entity(id)
);
CREATE TABLE IF NOT EXISTS analysis.account (
    id uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    platform text NOT NULL, account_key citext NOT NULL, owner_entity_id uuid REFERENCES analysis.entity(id)
);
CREATE TABLE IF NOT EXISTS analysis.vehicle (
    id uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    plate citext, make_model text, owner_entity_id uuid REFERENCES analysis.entity(id)
);

CREATE TABLE IF NOT EXISTS analysis.entity_alias (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    entity_id uuid NOT NULL REFERENCES analysis.entity(id) ON DELETE CASCADE,
    alias_text citext NOT NULL,
    alias_kind text CHECK (alias_kind IN ('nickname','legal','maiden','handle','misspelling','phonetic','initials','other')),
    confidence confidence,
    alias_dmeta text GENERATED ALWAYS AS (dmetaphone((alias_text)::text)) STORED,
    provenance source_ref[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alias_entity ON analysis.entity_alias (entity_id);
CREATE INDEX IF NOT EXISTS idx_alias_trgm   ON analysis.entity_alias USING gin ((alias_text::text) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_alias_dmeta  ON analysis.entity_alias (alias_dmeta);

CREATE TABLE IF NOT EXISTS analysis.entity_mention (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    surface_text citext NOT NULL,
    surface_norm text GENERATED ALWAYS AS (lower((surface_text)::text)) STORED,
    mention_kind text CHECK (mention_kind IN ('name','phone','handle','email','pronoun','partial','address','device','other')),
    subject_type text, subject_id uuid,
    start_char int, end_char int, context_snippet text,
    extraction_method text, confidence confidence,
    mention_dmeta text GENERATED ALWAYS AS (dmetaphone((surface_text)::text)) STORED,
    data_tier evidence_tier NOT NULL DEFAULT 'extracted',
    provenance source_ref[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mention_subject ON analysis.entity_mention (subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_mention_trgm    ON analysis.entity_mention USING gin ((surface_text::text) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_mention_dmeta   ON analysis.entity_mention (mention_dmeta);

CREATE TABLE IF NOT EXISTS analysis.entity_resolution (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    mention_id uuid NOT NULL REFERENCES analysis.entity_mention(id),
    canonical_entity_id uuid NOT NULL REFERENCES analysis.entity(id),
    source_specific_id text,
    match_method match_method NOT NULL,
    resolved_by text CHECK (resolved_by IN ('rule','model','human')),
    match_score confidence, similarity_metrics jsonb NOT NULL DEFAULT '{}',
    requires_human_review boolean NOT NULL DEFAULT true,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    reviewed_by text, reviewed_at timestamptz, review_notes text,
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    data_tier evidence_tier NOT NULL DEFAULT 'analytical',
    provenance source_ref[] NOT NULL DEFAULT '{}',
    sys_period tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_res_canonical ON analysis.entity_resolution (canonical_entity_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_res_current ON analysis.entity_resolution (mention_id) WHERE upper_inf(sys_period);

CREATE TABLE IF NOT EXISTS analysis.resolution_evidence (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    resolution_id uuid NOT NULL REFERENCES analysis.entity_resolution(id),
    polarity text NOT NULL CHECK (polarity IN ('supports','contradicts')),
    method text, evidence_ref_type text, evidence_ref_id uuid,
    weight confidence, note text,
    provenance source_ref[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_resev_res ON analysis.resolution_evidence (resolution_id, polarity);

CREATE TABLE IF NOT EXISTS analysis.entity_merge_event (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    op text NOT NULL CHECK (op IN ('merge','split')),
    surviving_entity_id uuid NOT NULL REFERENCES analysis.entity(id),
    merged_entity_id uuid NOT NULL REFERENCES analysis.entity(id),
    actor_id uuid, actor_kind text CHECK (actor_kind IN ('human','service','agent')),
    rationale text, reversible_to uuid REFERENCES analysis.entity_merge_event(id),
    requires_human_review boolean NOT NULL DEFAULT true,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    reviewed_by text, reviewed_at timestamptz,
    provenance source_ref[] NOT NULL DEFAULT '{}',
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT merge_distinct CHECK (surviving_entity_id <> merged_entity_id)
);
CREATE INDEX IF NOT EXISTS idx_merge_surv ON analysis.entity_merge_event (surviving_entity_id);

CREATE TABLE IF NOT EXISTS analysis.id_xref (
    id                  uuid PRIMARY KEY DEFAULT uuidv7(),
    canonical_entity_id uuid REFERENCES analysis.entity(id),
    system_a            source_system NOT NULL, native_id_a text NOT NULL,
    system_b            source_system NOT NULL, native_id_b text NOT NULL,
    match_method        match_method NOT NULL,
    confidence          confidence,
    source              source_ref,
    is_current          boolean NOT NULL DEFAULT true,
    sys_period          tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_xref_pair UNIQUE (system_a, native_id_a, system_b, native_id_b)
);
CREATE INDEX IF NOT EXISTS idx_xref_entity ON analysis.id_xref (canonical_entity_id);
CREATE INDEX IF NOT EXISTS idx_xref_b      ON analysis.id_xref (system_b, native_id_b);

DROP TRIGGER IF EXISTS trg_mention_append ON analysis.entity_mention;
CREATE TRIGGER trg_mention_append BEFORE UPDATE OR DELETE ON analysis.entity_mention
  FOR EACH ROW EXECUTE FUNCTION analysis.reject_mutation();
DROP TRIGGER IF EXISTS trg_resev_append ON analysis.resolution_evidence;
CREATE TRIGGER trg_resev_append   BEFORE UPDATE OR DELETE ON analysis.resolution_evidence
  FOR EACH ROW EXECUTE FUNCTION analysis.reject_mutation();
DROP TRIGGER IF EXISTS trg_merge_append ON analysis.entity_merge_event;
CREATE TRIGGER trg_merge_append   BEFORE UPDATE OR DELETE ON analysis.entity_merge_event
  FOR EACH ROW EXECUTE FUNCTION analysis.reject_mutation();


-- =====================================================================================
-- STEP 8 — ANALYSIS: NORMALIZED RECORD SPINE + MESSAGES
--   normalized_record [EXISTS-NEEDS-ALTER]. LIVE as-built cols (verified): id, artifact_id,
--   record_type, source, conversation_id(TEXT), role, participants, content, occurred_at,
--   knowledge_time, disclosure_tier(TEXT CHECK), attrs, created_at + 2 CHECKs + FK to
--   evidence.evidence_hash + 3 idx. disclosure_tier UNCHANGED. New cols purely additive.
--   NOTE: as-built conversation_id is TEXT (external thread key); the new conversation_ref
--   is a separate uuid FK to analysis.conversation — they coexist, no rename.
-- =====================================================================================
ALTER TABLE analysis.normalized_record
  ADD COLUMN IF NOT EXISTS conversation_ref   uuid,
  ADD COLUMN IF NOT EXISTS ts_precision       precision_class NOT NULL DEFAULT 'exact',
  ADD COLUMN IF NOT EXISTS sensitivity_tier   sensitivity_tier,
  ADD COLUMN IF NOT EXISTS data_tier          evidence_tier NOT NULL DEFAULT 'extracted',
  ADD COLUMN IF NOT EXISTS review_status      review_state  NOT NULL DEFAULT 'unreviewed',
  ADD COLUMN IF NOT EXISTS safe_for_legal_use boolean       NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS provenance_id      uuid REFERENCES analysis.processing_run(run_id);

CREATE TABLE IF NOT EXISTS analysis.conversation (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    source_artifact_id uuid NOT NULL REFERENCES evidence.evidence_hash(id),
    platform text NOT NULL, external_thread_key text, title text,
    participants jsonb NOT NULL DEFAULT '[]'::jsonb, participant_count int,
    primary_participant text, primary_participant_e164 text,
    is_group boolean NOT NULL DEFAULT false,
    started_at timestamptz, ended_at timestamptz,
    message_count int NOT NULL DEFAULT 0,
    is_evidence boolean NOT NULL DEFAULT false, exhibit_number text,
    relevance confidence, behavior_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    data_tier evidence_tier NOT NULL DEFAULT 'extracted',
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    platform_attrs jsonb NOT NULL DEFAULT '{}'::jsonb, raw_data jsonb,
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_conversation_thread UNIQUE (platform, external_thread_key)
);
CREATE INDEX IF NOT EXISTS idx_conv_platform ON analysis.conversation(platform);
CREATE INDEX IF NOT EXISTS idx_conv_primary  ON analysis.conversation(primary_participant_e164);

DO $$ BEGIN
  ALTER TABLE analysis.normalized_record
    ADD CONSTRAINT fk_normrec_conv FOREIGN KEY (conversation_ref) REFERENCES analysis.conversation(id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS idx_normrec_convref_time ON analysis.normalized_record(conversation_ref, occurred_at);
CREATE INDEX IF NOT EXISTS idx_normrec_fts  ON analysis.normalized_record USING gin (to_tsvector('english', coalesce(content,'')));
CREATE INDEX IF NOT EXISTS idx_normrec_trgm ON analysis.normalized_record USING gin (content gin_trgm_ops);

CREATE TABLE IF NOT EXISTS analysis.message (
    id uuid PRIMARY KEY REFERENCES analysis.normalized_record(id) ON DELETE CASCADE,
    conversation_id uuid NOT NULL REFERENCES analysis.conversation(id),
    ts_utc timestamptz,
    platform text NOT NULL, external_id text,
    serial_number bigint GENERATED ALWAYS AS IDENTITY,
    prev_message_id uuid REFERENCES analysis.message(id),
    next_message_id uuid REFERENCES analysis.message(id),
    time_since_prev_s int,
    sender_raw text, sender_e164 text, sender_entity_id uuid,
    recipient_raw text, recipient_e164 text,
    direction text CHECK (direction IN ('inbound','outbound','unknown')),
    message_type text NOT NULL DEFAULT 'text', delivery_status text, status_code int,
    is_blocked boolean NOT NULL DEFAULT false,
    raw_ts text, tz text, ts_earliest timestamptz, ts_latest timestamptz,
    temporal_confidence confidence, relative_time_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    word_count int, char_count int,
    content_sha256 bytea CHECK (content_sha256 IS NULL OR octet_length(content_sha256)=32),
    language text,
    surface_sentiment_hint text, inferred_intent_hint text, topic_hint text,
    domain_type_hint text, relevance_hint text, custody_relevance_hint text,
    evidence_strength_hint strength_class, extraction_confidence confidence,
    is_private boolean NOT NULL DEFAULT false, is_redacted boolean NOT NULL DEFAULT false,
    has_attachments boolean NOT NULL DEFAULT false, attachment_count int NOT NULL DEFAULT 0,
    has_behaviors boolean NOT NULL DEFAULT false, behavior_count int NOT NULL DEFAULT 0,
    max_behavior_severity text,
    screenshot_attachment_id uuid,
    body_embedding_ref text,
    platform_attrs jsonb NOT NULL DEFAULT '{}'::jsonb, raw_data jsonb,
    CONSTRAINT uq_message_thread_extid UNIQUE (conversation_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_msg_conv_time ON analysis.message(conversation_id, ts_utc);
CREATE INDEX IF NOT EXISTS idx_msg_sender    ON analysis.message(sender_e164);
CREATE INDEX IF NOT EXISTS idx_msg_chash     ON analysis.message(content_sha256);
CREATE INDEX IF NOT EXISTS idx_msg_attrs     ON analysis.message USING gin(platform_attrs);
CREATE INDEX IF NOT EXISTS idx_msg_private   ON analysis.message(id) WHERE is_private;

CREATE TABLE IF NOT EXISTS analysis.message_participant (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    message_id uuid NOT NULL REFERENCES analysis.message(id) ON DELETE CASCADE,
    entity_id uuid, participant_raw text, participant_e164 text,
    role text NOT NULL CHECK (role IN ('from','to','cc','bcc','group','third_party')),
    conduct_party conduct_party,
    CONSTRAINT uq_msg_part UNIQUE (message_id, role, participant_raw)
);
CREATE INDEX IF NOT EXISTS idx_msgpart_msg ON analysis.message_participant(message_id);

CREATE TABLE IF NOT EXISTS analysis.attachment (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    message_id uuid NOT NULL REFERENCES analysis.message(id) ON DELETE CASCADE,
    source_artifact_id uuid REFERENCES evidence.evidence_hash(id),
    media_asset_id uuid, filename text, attachment_type text, mime_type text,
    file_sha256 bytea CHECK (file_sha256 IS NULL OR octet_length(file_sha256)=32),
    file_size bigint, object_uri text, thumbnail_uri text,
    width int, height int, duration_s numeric,
    is_screenshot boolean NOT NULL DEFAULT false, contains_faces boolean NOT NULL DEFAULT false,
    ocr_text text, transcription text, exif jsonb, ocr_confidence confidence,
    embedding_ref text,
    data_tier evidence_tier NOT NULL DEFAULT 'extracted',
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    platform_attrs jsonb NOT NULL DEFAULT '{}'::jsonb, raw_data jsonb,
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_att_msg  ON analysis.attachment(message_id);
CREATE INDEX IF NOT EXISTS idx_att_exif ON analysis.attachment USING gin(exif);
CREATE INDEX IF NOT EXISTS idx_att_ocr_fts ON analysis.attachment
  USING gin (to_tsvector('english', coalesce(ocr_text,'')||' '||coalesce(transcription,'')));
DO $$ BEGIN
  ALTER TABLE analysis.message
    ADD CONSTRAINT fk_msg_screenshot FOREIGN KEY (screenshot_attachment_id) REFERENCES analysis.attachment(id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS analysis.call_log (
    id uuid PRIMARY KEY REFERENCES analysis.normalized_record(id) ON DELETE CASCADE,
    source_artifact_id uuid NOT NULL REFERENCES evidence.evidence_hash(id),
    conversation_id uuid REFERENCES analysis.conversation(id),
    from_raw text, from_e164 text, from_entity_id uuid,
    to_raw text, to_e164 text, to_entity_id uuid,
    call_type text NOT NULL CHECK (call_type IN
      ('incoming','outgoing','missed','rejected','blocked_incoming','blocked_outgoing','voicemail')),
    direction text CHECK (direction IN ('inbound','outbound','unknown')),
    started_at timestamptz, ts_precision precision_class NOT NULL DEFAULT 'exact',
    duration_s int, is_blocked boolean NOT NULL DEFAULT false, presentation text,
    data_tier evidence_tier NOT NULL DEFAULT 'extracted',
    platform_attrs jsonb NOT NULL DEFAULT '{}'::jsonb, raw_data jsonb,
    provenance_id uuid REFERENCES analysis.processing_run(run_id)
);
CREATE INDEX IF NOT EXISTS idx_call_started ON analysis.call_log(started_at);
CREATE INDEX IF NOT EXISTS idx_call_conv    ON analysis.call_log(conversation_id);

CREATE TABLE IF NOT EXISTS analysis.relational_classification (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    subject_type text NOT NULL CHECK (subject_type IN ('message','event','call')),
    subject_id uuid NOT NULL,
    event_category text,
    surface_sentiment text, emotional_tone text, relational_function text,
    cycle_phase cycle_phase, cycle_transition_type text,
    love_bombing_indicator boolean, repair_attempt_indicator boolean,
    cooperation_indicator boolean, neutral_context_indicator boolean,
    precedes_concerning_event boolean, follows_concerning_event boolean,
    temporal_proximity_to_conflict_s bigint, changes_nearby_interpretation boolean,
    corroborated boolean, conduct_party conduct_party, pattern_relevance text,
    mcl_factor_hint mcl_factor,
    classified_by text CHECK (classified_by IN ('rule','model','human')),
    confidence confidence, detector_provenance_id uuid,
    requires_human_review boolean NOT NULL DEFAULT true,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    data_tier evidence_tier NOT NULL DEFAULT 'analytical',
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT relcls_legal_gate CHECK (safe_for_legal_use = false OR review_status = 'approved')
);
CREATE INDEX IF NOT EXISTS idx_relcls_subject ON analysis.relational_classification(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_relcls_phase   ON analysis.relational_classification(cycle_phase);
CREATE INDEX IF NOT EXISTS idx_relcls_review  ON analysis.relational_classification(review_status) WHERE requires_human_review;


-- =====================================================================================
-- STEP 9 — ANALYSIS: GEO / LOCATION
-- =====================================================================================
CREATE TABLE IF NOT EXISTS analysis.location (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    name text, geog geo_point NOT NULL,
    geohash9 text GENERATED ALWAYS AS (ST_GeoHash(geog::geometry, 9)) STORED,
    address text, place_type text,
    is_fuzzed boolean NOT NULL DEFAULT false,
    sensitivity_tier sensitivity_tier NOT NULL DEFAULT 'restricted',
    spatial_confidence confidence,
    data_tier evidence_tier NOT NULL DEFAULT 'extracted'
      CHECK (data_tier IN ('extracted','inferred','analytical')),
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_location_dedup ON analysis.location (geohash9, coalesce(name,''));
CREATE INDEX IF NOT EXISTS idx_location_geog      ON analysis.location USING gist (geog);
CREATE INDEX IF NOT EXISTS idx_location_name_trgm ON analysis.location USING gin (name gin_trgm_ops);

CREATE TABLE IF NOT EXISTS analysis.gps_track (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    device_id uuid REFERENCES analysis.device(id), source_id uuid REFERENCES evidence.source(id),
    geog geography(LineString,4326) NOT NULL,
    started_at timestamptz, ended_at timestamptz, point_count int,
    data_tier evidence_tier NOT NULL DEFAULT 'extracted' CHECK (data_tier = 'extracted'),
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gps_track_geog ON analysis.gps_track USING gist (geog);

CREATE TABLE IF NOT EXISTS analysis.stay_point (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    track_id uuid REFERENCES analysis.gps_track(id), location_id uuid REFERENCES analysis.location(id),
    device_id uuid REFERENCES analysis.device(id), geog geo_point NOT NULL,
    arrived_at timestamptz, departed_at timestamptz, dwell_s bigint, spatial_confidence confidence,
    requires_human_review boolean NOT NULL DEFAULT false,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    data_tier evidence_tier NOT NULL DEFAULT 'inferred' CHECK (data_tier = 'inferred'),
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_stay_point_geog ON analysis.stay_point USING gist (geog);

CREATE TABLE IF NOT EXISTS analysis.geofence (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    name text NOT NULL, geog geography(Polygon,4326) NOT NULL, purpose text,
    data_tier evidence_tier NOT NULL DEFAULT 'analytical' CHECK (data_tier = 'analytical'),
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_geofence_geog ON analysis.geofence USING gist (geog);

CREATE TABLE IF NOT EXISTS analysis.home_base (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    entity_id uuid REFERENCES analysis.entity(id), location_id uuid REFERENCES analysis.location(id),
    spatial_confidence confidence, typical_schedule jsonb NOT NULL DEFAULT '{}'::jsonb,
    requires_human_review boolean NOT NULL DEFAULT false,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    data_tier evidence_tier NOT NULL DEFAULT 'inferred' CHECK (data_tier = 'inferred'),
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis.location_assertion (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    subject_type text NOT NULL CHECK (subject_type IN ('event','message','person','device','media')),
    subject_id uuid NOT NULL, location_id uuid REFERENCES analysis.location(id),
    geog geo_point, asserted_at_ts timestamptz, ts_precision precision_class NOT NULL DEFAULT 'inferred',
    spatial_confidence confidence, assertion_source assertion_source NOT NULL, evidence_strength strength_class,
    requires_human_review boolean NOT NULL DEFAULT false,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    data_tier evidence_tier NOT NULL DEFAULT 'inferred' CHECK (data_tier IN ('inferred','analytical')),
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT locassert_legal_gate CHECK (safe_for_legal_use = false OR review_status = 'approved')
);
CREATE INDEX IF NOT EXISTS idx_locassert_subject ON analysis.location_assertion (subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_locassert_geog    ON analysis.location_assertion USING gist (geog);

CREATE TABLE IF NOT EXISTS analysis.location_contradiction (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    claimed_assertion_id uuid NOT NULL REFERENCES analysis.location_assertion(id),
    observed_assertion_id uuid NOT NULL REFERENCES analysis.location_assertion(id),
    distance_m numeric(12,2), disagreement_flag boolean NOT NULL DEFAULT false, tie_break_reason text,
    analysis_confidence confidence,
    requires_human_review boolean NOT NULL DEFAULT true,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    data_tier evidence_tier NOT NULL DEFAULT 'analytical' CHECK (data_tier = 'analytical'),
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_loc_contra_distinct CHECK (claimed_assertion_id <> observed_assertion_id),
    CONSTRAINT loccontra_legal_gate CHECK (safe_for_legal_use = false OR review_status = 'approved')
);

CREATE TABLE IF NOT EXISTS analysis.geocode_request (
    id uuid PRIMARY KEY DEFAULT uuidv7(), query text NOT NULL, geog geo_point,
    status text NOT NULL DEFAULT 'pending',
    data_tier evidence_tier NOT NULL DEFAULT 'extracted' CHECK (data_tier = 'extracted'),
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    requested_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS analysis.geocode_result (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    request_id uuid NOT NULL REFERENCES analysis.geocode_request(id),
    provider geocode_provider NOT NULL, place_id text, address text, geog geo_point,
    confidence confidence, bounds jsonb, raw_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    data_tier evidence_tier NOT NULL DEFAULT 'extracted' CHECK (data_tier = 'extracted'),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_geocode_result_req ON analysis.geocode_result (request_id);
CREATE TABLE IF NOT EXISTS analysis.geocode_resolution (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    request_id uuid NOT NULL REFERENCES analysis.geocode_request(id),
    location_id uuid REFERENCES analysis.location(id),
    preferred_provider geocode_provider, chosen_result_id uuid REFERENCES analysis.geocode_result(id),
    distance_m numeric(12,2), disagreement_flag boolean NOT NULL DEFAULT false, tie_break_reason text,
    data_tier evidence_tier NOT NULL DEFAULT 'extracted' CHECK (data_tier = 'extracted'),
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    resolved_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS analysis.geocode_audit (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    request_id uuid REFERENCES analysis.geocode_request(id),
    action text NOT NULL, actor_kind text, detail jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_geocode_audit_req ON analysis.geocode_audit (request_id, occurred_at);
DROP TRIGGER IF EXISTS geocode_audit_immutable ON analysis.geocode_audit;
CREATE TRIGGER geocode_audit_immutable BEFORE UPDATE OR DELETE ON analysis.geocode_audit
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();


-- =====================================================================================
-- STEP 10 — ANALYSIS: EVENTS & BITEMPORAL TIMELINE
-- =====================================================================================
CREATE TABLE IF NOT EXISTS analysis.timeline_event (
    event_id uuid PRIMARY KEY DEFAULT uuidv7(),
    canonical_event_id canonical_id, event_key citext UNIQUE, serial_id bigint,
    title text NOT NULL, description text,
    event_type event_type NOT NULL, temporal_class temporal_class NOT NULL DEFAULT 'historical',
    valid_earliest timestamptz, valid_latest timestamptz, valid_point timestamptz,
    valid_range tstzrange GENERATED ALWAYS AS (tstzrange(valid_earliest, valid_latest, '[]')) STORED,
    current_certainty precision_class, current_confidence confidence,
    disclosure_horizon disclosure_horizon NOT NULL DEFAULT 'contemporaneous',
    assertion_type assertion_type NOT NULL DEFAULT 'analytical_finding',
    location_id uuid REFERENCES analysis.location(id), primary_geo geo_point,
    is_conflicted boolean NOT NULL DEFAULT false,
    requires_human_review boolean NOT NULL DEFAULT false,
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    reviewed_by text, reviewed_at timestamptz,
    conduct_party conduct_party, mcl_relevance mcl_factor[] NOT NULL DEFAULT '{}',
    source_artifact_id uuid REFERENCES evidence.evidence_hash(id),
    primary_record_id uuid REFERENCES analysis.normalized_record(id),
    ingest_run_id uuid REFERENCES analysis.processing_run(run_id),
    derived_from uuid[] NOT NULL DEFAULT '{}',
    prompt_version text, ontology_version text, schema_version text,
    attrs jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_event_validrange ON analysis.timeline_event USING gist (valid_range);
CREATE INDEX IF NOT EXISTS idx_event_type_point ON analysis.timeline_event (event_type, valid_point);
CREATE INDEX IF NOT EXISTS idx_event_title_trgm ON analysis.timeline_event USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_event_mcl        ON analysis.timeline_event USING gin (mcl_relevance);
CREATE INDEX IF NOT EXISTS idx_event_geo        ON analysis.timeline_event USING gist (primary_geo);

CREATE TABLE IF NOT EXISTS analysis.event_source_record (
    link_id uuid PRIMARY KEY DEFAULT uuidv7(),
    event_id uuid NOT NULL REFERENCES analysis.timeline_event(event_id) ON DELETE CASCADE,
    record_id uuid REFERENCES analysis.normalized_record(id),
    source_id uuid REFERENCES evidence.source(id),
    raw_ref jsonb,
    role text NOT NULL DEFAULT 'primary'
      CHECK (role IN ('primary','corroborating','context','contradicting')),
    CONSTRAINT esr_has_source CHECK (record_id IS NOT NULL OR source_id IS NOT NULL OR raw_ref IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_esr_record ON analysis.event_source_record (event_id, record_id) WHERE record_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS analysis.time_assertion (
    assertion_id uuid PRIMARY KEY DEFAULT uuidv7(),
    event_id uuid NOT NULL REFERENCES analysis.timeline_event(event_id) ON DELETE CASCADE,
    valid_earliest timestamptz NOT NULL, valid_latest timestamptz NOT NULL, valid_point timestamptz,
    valid_range tstzrange GENERATED ALWAYS AS (tstzrange(valid_earliest, valid_latest, '[]')) STORED,
    ts_raw text, ts_utc timestamptz, tz_offset_minutes int,
    tz_source text CHECK (tz_source IS NULL OR tz_source IN
      ('exif_offset','export_header','assumed_local','device_setting','unknown')),
    certainty precision_class NOT NULL,
    assertion_type assertion_type NOT NULL DEFAULT 'extracted_fact',
    confidence confidence, disclosure_horizon disclosure_horizon NOT NULL DEFAULT 'contemporaneous',
    is_conflicted boolean NOT NULL DEFAULT false, requires_human_review boolean NOT NULL DEFAULT false,
    discovered_at timestamptz, discovery_source uuid REFERENCES evidence.evidence_hash(id),
    ingested_at timestamptz NOT NULL DEFAULT now(), ingest_run_id uuid REFERENCES analysis.processing_run(run_id),
    sys_period tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),
    superseded_by uuid REFERENCES analysis.time_assertion(assertion_id),
    derived_from uuid[] NOT NULL DEFAULT '{}', anchor_refs uuid[] NOT NULL DEFAULT '{}',
    reasoning text, prompt_version text, ontology_version text, schema_version text,
    author text NOT NULL,
    CONSTRAINT valid_ordering CHECK (valid_earliest <= valid_latest),
    CONSTRAINT no_overlapping_belief EXCLUDE USING gist (event_id WITH =, sys_period WITH &&)
);
CREATE INDEX IF NOT EXISTS idx_ta_validrange ON analysis.time_assertion USING gist (valid_range);
CREATE INDEX IF NOT EXISTS idx_ta_current    ON analysis.time_assertion (event_id) WHERE upper_inf(sys_period);

CREATE TABLE IF NOT EXISTS analysis.temporal_anchor (
    anchor_id uuid PRIMARY KEY DEFAULT uuidv7(), anchor_key citext UNIQUE, label text NOT NULL,
    anchor_type anchor_kind NOT NULL, event_id uuid REFERENCES analysis.timeline_event(event_id),
    valid_earliest timestamptz NOT NULL, valid_latest timestamptz NOT NULL,
    valid_range tstzrange GENERATED ALWAYS AS (tstzrange(valid_earliest, valid_latest, '[]')) STORED,
    certainty precision_class NOT NULL, confidence confidence,
    derived_from uuid[] NOT NULL DEFAULT '{}', requires_human_review boolean NOT NULL DEFAULT false,
    author text NOT NULL, asserted_at timestamptz NOT NULL DEFAULT now(), retracted_at timestamptz,
    CONSTRAINT anchor_ordering CHECK (valid_earliest <= valid_latest)
);
CREATE INDEX IF NOT EXISTS idx_anchor_range ON analysis.temporal_anchor USING gist (valid_range);

CREATE TABLE IF NOT EXISTS analysis.relative_rule (
    rule_id uuid PRIMARY KEY DEFAULT uuidv7(), phrase_pattern text NOT NULL, resolution_expr text NOT NULL,
    result_certainty precision_class NOT NULL, lower_offset interval, upper_offset interval,
    config jsonb NOT NULL DEFAULT '{}', ontology_version text, prompt_version text,
    is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis.event_ordering (
    ordering_id uuid PRIMARY KEY DEFAULT uuidv7(),
    before_event uuid NOT NULL REFERENCES analysis.timeline_event(event_id) ON DELETE CASCADE,
    after_event  uuid NOT NULL REFERENCES analysis.timeline_event(event_id) ON DELETE CASCADE,
    relation temporal_relation NOT NULL DEFAULT 'preceded', basis text NOT NULL, confidence confidence,
    requires_human_review boolean NOT NULL DEFAULT false, derived_from uuid[] NOT NULL DEFAULT '{}',
    author text NOT NULL, asserted_at timestamptz NOT NULL DEFAULT now(), retracted_at timestamptz,
    CONSTRAINT no_self_order CHECK (before_event <> after_event)
);

CREATE TABLE IF NOT EXISTS analysis.waypoint_device_split (
    split_id uuid PRIMARY KEY DEFAULT uuidv7(),
    raw_path_id uuid NOT NULL REFERENCES evidence.raw_path(id),
    device_index int NOT NULL, split_from_activity uuid REFERENCES evidence.raw_activity(id),
    threshold_meters numeric NOT NULL DEFAULT 100,
    certainty precision_class NOT NULL DEFAULT 'inferred', confidence confidence,
    requires_human_review boolean NOT NULL DEFAULT false,
    ingest_run_id uuid REFERENCES analysis.processing_run(run_id),
    author text NOT NULL, asserted_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wds_path ON analysis.waypoint_device_split (raw_path_id);


-- =====================================================================================
-- STEP 11 — ANALYSIS: SYNTHESIZED FINDING (anchor for behavioral/legal findings)
-- =====================================================================================
-- TODO(human): this is a MINIMAL court-safe stub for the "findings domain" (paper §8.3)
--   that no D1-D8 doc owns. Flesh out subject linkage + finding taxonomy before relying on
--   it for court export. pattern_finding.finding_id and evidence_task.finding_id FK here.
CREATE TABLE IF NOT EXISTS analysis.finding (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    case_id uuid,
    finding_type text NOT NULL,
    title text NOT NULL, statement text,
    subject_refs uuid[] NOT NULL DEFAULT '{}',
    conduct_party conduct_party, mcl_factors mcl_factor[] NOT NULL DEFAULT '{}',
    assertion_type assertion_type NOT NULL DEFAULT 'analytical_finding',
    data_tier evidence_tier NOT NULL DEFAULT 'analytical',
    confidence confidence, evidence_strength strength_class,
    is_hypothesis boolean NOT NULL DEFAULT true,
    requires_human_review boolean NOT NULL DEFAULT true,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    bias_caution boolean NOT NULL DEFAULT true, authored_perspective text,
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_by text, created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT finding_legal_gate CHECK
      (safe_for_legal_use = false OR (review_status = 'approved' AND is_hypothesis = false))
);
CREATE INDEX IF NOT EXISTS idx_finding_type   ON analysis.finding (finding_type);
CREATE INDEX IF NOT EXISTS idx_finding_review ON analysis.finding (review_status);
CREATE INDEX IF NOT EXISTS idx_finding_mcl    ON analysis.finding USING gin (mcl_factors);

CREATE TABLE IF NOT EXISTS analysis.finding_version (
    version_id uuid PRIMARY KEY DEFAULT uuidv7(),
    finding_id uuid NOT NULL REFERENCES analysis.finding(id),
    snapshot jsonb NOT NULL, changed_by text NOT NULL, change_note text,
    ts timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS finding_version_immutable ON analysis.finding_version;
CREATE TRIGGER finding_version_immutable BEFORE UPDATE OR DELETE ON analysis.finding_version
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();


-- =====================================================================================
-- STEP 12 — ANALYSIS: BEHAVIORAL FINDINGS, PATTERNS & DETECTION CONFIG
-- =====================================================================================
CREATE TABLE IF NOT EXISTS analysis.detection_pattern_set (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    name citext NOT NULL, version text NOT NULL, source text, source_artifact text, description text,
    is_active boolean NOT NULL DEFAULT false, authored_perspective text,
    valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    UNIQUE (name, version)
);
CREATE INDEX IF NOT EXISTS idx_pattern_set_active ON analysis.detection_pattern_set (is_active) WHERE is_active;

CREATE TABLE IF NOT EXISTS analysis.behavior_category (
    category_id citext PRIMARY KEY, label text NOT NULL, description text,
    polarity category_polarity NOT NULL, default_severity smallint NOT NULL DEFAULT 5,
    mcl_factors mcl_factor[] NOT NULL DEFAULT '{}', aliases citext[] NOT NULL DEFAULT '{}',
    is_case_specific boolean NOT NULL DEFAULT false, source text, notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT behavior_category_sev_chk CHECK (default_severity BETWEEN 0 AND 10)
);
CREATE INDEX IF NOT EXISTS idx_behavior_category_mcl   ON analysis.behavior_category USING gin (mcl_factors);
CREATE INDEX IF NOT EXISTS idx_behavior_category_alias ON analysis.behavior_category USING gin (aliases);

CREATE TABLE IF NOT EXISTS analysis.detection_pattern (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    pattern_set_id uuid NOT NULL REFERENCES analysis.detection_pattern_set(id),
    category_id citext NOT NULL REFERENCES analysis.behavior_category(category_id),
    subcategory text, match_type pattern_match_type NOT NULL, pattern text NOT NULL,
    keywords text[] NOT NULL DEFAULT '{}', severity smallint NOT NULL DEFAULT 5, score smallint,
    mcl_factors mcl_factor[] NOT NULL DEFAULT '{}', description text,
    is_case_specific boolean NOT NULL DEFAULT false, authored_perspective text,
    bias_caution boolean NOT NULL DEFAULT true, source text,
    is_active boolean NOT NULL DEFAULT true, valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT detection_pattern_sev_chk   CHECK (severity BETWEEN 0 AND 10),
    CONSTRAINT detection_pattern_score_chk CHECK (score IS NULL OR score BETWEEN 1 AND 10),
    UNIQUE (pattern_set_id, category_id, match_type, pattern)
);
CREATE INDEX IF NOT EXISTS idx_detection_pattern_cat ON analysis.detection_pattern (category_id);
CREATE INDEX IF NOT EXISTS idx_detection_pattern_kw  ON analysis.detection_pattern USING gin (keywords);
CREATE INDEX IF NOT EXISTS idx_detection_pattern_trgm ON analysis.detection_pattern USING gin (pattern gin_trgm_ops);

CREATE TABLE IF NOT EXISTS analysis.pattern_lexicon (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    pattern_set_id uuid NOT NULL REFERENCES analysis.detection_pattern_set(id),
    lexicon_type text NOT NULL, term text NOT NULL, variants text[] NOT NULL DEFAULT '{}',
    match_type pattern_match_type NOT NULL DEFAULT 'literal',
    relevance_signal text, severity smallint NOT NULL DEFAULT 0,
    mcl_factors mcl_factor[] NOT NULL DEFAULT '{}', is_case_specific boolean NOT NULL DEFAULT true,
    sensitivity_tier sensitivity_tier NOT NULL DEFAULT 'restricted', source text,
    is_active boolean NOT NULL DEFAULT true, valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pattern_lexicon_sev_chk CHECK (severity BETWEEN 0 AND 10)
);
CREATE INDEX IF NOT EXISTS idx_pattern_lexicon_type     ON analysis.pattern_lexicon (lexicon_type);
CREATE INDEX IF NOT EXISTS idx_pattern_lexicon_variants ON analysis.pattern_lexicon USING gin (variants);

CREATE TABLE IF NOT EXISTS analysis.behavior_category_mcl (
    category_id citext NOT NULL REFERENCES analysis.behavior_category(category_id),
    factor_code mcl_factor NOT NULL, weight text, is_critical boolean NOT NULL DEFAULT false, note text,
    PRIMARY KEY (category_id, factor_code)
);
CREATE INDEX IF NOT EXISTS idx_behavior_category_mcl_factor ON analysis.behavior_category_mcl (factor_code);

CREATE TABLE IF NOT EXISTS analysis.pattern_finding (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    subject_type text NOT NULL, subject_id uuid NOT NULL,
    category_id citext NOT NULL REFERENCES analysis.behavior_category(category_id),
    pattern_id uuid REFERENCES analysis.detection_pattern(id),
    pattern_set_id uuid REFERENCES analysis.detection_pattern_set(id),
    subcategory text, detection_method detection_method NOT NULL, rule_name text,
    matched_text text, matched_pattern text, start_char int, end_char int,
    context_before text, context_after text,
    author_party conduct_party, author_entity_id uuid,
    bias_caution boolean NOT NULL DEFAULT true, authored_perspective text,
    confidence confidence, severity smallint, score smallint, evidence_strength strength_class,
    is_verified boolean NOT NULL DEFAULT false, verified_by text, verified_at timestamptz, verification_notes text,
    requires_human_review boolean NOT NULL DEFAULT true,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    finding_id uuid REFERENCES analysis.finding(id),
    data_tier evidence_tier NOT NULL DEFAULT 'inferred',
    provenance_id uuid REFERENCES analysis.processing_run(run_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pattern_finding_sev_chk   CHECK (severity IS NULL OR severity BETWEEN 0 AND 10),
    CONSTRAINT pattern_finding_score_chk CHECK (score IS NULL OR score BETWEEN 1 AND 10),
    CONSTRAINT pattern_finding_subj_chk  CHECK (subject_type IN ('message','ocr_text','transcript','event')),
    CONSTRAINT pattern_finding_tier_chk  CHECK (data_tier IN ('inferred','analytical')),
    CONSTRAINT pattern_finding_legal_gate CHECK (safe_for_legal_use = false OR review_status = 'approved'),
    CONSTRAINT pattern_finding_attribution_gate CHECK (safe_for_legal_use = false OR author_party IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_subject  ON analysis.pattern_finding (subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_category ON analysis.pattern_finding (category_id);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_author   ON analysis.pattern_finding (author_party);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_finding  ON analysis.pattern_finding (finding_id);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_triage   ON analysis.pattern_finding (severity DESC NULLS LAST, review_status);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_matched_trgm ON analysis.pattern_finding USING gin (matched_text gin_trgm_ops);
-- TODO(human): after span semantics fixed, add dedup unique index
--   (subject_id, category_id, start_char, end_char, matched_text) to stop triple-counting (D6 §5.9).


-- =====================================================================================
-- STEP 13 — ANALYSIS: LEGAL / CUSTODY, COURT-EVIDENCE SPINE, TASKS, EXPORT
-- =====================================================================================
CREATE TABLE IF NOT EXISTS analysis.legal_issue (
    id uuid PRIMARY KEY DEFAULT uuidv7(), case_id uuid NOT NULL, issue_key text NOT NULL,
    title text NOT NULL, description text,
    issue_type text NOT NULL DEFAULT 'custody' CHECK (issue_type IN
      ('custody','parenting_time','support','relocation','protective_order','property','contempt','other')),
    statutory_basis text, weight confidence, weight_basis text,
    created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (case_id, issue_key)
);
CREATE INDEX IF NOT EXISTS idx_legal_issue_case ON analysis.legal_issue (case_id, issue_type);

CREATE TABLE IF NOT EXISTS analysis.legal_issue_factor (
    legal_issue_id uuid NOT NULL REFERENCES analysis.legal_issue(id),
    factor mcl_factor NOT NULL REFERENCES analysis.custody_factor(factor),
    element_note text, PRIMARY KEY (legal_issue_id, factor)
);

CREATE TABLE IF NOT EXISTS analysis.evidence_item (
    id uuid PRIMARY KEY DEFAULT uuidv7(), case_id uuid NOT NULL,
    source_id uuid REFERENCES evidence.source(id),
    file_node_id uuid REFERENCES evidence.file_node(id),
    normalized_record_id uuid REFERENCES analysis.normalized_record(id),
    evidence_hash_id uuid REFERENCES evidence.evidence_hash(id),
    exhibit_number text, title text NOT NULL, description text, quote text, context text,
    evidence_type text NOT NULL DEFAULT 'communication' CHECK (evidence_type IN
      ('communication','document','photo','record','media','screenshot','transcript','metadata','other')),
    evidence_date timestamptz, evidence_date_end timestamptz,
    date_precision precision_class NOT NULL DEFAULT 'exact',
    assertion_type assertion_type NOT NULL DEFAULT 'extracted_fact',
    confidence confidence,
    confidence_tier text NOT NULL DEFAULT 'low' CHECK (confidence_tier IN ('high','medium','low')),
    relevance_score confidence, is_hypothesis boolean NOT NULL DEFAULT false,
    is_exhibit boolean NOT NULL DEFAULT false, is_authenticated boolean NOT NULL DEFAULT false,
    authentication_method text CHECK (authentication_method IS NULL OR authentication_method IN
      ('witness_with_knowledge','distinctive_characteristics','process_or_system','public_record',
       'hash_chain_of_custody','self_authenticating','stipulation')),
    chain_of_custody text,
    sensitivity_tier sensitivity_tier NOT NULL DEFAULT 'restricted',
    privacy_sensitivity text NOT NULL DEFAULT 'none' CHECK (privacy_sensitivity IN ('none','pii','minor','sensitive_pii')),
    redaction_status text NOT NULL DEFAULT 'none' CHECK (redaction_status IN ('none','required','applied')),
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    reviewed_by text, reviewed_at timestamptz, hitl_required boolean NOT NULL DEFAULT true,
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    supersedes_item_id uuid REFERENCES analysis.evidence_item(id),
    source_run_id uuid REFERENCES analysis.processing_run(run_id),
    prompt_version text, ontology_version text, schema_version text,
    created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}',
    UNIQUE (case_id, exhibit_number),
    CONSTRAINT evidence_item_safe_ck CHECK (
      safe_for_legal_use = false
      OR (review_status = 'approved' AND is_authenticated = true
          AND is_hypothesis = false AND redaction_status <> 'required')),
    CONSTRAINT evidence_item_conf_tier_ck CHECK
      (confidence_tier <> 'high' OR confidence IS NULL OR confidence >= 0.60)
);
CREATE INDEX IF NOT EXISTS idx_evitem_case   ON analysis.evidence_item (case_id, review_status);
CREATE INDEX IF NOT EXISTS idx_evitem_export ON analysis.evidence_item (case_id) WHERE safe_for_legal_use = true;
CREATE INDEX IF NOT EXISTS idx_evitem_title_trgm ON analysis.evidence_item USING gin (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS analysis.factor_citation (
    id uuid PRIMARY KEY DEFAULT uuidv7(),
    evidence_item_id uuid NOT NULL REFERENCES analysis.evidence_item(id),
    factor mcl_factor NOT NULL REFERENCES analysis.custody_factor(factor),
    legal_issue_id uuid REFERENCES analysis.legal_issue(id),
    supports_factor boolean NOT NULL,
    strength text NOT NULL DEFAULT 'moderate' CHECK (strength IN ('weak','moderate','strong','decisive')),
    supporting_text text, relevance_explanation text,
    assertion_type assertion_type NOT NULL DEFAULT 'analytical_finding',
    confidence confidence, is_hypothesis boolean NOT NULL DEFAULT false,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    supersedes_citation_id uuid REFERENCES analysis.factor_citation(id),
    created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (evidence_item_id, factor, supports_factor),
    CONSTRAINT factcite_legal_gate CHECK
      (safe_for_legal_use = false OR (review_status = 'approved' AND is_hypothesis = false))
);
CREATE INDEX IF NOT EXISTS idx_factcite_factor ON analysis.factor_citation (factor, supports_factor);
CREATE INDEX IF NOT EXISTS idx_factcite_item   ON analysis.factor_citation (evidence_item_id);

CREATE TABLE IF NOT EXISTS analysis.legal_timeline_event (
    id uuid PRIMARY KEY DEFAULT uuidv7(), case_id uuid NOT NULL,
    event_date timestamptz NOT NULL, event_date_end timestamptz,
    date_precision precision_class NOT NULL DEFAULT 'exact',
    title text NOT NULL, description text,
    event_type text NOT NULL DEFAULT 'communication' CHECK (event_type IN
      ('communication','incident','filing','hearing','order','exchange','visit','other')),
    evidence_item_ids uuid[] NOT NULL DEFAULT '{}', normalized_record_ids uuid[] NOT NULL DEFAULT '{}',
    mcl_factors mcl_factor[] NOT NULL DEFAULT '{}', participants text[] NOT NULL DEFAULT '{}',
    assertion_type assertion_type NOT NULL DEFAULT 'analytical_finding',
    confidence confidence, is_verified boolean NOT NULL DEFAULT false, is_disputed boolean NOT NULL DEFAULT false,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), metadata jsonb NOT NULL DEFAULT '{}',
    CONSTRAINT legaltl_legal_gate CHECK (safe_for_legal_use = false OR review_status = 'approved')
);
CREATE INDEX IF NOT EXISTS idx_legaltl_case ON analysis.legal_timeline_event (case_id, event_date);
CREATE INDEX IF NOT EXISTS idx_legaltl_fact ON analysis.legal_timeline_event USING gin (mcl_factors);

CREATE TABLE IF NOT EXISTS analysis.evidence_task (
    id uuid PRIMARY KEY DEFAULT uuidv7(), task_key text UNIQUE NOT NULL, case_id uuid NOT NULL,
    finding_id uuid REFERENCES analysis.finding(id),
    trigger_kind text NOT NULL DEFAULT 'manual' CHECK (trigger_kind IN
      ('contradiction','anomaly','gap','behavioral_pattern','custody_factor_concern','safety_concern',
       'communication_barrier','established_custodial_environment','selective_framing','timeline_hole',
       'attribution_uncertainty','manual')),
    evidence_needed text NOT NULL,
    evidence_need_kind text NOT NULL DEFAULT 'corroboration' CHECK (evidence_need_kind IN
      ('corroboration','original_source','authentication','metadata','completeness','chain_of_custody',
       'rebuttal','foundation','impeachment')),
    likely_source_id uuid REFERENCES evidence.source(id), likely_source_note text,
    priority text NOT NULL DEFAULT 'P3_low' CHECK (priority IN ('P0_critical','P1_high','P2_medium','P3_low','P4_backlog')),
    priority_score numeric, priority_inputs jsonb,
    priority_override text CHECK (priority_override IS NULL OR priority_override IN
      ('P0_critical','P1_high','P2_medium','P3_low','P4_backlog')),
    priority_override_reason text,
    risk text NOT NULL DEFAULT 'none' CHECK (risk IN ('none','low','medium','high')),
    risk_kind text[] NOT NULL DEFAULT '{}', risk_note text, due_date date, due_basis text,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN
      ('draft','proposed','needs_human_review','approved','in_progress','awaiting_response','blocked',
       'obtained','verified','closed_satisfied','closed_unmet','closed_overcome','superseded','archived')),
    human_action text,
    human_action_kind text NOT NULL DEFAULT 'none_yet' CHECK (human_action_kind IN
      ('review_label','approve_instrument','serve_subpoena','collect_self','request_from_counsel',
       'interview_witness','authenticate','redact','decide_relevance','file_motion','none_yet')),
    assertion_type assertion_type NOT NULL DEFAULT 'analytical_finding',
    confidence confidence,
    confidence_tier text NOT NULL DEFAULT 'low' CHECK (confidence_tier IN ('high','medium','low')),
    confidence_note text, is_hypothesis boolean NOT NULL DEFAULT false,
    label_sensitivity text NOT NULL DEFAULT 'routine' CHECK (label_sensitivity IN ('routine','sensitive','high')),
    hitl_required boolean NOT NULL DEFAULT false,
    hitl_status text NOT NULL DEFAULT 'pending' CHECK (hitl_status IN ('pending','approved','declined')),
    source_run_id uuid REFERENCES analysis.processing_run(run_id),
    prompt_version text, ontology_version text, schema_version text,
    review_status review_state NOT NULL DEFAULT 'unreviewed',
    created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), archive_reason text
);
CREATE INDEX IF NOT EXISTS idx_task_case_status ON analysis.evidence_task (case_id, status);
CREATE INDEX IF NOT EXISTS idx_task_priority    ON analysis.evidence_task (priority, due_date);
CREATE INDEX IF NOT EXISTS idx_task_riskkind    ON analysis.evidence_task USING gin (risk_kind);

CREATE TABLE IF NOT EXISTS analysis.task_event (
    event_id uuid PRIMARY KEY DEFAULT uuidv7(), task_id uuid NOT NULL REFERENCES analysis.evidence_task(id),
    from_status text, to_status text NOT NULL, actor text NOT NULL,
    actor_kind text NOT NULL CHECK (actor_kind IN ('system','agent','human')), reason text,
    ts timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_taskevent_task ON analysis.task_event (task_id, ts DESC);

CREATE TABLE IF NOT EXISTS analysis.task_revision (
    revision_id uuid PRIMARY KEY DEFAULT uuidv7(), task_id uuid NOT NULL REFERENCES analysis.evidence_task(id),
    snapshot jsonb NOT NULL, changed_by text NOT NULL, change_note text, ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis.task_person (
    task_id uuid NOT NULL REFERENCES analysis.evidence_task(id),
    person_id uuid NOT NULL REFERENCES analysis.person(id),
    role text NOT NULL CHECK (role IN ('subject','custodian','witness','child','third_party','self')),
    PRIMARY KEY (task_id, person_id, role)
);
CREATE TABLE IF NOT EXISTS analysis.task_legal_link (
    task_id uuid NOT NULL REFERENCES analysis.evidence_task(id),
    legal_issue_id uuid NOT NULL REFERENCES analysis.legal_issue(id),
    factor mcl_factor REFERENCES analysis.custody_factor(factor), element_note text,
    PRIMARY KEY (task_id, legal_issue_id, factor)
);
CREATE TABLE IF NOT EXISTS analysis.task_dependency (
    task_id uuid NOT NULL REFERENCES analysis.evidence_task(id),
    depends_on uuid NOT NULL REFERENCES analysis.evidence_task(id),
    dep_kind text NOT NULL CHECK (dep_kind IN ('blocks','prereq_of','corroborates','duplicate_of')),
    PRIMARY KEY (task_id, depends_on, dep_kind), CHECK (task_id <> depends_on)
);

CREATE TABLE IF NOT EXISTS analysis.discovery_request (
    id uuid PRIMARY KEY DEFAULT uuidv7(), task_id uuid NOT NULL REFERENCES analysis.evidence_task(id),
    instrument_type text NOT NULL CHECK (instrument_type IN
      ('subpoena','subpoena_duces_tecum','rfa','rfp','rog','witness_question','deposition_topic',
       'self_collection','records_request','preservation_letter')),
    target_person_id uuid REFERENCES analysis.person(id), target_custodian text,
    draft_text text NOT NULL, scope_note text,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','served','responded','withdrawn')),
    hitl_status text NOT NULL DEFAULT 'pending' CHECK (hitl_status IN ('pending','approved','declined')),
    prompt_version text, created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_discreq_task ON analysis.discovery_request (task_id, status);
CREATE TABLE IF NOT EXISTS analysis.discovery_request_revision (
    revision_id uuid PRIMARY KEY DEFAULT uuidv7(), request_id uuid NOT NULL REFERENCES analysis.discovery_request(id),
    snapshot jsonb NOT NULL, changed_by text NOT NULL, ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis.completion_evidence (
    id uuid PRIMARY KEY DEFAULT uuidv7(), task_id uuid NOT NULL REFERENCES analysis.evidence_task(id),
    source_id uuid REFERENCES evidence.source(id), evidence_item_id uuid REFERENCES analysis.evidence_item(id),
    evidence_hash_id uuid REFERENCES evidence.evidence_hash(id), sha256 bytea,
    outcome text NOT NULL CHECK (outcome IN ('satisfied','unmet','overcome','partial')),
    outcome_note text, recorded_by text NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT completion_sha_len CHECK (sha256 IS NULL OR octet_length(sha256) = 32)
);

CREATE OR REPLACE FUNCTION analysis.snapshot_task() RETURNS trigger
  LANGUAGE plpgsql AS $$ BEGIN
    INSERT INTO analysis.task_revision(task_id, snapshot, changed_by, change_note, ts)
    VALUES (OLD.id, to_jsonb(OLD), COALESCE(current_setting('app.actor', true),'unknown'),
            'auto-snapshot before UPDATE', now());
    RETURN NEW; END $$;
DROP TRIGGER IF EXISTS task_snapshot ON analysis.evidence_task;
CREATE TRIGGER task_snapshot BEFORE UPDATE ON analysis.evidence_task
  FOR EACH ROW EXECUTE FUNCTION analysis.snapshot_task();
CREATE OR REPLACE FUNCTION analysis.log_task_status() RETURNS trigger
  LANGUAGE plpgsql AS $$ BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
      IF NEW.status = 'archived' AND COALESCE(NEW.archive_reason,'') = '' THEN
        RAISE EXCEPTION 'archived status requires archive_reason (no silent discard)';
      END IF;
      INSERT INTO analysis.task_event(task_id, from_status, to_status, actor, actor_kind, reason, ts)
      VALUES (NEW.id, OLD.status, NEW.status, COALESCE(current_setting('app.actor', true),'system'),
              COALESCE(current_setting('app.actor_kind', true),'system'), NEW.archive_reason, now());
    END IF; RETURN NEW; END $$;
DROP TRIGGER IF EXISTS task_status_log ON analysis.evidence_task;
CREATE TRIGGER task_status_log BEFORE UPDATE OF status ON analysis.evidence_task
  FOR EACH ROW EXECUTE FUNCTION analysis.log_task_status();
DROP TRIGGER IF EXISTS taskevent_immutable ON analysis.task_event;
CREATE TRIGGER taskevent_immutable BEFORE UPDATE OR DELETE ON analysis.task_event
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();
DROP TRIGGER IF EXISTS taskrev_immutable ON analysis.task_revision;
CREATE TRIGGER taskrev_immutable BEFORE UPDATE OR DELETE ON analysis.task_revision
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();
DROP TRIGGER IF EXISTS discrev_immutable ON analysis.discovery_request_revision;
CREATE TRIGGER discrev_immutable BEFORE UPDATE OR DELETE ON analysis.discovery_request_revision
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();

CREATE TABLE IF NOT EXISTS analysis.export_package (
    id uuid PRIMARY KEY DEFAULT uuidv7(), case_id uuid NOT NULL, package_name text NOT NULL, purpose text,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','exported','withdrawn')),
    approved_by text, approved_at timestamptz, exported_at timestamptz,
    manifest jsonb NOT NULL DEFAULT '{}', signature bytea,
    created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS analysis.export_item (
    package_id uuid NOT NULL REFERENCES analysis.export_package(id),
    evidence_item_id uuid NOT NULL REFERENCES analysis.evidence_item(id),
    ordinal int, included_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (package_id, evidence_item_id)
);


-- =====================================================================================
-- STEP 14 — ANALYSIS: REVIEW / HITL + REDACTION / EXPORT
-- =====================================================================================
CREATE TABLE IF NOT EXISTS analysis.review_task (
    task_id uuid PRIMARY KEY DEFAULT uuidv7(), trigger_code text NOT NULL,
    target_kind text NOT NULL, target_id uuid NOT NULL,
    score_ids uuid[] NOT NULL DEFAULT '{}', blocks text NOT NULL, reviewer_role text,
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','in_review','resolved')),
    created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rtask_state ON analysis.review_task (state, trigger_code);

CREATE TABLE IF NOT EXISTS analysis.review_decision (
    decision_id uuid PRIMARY KEY DEFAULT uuidv7(),
    task_id uuid REFERENCES analysis.review_task(task_id),
    target_kind text NOT NULL, target_id uuid NOT NULL,
    reviewer text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('approved','rejected','needs_changes','needs_context','escalated','hold')),
    set_confidence confidence,
    set_evidence_strength strength_class,
    sensitive_label_decision jsonb,
    court_readiness text NOT NULL DEFAULT 'not_reviewed' CHECK (court_readiness IN
      ('not_reviewed','draft','needs_corroboration','review_passed','court_ready','excluded','strategically_sensitive')),
    tier_approved sensitivity_tier, requires_corroboration boolean NOT NULL DEFAULT false,
    score_snapshot uuid[] NOT NULL DEFAULT '{}',
    prompt_version_id uuid REFERENCES public.prompt_registry(prompt_id),
    ontology_version_id uuid REFERENCES public.ontology_version(ontology_version_id),
    schema_version_id uuid REFERENCES public.schema_version(schema_version_id),
    rationale text NOT NULL, decided_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rdec_target ON analysis.review_decision (target_kind, target_id);
DROP TRIGGER IF EXISTS rdec_append_only ON analysis.review_decision;
CREATE TRIGGER rdec_append_only BEFORE UPDATE OR DELETE ON analysis.review_decision
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();

CREATE TABLE IF NOT EXISTS analysis.redaction (
    redaction_id uuid PRIMARY KEY DEFAULT uuidv7(),
    redaction_run uuid REFERENCES analysis.processing_run(run_id),
    source_artifact uuid NOT NULL REFERENCES analysis.artifact_registry(artifact_id),
    redacted_artifact uuid NOT NULL REFERENCES analysis.artifact_registry(artifact_id),
    policy_version text NOT NULL, redaction_map jsonb NOT NULL, reversible boolean NOT NULL DEFAULT true,
    authorized_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS redaction_append_only ON analysis.redaction;
CREATE TRIGGER redaction_append_only BEFORE UPDATE OR DELETE ON analysis.redaction
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();

CREATE TABLE IF NOT EXISTS analysis.export (
    export_id uuid PRIMARY KEY DEFAULT uuidv7(),
    export_run uuid REFERENCES analysis.processing_run(run_id),
    package_uri text NOT NULL, manifest_sha256 bytea NOT NULL, signature bytea,
    included_artifacts uuid[] NOT NULL, tier sensitivity_tier NOT NULL, purpose text,
    requested_by text NOT NULL, approved_by text NOT NULL,
    blocked_by_open_questions uuid[] NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now()
);
DROP TRIGGER IF EXISTS export_append_only ON analysis.export;
CREATE TRIGGER export_append_only BEFORE UPDATE OR DELETE ON analysis.export
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();


-- =====================================================================================
-- STEP 15 — PUBLIC: WORK-PRODUCT OPERATIONAL MEMORY + AUDIT SPINE
-- =====================================================================================
CREATE TABLE IF NOT EXISTS public.memory_items (
    memory_id uuid PRIMARY KEY DEFAULT uuidv7(),
    memory_type text NOT NULL CHECK (memory_type IN
      ('user_preference','project_fact','evidence_fact','hypothesis','analysis_finding','design_decision',
       'open_question','warning','artifact_summary','run_summary','deprecated_memory')),
    title text NOT NULL, summary text, content_inline text, content_uri text, content_hash bytea,
    source_of_memory text, created_by text NOT NULL, confidence confidence,
    assertion_type assertion_type,
    status text NOT NULL DEFAULT 'active' CHECK (status IN
      ('active','draft','needs_review','superseded','deprecated','rejected','archived')),
    review_status text NOT NULL DEFAULT 'none' CHECK (review_status IN ('none','pending','approved','rejected')),
    is_sensitive boolean NOT NULL DEFAULT false, mirror_store source_system,
    superseded_by uuid REFERENCES public.memory_items(memory_id),
    related_artifact_ids uuid[] NOT NULL DEFAULT '{}', related_evidence_ids uuid[] NOT NULL DEFAULT '{}',
    related_ontology_id uuid REFERENCES public.ontology_version(ontology_version_id),
    related_schema_id uuid REFERENCES public.schema_version(schema_version_id),
    tags jsonb NOT NULL DEFAULT '[]',
    fts tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(summary,''))) STORED,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mem_type_status ON public.memory_items (memory_type, status);
CREATE INDEX IF NOT EXISTS idx_mem_fts         ON public.memory_items USING gin (fts);
CREATE INDEX IF NOT EXISTS idx_mem_title_trgm  ON public.memory_items USING gin (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS public.decision_log (
    decision_id uuid PRIMARY KEY DEFAULT uuidv7(), decision_title text NOT NULL,
    decision_type text NOT NULL CHECK (decision_type IN
      ('schema','ontology','legal_relevance','evidence_classification','tooling','storage','privacy','export','human_review')),
    context text, options_considered jsonb NOT NULL DEFAULT '[]', decision_made text NOT NULL,
    reasoning_summary text, evidence_or_artifacts_considered jsonb NOT NULL DEFAULT '[]',
    owner text NOT NULL, reversibility text CHECK (reversibility IN ('reversible','costly','irreversible')),
    related_risks text, related_open_questions uuid[] NOT NULL DEFAULT '{}',
    supersedes uuid REFERENCES public.decision_log(decision_id),
    review_status text NOT NULL DEFAULT 'none' CHECK (review_status IN ('none','pending','approved','rejected')),
    decided_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.session_summaries (
    session_id uuid PRIMARY KEY DEFAULT uuidv7(), session_start timestamptz NOT NULL, session_end timestamptz,
    user_goal text, work_completed text, files_inspected jsonb NOT NULL DEFAULT '[]',
    artifacts_created jsonb NOT NULL DEFAULT '[]', decisions_made uuid[] NOT NULL DEFAULT '{}',
    open_questions uuid[] NOT NULL DEFAULT '{}', next_actions text, blockers text,
    tone_preference_notes text, important_warnings text, related_run_ids uuid[] NOT NULL DEFAULT '{}',
    fts tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(user_goal,'') || ' ' || coalesce(work_completed,''))) STORED,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sess_fts ON public.session_summaries USING gin (fts);
DROP TRIGGER IF EXISTS sess_append_only ON public.session_summaries;
CREATE TRIGGER sess_append_only BEFORE UPDATE OR DELETE ON public.session_summaries
  FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();

CREATE TABLE IF NOT EXISTS public.open_questions (
    question_id uuid PRIMARY KEY DEFAULT uuidv7(), question_text text NOT NULL,
    category text NOT NULL CHECK (category IN
      ('data_gap','schema','ontology','legal_relevance','corroboration_needed','privacy','technical')),
    raised_by text,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','investigating','answered','wont_fix','superseded')),
    answer_summary text, answered_by text, answered_at timestamptz,
    related_run_id uuid REFERENCES analysis.processing_run(run_id),
    related_artifact_ids uuid[] NOT NULL DEFAULT '{}',
    blocks_export boolean NOT NULL DEFAULT false, requires_corroboration boolean NOT NULL DEFAULT false,
    priority int NOT NULL DEFAULT 3, raised_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_oq_blocks ON public.open_questions (blocks_export) WHERE blocks_export;

CREATE TABLE IF NOT EXISTS public.decision_precedent (
    precedent_id uuid PRIMARY KEY DEFAULT uuidv7(),
    decision_id uuid NOT NULL REFERENCES public.decision_log(decision_id),
    source_decision_id uuid NOT NULL REFERENCES public.decision_log(decision_id),
    similarity_score confidence,
    relationship_type text CHECK (relationship_type IN ('similar_scenario','same_policy','exception_precedent')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.change_log (
    seq bigint GENERATED ALWAYS AS IDENTITY,
    change_id uuid PRIMARY KEY DEFAULT uuidv7(),
    table_name text NOT NULL, record_id uuid, field_name text,
    action text NOT NULL, previous_value text, new_value text, actor text NOT NULL,
    change_origin text NOT NULL CHECK (change_origin IN ('model_generated','human_approved','system')),
    reason text, related_run_id uuid REFERENCES analysis.processing_run(run_id),
    related_decision_id uuid REFERENCES public.decision_log(decision_id),
    detail jsonb, prev_change_hash bytea, row_hash bytea NOT NULL,
    change_timestamp timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_clog_record ON public.change_log (table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_clog_time   ON public.change_log (change_timestamp);
DROP TRIGGER IF EXISTS clog_append_only ON public.change_log;
CREATE TRIGGER clog_append_only BEFORE UPDATE OR DELETE ON public.change_log
  FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();
CREATE OR REPLACE FUNCTION public.change_log_chain() RETURNS trigger
  LANGUAGE plpgsql AS $$
DECLARE prev bytea;
BEGIN
  SELECT row_hash INTO prev FROM public.change_log ORDER BY seq DESC LIMIT 1;
  NEW.prev_change_hash := prev;
  NEW.row_hash := digest(
      coalesce(NEW.table_name,'') || '|' || coalesce(NEW.record_id::text,'') || '|' ||
      coalesce(NEW.field_name,'') || '|' || NEW.action || '|' ||
      coalesce(NEW.previous_value,'') || '|' || coalesce(NEW.new_value,'') || '|' ||
      NEW.actor || '|' || NEW.change_origin || '|' || coalesce(encode(prev,'hex'),''), 'sha256');
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS clog_chain ON public.change_log;
CREATE TRIGGER clog_chain BEFORE INSERT ON public.change_log
  FOR EACH ROW EXECUTE FUNCTION public.change_log_chain();
-- TODO(human): version-pin the change_log canonical-serialization recipe (mirror hash_canon_version)
--   before relying on it for tamper-evidence in an export. Per-table audit triggers feeding this
--   spine are described in D8 §G but NOT generated here (parametrised over TG_TABLE_NAME).


-- =====================================================================================
-- STEP 16 — PUBLIC / ANALYSIS VIEWS (court export gates)
-- =====================================================================================
CREATE OR REPLACE VIEW public.vw_event_evidence_package AS
SELECT e.event_id, e.serial_id, e.title, e.event_type,
       ta.valid_earliest, ta.valid_latest, ta.valid_point, ta.ts_utc,
       ta.certainty, ta.assertion_type, ta.confidence, ta.disclosure_horizon,
       CASE
         WHEN ta.certainty = 'exact'       AND ta.confidence >= 0.80 THEN 'HIGH'
         WHEN ta.certainty = 'approximate' AND ta.confidence >= 0.60 THEN 'MEDIUM'
         ELSE 'LOW'
       END AS temporal_confidence_tier,
       e.mcl_relevance, e.source_artifact_id, ta.reasoning
FROM analysis.timeline_event e
JOIN analysis.time_assertion ta ON ta.event_id = e.event_id AND upper_inf(ta.sys_period)
WHERE e.safe_for_legal_use AND NOT e.requires_human_review AND NOT ta.requires_human_review;

CREATE OR REPLACE VIEW analysis.vw_court_export AS
SELECT ei.id, ei.case_id, ei.exhibit_number, ei.title, ei.description, ei.quote, ei.context,
       ei.evidence_type, ei.evidence_date, ei.date_precision, ei.assertion_type, ei.confidence,
       ei.confidence_tier, ei.is_authenticated, ei.authentication_method, ei.chain_of_custody,
       ei.sensitivity_tier, ei.redaction_status, ei.source_id, ei.file_node_id, ei.evidence_hash_id,
       ei.reviewed_by, ei.reviewed_at
FROM analysis.evidence_item ei
WHERE ei.safe_for_legal_use = true
  AND ei.review_status      = 'approved'
  AND ei.confidence_tier IN ('high','medium')
  AND ei.is_hypothesis      = false
  AND ei.is_authenticated   = true
  AND ei.redaction_status  <> 'required'
  AND ei.sensitivity_tier  <> 'sealed';

CREATE OR REPLACE VIEW analysis.vw_open_tasks AS
SELECT t.id, t.task_key, t.case_id, t.status, t.priority, t.priority_score, t.due_date, t.due_basis,
       t.human_action, t.human_action_kind, t.label_sensitivity, t.hitl_required, t.hitl_status,
       t.confidence_tier, t.is_hypothesis,
       (SELECT count(*) FROM analysis.task_dependency d
         WHERE d.depends_on = t.id AND d.dep_kind IN ('blocks','prereq_of')) AS blocks_n,
       (SELECT e.to_status FROM analysis.task_event e WHERE e.task_id = t.id ORDER BY e.ts DESC LIMIT 1) AS last_event
FROM analysis.evidence_task t
WHERE t.status NOT IN ('closed_satisfied','closed_unmet','closed_overcome','superseded','archived')
ORDER BY t.priority, t.priority_score DESC NULLS LAST, t.due_date NULLS LAST;

-- TODO(human): pg_duckdb analytical views (vw_lineage, geo route/place analytics) read these
--   tables via the embedded engine; build them in the analytics lane, not as base DDL.

-- =====================================================================================
-- NO DESTRUCTIVE DROPS. The design's deprecated/competing tables never existed live
-- (analysis.provenance, evidence.ingestion_run, D3 raw_timeline_segment/timeline_waypoint —
-- absent per PG_live_summary.txt). If a future audit finds one, comment out + guard:
-- -- TODO(human): confirm drop  -- DROP TABLE IF EXISTS analysis.<deprecated> CASCADE;
-- =====================================================================================
-- END 0005_forensic_reconciliation.sql — additive, idempotent, run by hand on live volume.
-- =====================================================================================
