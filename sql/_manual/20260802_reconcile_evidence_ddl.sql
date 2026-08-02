-- 20260802_reconcile_evidence_ddl.sql — CAPTURED LIVE DDL, do not apply blindly.
--
-- Byline: Claude Code . Fable 5 . 2026-08-02
--
-- WHY: the 2026-08-02 hashing audit (finding 1, HIGH) found that the custody
-- code depends on evidence.source / evidence.custody_event (incl. its
-- event_digest chain trigger) / evidence.evidence_hash columns whose DDL
-- appears in NO numbered migration 0001-0016 — it was applied out-of-band.
-- An opposing expert must be able to reproduce the schema the chain depends
-- on from this repo alone, so here is the live DDL, captured verbatim from
-- the production database (pg_dump --schema-only) on 2026-08-02.
--
-- This file is EVIDENCE OF WHAT EXISTS, not a migration to run: applying it
-- to a database that already has these tables will error, which is fine.
-- custody.py's stale "migration 0005" citation was corrected the same day.

--
-- PostgreSQL database dump
--

\restrict OCCWX8JLBLZamSEeSRJNXBbAqsqf96JI73wpZHdNaTQcov5tCpQCyf24RdQX91o

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: custody_event; Type: TABLE; Schema: evidence; Owner: -
--

CREATE TABLE evidence.custody_event (
    seq bigint NOT NULL,
    id uuid DEFAULT uuidv7() NOT NULL,
    source_id uuid NOT NULL,
    file_node_id uuid,
    evidence_hash_id uuid,
    event_type text NOT NULL,
    actor text NOT NULL,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    occurred_certainty ai.precision_class DEFAULT 'exact'::ai.precision_class NOT NULL,
    detail jsonb DEFAULT '{}'::jsonb NOT NULL,
    prev_event_digest bytea,
    event_digest bytea NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT custody_event_event_type_check CHECK ((event_type = ANY (ARRAY['collected'::text, 'sealed'::text, 'in_processing'::text, 'verified'::text, 'disputed'::text, 'released'::text, 're_hashed'::text, 'integrity_violation'::text, 'superseded'::text, 'accessed'::text])))
);


--
-- Name: custody_event_seq_seq; Type: SEQUENCE; Schema: evidence; Owner: -
--

ALTER TABLE evidence.custody_event ALTER COLUMN seq ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME evidence.custody_event_seq_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
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
    level text DEFAULT 'H1'::text NOT NULL,
    source_id uuid,
    file_node_id uuid,
    md5_prefilter bytea,
    record_locator jsonb,
    member_hash_ids uuid[],
    canon_version text DEFAULT 'h1-rawbytes-v1'::text NOT NULL,
    computed_by text,
    CONSTRAINT evidence_hash_check CHECK (((algo <> 'sha256'::text) OR (octet_length(digest) = 32))),
    CONSTRAINT evidence_hash_level_check CHECK ((level = ANY (ARRAY['H1'::text, 'H2'::text, 'H3'::text])))
);


--
-- Name: file_node; Type: TABLE; Schema: evidence; Owner: -
--

CREATE TABLE evidence.file_node (
    id uuid DEFAULT uuidv7() NOT NULL,
    source_id uuid NOT NULL,
    parent_node_id uuid,
    node_kind text NOT NULL,
    node_path ai.ltree,
    ordinal integer,
    sha256 bytea,
    byte_span_start bigint,
    byte_span_end bigint,
    locator jsonb DEFAULT '{}'::jsonb NOT NULL,
    mime_type text,
    extraction_confidence ai.confidence,
    attrs jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT file_node_node_kind_check CHECK ((node_kind = ANY (ARRAY['file'::text, 'archive_member'::text, 'page'::text, 'frame'::text, 'region'::text, 'screenshot'::text, 'ocr_block'::text, 'attachment'::text, 'message_unit'::text, 'event_unit'::text]))),
    CONSTRAINT file_node_sha_len CHECK (((sha256 IS NULL) OR (octet_length(sha256) = 32)))
);


--
-- Name: source; Type: TABLE; Schema: evidence; Owner: -
--

CREATE TABLE evidence.source (
    id uuid DEFAULT uuidv7() NOT NULL,
    sha256 bytea NOT NULL,
    md5_prefilter bytea,
    byte_size bigint NOT NULL,
    mime_type text,
    original_filename text,
    source_type text NOT NULL,
    source_platform text,
    custodian text DEFAULT 'Matt Salem'::text NOT NULL,
    acquisition_source text NOT NULL,
    acquisition_method text,
    origin_device_id uuid,
    origin_account uuid,
    acquired_at_raw text,
    acquired_at_utc timestamp with time zone,
    acquired_tz_offset text,
    acquired_certainty ai.precision_class DEFAULT 'exact'::ai.precision_class NOT NULL,
    provenance_tier text DEFAULT 'r2_canonical'::text NOT NULL,
    r2_bucket text,
    r2_key text,
    local_path text,
    hash_canon_version text DEFAULT 'h1-rawbytes-v1'::text NOT NULL,
    sensitivity_tier ai.sensitivity_tier DEFAULT 'restricted'::ai.sensitivity_tier NOT NULL,
    legal_sensitivity text DEFAULT 'none'::text NOT NULL,
    privacy_sensitivity text DEFAULT 'none'::text NOT NULL,
    supersedes_source_id uuid,
    custody_status text DEFAULT 'collected'::text NOT NULL,
    extraction_status text DEFAULT 'pending'::text NOT NULL,
    processing_status text DEFAULT 'pending'::text NOT NULL,
    review_status text DEFAULT 'not_reviewed'::text NOT NULL,
    export_status text DEFAULT 'not_exported'::text NOT NULL,
    verified_by text,
    verified_at timestamp with time zone,
    original_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    derived_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    ingested_at timestamp with time zone DEFAULT now() NOT NULL,
    acquisition_id uuid,
    CONSTRAINT source_acquisition_method_check CHECK (((acquisition_method IS NULL) OR (acquisition_method = ANY (ARRAY['forensic_image'::text, 'manual_export'::text, 'cloud_pull'::text, 'photograph'::text, 'scan'::text, 'backup'::text])))),
    CONSTRAINT source_custody_status_check CHECK ((custody_status = ANY (ARRAY['collected'::text, 'sealed'::text, 'in_processing'::text, 'verified'::text, 'disputed'::text, 'released'::text]))),
    CONSTRAINT source_export_status_check CHECK ((export_status = ANY (ARRAY['not_exported'::text, 'in_package'::text, 'exported'::text, 'withdrawn'::text]))),
    CONSTRAINT source_extraction_status_check CHECK ((extraction_status = ANY (ARRAY['pending'::text, 'running'::text, 'done'::text, 'failed'::text, 'n/a'::text]))),
    CONSTRAINT source_legal_sensitivity_check CHECK ((legal_sensitivity = ANY (ARRAY['none'::text, 'privileged'::text, 'confidential'::text, 'in_camera'::text]))),
    CONSTRAINT source_privacy_sensitivity_check CHECK ((privacy_sensitivity = ANY (ARRAY['none'::text, 'pii'::text, 'minor'::text, 'sensitive_pii'::text]))),
    CONSTRAINT source_processing_status_check CHECK ((processing_status = ANY (ARRAY['pending'::text, 'enriched'::text, 'analyzed'::text, 'failed'::text]))),
    CONSTRAINT source_provenance_tier_check CHECK ((provenance_tier = ANY (ARRAY['r2_canonical'::text, 'backup_corroborating'::text]))),
    CONSTRAINT source_review_status_check CHECK ((review_status = ANY (ARRAY['not_reviewed'::text, 'in_review'::text, 'reviewed'::text, 'flagged'::text]))),
    CONSTRAINT source_sha256_len CHECK ((octet_length(sha256) = 32)),
    CONSTRAINT source_source_type_check CHECK ((source_type = ANY (ARRAY['device_dump'::text, 'chat_export'::text, 'screenshot'::text, 'call_log'::text, 'pdf'::text, 'media'::text, 'takeout'::text, 'social_export'::text, 'document'::text, 'other'::text])))
);


--
-- Name: COLUMN source.acquisition_source; Type: COMMENT; Schema: evidence; Owner: -
--

COMMENT ON COLUMN evidence.source.acquisition_source IS 'PER-FILE acquisition source (e.g. "sbv", "manual_export"), written at ingest. Describes the ingest CHANNEL, not the legal/physical provenance — that is evidence.acquisition.method + .authority.';


--
-- Name: COLUMN source.acquisition_method; Type: COMMENT; Schema: evidence; Owner: -
--

COMMENT ON COLUMN evidence.source.acquisition_method IS 'PER-FILE acquisition method, written at ingest by server/evidence/custody.py. Retained and live. For the per-EVENT record — device, authority, custodian, time-scoped handoff, one row covering many files — join evidence.acquisition via evidence.source.acquisition_id. On disagreement the acquisition row wins: it is HITL-authored, the per-file value is a pipeline default.';


--
-- Name: custody_event custody_event_id_key; Type: CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.custody_event
    ADD CONSTRAINT custody_event_id_key UNIQUE (id);


--
-- Name: custody_event custody_event_pkey; Type: CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.custody_event
    ADD CONSTRAINT custody_event_pkey PRIMARY KEY (seq);


--
-- Name: evidence_hash evidence_hash_pkey; Type: CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.evidence_hash
    ADD CONSTRAINT evidence_hash_pkey PRIMARY KEY (id);


--
-- Name: evidence_hash evidence_hash_subject_ck; Type: CHECK CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE evidence.evidence_hash
    ADD CONSTRAINT evidence_hash_subject_ck CHECK (((level = 'H3'::text) OR (source_id IS NOT NULL) OR (file_node_id IS NOT NULL))) NOT VALID;


--
-- Name: file_node file_node_pkey; Type: CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.file_node
    ADD CONSTRAINT file_node_pkey PRIMARY KEY (id);


--
-- Name: source source_pkey; Type: CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.source
    ADD CONSTRAINT source_pkey PRIMARY KEY (id);


--
-- Name: source source_sha256_uniq; Type: CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.source
    ADD CONSTRAINT source_sha256_uniq UNIQUE (sha256);


--
-- Name: idx_custody_source; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_custody_source ON evidence.custody_event USING btree (source_id, occurred_at);


--
-- Name: idx_custody_type; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_custody_type ON evidence.custody_event USING btree (event_type, occurred_at DESC);


--
-- Name: idx_evhash_filenode; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_evhash_filenode ON evidence.evidence_hash USING btree (file_node_id);


--
-- Name: idx_evhash_level_source; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_evhash_level_source ON evidence.evidence_hash USING btree (level, source_id);


--
-- Name: idx_evhash_meta; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_evhash_meta ON evidence.evidence_hash USING gin (meta);


--
-- Name: idx_evidence_hash_digest; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_evidence_hash_digest ON evidence.evidence_hash USING btree (digest);


--
-- Name: idx_filenode_parent; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_filenode_parent ON evidence.file_node USING btree (parent_node_id);


--
-- Name: idx_filenode_path; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_filenode_path ON evidence.file_node USING gist (node_path);


--
-- Name: idx_filenode_sha; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_filenode_sha ON evidence.file_node USING btree (sha256);


--
-- Name: idx_filenode_source; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_filenode_source ON evidence.file_node USING btree (source_id);


--
-- Name: idx_source_acquisition; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_source_acquisition ON evidence.source USING btree (acquisition_id);


--
-- Name: idx_source_custody; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_source_custody ON evidence.source USING btree (custody_status);


--
-- Name: idx_source_filename_trgm; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_source_filename_trgm ON evidence.source USING gin (original_filename public.gin_trgm_ops);


--
-- Name: idx_source_orig_meta; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_source_orig_meta ON evidence.source USING gin (original_metadata);


--
-- Name: idx_source_platform; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_source_platform ON evidence.source USING btree (source_platform, source_type);


--
-- Name: idx_source_supersedes; Type: INDEX; Schema: evidence; Owner: -
--

CREATE INDEX idx_source_supersedes ON evidence.source USING btree (supersedes_source_id);


--
-- Name: custody_event custody_event_chain; Type: TRIGGER; Schema: evidence; Owner: -
--

CREATE TRIGGER custody_event_chain BEFORE INSERT ON evidence.custody_event FOR EACH ROW EXECUTE FUNCTION evidence.chain_custody_event();


--
-- Name: custody_event custody_event_immutable; Type: TRIGGER; Schema: evidence; Owner: -
--

CREATE TRIGGER custody_event_immutable BEFORE DELETE OR UPDATE ON evidence.custody_event FOR EACH ROW EXECUTE FUNCTION evidence.forbid_mutation();


--
-- Name: file_node filenode_immutable; Type: TRIGGER; Schema: evidence; Owner: -
--

CREATE TRIGGER filenode_immutable BEFORE DELETE OR UPDATE ON evidence.file_node FOR EACH ROW EXECUTE FUNCTION evidence.forbid_mutation();


--
-- Name: source source_immutable; Type: TRIGGER; Schema: evidence; Owner: -
--

CREATE TRIGGER source_immutable BEFORE DELETE OR UPDATE ON evidence.source FOR EACH ROW EXECUTE FUNCTION evidence.source_immutable_core();


--
-- Name: custody_event custody_event_evidence_hash_id_fkey; Type: FK CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.custody_event
    ADD CONSTRAINT custody_event_evidence_hash_id_fkey FOREIGN KEY (evidence_hash_id) REFERENCES evidence.evidence_hash(id);


--
-- Name: custody_event custody_event_file_node_id_fkey; Type: FK CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.custody_event
    ADD CONSTRAINT custody_event_file_node_id_fkey FOREIGN KEY (file_node_id) REFERENCES evidence.file_node(id);


--
-- Name: custody_event custody_event_source_id_fkey; Type: FK CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.custody_event
    ADD CONSTRAINT custody_event_source_id_fkey FOREIGN KEY (source_id) REFERENCES evidence.source(id);


--
-- Name: evidence_hash evidence_hash_file_node_id_fkey; Type: FK CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.evidence_hash
    ADD CONSTRAINT evidence_hash_file_node_id_fkey FOREIGN KEY (file_node_id) REFERENCES evidence.file_node(id);


--
-- Name: evidence_hash evidence_hash_source_id_fkey; Type: FK CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.evidence_hash
    ADD CONSTRAINT evidence_hash_source_id_fkey FOREIGN KEY (source_id) REFERENCES evidence.source(id);


--
-- Name: file_node file_node_parent_node_id_fkey; Type: FK CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.file_node
    ADD CONSTRAINT file_node_parent_node_id_fkey FOREIGN KEY (parent_node_id) REFERENCES evidence.file_node(id);


--
-- Name: file_node file_node_source_id_fkey; Type: FK CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.file_node
    ADD CONSTRAINT file_node_source_id_fkey FOREIGN KEY (source_id) REFERENCES evidence.source(id);


--
-- Name: source source_acquisition_id_fkey; Type: FK CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.source
    ADD CONSTRAINT source_acquisition_id_fkey FOREIGN KEY (acquisition_id) REFERENCES evidence.acquisition(id);


--
-- Name: source source_supersedes_source_id_fkey; Type: FK CONSTRAINT; Schema: evidence; Owner: -
--

ALTER TABLE ONLY evidence.source
    ADD CONSTRAINT source_supersedes_source_id_fkey FOREIGN KEY (supersedes_source_id) REFERENCES evidence.source(id);


--
-- PostgreSQL database dump complete
--

\unrestrict OCCWX8JLBLZamSEeSRJNXBbAqsqf96JI73wpZHdNaTQcov5tCpQCyf24RdQX91o

