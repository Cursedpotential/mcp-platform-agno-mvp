# Py MCP Server Tools — Complete Documentation

**Server:** dial-py-core (port 8082)
**Transport:** HTTP (FastMCP)
**Tags:** `ai`, `knowledge-graph`, `vector-search`, `identification`, `workflow`
**Status:** 22 built (3 placeholders)

---

## Semantica Tools (6)

### `semantica_extract_entities`
- **Description:** NER extraction from text using spaCy
- **Input:** `text` (text to analyze)
- **Output:** JSON array of entities with type, confidence, position
- **File:** `py-mcp-server/src/server.py` (line ~189)
- **Status:** ✅ Built

### `semantica_build_graph`
- **Description:** Build temporal knowledge graph from extracted entities
- **Input:** `text`, optional `conversation_id`
- **Output:** Graph nodes and relationships
- **File:** `py-mcp-server/src/server.py` (line ~205)
- **Status:** ✅ Built

### `semantica_extract_temporal_facts`
- **Description:** Extract temporal facts (events with timestamps) from text
- **Input:** `text`
- **Output:** Array of temporal facts with dates, events, entities
- **File:** `py-mcp-server/src/server.py` (line ~227)
- **Status:** ✅ Built

### `semantica_detect_conflicts`
- **Description:** Detect contradictions across time periods
- **Input:** `conversation_id`
- **Output:** Array of conflicts with evidence
- **File:** `py-mcp-server/src/server.py` (line ~251)
- **Status:** ✅ Built

### `semantica_generate_embeddings`
- **Description:** Generate 768-dim vector embeddings for text
- **Input:** `text`
- **Output:** Embedding vector
- **File:** `py-mcp-server/src/server.py` (line ~270)
- **Status:** ✅ Built

### `semantica_track_provenance`
- **Description:** W3C PROV-O provenance chain tracking
- **Input:** `source_hash`, `timestamp`, `platform`, `sender`
- **Output:** Provenance record
- **File:** `py-mcp-server/src/server.py` (line ~293)
- **Status:** ✅ Built

---

## Vector Search Tools (3)

### `lancedb_vector_search`
- **Description:** Semantic vector search across LanceDB
- **Input:** `query`, optional `collection`, `limit`
- **Output:** Array of matching vectors with scores
- **Status:** ✅ Built

### `lancedb_upsert`
- **Description:** Upsert vectors with metadata into LanceDB
- **Input:** `collection`, `vectors`, `metadata`
- **Output:** Confirmation with count
- **Status:** ✅ Built

### `lancedb_list_collections`
- **Description:** List all LanceDB collections
- **Input:** None
- **Output:** Array of collection names
- **Status:** ✅ Built

---

## Graph Query Tools (2)

### `neo4j_cypher_query`
- **Description:** Execute arbitrary Cypher queries on Neo4j
- **Input:** `query` (Cypher), optional `params`
- **Output:** Query results
- **Status:** ✅ Built

### `neo4j_get_entity_timeline`
- **Description:** Get entity state evolution over time
- **Input:** `entity_name`
- **Output:** Timeline of entity states
- **Status:** ✅ Built

---

## DPK Identification Tools (5) — NEW

### `dpk_hap_score`
- **Description:** HAP scoring using IBM Granite 38M model (0-1 toxicity)
- **Input:** `text`, optional `mode` (pass1/pass2)
- **Output:** JSON with score, sentence_scores, categories, confidence
- **Model:** ibm-granite/granite-guardian-hap-38m (6.16k tok/sec CPU)
- **File:** `py-mcp-server/src/tools/dpk_tools.py`
- **Skill:** `docs/wiki/skills/nlp/dpk-hap.md`
- **Status:** ✅ Built

### `dpk_pii_redact`
- **Description:** PII detection and redaction using Microsoft Presidio + spaCy
- **Input:** `text`, optional `entities`, `operator`, `score_threshold`
- **Output:** JSON with redacted_text, detected_pii, pii_entity_types, pii_count
- **Entities:** PERSON, EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, LOCATION, DATE_TIME
- **File:** `py-mcp-server/src/tools/dpk_tools.py`
- **Skill:** `docs/wiki/skills/nlp/dpk-pii-redactor.md`
- **Status:** ✅ Built

### `dpk_lang_id`
- **Description:** Language identification using fasttext
- **Input:** `text`
- **Output:** JSON with language (ISO 639-1), confidence
- **Model:** fasttext-lid-176
- **File:** `py-mcp-server/src/tools/dpk_tools.py`
- **Status:** ✅ Built

### `dpk_doc_quality`
- **Description:** Document quality scoring
- **Input:** `text`
- **Output:** JSON with score (0-1), metrics dict
- **File:** `py-mcp-server/src/tools/dpk_tools.py`
- **Status:** ✅ Built

### `dpk_readability`
- **Description:** Readability metrics (Flesch Reading Ease, Flesch-Kincaid Grade)
- **Input:** `text`
- **Output:** JSON with flesch_reading_ease, flesch_kincaid_grade, avg_sentence_length
- **File:** `py-mcp-server/src/tools/dpk_tools.py`
- **Status:** ✅ Built

---

## Voice Fingerprinting Tools (1) — NEW

### `fingerprint_voice`
- **Description:** Voice fingerprinting using Burrows' Delta (faststylometry)
- **Input:** `text`, optional `reference_texts` (JSON array)
- **Output:** JSON with style_features, delta_score, author_probability
- **File:** `py-mcp-server/src/tools/voice_tools.py`
- **Skill:** `docs/wiki/skills/nlp/voice-fingerprinting.md`
- **Status:** ✅ Built

---

## User Detection Tools (3) — PLACEHOLDER

### `user_behavioral_detection`
- **Description:** User's custom behavioral pattern detection
- **Input:** `text`, optional `context`, `mode`
- **Output:** JSON with patterns, severity, confidence
- **File:** `py-mcp-server/src/tools/user_detection.py`
- **Status:** 🔧 Placeholder — needs connection to user's detection system

### `user_darvo_detection`
- **Description:** User's custom DARVO (Deny, Attack, Reverse Victim/Offender) detection
- **Input:** `text`, optional `context`, `mode`
- **Output:** JSON with darvo_score, role_classification, evidence_spans
- **File:** `py-mcp-server/src/tools/user_detection.py`
- **Status:** 🔧 Placeholder — needs custom model (Sprint 3)

### `user_coercive_control`
- **Description:** User's custom coercive control analysis (48-behavior taxonomy)
- **Input:** `text`, optional `context`, `mode`
- **Output:** JSON with behaviors, severity
- **File:** `py-mcp-server/src/tools/user_detection.py`
- **Status:** 🔧 Placeholder — needs custom model (Sprint 3)

---

## Workflow Tools (5) — NEW, Config-Driven

### `workflow_list`
- **Description:** List all workflows and modules from config
- **Input:** None
- **Output:** JSON with workflows and modules
- **Config:** `py-mcp-server/config/workflows.json`
- **File:** `py-mcp-server/src/tools/workflow_tools.py`
- **Status:** ✅ Built

### `workflow_run`
- **Description:** Run a configured workflow on text
- **Input:** `text`, `workflow_name` (default: full_analysis), `mode`
- **Output:** JSON with results from all modules
- **Config:** `py-mcp-server/config/workflows.json`
- **File:** `py-mcp-server/src/tools/workflow_tools.py`
- **Status:** ✅ Built

### `workflow_update_config`
- **Description:** Update workflow config at runtime
- **Input:** `config_json` (JSON with modules/workflows to update)
- **Output:** Updated config summary
- **File:** `py-mcp-server/src/tools/workflow_tools.py`
- **Status:** ✅ Built

### `workflow_add_module`
- **Description:** Add a module to a workflow at runtime
- **Input:** `workflow_name`, `module_id`, optional `position`
- **Output:** Updated workflow
- **File:** `py-mcp-server/src/tools/workflow_tools.py`
- **Status:** ✅ Built

### `workflow_remove_module`
- **Description:** Remove a module from a workflow at runtime
- **Input:** `workflow_name`, `module_id`
- **Output:** Updated workflow
- **File:** `py-mcp-server/src/tools/workflow_tools.py`
- **Status:** ✅ Built

---

## Health Check

### `ping`
- **Description:** Ping the Py MCP server
- **Input:** None
- **Output:** "pong"
- **Status:** ✅ Built

---

## Unwrapped Utilities (Could Be Wrapped)

| Script | Path | Description |
|--------|------|-------------|
| `dataset_loader.py` | utilities/python-tools/ | Load behavioral patterns, MCL factors, ontologies |
| `hurtlex_loader.py` | utilities/python-tools/ | Load HurtLex offensive language dataset |
| `chatgpt_parser.py` | utilities/scripts/ | Parse ChatGPT JSON exports |
| `conversation_splitter.py` | utilities/scripts/ | Split large conversations |
| `conversation_to_docx.py` | utilities/scripts/ | JSONL → DOCX conversion |
| `docx_to_pdf.py` | utilities/scripts/ | DOCX → PDF conversion |
| `markdown_to_pdf.py` | utilities/scripts/ | Markdown → PDF conversion |
| `find_duplicates.py` | utilities/scripts/ | Hash-based duplicate finder |
| `forensic_diff.py` | utilities/scripts/ | Forensic diff analysis |
| `pandoc_converter.py` | utilities/scripts/ | Pandoc wrapper |
| `output_schemas.py` | utilities/scripts/ | Validate JSONL against schemas |
| `chunk_file_tool.py` | utilities/scripts/ | Split files into chunks |
