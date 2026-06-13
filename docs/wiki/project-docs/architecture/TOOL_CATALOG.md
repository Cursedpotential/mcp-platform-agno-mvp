# AI DIAL Stack — MCP Tool Catalog

This document catalogs every tool exposed across all three MCP servers. AI DIAL presents these as a unified flat list to the Chat UI and API consumers.

---

## TS MCP Server (port 8081) — Tags: `parser`, `database`, `ingestion`

### Parser Tools

| Tool | Description | Status | Legacy Source |
|------|-------------|--------|---------------|
| `sms_xml_parser` | Parse SMS/MMS XML exports (streaming, multi-GB) | ✅ Built | `loaders/xml-sms-parser.ts` |
| `facebook_export_parser` | Parse Facebook Messenger JSON/HTML exports (`Facebook JSON` is MVP priority) | ✅ Built | `loaders/facebook-parser.ts` |
| `whatsapp_txt_parser` | Parse WhatsApp .txt chat exports | ✅ Built | `readers/WhatsAppTxtReader.ts` |
| `pdf_parser` | Parse PDF iMessage exports via pdfplumber | ✅ Built | `loaders/pdf-imessage-parser.ts` |
| `format_detector` | Confidence-scored format detection for any file | ⏳ Planned | `ingest/format-detection.ts` |

### Database Tools

| Tool | Description | Status | Legacy Source |
|------|-------------|--------|---------------|
| `duckdb_vault` | DuckDB master clock — SHA-256, UUIDv7, dedup, audit | ✅ Built | `storage/duckdb.ts` |
| `postgres_writer` | Write evidence to unified PostgreSQL | ✅ Built | `drizzle/evidence/schema.ts` |
| `duckdb_query` | Query DuckDB for ingestion logs and audit trail | ⏳ Planned | `storage/duckdb.ts` |
| `postgres_search` | Full-text BM25 search across PostgreSQL evidence | ⏳ Planned | — |

### Admin Tools

| Tool | Description | Status | Legacy Source |
|------|-------------|--------|---------------|
| `admin_list_llm_providers` | List all configured LLM providers with status | ✅ Built | — |
| `admin_upsert_llm_provider` | Add/update an LLM provider (name, endpoint, key) | ✅ Built | — |
| `admin_list_system_prompts` | List all system prompts with versions | ✅ Built | — |
| `admin_upsert_system_prompt` | Add/update a system prompt | ✅ Built | — |

### Review Queue Tools (HITL)

| Tool | Description | Status | Legacy Source |
|------|-------------|--------|---------------|
| `review_list_pending` | List items awaiting human review | ✅ Built | `entity_match_candidates` |
| `review_approve` | Approve an item and commit to production | ✅ Built | `entity_match_candidates` |
| `review_reject` | Reject an item with reason | ✅ Built | `entity_match_candidates` |
| `review_submit` | Submit low-confidence AI result for human review | ✅ Built | `entity_match_candidates` |

---

## Py MCP Server (port 8082) — Tags: `ai`, `knowledge-graph`, `vector-search`

### Semantica Tools

| Tool | Description | Status | Legacy Source |
|------|-------------|--------|---------------|
| `semantica_extract_entities` | NER extraction from text | ✅ Built | `memory_service.py` |
| `semantica_build_graph` | Build temporal knowledge graph from entities | ✅ Built | `memory_service.py` |
| `semantica_extract_temporal_facts` | Extract temporal facts from text | ✅ Built | `memory_service.py` |
| `semantica_detect_conflicts` | Detect contradictions across time | ✅ Built | `memory_service.py` |
| `semantica_generate_embeddings` | Generate 768-dim vector embeddings | ✅ Built | `memory_service.py` |
| `semantica_track_provenance` | W3C PROV-O provenance chain tracking | ✅ Built | `memory_service.py` |

### Vector Search Tools

| Tool | Description | Status | Legacy Source |
|------|-------------|--------|---------------|
| `lancedb_vector_search` | Semantic vector search across LanceDB | ✅ Built | `storage/lancedb.ts` |
| `lancedb_upsert` | Upsert vectors with metadata into LanceDB | ✅ Built | `storage/lancedb.ts` |
| `lancedb_list_collections` | List all LanceDB collections | ✅ Built | — |

### Graph Query Tools

| Tool | Description | Status | Legacy Source |
|------|-------------|--------|---------------|
| `neo4j_cypher_query` | Execute arbitrary Cypher queries on Neo4j | ✅ Built | `storage/neo4j/` |
| `neo4j_get_entity_timeline` | Get entity state evolution over time | ✅ Built | `storage/neo4j/` |

### DPK Identification Tools (NEW)

| Tool | Description | Status | Source |
|------|-------------|--------|--------|
| `dpk_hap_score` | HAP scoring using IBM Granite 38M model (0-1 toxicity) | ✅ Built | `tools/dpk_tools.py` |
| `dpk_pii_redact` | PII detection and redaction using Microsoft Presidio + spaCy | ✅ Built | `tools/dpk_tools.py` |
| `dpk_lang_id` | Language identification using fasttext (ISO 639-1) | ✅ Built | `tools/dpk_tools.py` |
| `dpk_doc_quality` | Document quality scoring (structure, length, readability) | ✅ Built | `tools/dpk_tools.py` |
| `dpk_readability` | Readability metrics (Flesch Reading Ease, Flesch-Kincaid Grade) | ✅ Built | `tools/dpk_tools.py` |

### Voice Fingerprinting Tools (NEW)

| Tool | Description | Status | Source |
|------|-------------|--------|--------|
| `fingerprint_voice` | Voice fingerprinting using Burrows' Delta (faststylometry) | ✅ Built | `tools/voice_tools.py` |

### User Detection Tools (NEW — Placeholder)

| Tool | Description | Status | Source |
|------|-------------|--------|--------|
| `user_behavioral_detection` | User's custom behavioral pattern detection | 🔧 Placeholder | `tools/user_detection.py` |
| `user_darvo_detection` | User's custom DARVO detection | 🔧 Placeholder | `tools/user_detection.py` |
| `user_coercive_control` | User's custom coercive control analysis | 🔧 Placeholder | `tools/user_detection.py` |

### Workflow Tools (NEW — Config-Driven)

| Tool | Description | Status | Source |
|------|-------------|--------|--------|
| `workflow_list` | List all workflows and modules from config | ✅ Built | `tools/workflow_tools.py` |
| `workflow_run` | Run a configured workflow on text | ✅ Built | `tools/workflow_tools.py` |
| `workflow_update_config` | Update workflow config at runtime | ✅ Built | `tools/workflow_tools.py` |
| `workflow_add_module` | Add a module to a workflow at runtime | ✅ Built | `tools/workflow_tools.py` |
| `workflow_remove_module` | Remove a module from a workflow at runtime | ✅ Built | `tools/workflow_tools.py` |

**Workflow Config:** `mcp-servers/py-mcp-server/config/workflows.json` — edit to add/remove/reorder modules

---

## JS MCP Server (port 8083) — Tags: `legacy`, `document-processing`

### Document Processing Tools

| Tool | Description | Status | Legacy Source |
|------|-------------|--------|---------------|
| `docling_convert` | Convert documents via Docling API | ⏳ Planned | — |
| `pandoc_convert` | Convert between document formats via Pandoc | ⏳ Planned | — |
| `chatgpt_json_parser` | Parse ChatGPT conversation exports | ⏳ Planned | `Evidence_Analysis/Scripts/chatgpt_parser.py` |
| `google_timeline_parser` | Parse Google Timeline location data | ⏳ Planned | `Evidence_Analysis/Scripts/parser.py` |

---

## Planned Tools (Phase D–F)

### Enrichment Tools

| Tool | Description | Phase |
|------|-------------|-------|
| `pass1_blind_classifier` | Blind NLP classification (24hr context window) | Phase D |
| `embedding_generator` | Generate + store 768-dim embeddings in LanceDB | Phase D |
| `pass2_hindsight_analyzer` | Longitudinal pattern analysis | Phase F |
| `contradiction_detector` | Compare Pass 1 vs Pass 2 for contradictions | Phase F |

### Forensics Tools

| Tool | Description | Phase |
|------|-------------|-------|
| `gaslighting_detector` | Detect gaslighting via sentiment drift analysis | Phase F |
| `coercive_control_analyzer` | Detect coercive control patterns | Phase F |
| `timeline_generator` | Generate chronological event timeline | Phase F |
| `legal_evidence_packager` | Prepare court-submission evidence package | Phase F |
| `severity_scorer` | Score overall severity of behavioral patterns | Phase F |

### Content Analysis Tools

| Tool | Description | Phase |
|------|-------------|-------|
| `sentiment_analyzer` | Analyze emotional sentiment | Phase D |
| `toxicity_detector` | Detect toxic/harmful language | Phase D |
| `manipulation_detector` | Detect manipulation tactics | Phase F |
| `entity_extractor` | Extract named entities from text | Phase D |
| `pii_detector` | Detect personally identifiable information | Phase D |
| `pii_redactor` | Redact PII from text | Phase D |

### OCR Tools

| Tool | Description | Phase |
|------|-------------|-------|
| `ocr_extract_text` | Extract text from images | Phase D |
| `ocr_extract_from_pdf` | Extract text from scanned PDFs | Phase D |
| `ocr_detect_handwriting` | Detect and extract handwritten text | Phase D |

---

## Standard Response Format

All tools return:

```json
{
  "success": true,
  "data": { ... },
  "metadata": { "processing_time_ms": 1234, "tool_id": "sms_xml_parser" },
  "warnings": [],
  "errors": []
}
```

---

**Last Updated:** March 12, 2026
**Total Tools:** 22 built, 22 planned
