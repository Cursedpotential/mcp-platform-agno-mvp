-- Minimal PostgreSQL 18 prerequisite schema for rollback-only migration 0030
-- behavior validation. This is a test fixture, not a bootstrap replacement.
--
-- Byline: Codex · GPT-5 · 2026-08-15

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

CREATE SCHEMA ai;
CREATE SCHEMA analysis;
CREATE SCHEMA evidence;
CREATE SCHEMA ops;
CREATE SCHEMA working;

CREATE TYPE ai.review_state AS ENUM (
    'unreviewed', 'in_review', 'approved', 'rejected', 'superseded'
);

CREATE TABLE evidence.source (
    id                UUID PRIMARY KEY DEFAULT uuidv7(),
    sha256            BYTEA NOT NULL CHECK (octet_length(sha256) = 32),
    byte_size         BIGINT NOT NULL,
    source_type       TEXT NOT NULL,
    acquisition_source TEXT NOT NULL,
    original_filename TEXT
);

CREATE TABLE evidence.file_node (
    id        UUID PRIMARY KEY DEFAULT uuidv7(),
    source_id UUID NOT NULL REFERENCES evidence.source(id),
    node_kind TEXT NOT NULL,
    sha256    BYTEA CHECK (sha256 IS NULL OR octet_length(sha256) = 32)
);

CREATE TABLE evidence.evidence_hash (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    source_ref   TEXT NOT NULL,
    algo         TEXT NOT NULL DEFAULT 'sha256',
    digest       BYTEA NOT NULL CHECK (octet_length(digest) = 32),
    level        TEXT NOT NULL DEFAULT 'H1',
    source_id    UUID REFERENCES evidence.source(id),
    file_node_id UUID REFERENCES evidence.file_node(id),
    canon_version TEXT NOT NULL DEFAULT 'h1-rawbytes-v1',
    computed_by  TEXT
);

CREATE TABLE ops.processing_run (
    run_id   UUID PRIMARY KEY DEFAULT uuidv7(),
    run_type TEXT NOT NULL,
    actor    TEXT NOT NULL,
    status   TEXT NOT NULL DEFAULT 'queued'
);

CREATE TABLE ops.audit_ledger (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts              TIMESTAMPTZ NOT NULL,
    actor           TEXT NOT NULL,
    action_type     TEXT NOT NULL,
    object_schema   TEXT,
    object_ref      TEXT,
    horizon_context JSONB,
    base_version    INTEGER,
    payload_hash    TEXT,
    prev_hash       TEXT,
    entry_hash      TEXT NOT NULL
);

CREATE TABLE working.normalized_record (
    id            UUID PRIMARY KEY DEFAULT uuidv7(),
    artifact_id   UUID NOT NULL REFERENCES evidence.evidence_hash(id),
    record_type   TEXT NOT NULL,
    source        TEXT NOT NULL,
    conversation_id TEXT,
    role          TEXT,
    content       TEXT NOT NULL DEFAULT '',
    occurred_at   TIMESTAMPTZ,
    disclosure_tier TEXT NOT NULL DEFAULT 'contemporaneous',
    review_status ai.review_state NOT NULL DEFAULT 'unreviewed',
    provenance_id UUID REFERENCES ops.processing_run(run_id),
    case_id       TEXT NOT NULL DEFAULT 'primary',
    domain        TEXT NOT NULL DEFAULT 'evidence'
);

CREATE FUNCTION working.forbid_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only: % blocked (corrections are new rows)',
        TG_TABLE_NAME, TG_OP;
END;
$$;

CREATE TABLE analysis.evidence_item (
    id                   UUID PRIMARY KEY DEFAULT uuidv7(),
    case_id              UUID NOT NULL,
    source_id            UUID REFERENCES evidence.source(id),
    file_node_id         UUID REFERENCES evidence.file_node(id),
    normalized_record_id UUID REFERENCES working.normalized_record(id),
    evidence_hash_id     UUID REFERENCES evidence.evidence_hash(id),
    title                TEXT NOT NULL,
    description          TEXT,
    quote                TEXT,
    evidence_type        TEXT NOT NULL DEFAULT 'communication',
    evidence_date        TIMESTAMPTZ,
    review_status        ai.review_state NOT NULL DEFAULT 'unreviewed',
    hitl_required        BOOLEAN NOT NULL DEFAULT true,
    safe_for_legal_use   BOOLEAN NOT NULL DEFAULT false,
    is_authenticated     BOOLEAN NOT NULL DEFAULT false,
    source_run_id        UUID REFERENCES ops.processing_run(run_id),
    created_by           TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata             JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE analysis.review_task (
    task_id       UUID PRIMARY KEY DEFAULT uuidv7(),
    trigger_code  TEXT NOT NULL,
    target_kind   TEXT NOT NULL,
    target_id     UUID NOT NULL,
    blocks        TEXT NOT NULL,
    reviewer_role TEXT,
    state         TEXT NOT NULL DEFAULT 'pending'
                  CHECK (state IN ('pending', 'in_review', 'resolved')),
    created_by    TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE analysis.review_decision (
    decision_id    UUID PRIMARY KEY DEFAULT uuidv7(),
    task_id        UUID REFERENCES analysis.review_task(task_id),
    target_kind    TEXT NOT NULL,
    target_id      UUID NOT NULL,
    reviewer       TEXT NOT NULL,
    decision       TEXT NOT NULL CHECK (decision IN (
        'approved', 'rejected', 'needs_changes', 'needs_context', 'escalated', 'hold'
    )),
    court_readiness TEXT NOT NULL DEFAULT 'not_reviewed',
    rationale      TEXT NOT NULL,
    decided_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER review_decision_append_only
    BEFORE UPDATE OR DELETE ON analysis.review_decision
    FOR EACH ROW EXECUTE FUNCTION working.forbid_mutation();
