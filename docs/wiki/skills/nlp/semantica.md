# Semantica — Skill Reference

## Overview
- **What**: Custom NLP engine for entity/relation extraction, temporal fact detection, conflict identification, and embedding generation. Core semantics processor for forensic-grade knowledge graph construction. Replaces deprecated Graphiti.
- **Version**: Custom (dial-stack integrated)
- **Category**: NLP/Processing
- **Installed In**: Python service `semantica` (MCP server via FastMCP, port 8081)

## Architecture

Semantica is a two-pass enrichment system designed for forensic analysis:
- **Pass 1 (Blind)**: Initial extraction with 24-hour context window, WORM immutable storage (DuckDB)
- **Pass 2 (Hindsight)**: Longitudinal analysis detecting patterns, conflicts, and narrative shifts across entire timeline

### Service Topology
Semantica exposes 11 MCP tools via FastMCP stdio transport:

**NLP Pipeline (5 tools)**:
1. `ping` — Health check
2. `semantica_extract_entities` — NER with confidence scores
3. `semantica_build_graph` — Relation extraction and graph construction
4. `semantica_extract_temporal_facts` — Date/time-aware fact identification
5. `semantica_detect_conflicts` — Contradiction detection (key for forensics)

**Data Storage (2 tools)**:
6. `semantica_generate_embeddings` — 768-dim vector generation (Sentence-Transformers)
7. `semantica_track_provenance` — W3C PROV-O compliance tracking

**Database Operations (4 tools)**:
8. `lancedb_vector_search` — Semantic similarity queries
9. `lancedb_upsert` — Vector index updates
10. `lancedb_list_collections` — Collection management
11. `neo4j_cypher_query` — Graph pattern queries
12. `neo4j_get_entity_timeline` — Temporal entity lineage

### Lazy Singleton Services
All services initialized on first use:
- `_get_neo4j()` — Graph database connection
- `_get_lancedb()` — Vector store connection
- `_get_ner()` — spaCy-based Named Entity Recognizer (en_core_web_sm)
- `_get_graph_builder()` — Relation extraction module (transformer-based)
- `_get_temporal_query()` — Temporal fact extractor (regex + date parsing)
- `_get_conflict_detector()` — Contradiction logic engine
- `_get_embedding_generator()` — Sentence-Transformers (768-dim output)
- `_get_provenance_tracker()` — PROV-O document builder

## Pipeline Details

### 1. Named Entity Recognition (NER)
Extracts PERSON, ORG, LOC, PRODUCT, MONEY, DATE, EVENT entities using spaCy ML pipeline.
```python
entities = semantica_extract_entities(text)
# Returns: [
#   {"text": "Alice", "type": "PERSON", "start": 0, "end": 5, "confidence": 0.98},
#   {"text": "Acme Inc", "type": "ORG", "start": 25, "end": 33, "confidence": 0.95}
# ]
```

### 2. Relation Extraction
Identifies semantic relations (WORKS_FOR, OWNS, LOCATED_IN, COMMUNICATES_WITH, etc.) between extracted entities.
```python
relations = semantica_build_graph(entities, text)
# Returns graph with nodes (entities) and edges (relations with confidence scores)
```

### 3. Temporal Fact Extraction
Combines entities + relations + date expressions into time-stamped facts. Handles relative dates ("yesterday"), absolute dates ("2024-03-12"), and implicit timestamps (context-based inference).
```python
facts = semantica_extract_temporal_facts(text, relations, reference_date)
# Returns: [
#   {
#     "entity": "Alice", "relation": "WORKS_FOR", "target": "Acme Inc",
#     "timestamp": "2024-03-12T00:00:00Z", "confidence": 0.87,
#     "date_confidence": 0.65  # Lower if date inferred from context
#   }
# ]
```

### 4. Conflict/Contradiction Detection
**Critical for forensics**: Detects when facts contradict (same entity-relation-target with incompatible timestamps or values).
```python
conflicts = semantica_detect_conflicts(facts_batch)
# Returns: [
#   {
#     "type": "temporal_contradiction",
#     "facts": [fact_a, fact_b],
#     "severity": "HIGH",
#     "description": "Alice stated working at Acme (2024-03) but also at Beta Corp (2024-02-15)",
#     "deception_risk": 0.78
#   }
# ]
```

### 5. Embedding Generation
768-dimensional vectors via Sentence-Transformers (all-MiniLM-L6-v2). Each fact becomes queryable by semantic similarity.
```python
embeddings = semantica_generate_embeddings(facts)
# Returns: {"fact_id": [0.123, 0.456, ...], ...}
# Stored in LanceDB for similarity search
```

### 6. Provenance Tracking
W3C PROV-O compliance: tracks source document, extraction timestamp, tool version, confidence metadata.
```python
prov_doc = semantica_track_provenance(fact, source_doc, extraction_metadata)
# RDF-serializable provenance graph linking facts to sources
```

## Integration Points

- **Input**: Raw text from DIAL Chat, document upload, or streaming events
- **DuckDB**: Temporal facts written immutably (Pass 1 WORM layer); supports temporal indexes
- **PostgreSQL**: Normalized entities, relations, and metadata; pgvector for embeddings
- **Neo4j**: Knowledge graph nodes/edges; supports Cypher pattern queries for entity timelines
- **LanceDB**: Vector index for semantic search across facts
- **Frontend**: Confidence scores, conflict flags, and provenance displayed in evidence review UI

## Two-Pass Enrichment Workflow

**Pass 1 (Blind, 24-hour context)**:
1. Ingest document to DuckDB (immutable WORM log)
2. Extract entities, relations, temporal facts
3. Store in PostgreSQL and Neo4j
4. Generate embeddings → LanceDB index
5. Track provenance → PROV-O RDF

**Pass 2 (Hindsight, longitudinal)**:
1. Query Neo4j entity timelines across all sources
2. Detect narrative shifts (conflicting facts over time)
3. Compute conflict severity and deception risk scores
4. Annotate original facts with temporal contradiction flags
5. Output: forensically defensible contradiction report

## Common Pitfalls

- **Confidence Thresholds**: Default 0.7; lower for exploratory queries, raise for high-stakes determinations
- **Temporal Ambiguity**: Dates inferred from text have lower confidence; explicit timestamps preferred
- **Relation Overlap**: Same relation extracted multiple times; deduplication performed automatically
- **Embedding Dimension**: 768-dim fixed; ensure compatibility with LanceDB/pgvector (use 768-dim projection if needed)
- **Conflict False Positives**: Date inference errors trigger false contradictions; validate timestamp confidences
- **Batch Size**: Documents chunked at 4096 tokens; overlapping context windows preserve cross-sentence relations
- **Provenance Overhead**: PROV-O RDF can be verbose; optional in high-throughput scenarios

## References
- [Semantica Internal Docs](https://github.com/dial-stack/semantica) (internal)
- [W3C PROV-O Specification](https://www.w3.org/TR/prov-o/)
- [spaCy Named Entity Recognition](https://spacy.io/api/entityrecognizer)
- [Sentence-Transformers (all-MiniLM)](https://www.sbert.net/docs/sentence_transformer/pretrained_models/sentence-transformers-models.html#general-models)
- [Temporal Information Extraction (EMNLP 2018)](https://www.aclweb.org/anthology/P18-1202)
