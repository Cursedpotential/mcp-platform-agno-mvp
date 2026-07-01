-- ============================================================================
-- Forensic Staging DB — consolidated SQLite schema (Salem v. Kinzel)
-- Byline: Claude Code · Opus 4.8 · 2026-06-20
-- Staging store for the transcript-mining pipeline (see transcript-mining-pipeline-spec.md).
-- Local SQLite mirror of the canonical PG design; imported to PG via pg_duckdb when ready.
-- ============================================================================
--
-- PROVENANCE / RECONCILIATION (audit of extracted-code/ schema iterations):
--   • Messaging stack: 3 iterations found. WINNER = SMS_TABLES_FINAL.sql (a strict
--     superset), which lives INSIDE the mislabeled ZIP
--     `sbv/Salem_SMS_Tables_Complete_Deployment_2025-12-27.sql` (PK/ZIP header, not SQL).
--     Discarded: message-schemas.ts (self-labeled placeholder); production-message-schemas.ts
--     (subset, superseded). Body field unified as `content` (was text→body→content).
--   • mcl_factors appeared 3× with conflicting designs → SPLIT: `mcl_factors` (legal
--     reference, PK = letter A–L) vs `mcl_factor_config` (app detection tuning).
--   • Drizzle Postgres `schema.ts` authoritative over the MySQL fork
--     (prompts-/patterns-/settings-schema.ts); net-new tables from settings-schema kept out
--     of staging (app/ops config, not forensic records).
--   • Salem Zep ontology → relational: generic `case_entities` + `case_relations`
--     (+ JSON spillover) plus `darvo_stages` and `mcl_factor_findings`.
--   • pgvector columns EXCLUDED here (learned_knowledge.embedding, transcript_insight.embedding)
--     — deferred to PG/Milvus at import time.
--
-- OPEN DECISIONS (defaults applied below; change before building if needed):
--   1. Scope = forensic records only (messaging + ontology + MCL + Agno runtime).
--      App/ops config tables excluded. [DEFAULT: forensic-only]
--   2. mcl_factors split into reference + config. [DEFAULT: split]
--   3. Ontology = generic case_entities + case_relations (vs per-entity tables). [DEFAULT: generic]
--   4. Message-layer findings (messaging_behaviors/factor_citations) kept separate from
--      ontology-layer (darvo_stages/mcl_factor_findings). [DEFAULT: separate]
--   5. content_lower as plain TEXT (app populates) vs SQLite GENERATED. [DEFAULT: plain TEXT]
--   6. All booleans normalized to INTEGER 0/1. [DEFAULT: 0/1]
--   7. messaging_entities kept distinct from case_entities (extraction layer). [DEFAULT: separate]
--   8. Postgres schema.ts authoritative; MySQL fork deprecated. [DEFAULT: yes]
--   9. Provenance: single TEXT `source_locator` (vs split line columns). [DEFAULT: single TEXT]
--  10. message-schemas.ts placeholder discarded; per-platform extras → raw_data JSON. [DEFAULT: discard]
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- REFERENCE / LEGAL
-- ============================================================
CREATE TABLE mcl_factors (              -- legal reference (FINAL wins)
    id              TEXT PRIMARY KEY,    -- 'A'..'L'
    name            TEXT NOT NULL,
    description     TEXT,
    statutory_text  TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE behavior_categories (
    id                TEXT PRIMARY KEY,  -- 'gaslighting', etc.
    name              TEXT NOT NULL,
    description       TEXT,
    severity_default  TEXT DEFAULT 'medium',
    mcl_factors       TEXT,              -- JSON array e.g. ["F","G","K"]
    keyword_patterns  TEXT,              -- JSON array of regex
    context_required  INTEGER DEFAULT 0,
    created_at        TEXT DEFAULT (datetime('now'))
);

-- App-side detection tuning (renamed to avoid clash with legal mcl_factors)
CREATE TABLE mcl_factor_config (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    factor_letter     TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    description       TEXT NOT NULL,
    keywords          TEXT,             -- JSON
    pattern_categories TEXT,            -- JSON
    is_active         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- MESSAGING (canonical = SMS_TABLES_FINAL.sql)
-- ============================================================
CREATE TABLE messaging_documents (
    id                    TEXT PRIMARY KEY,           -- uuid
    filename              TEXT NOT NULL,
    file_type             TEXT NOT NULL,
    file_hash             TEXT NOT NULL UNIQUE,        -- SHA-256
    file_size             INTEGER NOT NULL,
    storage_path          TEXT NOT NULL,
    storage_provider      TEXT,
    status                TEXT DEFAULT 'pending'
        CHECK (status IN ('pending','processing','completed','failed','verified')),
    processed_at          TEXT,
    processing_duration_ms INTEGER,
    raw_text              TEXT,
    message_count         INTEGER DEFAULT 0,
    page_count            INTEGER,
    source_device         TEXT,
    source_platform       TEXT,
    export_date           TEXT,
    date_range_start      TEXT,
    date_range_end        TEXT,
    acquired_by           TEXT DEFAULT 'Matt Salem',
    acquired_date         TEXT NOT NULL DEFAULT (datetime('now')),
    acquisition_method    TEXT,
    verified_by           TEXT,
    verified_date         TEXT,
    metadata              TEXT DEFAULT '{}',           -- JSON
    source_file           TEXT,
    source_locator        TEXT,
    source_timestamp      TEXT,
    tool_origin           TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now'))
);

CREATE TABLE messaging_conversations (
    id                    TEXT PRIMARY KEY,
    document_id           TEXT REFERENCES messaging_documents(id) ON DELETE SET NULL,
    platform              TEXT NOT NULL,
    platform_id           TEXT,
    platform_name         TEXT,
    participants          TEXT NOT NULL,               -- JSON array
    participant_count     INTEGER NOT NULL,
    primary_participant   TEXT,
    primary_participant_normalized TEXT,
    started_at            TEXT,
    ended_at              TEXT,
    last_message_at       TEXT,
    message_count         INTEGER DEFAULT 0,
    is_group              INTEGER DEFAULT 0,
    group_name            TEXT,
    behavior_summary      TEXT DEFAULT '{}',           -- JSON
    total_words           INTEGER DEFAULT 0,
    avg_message_length    INTEGER,
    is_evidence           INTEGER DEFAULT 0,
    exhibit_number        TEXT,
    relevance_score       REAL,
    source_file           TEXT,
    source_locator        TEXT,
    source_timestamp      TEXT,
    tool_origin           TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now')),
    UNIQUE(platform, platform_id)
);

CREATE TABLE messaging_messages (
    id                    TEXT PRIMARY KEY,
    conversation_id       TEXT NOT NULL REFERENCES messaging_conversations(id) ON DELETE CASCADE,
    document_id           TEXT REFERENCES messaging_documents(id) ON DELETE SET NULL,
    external_id           TEXT,
    serial_number         INTEGER,
    timestamp             TEXT NOT NULL,
    timestamp_precision   TEXT DEFAULT 'exact'
        CHECK (timestamp_precision IN ('exact','minute','hour','day','approximate')),
    timezone              TEXT,
    date_us               TEXT,
    time_12h              TEXT,
    sender                TEXT NOT NULL,
    sender_normalized     TEXT,
    sender_name           TEXT,
    recipient             TEXT,
    recipient_normalized  TEXT,
    content               TEXT,                         -- body (was 'text'/'body' in older iters)
    content_lower         TEXT,                         -- populate in app (PG was GENERATED)
    content_hash          TEXT,                         -- SHA-256
    word_count            INTEGER,
    character_count       INTEGER,
    direction             TEXT NOT NULL CHECK (direction IN ('inbound','outbound','unknown')),
    message_type          TEXT DEFAULT 'text'
        CHECK (message_type IN ('text','mms','voice','video','sticker','reaction','system')),
    status                TEXT,
    is_read               INTEGER,
    read_timestamp        TEXT,
    has_attachments       INTEGER DEFAULT 0,
    attachment_count      INTEGER DEFAULT 0,
    attachment_types      TEXT,                         -- JSON array
    previous_message_id   TEXT,
    next_message_id       TEXT,
    time_since_previous_seconds INTEGER,
    has_behaviors         INTEGER DEFAULT 0,
    behavior_count        INTEGER DEFAULT 0,
    behavior_categories   TEXT,                         -- JSON array
    max_severity          TEXT,
    contains_apology      INTEGER DEFAULT 0,
    contains_blame        INTEGER DEFAULT 0,
    contains_threat       INTEGER DEFAULT 0,
    contains_minimizing   INTEGER DEFAULT 0,
    question_count        INTEGER DEFAULT 0,
    exclamation_count     INTEGER DEFAULT 0,
    caps_ratio            REAL,
    is_evidence           INTEGER DEFAULT 0,
    evidence_item_id      TEXT,
    is_redacted           INTEGER DEFAULT 0,
    redaction_reason      TEXT,
    raw_data              TEXT,                         -- JSON (per-platform extras land here)
    source_file           TEXT,
    source_locator        TEXT,
    source_timestamp      TEXT,
    tool_origin           TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    UNIQUE(conversation_id, external_id)
);
CREATE INDEX idx_msg_conv ON messaging_messages(conversation_id);
CREATE INDEX idx_msg_ts ON messaging_messages(timestamp);
CREATE INDEX idx_msg_sender ON messaging_messages(sender_normalized);
CREATE INDEX idx_msg_hash ON messaging_messages(content_hash);
CREATE INDEX idx_msg_conv_ts ON messaging_messages(conversation_id, timestamp);

CREATE TABLE messaging_attachments (
    id              TEXT PRIMARY KEY,
    message_id      TEXT NOT NULL REFERENCES messaging_messages(id) ON DELETE CASCADE,
    filename        TEXT,
    file_type       TEXT NOT NULL,
    mime_type       TEXT,
    file_hash       TEXT,
    file_size       INTEGER,
    storage_path    TEXT,
    thumbnail_path  TEXT,
    width           INTEGER,
    height          INTEGER,
    duration_seconds INTEGER,
    ocr_text        TEXT,
    transcription   TEXT,
    contains_faces  INTEGER,
    face_count      INTEGER,
    is_screenshot   INTEGER,
    exif_data       TEXT,                               -- JSON
    metadata        TEXT DEFAULT '{}',
    source_file     TEXT, source_locator TEXT, source_timestamp TEXT, tool_origin TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_att_msg ON messaging_attachments(message_id);

CREATE TABLE messaging_behaviors (
    id              TEXT PRIMARY KEY,
    message_id      TEXT NOT NULL REFERENCES messaging_messages(id) ON DELETE CASCADE,
    category        TEXT NOT NULL REFERENCES behavior_categories(id),
    subcategory     TEXT,
    matched_pattern TEXT,
    matched_text    TEXT,
    start_char      INTEGER,
    end_char        INTEGER,
    context_before  TEXT,
    context_after   TEXT,
    confidence      REAL NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    detection_method TEXT NOT NULL,
    rule_name       TEXT,
    model_name      TEXT,
    is_verified     INTEGER DEFAULT 0,
    verified_by     TEXT,
    verified_at     TEXT,
    verification_notes TEXT,
    is_disputed     INTEGER DEFAULT 0,
    mcl_factors     TEXT,                               -- JSON array
    source_file     TEXT, source_locator TEXT, source_timestamp TEXT, tool_origin TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_beh_msg ON messaging_behaviors(message_id);
CREATE INDEX idx_beh_cat ON messaging_behaviors(category);

CREATE TABLE messaging_behavior_patterns (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES messaging_conversations(id) ON DELETE CASCADE,
    pattern_type    TEXT NOT NULL,
    pattern_name    TEXT,
    description     TEXT,
    message_ids     TEXT NOT NULL,                      -- JSON array of message ids
    message_count   INTEGER NOT NULL,
    start_timestamp TEXT NOT NULL,
    end_timestamp   TEXT NOT NULL,
    duration_hours  INTEGER,
    behavior_categories TEXT,                           -- JSON array
    severity_progression TEXT,
    confidence      REAL,
    evidence_summary TEXT,
    is_evidence     INTEGER DEFAULT 0,
    mcl_factors     TEXT,
    source_file     TEXT, source_locator TEXT, source_timestamp TEXT, tool_origin TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE messaging_evidence_items (
    id              TEXT PRIMARY KEY,
    message_id      TEXT REFERENCES messaging_messages(id) ON DELETE SET NULL,
    pattern_id      TEXT REFERENCES messaging_behavior_patterns(id) ON DELETE SET NULL,
    document_id     TEXT REFERENCES messaging_documents(id) ON DELETE SET NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    quote           TEXT,
    context         TEXT,
    evidence_type   TEXT,
    category        TEXT,
    evidence_date   TEXT NOT NULL,
    date_precision  TEXT DEFAULT 'exact',
    mcl_factors     TEXT NOT NULL,                      -- JSON array
    relevance_score REAL,
    strength        TEXT,
    exhibit_number  TEXT,
    is_exhibit      INTEGER DEFAULT 0,
    is_filed        INTEGER DEFAULT 0,
    filed_date      TEXT,
    is_authenticated INTEGER DEFAULT 0,
    authentication_method TEXT,
    chain_of_custody TEXT,
    metadata        TEXT DEFAULT '{}',
    source_file     TEXT, source_locator TEXT, source_timestamp TEXT, tool_origin TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE messaging_factor_citations (
    id              TEXT PRIMARY KEY,
    evidence_id     TEXT NOT NULL REFERENCES messaging_evidence_items(id) ON DELETE CASCADE,
    factor_id       TEXT NOT NULL REFERENCES mcl_factors(id) ON DELETE CASCADE,
    supports_factor INTEGER DEFAULT 1,
    strength        TEXT CHECK (strength IN ('weak','moderate','strong','decisive')),
    explanation     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(evidence_id, factor_id)
);

CREATE TABLE messaging_entities (
    id              TEXT PRIMARY KEY,
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('person','location','organization','phone','email')),
    name            TEXT NOT NULL,
    normalized_name TEXT,
    aliases         TEXT,                               -- JSON array
    phone_numbers   TEXT,                               -- JSON array
    email_addresses TEXT,                               -- JSON array
    address         TEXT,
    latitude        REAL,
    longitude       REAL,
    role            TEXT,
    is_party        INTEGER DEFAULT 0,
    relationship_to_petitioner TEXT,
    relationship_to_respondent TEXT,
    is_flagged      INTEGER DEFAULT 0,
    flag_reason     TEXT,
    metadata        TEXT DEFAULT '{}',
    source_file     TEXT, source_locator TEXT, source_timestamp TEXT, tool_origin TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(entity_type, normalized_name)
);

CREATE TABLE messaging_entity_mentions (
    id              TEXT PRIMARY KEY,
    message_id      TEXT NOT NULL REFERENCES messaging_messages(id) ON DELETE CASCADE,
    entity_id       TEXT NOT NULL REFERENCES messaging_entities(id) ON DELETE CASCADE,
    mention_text    TEXT NOT NULL,
    start_char      INTEGER,
    end_char        INTEGER,
    confidence      REAL,
    extraction_method TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE messaging_timeline_events (
    id              TEXT PRIMARY KEY,
    event_date      TEXT NOT NULL,
    event_date_end  TEXT,
    date_precision  TEXT DEFAULT 'exact',
    title           TEXT NOT NULL,
    description     TEXT,
    event_type      TEXT NOT NULL,
    message_ids     TEXT,                               -- JSON array
    pattern_ids     TEXT,                               -- JSON array
    evidence_ids    TEXT,                               -- JSON array
    location        TEXT,
    latitude        REAL,
    longitude       REAL,
    participants    TEXT,                               -- JSON array
    mcl_factors     TEXT,                               -- JSON array
    is_verified     INTEGER DEFAULT 0,
    is_disputed     INTEGER DEFAULT 0,
    metadata        TEXT DEFAULT '{}',
    source_file     TEXT, source_locator TEXT, source_timestamp TEXT, tool_origin TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- ONTOLOGY (Zep graph → relational)
-- ============================================================
CREATE TABLE case_entities (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    zep_uuid         TEXT,
    entity_type      TEXT NOT NULL CHECK (entity_type IN
                       ('Person','Location','Incident','Statement','Vulnerability')),
    name             TEXT,
    owner            TEXT,
    -- Person
    relationship_type TEXT, connection_to TEXT, gender TEXT, risk_level TEXT,
    role_in_case TEXT, is_replacement_candidate INTEGER,
    -- Location
    category TEXT, safety_status TEXT,
    -- Incident
    event_type TEXT, date_approx TEXT, substances_involved TEXT, context_of_use TEXT,
    is_manufactured INTEGER, strategic_goal TEXT, trigger_person TEXT, mcl_factor TEXT,
    -- Statement
    content_summary TEXT, medium TEXT, topic_cluster TEXT, told_to TEXT,
    inconsistency_flag INTEGER, darvo_stage TEXT, deception_strategy TEXT,
    contradicts_evidence INTEGER,
    -- Vulnerability
    description TEXT,
    attributes       TEXT,                              -- JSON spillover
    message_id       TEXT REFERENCES messaging_messages(id) ON DELETE SET NULL,
    source_file      TEXT, source_locator TEXT, source_timestamp TEXT, tool_origin TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_ce_type ON case_entities(entity_type);

CREATE TABLE case_relations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    relation_type    TEXT NOT NULL CHECK (relation_type IN
                       ('USED_TACTIC','SPREADS_RUMOR','CONTRADICTS','EXPOSED_CHILD',
                        'AFFECTED_ACCESS','TARGETED_WOUND','WAS_AT','MADE_STATEMENT')),
    source_entity_id INTEGER NOT NULL REFERENCES case_entities(id) ON DELETE CASCADE,
    target_entity_id INTEGER NOT NULL REFERENCES case_entities(id) ON DELETE CASCADE,
    tactic_type TEXT, financial_mode TEXT,             -- CoerciveTactic
    intent TEXT, effect_on_listener TEXT,              -- SpreadsRumor
    discrepancy_type TEXT,                             -- Contradicts
    duration TEXT, impact TEXT,                        -- ExposedTo
    action TEXT, gatekeeping_subtype TEXT,             -- Facilitated
    mechanism TEXT, is_microaggression INTEGER,        -- Exploits
    date_approx TEXT, with_whom TEXT, evidence_source TEXT, -- WasAt / MadeStatement
    attributes       TEXT,                              -- JSON spillover
    source_file      TEXT, source_locator TEXT, source_timestamp TEXT, tool_origin TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_cr_type ON case_relations(relation_type);
CREATE INDEX idx_cr_src ON case_relations(source_entity_id);
CREATE INDEX idx_cr_tgt ON case_relations(target_entity_id);

CREATE TABLE darvo_stages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id        INTEGER REFERENCES case_entities(id) ON DELETE CASCADE,  -- the Statement
    message_id       TEXT REFERENCES messaging_messages(id) ON DELETE SET NULL,
    stage            TEXT NOT NULL CHECK (stage IN
                       ('deny','attack','reverse_victim','reverse_offender')),
    deception_strategy TEXT,
    quote            TEXT,
    confidence       REAL,
    source_file      TEXT, source_locator TEXT, source_timestamp TEXT, tool_origin TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE mcl_factor_findings (         -- unifies ontology mcl_factor + citations
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    factor_id        TEXT NOT NULL REFERENCES mcl_factors(id),
    entity_id        INTEGER REFERENCES case_entities(id) ON DELETE CASCADE,
    message_id       TEXT REFERENCES messaging_messages(id) ON DELETE CASCADE,
    evidence_id      TEXT REFERENCES messaging_evidence_items(id) ON DELETE CASCADE,
    behavior_id      TEXT REFERENCES messaging_behaviors(id) ON DELETE CASCADE,
    supports_factor  INTEGER DEFAULT 1,
    strength         TEXT CHECK (strength IN ('weak','moderate','strong','decisive')),
    explanation      TEXT,
    source_file      TEXT, source_locator TEXT, source_timestamp TEXT, tool_origin TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- AGNO RUNTIME (from agno-alpha-schema.sql; embeddings DEFERRED to PG/Milvus)
-- ============================================================
CREATE TABLE agent_run (
    id               TEXT PRIMARY KEY,
    agent_name       TEXT NOT NULL,
    run_type         TEXT NOT NULL CHECK (run_type IN ('platform','builder')),
    status           TEXT NOT NULL CHECK (status IN
                       ('queued','running','awaiting_approval','completed','failed','cancelled')),
    user_prompt      TEXT NOT NULL,
    summarized_plan  TEXT,
    approval_required INTEGER NOT NULL DEFAULT 1,
    started_at       TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at     TEXT,
    error_message    TEXT
);

CREATE TABLE approval_request (
    id               TEXT PRIMARY KEY,
    agent_run_id     TEXT NOT NULL REFERENCES agent_run(id) ON DELETE CASCADE,
    requested_action TEXT NOT NULL,
    requested_by_agent TEXT NOT NULL,
    risk_level       TEXT NOT NULL CHECK (risk_level IN ('low','medium','high','critical')),
    approval_status  TEXT NOT NULL CHECK (approval_status IN
                       ('pending','approved','rejected','expired')),
    requested_at     TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at       TEXT,
    decided_by       TEXT,
    decision_notes   TEXT
);

CREATE TABLE learned_knowledge (        -- embedding VECTOR(1536) DEFERRED
    id               TEXT PRIMARY KEY,
    namespace        TEXT NOT NULL,
    title            TEXT NOT NULL,
    content          TEXT NOT NULL,
    source_agent     TEXT NOT NULL,
    confidence       REAL NOT NULL DEFAULT 0.8,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE transcript_insight (       -- embedding VECTOR(1536) DEFERRED
    id               TEXT PRIMARY KEY,
    transcript_source TEXT NOT NULL,
    source_position  TEXT,
    insight_type     TEXT NOT NULL CHECK (insight_type IN
                       ('decision','code_artifact','goal','blocker','architecture',
                        'next_action','issue_found','learning')),
    title            TEXT NOT NULL,
    content          TEXT NOT NULL,
    confidence       REAL NOT NULL DEFAULT 0.85,
    related_insight_ids TEXT,             -- JSON array (was uuid[])
    extracted_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
