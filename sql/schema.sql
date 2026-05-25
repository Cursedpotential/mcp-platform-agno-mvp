-- Agno MCP Platform MVP Schema
-- Requires: PostgreSQL + pgvector extension

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- -- Agent Run Tracking ---------------------------------------
CREATE TABLE IF NOT EXISTS agent_run (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name TEXT NOT NULL,
    run_type TEXT NOT NULL CHECK (run_type IN ('platform', 'builder')),
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'awaiting_approval', 'completed', 'failed', 'cancelled')),
    user_prompt TEXT NOT NULL,
    summarized_plan TEXT,
    approval_required BOOLEAN NOT NULL DEFAULT TRUE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

-- -- Approval Request Checkpoints -----------------------------
CREATE TABLE IF NOT EXISTS approval_request (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_run_id UUID NOT NULL REFERENCES agent_run(id) ON DELETE CASCADE,
    requested_action TEXT NOT NULL,
    requested_by_agent TEXT NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    approval_status TEXT NOT NULL CHECK (approval_status IN ('pending', 'approved', 'rejected', 'expired')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ,
    decided_by TEXT,
    decision_notes TEXT
);

-- -- Learned Knowledge ----------------------------------------
CREATE TABLE IF NOT EXISTS learned_knowledge (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    namespace TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_agent TEXT NOT NULL,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0.8000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    embedding VECTOR(1536)
);

-- -- Transcript Insights --------------------------------------
-- Raw structured extractions from AI chat transcripts.
-- Separate from learned_knowledge: these are raw extractions, not synthesized patterns.
CREATE TABLE IF NOT EXISTS transcript_insight (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transcript_source TEXT NOT NULL,
    source_position TEXT,  -- e.g., "lines 450-520" or "chunk 7 of 23"
    insight_type TEXT NOT NULL CHECK (insight_type IN (
        'decision', 'code_artifact', 'goal', 'blocker',
        'architecture', 'next_action', 'issue_found', 'learning'
    )),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0.8500,
    related_insight_ids UUID[],  -- Links to related insights (same session or topic)
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    embedding VECTOR(1536)
);

-- -- Indexes --------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_agent_run_status ON agent_run(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_approval_request_status ON approval_request(approval_status, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_learned_knowledge_namespace ON learned_knowledge(namespace, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transcript_insight_type ON transcript_insight(insight_type, extracted_at DESC);
CREATE INDEX IF NOT EXISTS idx_transcript_insight_source ON transcript_insight(transcript_source, extracted_at DESC);
