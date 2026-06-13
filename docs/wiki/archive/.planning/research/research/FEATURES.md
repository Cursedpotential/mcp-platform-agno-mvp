---
title: GraphRAG Feature Landscape
version: 2.0.0
created: 2026-02-28 15:15
author: thinking@opencode
project: MCP_Tool_Platform
status: final
---

# Feature Landscape: GraphRAG as Abstraction Layer

**Domain:** Evidence management platform — GraphRAG integration for NER, routing, retrieval
**Researched:** 2026-02-28
**Confidence:** HIGH (features verified via Context7 + official documentation)

## Feature Ownership Map

The central question: **What does each package handle out-of-box, and what still needs custom code?**

### Neo4j GraphRAG Python — Real-Time Abstraction Layer

| Feature | Out-of-Box? | How It Works | Replaces |
|---|---|---|---|
| **Entity extraction (NER)** | YES | SimpleKGPipeline: give it text, it extracts entities via LLM and writes nodes to Neo4j | Custom Python bridge NER + manual Cypher writes |
| **Relationship extraction** | YES | SimpleKGPipeline: extracts relationships between entities, writes edges to Neo4j | Custom relationship detection code |
| **Graph writes to Neo4j** | YES | Native Neo4j driver integration. Writes directly to specified database. | Manual Cypher write logic in TrinityRouter |
| **Vector similarity search** | YES | VectorRetriever: searches Neo4j vector indexes | Custom LanceDB similarity search code |
| **Structured graph queries** | YES | Text2CypherRetriever: converts natural language to Cypher, executes against Neo4j | Custom Cypher query construction |
| **Query routing (multi-retriever)** | YES | ToolsRetriever: wraps multiple retrievers as "tools", lets LLM pick which to use | TrinityRouter query routing logic (the big one) |
| **Custom entity types** | YES | SimpleKGPipeline accepts `entities` and `relations` lists — define domain-specific types | N/A — new capability |
| **Embedding generation** | YES | Supports custom embedder interface — plug in Ollama nomic-embed-text | Custom embedding pipeline |
| **Error handling on extraction** | YES | `on_error="IGNORE"` — continues on malformed LLM responses | Custom error handling in Python bridge |

### Microsoft GraphRAG — Batch Enrichment Engine

| Feature | Out-of-Box? | How It Works | Replaces |
|---|---|---|---|
| **Community detection (Leiden)** | YES | 6-phase pipeline: chunk → extract → detect communities → summarize | Nothing — this is NEW capability. Referenced in STORAGE_ARCHITECTURE.md but not yet built. |
| **Community summarization** | YES | LLM generates natural language summaries of each community | Nothing — NEW capability |
| **Global search (map-reduce)** | YES | Searches across ALL community reports, synthesizes answer | Nothing — NEW. Enables "summarize all evidence about X" queries. |
| **Local search (entity-centric)** | YES | Traverses graph from target entity, retrieves connected context | Partially replaces custom Neo4j traversal queries |
| **DRIFT search (hybrid)** | YES | Combines local entity traversal with community-level context | Nothing — NEW. Best general-purpose search mode. |
| **Basic search (vector RAG)** | YES | Pure vector similarity search | Overlaps with existing LanceDB search |
| **Claim/covariate extraction** | YES | Extracts behavioral claims (promises, threats, assertions) from text | Nothing — NEW. Critical for forensic evidence: "He promised X but did Y" |
| **Fast indexing (NLP)** | YES | Uses NLTK/spaCy instead of LLM for extraction. Free compute, noisier graphs. | Nothing — cost-saving option |
| **Standard indexing (LLM)** | YES | LLM-based extraction. Expensive (~75% of pipeline cost) but high quality. | Nothing — quality option |
| **LanceDB vector store** | YES | Default vector store. Point at existing LanceDB directory. | N/A — reuses existing infra |
| **Ollama via LiteLLM** | YES | Supports 100+ LLM providers including Ollama as proxy | N/A — uses existing Ollama |
| **Python API (programmatic)** | YES | `from graphrag.api import build_index, local_search` — no CLI required | N/A — can call from Python bridge |
| **BYOG (Bring Your Own Graph)** | YES | Skip extraction, start from entities.parquet + relationships.parquet | Enables using Neo4j GraphRAG's extraction output as input to MS GraphRAG community detection |

### What Still Needs Custom Code

| Feature | Why Custom | Which Phase |
|---|---|---|
| **DuckDB first-touch (SHA-256, chain of custody)** | Forensic requirement. No library handles cryptographic evidence hashing at ingestion. | Already exists (TrinityRouter) |
| **Write-status tracking across tiers** | Reliability feature for multi-store writes. Library packages write to one store each. | Already exists (TrinityRouter) |
| **Health checks** | Operations concern. Libraries don't monitor each other. | Already exists (TrinityRouter) |
| **Parquet-to-Neo4j import** | MS GraphRAG outputs parquet files. Getting community data INTO Neo4j requires Cypher import script. | Phase 2 |
| **Pass 1 immutability enforcement** | Domain rule: blind classification is locked with SHA-256. No library enforces this. | Already exists |
| **Graphiti temporal edges** | Neither GraphRAG package handles valid_at/invalid_at temporal awareness. | Already ~40% built |
| **Contradiction detection** | Graphiti-specific. Comparing claims across time to find contradictions. | Already ~40% built |
| **Python bridge HTTP API** | TypeScript server → Python packages communication layer. | Already exists |
| **Batch trigger logic** | When to run MS GraphRAG batch pipeline (e.g., after N documents, nightly, manual). | Phase 2 — simple cron or threshold trigger |

## Table Stakes (Must Have for MVP)

Features the platform MUST have to be useful. GraphRAG coverage shown.

| Feature | Expected By Users | Complexity | GraphRAG Coverage |
|---|---|---|---|
| Entity extraction from messages | Core value prop — who, what, when, where | Medium | **SimpleKGPipeline handles this fully** |
| Relationship mapping | See connections between people/events | Medium | **SimpleKGPipeline handles this fully** |
| Semantic search across evidence | "Find messages about custody schedule" | Low | **VectorRetriever or Basic search** |
| Chain of custody (SHA-256) | Legal requirement for evidence | Low | **Custom — DuckDB first touch** |
| Temporal ordering | Messages in chronological order | Low | **DuckDB master clock — already exists** |
| Cross-platform ingestion | Import from SMS, iMessage, email, etc. | Medium | **Custom — DuckDB schema unification** |
| Pass 1 blind classification | Sentiment/intent at time of receipt | Medium | **SimpleKGPipeline or custom — depends on approach** |

## Differentiators (Set Platform Apart)

Features that make this platform unique vs generic document management.

| Feature | Value Proposition | Complexity | GraphRAG Coverage |
|---|---|---|---|
| **Community detection** | "These 47 messages form a gaslighting campaign" — invisible to per-message analysis | High | **MS GraphRAG Leiden algorithm — this is its killer feature** |
| **Global summarization** | "Summarize all evidence about financial abuse over 3 years" | Medium | **MS GraphRAG global search — map-reduce over community reports** |
| **Contradiction detection** | "He said X on Jan 5 but Y on Feb 12" — temporal fact comparison | High | **Graphiti — temporal edges with valid_at/invalid_at** |
| **Claim extraction** | Extract specific promises, threats, assertions as structured data | Medium | **MS GraphRAG claim/covariate extraction — designed for this** |
| **Multi-hop retrieval** | "Find everyone connected to the custody dispute through financial records" | High | **MS GraphRAG local search + DRIFT search** |
| **DRIFT search** | Best-of-both: entity-specific + community-aware hybrid retrieval | Medium | **MS GraphRAG DRIFT search — unique capability** |
| **AI-driven query routing** | System picks the right search mode automatically | Medium | **Neo4j GraphRAG ToolsRetriever — LLM selects retriever** |
| **Behavioral pattern detection** | Match against 303+ patterns (DARVO, gaslighting, etc.) | High | **Partially — community detection surfaces clusters. Pattern matching still custom.** |

## Anti-Features (Explicitly Do NOT Build)

| Anti-Feature | Why Avoid | What To Do Instead |
|---|---|---|
| **Real-time community detection** | Leiden algorithm is batch-only by design. Attempting real-time = engineering nightmare + bad results on small data. | Run MS GraphRAG batch pipeline periodically (nightly or after N docs). Community detection needs volume to find real patterns. |
| **Custom entity extraction pipeline** | Reimplementing what SimpleKGPipeline already does. Months of work for worse results. | Use SimpleKGPipeline. Customize entity types and relations list, not the extraction logic. |
| **Custom graph query language** | Building a DSL on top of Cypher. Adds complexity, hides Neo4j's native power. | Use Text2CypherRetriever — LLM generates Cypher directly. Users describe what they want in natural language. |
| **Custom vector store** | Building embedding storage when LanceDB is already deployed and both GraphRAG packages support it natively. | Use LanceDB for everything. MS GraphRAG defaults to it. Neo4j GraphRAG can use Neo4j's native vector indexes. |
| **Multi-tenant isolation at GraphRAG level** | GraphRAG pipelines are single-corpus by design. Tenant isolation adds massive complexity. | Isolate at DuckDB level (per-case databases) and Neo4j level (per-case databases). GraphRAG operates per-case. |
| **Real-time Graphiti + SimpleKGPipeline dual extraction** | Running both on every message doubles LLM cost and creates duplicate entities in different schemas. | Run SimpleKGPipeline for semantic facts. Run Graphiti for temporal memory. Different databases, different purposes. Don't run both on the same text for the same purpose. |

## Feature Dependencies

```
DuckDB First Touch (SHA-256, chain of custody)
  ↓
SimpleKGPipeline (real-time NER → Neo4j/Semantica)
  ↓                                      
LanceDB (embeddings)                     
  ↓                                      
MS GraphRAG Batch Pipeline (community detection — needs accumulated docs)
  ↓
Community Reports in Neo4j (needs parquet import)
  ↓
Global Search / DRIFT Search (needs community reports)

PARALLEL PATH (independent):
DuckDB First Touch
  ↓
Graphiti (temporal memory → Neo4j/temporal_memory)
  ↓
Contradiction Detection (needs temporal edges accumulated over time)
```

## MVP Recommendation

For MVP, prioritize in this order:

1. **DuckDB first-touch + SHA-256** — Already exists. Foundation for everything.
2. **SimpleKGPipeline entity extraction** — Immediate value. Give it text, get entities in Neo4j.
3. **VectorRetriever semantic search** — "Find messages about X" — core user workflow.
4. **Text2CypherRetriever graph queries** — "Show me everyone connected to Alice" — core user workflow.
5. **ToolsRetriever query routing** — System automatically picks the right search mode.

**Defer to post-MVP:**
- MS GraphRAG batch pipeline (needs document volume before community detection is meaningful)
- Global search (needs community reports, which need batch pipeline)
- Claim extraction (valuable but not blocking core search/retrieval)
- DRIFT search (powerful but needs community reports as input)

## Sources

- Context7: `/neo4j/neo4j-graphrag-python` — SimpleKGPipeline, ToolsRetriever, VectorRetriever, Text2CypherRetriever
- Context7: `/microsoft/graphrag` — pipeline phases, search modes, claim extraction, BYOG
- Context7: `/websites/microsoft_github_io_graphrag` — fast vs standard indexing, vector store config
- Existing codebase: STORAGE_ARCHITECTURE.md (community detection reference), systemRouter.ts (current routing logic)
