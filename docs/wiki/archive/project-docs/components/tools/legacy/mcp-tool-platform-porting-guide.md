# MCP_Tool_Platform Legacy Tools — Porting Guide

**Status:** ARCHIVED — READ-ONLY
**Location:** `C:\Users\matts\Projects\TheBigOne\MCP_Tool_Platform\`
**Action:** Port relevant tools to dial-stack Py/TS MCP servers

---

## Ingest System (Should Port)

### BehavioralFlagExtractor
- **Path:** `server/mcp/ingest/extractors/BehavioralFlagExtractor.ts`
- **Purpose:** Extract behavioral pattern flags from text during ingestion
- **Relevance:** HIGH — core behavioral detection, maps to MCL factors
- **Port to:** `py-mcp-server/src/tools/behavioral_tools.py`
- **Dependencies:** spaCy, behavioral patterns DB
- **Notes:** Already integrated with MCL factor mapping

### GlinerExtractor
- **Path:** `server/mcp/ingest/extractors/GlinerExtractor.ts`
- **Purpose:** GLiNER entity extraction (generalized NER)
- **Relevance:** HIGH — complements spaCy NER with zero-shot entity detection
- **Port to:** `py-mcp-server/src/tools/entity_tools.py`
- **Dependencies:** GLiNER model (HuggingFace)
- **Notes:** Zero-shot NER — can detect entity types without training

### RecognizersExtractor
- **Path:** `server/mcp/ingest/extractors/RecognizersExtractor.ts`
- **Purpose:** Microsoft Recognizers-Text pattern recognition (dates, numbers, phones, URLs)
- **Relevance:** HIGH — structured entity recognition
- **Port to:** `py-mcp-server/src/tools/recognizer_tools.py`
- **Dependencies:** Microsoft Recognizers-Text
- **Notes:** Complements spaCy — handles structured patterns spaCy misses

### format-detection.ts
- **Path:** `server/mcp/ingest/format-detection.ts`
- **Purpose:** Confidence-scored file format detection
- **Relevance:** HIGH — needed before parser selection
- **Port to:** `ts-mcp-server/src/tools/FormatDetector.ts`
- **Dependencies:** File type libraries
- **Notes:** Currently planned but not built in TS MCP

### forensicHasher.ts
- **Path:** `server/mcp/ingest/forensicHasher.ts`
- **Purpose:** SHA-256 hashing at first touch for chain of custody
- **Relevance:** CRITICAL — already exists in TS MCP (DuckDbVault)
- **Port to:** Already ported
- **Notes:** Verify feature parity

---

## Forensics Tools (Should Port)

### chain-custody.ts
- **Path:** `server/mcp/forensics/chain-custody.ts`
- **Purpose:** Chain of custody tracking and verification
- **Relevance:** CRITICAL — mandatory auditing
- **Port to:** Already partially in `audit_hooks.py`
- **Notes:** Verify feature parity with existing audit system

### pattern-analyzer.ts
- **Path:** `server/mcp/forensics/pattern-analyzer.ts`
- **Purpose:** Communication pattern analysis
- **Relevance:** HIGH — behavioral pattern detection
- **Port to:** `py-mcp-server/src/tools/pattern_tools.py`
- **Dependencies:** Behavioral patterns DB, Neo4j

### timeline-generator.ts
- **Path:** `server/mcp/forensics/timeline-generator.ts`
- **Purpose:** Generate chronological event timelines
- **Relevance:** HIGH — timeline construction from evidence
- **Port to:** `py-mcp-server/src/tools/timeline_tools.py`
- **Dependencies:** Semantica temporal facts, Neo4j

### behavior-service.ts
- **Path:** `server/mcp/forensics/behavior-service.ts`
- **Purpose:** Behavioral analysis service
- **Relevance:** HIGH — maps to user's custom detection system
- **Port to:** `py-mcp-server/src/tools/behavioral_tools.py`
- **Dependencies:** Behavioral patterns, MCL factors

### identity-service.ts
- **Path:** `server/mcp/forensics/identity-service.ts`
- **Purpose:** Entity identity resolution across sources
- **Relevance:** MEDIUM — entity deduplication
- **Port to:** `py-mcp-server/src/tools/identity_tools.py`
- **Dependencies:** Splink/Dedupe

---

## Analysis Tools (Should Port)

### classifier.ts
- **Path:** `server/mcp/analysis/classifier.ts`
- **Purpose:** Evidence classification
- **Relevance:** MEDIUM — categorization
- **Port to:** `py-mcp-server/src/tools/classifier_tools.py`

### multi-pass-classifier.ts
- **Path:** `server/mcp/analysis/multi-pass-classifier.ts`
- **Purpose:** Multi-pass classification (Pass 1 blind, Pass 2 hindsight)
- **Relevance:** HIGH — core architecture pattern
- **Port to:** `py-mcp-server/src/tools/classifier_tools.py`
- **Notes:** Implements the Pass 1/Pass 2 architecture

### conversation-segmentation.ts
- **Path:** `server/mcp/analysis/conversation-segmentation.ts`
- **Purpose:** Segment conversations into logical units
- **Relevance:** MEDIUM — conversation parsing
- **Port to:** `py-mcp-server/src/tools/segmentation_tools.py`

### priority-screener.ts
- **Path:** `server/mcp/analysis/priority-screener.ts`
- **Purpose:** Priority screening for HITL review
- **Relevance:** MEDIUM — feeds review queue
- **Port to:** `py-mcp-server/src/tools/screening_tools.py`

---

## Python Tools (Should Port)

### get_embedding.py
- **Path:** `server/python-tools/get_embedding.py`
- **Purpose:** Generate embeddings
- **Relevance:** Already exists in Semantica
- **Port to:** Already ported

### pdf_extractor.py
- **Path:** `server/python-tools/pdf_extractor.py`
- **Purpose:** Extract PDF content
- **Relevance:** Already exists via Docling
- **Port to:** Already ported

### topic_detector.py
- **Path:** `server/python-tools/topic_detector.py`
- **Purpose:** Detect topics in text
- **Relevance:** MEDIUM — topic modeling
- **Port to:** `py-mcp-server/src/tools/topic_tools.py`

### nlp_runner.py
- **Path:** `server/python-tools/nlp_runner.py`
- **Purpose:** NLP pipeline runner
- **Relevance:** Already exists in Semantica
- **Port to:** Already ported

### unstructured_parser.py
- **Path:** `server/python-tools/unstructured_parser.py`
- **Purpose:** Parse unstructured data
- **Relevance:** HIGH — handles messy data
- **Port to:** `py-mcp-server/src/tools/unstructured_tools.py`

---

## Data Files (Should Migrate)

### Ontologies
- **mcl_722_23.ttl** — Michigan Best Interest Factors (already in dial-stack)
- **behavioral_patterns.ttl** — Behavioral patterns ontology (already in dial-stack)

### Datasets
- **HurtLex lexicon** — Offensive language dataset
- **Training datasets** — Custom training data
- **Content store** — SHA-256 content-addressable storage

---

## Already Deprecated (Do NOT Port)

- **Graphiti** — Replaced by Semantica
- **LangChain/LangGraph** — Dropped in favor of native MCP
- **Supabase client** — Replaced by self-hosted PostgreSQL
- **Chroma client** — Replaced by LanceDB
- **coordinator.ts** — Replaced by DIAL orchestration

---

## Porting Priority

| Priority | Tool | Reason |
|----------|------|--------|
| 1 | BehavioralFlagExtractor | Core behavioral detection |
| 2 | GlinerExtractor | Zero-shot NER |
| 3 | RecognizersExtractor | Structured entity recognition |
| 4 | format-detection.ts | Parser selection |
| 5 | timeline-generator.ts | Timeline construction |
| 6 | pattern-analyzer.ts | Communication patterns |
| 7 | behavior-service.ts | Behavioral analysis |
| 8 | multi-pass-classifier.ts | Pass 1/Pass 2 architecture |
| 9 | unstructured_parser.ts | Messy data handling |
| 10 | identity-service.ts | Entity resolution |
