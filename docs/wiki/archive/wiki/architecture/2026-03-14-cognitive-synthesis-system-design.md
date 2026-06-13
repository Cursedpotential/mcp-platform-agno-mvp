# Identification & Analysis Tools — Design Document

**Date:** 2026-03-14
**Status:** FOCUSED SCOPE — Awaiting user review
**Author:** brainstorm@opencode
**Process:** Spec-Driven Development (see `docs/SPEC_DRIVEN_DEVELOPMENT.md`)

---

## Scope

**This plan covers ONLY the identification and analysis tools** — the tools that detect behaviors, abuse language, patterns, and anomalies in conversations, chats, emails, and other evidence.

**NOT in scope (handled by other agents):**
- Ingestion and parsing (SMS, Facebook, iMessage, WhatsApp, etc.)
- Data merge tools (Splink, Dedupe, etc.)
- DPK/data-prep-toolkit installation and configuration

**Where these tools sit in the workflow:**
```
[Parsers] → [DuckDB] → [PostgreSQL] → [IDENTIFICATION TOOLS] → [Semantica] → [Neo4j]
                                                          ↓
                                              [IDENTIFICATION TOOLS] ← (hindsight/meta analysis)
```

**Key insight from user:** These tools get used at MULTIPLE points:
1. During initial ingestion (Pass 1 — blind classification)
2. During hindsight/meta analysis (Pass 2 — full context)
3. During ad-hoc analysis (anytime an analyst needs them)

---

## Architectural Principles (Confirmed)

1. **Everything is a tool or module** — swap in/out freely
2. **Bidirectional data flow** — any direction, any frontend
3. **DIAL is optional orchestrator** — minimal, flexible, can be called as a tool
4. **Multi-server** — tools across TS (8081), Py (8082), JS (8083)
5. **Mandatory auditing** — SHA-256, UUIDv7, chain of custody via hooks (no bypass)
6. **MCP gateway/proxy** — single endpoint, lazy/dynamic loading

---

## Identification Tools — Complete Inventory

### Tier 1: DPK Pre-Processing (IBM Data Prep Kit)
These run FIRST on raw text, before any custom detection:

| Tool | Model/Library | Server | Hardware | Status |
|------|--------------|--------|----------|--------|
| `dpk_hap_score` | `ibm-granite/granite-guardian-hap-38m` | Py MCP | CPU, 6.16k tok/sec | Off-shelf |
| `dpk_pii_redact` | Microsoft Presidio + Flair NER | Py MCP | CPU | Off-shelf |
| `dpk_lang_id` | fasttext | Py MCP | CPU | Off-shelf |
| `dpk_doc_quality` | Custom scoring | Py MCP | CPU | Off-shelf |
| `dpk_doc_chunk` | Configurable | Py MCP | CPU | Off-shelf |
| `dpk_readability` | Standard metrics | Py MCP | CPU | Off-shelf |

### Tier 2: User's Custom Detection System
The user's own detection system — primary behavioral detection:

| Tool | Description | Server | Status |
|------|-------------|--------|--------|
| `user_behavioral_detection` | User's custom behavioral pattern detection | Py MCP | User's system |
| `user_darvo_detection` | User's custom DARVO detection | Py MCP | User's system |
| `user_coercive_control` | User's custom coercive control analysis | Py MCP | User's system |

**IMPORTANT:** DPK feeds clean data INTO user's system. User's system is the primary detector.

### Tier 3: Voice & Style Fingerprinting

| Tool | Model/Library | Server | Hardware | Status |
|------|--------------|--------|----------|--------|
| `fingerprint_voice` | faststylometry (Burrows' Delta) | TS MCP | CPU | Off-shelf |
| `fingerprint_voice_audio` | Resemblyzer (256-dim embeddings) | TS MCP | CPU | TODO |

### Tier 4: Semantica NLP (Already Built)

| Tool | Description | Server | Status |
|------|-------------|--------|--------|
| `semantica_extract_entities` | NER extraction | Py MCP | Built |
| `semantica_build_graph` | Relation extraction | Py MCP | Built |
| `semantica_extract_temporal_facts` | Event extraction | Py MCP | Built |
| `semantica_detect_conflicts` | Contradiction detection | Py MCP | Built |
| `semantica_generate_embeddings` | Vector generation | Py MCP | Built |
| `semantica_track_provenance` | PROV-O tracking | Py MCP | Built |

### Tier 5: Existing Behavioral Analysis (Training Material)
These contain **case-specific ontology** — use as training/seed material:

| Source | Contains | Location |
|--------|----------|----------|
| `manipulation-patterns/` skill | DARVO, gaslighting, coercive control patterns | `.config/opencode/skills/` |
| `@custody-support` agent | NPD/BPD patterns, BIFF communication | `.claude/agents/` |
| `@forensic` agent | Evidence pipeline, forensic analysis | `.claude/agents/` |
| `LGL-forensic-analyst.md` prompt | Multi-stage evidence pipeline | `.config/opencode/prompts/` |
| `LGL-custody-support.md` prompt | Trauma-informed support | `.config/opencode/prompts/` |
| MCL Factor Mapper | 303+ behavioral patterns with MCL mappings | `semantica_pipeline.py` |

---

## Tool Interface Standard (Swappable Modules)

Every identification tool follows this interface:

```python
# Standard interface for all identification tools
@mcp.tool()
def tool_name(
    text: str,                    # Input text to analyze
    context: Optional[str] = None,  # Optional context (prior analysis, metadata)
    mode: str = "pass1",          # "pass1" (blind) or "pass2" (hindsight)
) -> str:
    """
    Tool description.
    
    Args:
        text: Text to analyze
        context: Optional context from prior analysis
        mode: "pass1" for blind classification, "pass2" for hindsight analysis
    
    Returns:
        JSON with:
        - score: float (0-1)
        - categories: list[str]
        - confidence: float (0-1)
        - evidence: list[dict] (text spans supporting the finding)
        - metadata: dict (model info, timestamp, etc.)
    """
    # MANDATORY: Audit hook fires automatically
    # Implementation here
    return json.dumps(result)
```

This standard interface means:
- Any tool can be swapped for an alternative implementation
- Workflows compose tools without depending on specific implementations
- New tools just need to implement the interface

---

## Database Schema Design

### What We Extract (Per Message)

Each identification tool produces different outputs. Here's what we'll end up with:

| Tool | Extracts | Data Type |
|------|----------|-----------|
| `dpk_hap_score` | Toxicity score (0-1), per-sentence scores | float, float[] |
| `dpk_pii_redact` | PII entities found, redacted text, entity types | jsonb, text, text[] |
| `dpk_lang_id` | Language code, confidence | text, float |
| `dpk_doc_quality` | Quality score, metrics (length, structure, etc.) | float, jsonb |
| `dpk_readability` | Flesch-Kincaid, grade level, reading ease | jsonb |
| `fingerprint_voice` | Style features, Burrows' Delta score, author probability | jsonb, float, float |
| `user_behavioral_detection` | Pattern matches, severity, confidence | jsonb, int, float |
| `user_darvo_detection` | DARVO score, role classification, evidence spans | float, text, jsonb |
| `user_coercive_control` | Behaviors detected, frequency, severity | jsonb, jsonb, int |
| `semantica_extract_entities` | Named entities (people, places, dates, orgs) | jsonb |
| `semantica_build_graph` | Relationships between entities | jsonb |

### New Tables

```sql
-- =============================================================================
-- EVIDENCE SCHEMA: Message Analysis Results
-- =============================================================================
-- Stores per-message results from all identification tools.
-- Each message can have multiple analysis rows (different tools, different passes).

CREATE TABLE IF NOT EXISTS evidence.message_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    message_id UUID NOT NULL REFERENCES evidence.messages(id) ON DELETE CASCADE,
    
    -- Analysis metadata
    tool_name VARCHAR(100) NOT NULL,        -- e.g., 'dpk_hap', 'user_darvo', 'fingerprint_voice'
    tool_version VARCHAR(50),               -- Model version for reproducibility
    analysis_pass VARCHAR(20) NOT NULL      -- 'pass1' (blind), 'pass2' (hindsight), 'ad_hoc'
        CHECK (analysis_pass IN ('pass1', 'pass2', 'ad_hoc')),
    analysis_run_id UUID,                   -- Groups analyses from same run
    
    -- DPK HAP results
    hap_score NUMERIC(5,4),                 -- 0-1 toxicity score
    hap_sentence_scores JSONB,              -- Per-sentence scores array
    
    -- PII detection results
    pii_detected JSONB,                     -- [{type, text, start, end, confidence}]
    pii_redacted_text TEXT,                 -- Text with PII replaced
    pii_entity_types TEXT[],                -- ['PERSON', 'EMAIL_ADDRESS', ...]
    
    -- Language & quality
    detected_language VARCHAR(10),          -- ISO language code
    language_confidence NUMERIC(5,4),
    doc_quality_score NUMERIC(5,4),
    readability_metrics JSONB,              -- {flesch_kincaid, grade_level, reading_ease, ...}
    
    -- Voice fingerprinting
    voice_style_features JSONB,             -- {avg_word_length, vocab_richness, punctuation_heatmap, ...}
    voice_delta_score NUMERIC(5,4),         -- Burrows' Delta distance
    voice_author_probability NUMERIC(5,4),  -- Probability of same author
    
    -- Behavioral detection (user's custom system)
    behavioral_patterns JSONB,              -- [{pattern_id, name, confidence, evidence_spans}]
    behavioral_severity INT,                -- 1-10 overall severity
    behavioral_confidence NUMERIC(5,4),
    
    -- DARVO detection
    darvo_score NUMERIC(5,4),               -- 0-1 DARVO likelihood
    darvo_role_classification VARCHAR(50),  -- 'victim', 'offender', 'neutral'
    darvo_evidence_spans JSONB,             -- [{text, start, end, type}]
    
    -- Coercive control
    coercive_behaviors JSONB,               -- [{behavior, frequency, severity, evidence}]
    coercive_severity INT,                  -- 1-10
    
    -- Semantica NER results (cached here for quick access)
    extracted_entities JSONB,               -- [{text, type, confidence, start, end}]
    extracted_relations JSONB,              -- [{subject, predicate, object, confidence}]
    
    -- Generic fallback (for tools not covered above)
    raw_results JSONB,                      -- Full tool output as JSON
    
    -- Audit fields (MANDATORY)
    source_hash VARCHAR(64) NOT NULL,       -- SHA-256 of input text
    processing_time_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ma_message ON evidence.message_analysis(message_id);
CREATE INDEX IF NOT EXISTS idx_ma_tool ON evidence.message_analysis(tool_name);
CREATE INDEX IF NOT EXISTS idx_ma_pass ON evidence.message_analysis(analysis_pass);
CREATE INDEX IF NOT EXISTS idx_ma_run ON evidence.message_analysis(analysis_run_id);
CREATE INDEX IF NOT EXISTS idx_ma_hap ON evidence.message_analysis(hap_score) WHERE hap_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ma_darvo ON evidence.message_analysis(darvo_score) WHERE darvo_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ma_severity ON evidence.message_analysis(behavioral_severity) WHERE behavioral_severity IS NOT NULL;

-- =============================================================================
-- EVIDENCE SCHEMA: Analysis Runs
-- =============================================================================
-- Tracks each analysis run (batch of messages analyzed together)

CREATE TABLE IF NOT EXISTS evidence.analysis_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    run_type VARCHAR(50) NOT NULL,          -- 'ingestion_pass1', 'hindsight_pass2', 'ad_hoc'
    triggered_by VARCHAR(100),              -- 'ingestion_agent', 'analyst', 'scheduled'
    tools_used TEXT[] NOT NULL,             -- ['dpk_hap', 'user_darvo', ...]
    message_count INT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    metadata JSONB
);

-- =============================================================================
-- EVIDENCE SCHEMA: Behavioral Findings
-- =============================================================================
-- High-level findings that span multiple messages (patterns, trends)

CREATE TABLE IF NOT EXISTS evidence.behavioral_findings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    
    -- Finding details
    finding_type VARCHAR(100) NOT NULL,     -- 'darvo_pattern', 'coercive_control', 'gaslighting', etc.
    severity INT NOT NULL CHECK (severity BETWEEN 1 AND 10),
    confidence NUMERIC(5,4) NOT NULL,
    
    -- Evidence
    message_ids UUID[] NOT NULL,            -- Messages supporting this finding
    evidence_spans JSONB,                   -- [{message_id, text, start, end}]
    pattern_description TEXT,
    
    -- MCL mapping
    mcl_factors VARCHAR(50)[],              -- ['(b)', '(c)', '(d)'] — which factors apply
    
    -- Timeline
    first_occurrence TIMESTAMPTZ,
    last_occurrence TIMESTAMPTZ,
    frequency_count INT DEFAULT 1,
    
    -- Review status
    review_status VARCHAR(20) DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'reviewed', 'confirmed', 'dismissed')),
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    
    -- Audit
    source_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bf_type ON evidence.behavioral_findings(finding_type);
CREATE INDEX IF NOT EXISTS idx_bf_severity ON evidence.behavioral_findings(severity);
CREATE INDEX IF NOT EXISTS idx_bf_review ON evidence.behavioral_findings(review_status);
```

### Schema Design Decisions

1. **`message_analysis` is the central table** — one row per tool per message per pass
2. **Tool-specific columns** for common tools (HAP, PII, DARVO, voice) — fast queries
3. **`raw_results` JSONB fallback** — for new tools not yet schema'd
4. **`behavioral_findings` for cross-message patterns** — findings that span multiple messages
5. **`analysis_runs` for batch tracking** — groups analyses from same run
6. **All tables link to `evidence.messages`** via `message_id` foreign key
7. **MCL factor mapping** in `behavioral_findings` — links to existing `app.mcl_factors`
8. **Review status** in `behavioral_findings` — feeds into existing `app.review_queue` for HITL

### What We End Up With

After running all identification tools on a message, the `message_analysis` table contains:
- **Toxicity score** (HAP) — is this message abusive?
- **PII entities** — what personal info needs redaction?
- **Language** — what language is this message in?
- **Quality/readability** — is this a substantive message or noise?
- **Voice fingerprint** — who wrote this? (authorial style analysis)
- **Behavioral patterns** — does this match known manipulation patterns?
- **DARVO score** — is this Deny/Attack/Reverse Victim-Offender?
- **Coercive control** — what coercive behaviors are present?
- **Entities** — who/what/where/when mentioned?
- **Relationships** — how do entities relate?

This data then feeds into:
- **Neo4j** (via Semantica) — temporal knowledge graph with behavioral annotations
- **LanceDB** — vector embeddings for semantic search
- **WunderGraph Cosmo** — federated queries across all tiers
- **React dashboard** — HITL review of findings

---

## Implementation Plan

### Phase 1: DPK Tools (Py MCP Server)

Install DPK and wrap transforms as MCP tools:

```python
# py-mcp-server/src/tools/dpk_tools.py

from dpk_hap import HAP
from dpk_pii_redactor import PIIRedactor
from dpk_lang_id import LangId
from dpk_doc_quality import DocQuality
from dpk_doc_chunk import DocChunk
from dpk_readability import Readability

@mcp.tool()
def dpk_hap_score(text: str, mode: str = "pass1") -> str:
    """HAP scoring using IBM Granite 38M model."""
    ...

@mcp.tool()
def dpk_pii_redact(text: str) -> str:
    """PII detection and redaction using Presidio + Flair."""
    ...

@mcp.tool()
def dpk_lang_id(text: str) -> str:
    """Language identification using fasttext."""
    ...

@mcp.tool()
def dpk_doc_quality(text: str) -> str:
    """Document quality scoring."""
    ...

@mcp.tool()
def dpk_doc_chunk(text: str, chunk_size: int = 512) -> str:
    """Document chunking for RAG."""
    ...

@mcp.tool()
def dpk_readability(text: str) -> str:
    """Readability metrics."""
    ...
```

### Phase 2: Voice Fingerprinting (TS MCP Server)

```typescript
// ts-mcp-server/src/tools/VoiceFingerprint.ts

import { stylometric } from 'faststylometry';

export async function fingerprintVoice(text: string, referenceTexts?: string[]) {
  // Burrows' Delta algorithm for authorial voice analysis
  // Returns: author_probability, style_features, delta_score
}
```

### Phase 3: Connect User's Custom Detection System

User's custom detection system gets wrapped as MCP tools:

```python
# py-mcp-server/src/tools/user_detection.py

@mcp.tool()
def user_behavioral_detection(text: str, context: Optional[str] = None) -> str:
    """User's custom behavioral pattern detection."""
    # Calls user's detection system
    ...

@mcp.tool()
def user_darvo_detection(text: str, context: Optional[str] = None) -> str:
    """User's custom DARVO detection."""
    ...

@mcp.tool()
def user_coercive_control(text: str, context: Optional[str] = None) -> str:
    """User's custom coercive control analysis."""
    ...
```

### Phase 4: Workflow Tools (Composite Tools)

Workflow tools that compose atomic tools:

```python
# py-mcp-server/src/tools/workflows.py

@mcp.tool()
def analyze_text_full(text: str, mode: str = "pass1") -> str:
    """
    Full text analysis workflow — runs all identification tools.
    This is ALSO a tool (composite tool that calls atomic tools).
    """
    # DPK pre-processing
    lang = dpk_lang_id(text)
    hap = dpk_hap_score(text, mode)
    quality = dpk_doc_quality(text)
    
    # PII handling
    pii = dpk_pii_redact(text)
    clean_text = pii["redacted_text"]
    
    # User's custom detection
    behavioral = user_behavioral_detection(clean_text, mode)
    darvo = user_darvo_detection(clean_text, mode)
    coercive = user_coercive_control(clean_text, mode)
    
    # Voice fingerprinting
    voice = fingerprint_voice(clean_text)
    
    # Semantica NLP
    entities = semantica_extract_entities(clean_text)
    
    # MANDATORY audit hook fires automatically
    
    return json.dumps({
        "lang": lang, "hap": hap, "quality": quality,
        "pii": pii, "behavioral": behavioral, "darvo": darvo,
        "coercive": coercive, "voice": voice, "entities": entities,
    })
```

---

## Skill Documents (Rule 5)

Create skill documents for each tool category:

1. `docs/wiki/skills/nlp/dpk-hap.md` — HAP scoring with IBM Granite
2. `docs/wiki/skills/nlp/dpk-pii-redactor.md` — PII detection and redaction
3. `docs/wiki/skills/nlp/voice-fingerprinting.md` — Voice/style fingerprinting
4. `docs/wiki/skills/nlp/behavioral-detection.md` — User's custom detection system
5. `docs/wiki/skills/nlp/identification-workflows.md` — Composite workflow tools

---

## Tool Catalog Updates

Add to `docs/TOOL_CATALOG.md`:

### Py MCP Server — Identification Tools

| Tool | Description | Status | Tier |
|------|-------------|--------|------|
| `dpk_hap_score` | HAP scoring (IBM Granite 38M) | To build | DPK |
| `dpk_pii_redact` | PII detection and redaction | To build | DPK |
| `dpk_lang_id` | Language identification | To build | DPK |
| `dpk_doc_quality` | Document quality scoring | To build | DPK |
| `dpk_doc_chunk` | Document chunking for RAG | To build | DPK |
| `dpk_readability` | Readability metrics | To build | DPK |
| `user_behavioral_detection` | Custom behavioral patterns | To build | Custom |
| `user_darvo_detection` | Custom DARVO detection | To build | Custom |
| `user_coercive_control` | Custom coercive control | To build | Custom |
| `analyze_text_full` | Full analysis workflow | To build | Workflow |

### TS MCP Server — Identification Tools

| Tool | Description | Status | Tier |
|------|-------------|--------|------|
| `fingerprint_voice` | Voice fingerprinting (Burrows' Delta) | To build | Style |

---

## Next Steps

1. **User review** of this focused plan
2. **Create spec files** in `docs/specs/` for each tool category
3. **Begin Phase 1** — install DPK, create dpk_tools.py
4. **Begin Phase 2** — create voice fingerprinting in TS MCP
5. **Begin Phase 3** — connect user's custom detection system
6. **Begin Phase 4** — create workflow composite tools

---

## TODO: Microsoft Libraries (For Future Investigation)

| Library | URL | Purpose | Priority |
|---------|-----|---------|----------|
| **Microsoft Recognizers-Text** | github.com/microsoft/Recognizers-Text | NER for everything but names (numbers, dates, phone numbers, URLs, emails, etc.) | HIGH |
| **Microsoft Component Detection** | github.com/microsoft/component-detection | Detect software components/dependencies in code (off-topic but useful for forensics) | LOW |
| **Microsoft MCP Docs** | github.com/microsoftdocs/mcp | Microsoft MCP documentation and patterns | MEDIUM |

**Recognizers-Text** is particularly interesting — it handles structured entity recognition (numbers, dates, phone numbers, URLs, emails, IP addresses, etc.) which complements spaCy's name/entity recognition. Could replace or supplement regex patterns in PII detection.

---

## Naming Convention (To Establish)

**Pattern:** `{source}_{action}_{target}`

**Examples:**
- `dpk_hap_score` — DPK source, score action, HAP target
- `dpk_pii_redact` — DPK source, redact action, PII target
- `user_behavioral_detect` — User source, detect action, behavioral target
- `semantica_entity_extract` — Semantica source, extract action, entity target
- `voice_fingerprint_generate` — Voice source, generate action, fingerprint target

**Rules:**
- Lowercase with underscores
- Source prefix identifies which system/library
- Action verb describes what it does
- Target noun describes what it operates on
- Max 3 words (source_action_target)

---

## TODO: UI/Frontend — Workflow Settings Page

**For:** UI/Frontend agent (React + CopilotKit)
**Backend:** Ready — all MCP tools exist

### Requirements
1. **View workflows** — Show all workflows with modules and enabled/disabled status
2. **Toggle modules** — Enable/disable individual modules within a workflow
3. **Add/remove modules** — Drag modules between available and active lists
4. **Reorder modules** — Drag-and-drop to change execution order
5. **Create workflows** — Form to create new custom workflows from available modules
6. **Edit module config** — Edit per-module settings (thresholds, operators, modes)
7. **View run history** — Show past workflow runs from `evidence.analysis_runs`

### API (via MCP tools)
- `workflow_list()` — GET all workflows and modules
- `workflow_update_config(json)` — PUT update config at runtime
- `workflow_add_module(workflow, module_id, position)` — POST add module
- `workflow_remove_module(workflow, module_id)` — DELETE remove module
