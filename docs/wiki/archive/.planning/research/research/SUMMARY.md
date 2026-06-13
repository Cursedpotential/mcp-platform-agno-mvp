---
title: GraphRAG Integration Research Summary
version: 2.0.0
created: 2026-02-28 14:00
modified: 2026-02-28 15:00
author: thinking@opencode
project: MCP_Tool_Platform
status: final
---

# Research Summary: GraphRAG as Abstraction Layer

**Domain:** Evidence management platform with knowledge graph retrieval
**Researched:** 2026-02-28
**Overall confidence:** MEDIUM-HIGH

## Executive Summary

Microsoft GraphRAG (`graphrag 3.0.5`) and Neo4j GraphRAG Python (`neo4j-graphrag-python 1.5.0`) are **complementary packages** that together can serve as the intelligence and routing layer between DuckDB ingestion and the existing storage backends (LanceDB, Neo4j/Semantica, Neo4j/Graphiti). The goal: replace most custom TrinityRouter routing logic, custom NLP extraction code, and custom retrieval orchestration with battle-tested library code.

**The key insight:** These are not competing libraries — they operate at different levels:

| Package | Role | Strength |
|---|---|---|
| **Neo4j GraphRAG Python** | Real-time abstraction layer | NER, entity extraction, graph writes to Neo4j, query routing via ToolsRetriever — the "it just works" layer |
| **Microsoft GraphRAG** | Batch enrichment engine | Community detection (Leiden), global summarization, cross-document patterns — the "hindsight synthesis" engine |
| **Graphiti** (existing, ~40% built) | Temporal memory | Temporal edges, episodic memory, contradiction detection — neither GraphRAG package can do this |

**Recommendation:** Use Neo4j GraphRAG Python as the **primary abstraction layer** for real-time operations (entity extraction via SimpleKGPipeline, query routing via ToolsRetriever). Use Microsoft GraphRAG as the **batch enrichment engine** for Pass 2 community detection and global summarization. Keep Graphiti for temporal memory. DuckDB remains the untouched first-touch/chain-of-custody layer.

## The Integration Architecture

```
INGESTION (real-time):
  Document → DuckDB (SHA-256, chain of custody — UNCHANGED)
           → Neo4j GraphRAG SimpleKGPipeline (NER, entity extraction → Neo4j/Semantica)
           → LanceDB (embeddings — via pipeline or direct)
           → Graphiti (temporal edges — UNCHANGED)

ENRICHMENT (batch, periodic):
  DuckDB accumulated docs → Microsoft GraphRAG pipeline
    → Leiden community detection
    → Community summarization
    → Cross-document relationship discovery
    → Parquet outputs → imported into Neo4j/Semantica via Cypher

RETRIEVAL (query-time):
  Query → Neo4j GraphRAG ToolsRetriever (REPLACES custom TrinityRouter query routing)
    → VectorRetriever (semantic similarity — LanceDB or Neo4j vector index)
    → Text2CypherRetriever (structured graph queries against Neo4j)
    → MS GraphRAG local/global/drift search (community-aware retrieval)
    → Graphiti search (temporal/contradiction queries)
```

## What Gets Replaced vs What Stays

### Custom Code That Gets REPLACED

| Current Custom Code | Replaced By | Confidence |
|---|---|---|
| TrinityRouter entity extraction dispatch | Neo4j GraphRAG SimpleKGPipeline | **HIGH** |
| TrinityRouter query routing (5-tier coordination) | Neo4j GraphRAG ToolsRetriever | **MEDIUM** — needs custom tool definitions |
| Python bridge NER/NLP extraction | SimpleKGPipeline (LLM-based) | **HIGH** |
| Missing community detection (Pass 2) | Microsoft GraphRAG Leiden algorithm | **HIGH** |
| Missing global summarization | Microsoft GraphRAG global search (map-reduce) | **HIGH** |
| Missing multi-hop retrieval | Neo4j GraphRAG VectorRetriever + Text2CypherRetriever | **HIGH** |
| Custom embedding pipeline | Both packages support Ollama embeddings via LiteLLM | **MEDIUM** |

### Custom Code That STAYS

| Component | Why It Stays |
|---|---|
| **DuckDB first-touch + SHA-256 chain of custody** | Domain-specific forensic requirement. No library handles this. |
| **TrinityRouter write-status tracking** | Reliability feature for multi-store writes. No library equivalent. |
| **TrinityRouter health checks** | Operations concern, not a library's job. |
| **Graphiti temporal edges + contradiction detection** | Neither GraphRAG package is temporally aware. Unique capability. |
| **MySQL app metadata (Drizzle)** | Application layer, outside GraphRAG scope entirely. |

### TrinityRouter Evolution

TrinityRouter (currently 389 lines) becomes a **thin delegation layer**:

```
BEFORE (current): TrinityRouter does routing + extraction + orchestration + health
AFTER (target):   TrinityRouter does DuckDB-first-touch + delegates to GraphRAG packages

Reduced responsibilities:
  1. DuckDB write (SHA-256, chain of custody) — STAYS
  2. Delegate extraction → Neo4j GraphRAG SimpleKGPipeline — NEW
  3. Delegate queries → Neo4j GraphRAG ToolsRetriever — NEW  
  4. Trigger batch enrichment → Microsoft GraphRAG — NEW
  5. Write-status tracking — STAYS (simplified)
  6. Health checks — STAYS
```

## Implications for Roadmap

### Phase 1: Neo4j GraphRAG Python Integration (Real-Time Path)
- Replace custom NER/entity extraction with SimpleKGPipeline
- Set up ToolsRetriever with custom tool definitions for existing storage tiers
- **Why first:** Immediate custom code reduction. SimpleKGPipeline is the most "it just works" component — give it text, it extracts entities and writes to Neo4j.
- **Risk:** LOW — well-documented, native Neo4j, existing Neo4j infrastructure

### Phase 2: Microsoft GraphRAG Batch Pipeline
- Set up periodic batch indexing for community detection + summarization
- Build parquet-to-Neo4j import pipeline for community data
- Start with `fast` (NLP) method to avoid LLM cost explosion
- **Why second:** Batch processing needs documents already in the system (Phase 1 must work first).
- **Risk:** MEDIUM — parquet-to-Neo4j import is custom glue code

### Phase 3: TrinityRouter Simplification
- Reduce from 389-line orchestrator to thin DuckDB-first-touch + delegation layer
- Route extraction → SimpleKGPipeline, queries → ToolsRetriever, batch → MS GraphRAG
- **Why third:** Need proven replacements before stripping the coordinator
- **Risk:** LOW — making code simpler, not more complex

### Phase 4: Graphiti Boundary Definition
- Define clear boundary: Graphiti owns temporal edges + contradiction detection
- Neo4j GraphRAG owns semantic facts + entity relationships
- Evaluate entity extraction overlap between Graphiti and SimpleKGPipeline
- **Why last:** Graphiti is ~40% built and working. Boundary question requires Phases 1-2 experience.
- **Risk:** HIGH — overlap is poorly documented, needs empirical testing

### Phase Ordering Rationale
- Phase 1 before 2: real-time ingestion matters more than batch enrichment
- Phase 2 before 3: proven replacements needed before simplifying TrinityRouter
- Phase 4 last: Graphiti boundary is an empirical question, not a design question

### Research Flags
- Phase 1: Standard patterns, well-documented. **LOW research risk.**
- Phase 2: MS GraphRAG `fast` method quality needs empirical testing. **MEDIUM research risk.**
- Phase 3: No library handles DuckDB chain-of-custody — stays custom. **LOW research risk.**
- Phase 4: Graphiti + Neo4j GraphRAG entity extraction overlap. **HIGH research risk** — needs hands-on testing.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Both packages verified via Context7, PyPI, official docs. Versions current as of Feb 2026. |
| Features | HIGH | Feature sets confirmed via Context7 queries + official documentation |
| Architecture | MEDIUM | Two-package integration pattern is novel — no reference implementations found. Logical but unproven. |
| Pitfalls | MEDIUM | Cost estimates based on documented behavior + community reports. Ollama JSON issues confirmed by multiple sources. |

## Gaps to Address

1. **SimpleKGPipeline + existing Neo4j schema compatibility**: Does SimpleKGPipeline's default schema conflict with Semantica's existing node/edge types? Needs Phase 1 testing.
2. **Microsoft GraphRAG parquet → Neo4j import**: Bratanič's `ms_graphrag_import.ipynb` provides a proven pattern using Cypher UNWIND for batch import. Creates `__Entity__`, `__Chunk__`, `__Community__` nodes with `RELATED`, `HAS_ENTITY`, `IN_COMMUNITY` relationships. Need to adapt for our dual-database setup (import into `semantic_facts` DB specifically).
3. **Entity resolution NOT included in MS GraphRAG**: Must be custom post-import step. Bratanič's approach: k-NN on entity name embeddings → WCC (Weakly Connected Components via Neo4j GDS) → word distance filtering → LLM evaluation for final merge. Critical for custody domain where same person appears as "Matt", "Matthew", "Dad", etc.
4. **Ollama structured output reliability**: GraphRAG docs explicitly warn about malformed JSON from Ollama models. Needs testing with qwen2.5:14b, mistral-nemo.
5. **LanceDB version compatibility**: Both MS GraphRAG and the existing platform use LanceDB. Version conflicts possible. MS GraphRAG may pin a different version than our `@lancedb/lancedb ^0.15.0`.
6. **Graphiti entity extraction vs SimpleKGPipeline**: Both extract entities into Neo4j. Which runs when? Do they conflict? Unknown — requires empirical testing in Phase 4.
7. **Neo4j GDS required**: Leiden algorithm for community detection and WCC for entity resolution both require Neo4j Graph Data Science library. Must verify Neo4j Aura tier supports GDS, or run community edition locally.

## Key Reference Material (verified 2026-02-28)

### Neo4j Blog Integration Guide
**Source:** https://neo4j.com/blog/developer/microsoft-graphrag-neo4j/
- Full parquet → Neo4j import pipeline with Cypher queries
- Local + global retriever implementations using LangChain and LlamaIndex
- Neo4j graph schema: `__Entity__`, `__Chunk__`, `__Community__` nodes
- Vector index creation on entity description embeddings for local search

### Bratanič Deep Dive (Medium)
**Source:** https://medium.com/neo4j/implementing-from-local-to-global-graphrag-with-neo4j-and-between-lines-d6571220d7e0
- Entity resolution approach (k-NN + WCC + word distance + LLM eval)
- Cost analysis: ~75% of indexing cost is entity extraction phase
- Leiden community detection via Neo4j GDS
- `fast` NLP method (spaCy/NLTK) reduces cost dramatically vs LLM extraction

### Original Paper & Pattern Catalog
**Source:** https://graphrag.com/appendices/research/2404.16130
- "From Local to Global" methodology
- Hierarchical community detection at multiple levels
- Map-reduce global search pattern

### Implementation Notebooks
**Source:** https://github.com/tomasonjo/blogs/tree/master/msft_graphrag
- `ms_graphrag_import.ipynb` — Parquet → Neo4j import with UNWIND Cypher
- `ms_graphrag_retriever.ipynb` — Local + global retriever implementations

## Sources

- Context7: `/microsoft/graphrag` — architecture, pipeline, search modes, BYOG, config
- Context7: `/websites/microsoft_github_io_graphrag` — vector stores, models, NLP extraction
- Context7: `/neo4j/neo4j-graphrag-python` — SimpleKGPipeline, retrievers, ToolsRetriever
- PyPI: graphrag 3.0.5 (Feb 27, 2026), neo4j-graphrag-python 1.5.0
- Neo4j Blog: https://neo4j.com/blog/developer/microsoft-graphrag-neo4j/
- Medium (Bratanič): https://medium.com/neo4j/implementing-from-local-to-global-graphrag-with-neo4j-and-between-lines-d6571220d7e0
- graphrag.com: https://graphrag.com/appendices/research/2404.16130
- GitHub: https://github.com/tomasonjo/blogs/tree/master/msft_graphrag
- Existing codebase: STORAGE_ARCHITECTURE.md, INGESTION_ARCHITECTURE.md, systemRouter.ts, graphiti-client.ts
