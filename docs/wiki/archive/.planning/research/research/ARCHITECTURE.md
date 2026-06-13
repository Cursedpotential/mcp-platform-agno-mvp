---
title: GraphRAG Integration Architecture
version: 2.0.0
created: 2026-02-28 15:30
author: thinking@opencode
project: MCP_Tool_Platform
status: final
---

# Architecture: GraphRAG as Abstraction Layer

**Domain:** Evidence management platform — GraphRAG replacing custom routing/NLP
**Researched:** 2026-02-28
**Confidence:** MEDIUM (integration pattern is novel — logical but unproven)

## Current Architecture (Before GraphRAG)

```
┌──────────────────────────────────────────────────────────────────┐
│                        MCP Gateway                               │
│                    (TypeScript / Node 22)                         │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                   TrinityRouter (389 lines)                       │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────┐             │
│  │ Write Flow   │ │ Query Flow   │ │ Enrichment    │             │
│  │ - DuckDB     │ │ - Custom     │ │ - Pass 1/2    │             │
│  │ - LanceDB    │ │   routing    │ │   dispatch    │             │
│  │ - Neo4j      │ │ - Manual     │ │ - Queue mgmt  │             │
│  │ - Status     │ │   tier       │ │               │             │
│  │   tracking   │ │   selection  │ │               │             │
│  └─────────────┘ └──────────────┘ └───────────────┘             │
│  ┌─────────────┐ ┌──────────────┐                               │
│  │ Health       │ │ SHA-256      │                               │
│  │ Checks       │ │ Chain of     │                               │
│  │              │ │ Custody      │                               │
│  └─────────────┘ └──────────────┘                               │
└───────┬──────────────┬──────────────┬──────────────┬────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
   ┌─────────┐   ┌──────────┐   ┌─────────┐   ┌─────────┐
   │ DuckDB  │   │ LanceDB  │   │ Neo4j   │   │ MySQL   │
   │ Master  │   │ Vectors  │   │ Dual DB │   │ App     │
   │ Clock   │   │ + Binary │   │         │   │ Meta    │
   └─────────┘   └──────────┘   └─────────┘   └─────────┘
                                │         │
                           Semantica   Graphiti
                          (semantic    (temporal
                           _facts)     _memory)

Python Bridge (separate process):
   ┌──────────────────────────────────────┐
   │ Custom NLP Pipeline                   │
   │ - spaCy NER                           │
   │ - Duckling (dates/amounts)            │
   │ - Sentiment analysis                  │
   │ - Manual entity → Cypher writes       │
   └──────────────────────────────────────┘
```

**Problems with current architecture:**
1. TrinityRouter is a 389-line monolith handling writes, queries, enrichment, health, AND routing
2. Custom NLP pipeline duplicates what SimpleKGPipeline does out-of-box
3. Query routing is hand-coded tier selection — brittle, doesn't scale with new data types
4. No community detection (Pass 2 placeholder referenced but not built)
5. No global summarization capability
6. Entity extraction → graph write is manual glue code

## Target Architecture (With GraphRAG)

```
┌──────────────────────────────────────────────────────────────────┐
│                        MCP Gateway                               │
│                    (TypeScript / Node 22)                         │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│              TrinityRouter (SIMPLIFIED — ~100 lines)             │
│  ┌─────────────────────┐  ┌──────────────────────────────┐      │
│  │ DuckDB First Touch  │  │ Delegation Layer             │      │
│  │ - SHA-256 hashing   │  │ - Route to Python bridge     │      │
│  │ - Write-status      │  │ - Trigger batch enrichment   │      │
│  │ - Health checks     │  │ - Return results to gateway  │      │
│  └─────────────────────┘  └──────────────────────────────┘      │
└───────┬──────────────────────────────┬──────────────────────────┘
        │                              │
        ▼                              ▼
   ┌─────────┐              ┌──────────────────────────────────┐
   │ DuckDB  │              │      Python Bridge (FastAPI)     │
   │ Master  │              │                                  │
   │ Clock   │              │  ┌────────────────────────────┐  │
   └─────────┘              │  │  REAL-TIME PATH            │  │
                            │  │  Neo4j GraphRAG Python     │  │
                            │  │                            │  │
                            │  │  SimpleKGPipeline          │  │
                            │  │  → Entity extraction       │  │
                            │  │  → Relationship extraction │  │
                            │  │  → Graph writes → Neo4j    │  │
                            │  │                            │  │
                            │  │  ToolsRetriever            │  │
                            │  │  → VectorRetriever         │  │
                            │  │  → Text2CypherRetriever    │  │
                            │  │  → LLM picks best tool     │  │
                            │  └────────────────────────────┘  │
                            │                                  │
                            │  ┌────────────────────────────┐  │
                            │  │  BATCH PATH                │  │
                            │  │  Microsoft GraphRAG        │  │
                            │  │                            │  │
                            │  │  build_index()             │  │
                            │  │  → Entity extraction       │  │
                            │  │  → Leiden communities      │  │
                            │  │  → Community summaries     │  │
                            │  │  → Parquet output          │  │
                            │  │  → Neo4j import (custom)   │  │
                            │  │                            │  │
                            │  │  local_search()            │  │
                            │  │  global_search()           │  │
                            │  │  drift_search()            │  │
                            │  └────────────────────────────┘  │
                            │                                  │
                            │  ┌────────────────────────────┐  │
                            │  │  TEMPORAL PATH             │  │
                            │  │  Graphiti                  │  │
                            │  │                            │  │
                            │  │  add_episode()             │  │
                            │  │  → Temporal edges          │  │
                            │  │  → Contradiction detection │  │
                            │  │  → Episodic memory         │  │
                            │  │                            │  │
                            │  │  search()                  │  │
                            │  │  → Temporal queries        │  │
                            │  └────────────────────────────┘  │
                            └──────┬───────┬───────┬───────────┘
                                   │       │       │
                                   ▼       ▼       ▼
                            ┌──────────┐ ┌─────────┐ ┌─────────┐
                            │ LanceDB  │ │ Neo4j   │ │ MySQL   │
                            │ Vectors  │ │ Dual DB │ │ App     │
                            │ + Binary │ │         │ │ Meta    │
                            └──────────┘ └─────────┘ └─────────┘
                                         │         │
                                    Semantica   Graphiti
                                   (semantic    (temporal
                                    _facts)     _memory)
```

## Component Boundaries

| Component | Responsibility | Communicates With | Language |
|---|---|---|---|
| **MCP Gateway** | Tool discovery, invocation, content refs | TrinityRouter | TypeScript |
| **TrinityRouter** (simplified) | DuckDB first touch, delegation, health | DuckDB, Python Bridge | TypeScript |
| **Python Bridge** | Hosts all three GraphRAG packages | Neo4j, LanceDB, Ollama | Python |
| **SimpleKGPipeline** | Real-time NER → Neo4j graph writes | Neo4j/Semantica, Ollama | Python |
| **ToolsRetriever** | AI-driven query routing across retrievers | Neo4j, LanceDB, Ollama | Python |
| **MS GraphRAG Pipeline** | Batch community detection + summarization | LanceDB, Ollama, Parquet files | Python |
| **Graphiti** | Temporal memory + contradiction detection | Neo4j/temporal_memory, Ollama | Python |
| **DuckDB** | Master clock, SHA-256, write tracking | TrinityRouter only | Embedded |
| **LanceDB** | Vectors + binary storage | Python Bridge, MS GraphRAG | Embedded |
| **Neo4j** | Dual graph databases | SimpleKGPipeline, Graphiti, MS GraphRAG (via import) | Server |
| **MySQL** | App metadata | Drizzle ORM (TypeScript) | Server |

## Data Flow: Ingestion

```
1. Document arrives at MCP Gateway
   │
2. TrinityRouter: DuckDB First Touch
   │  ├─ Generate SHA-256 hash
   │  ├─ Write to ingestion_log
   │  ├─ Normalize timestamps to UTC
   │  ├─ Deduplicate by content hash
   │  └─ Init write-status tracking
   │
3. TrinityRouter delegates to Python Bridge
   │
4. PARALLEL — Python Bridge dispatches to:
   │
   ├─ SimpleKGPipeline (real-time, Neo4j GraphRAG)
   │  ├─ LLM extracts entities: Person, Location, Date, Event, Claim
   │  ├─ LLM extracts relationships: SENT_TO, MENTIONED, CONTRADICTS
   │  ├─ Writes entity nodes → Neo4j/semantic_facts
   │  ├─ Writes relationship edges → Neo4j/semantic_facts
   │  └─ Generates + stores embeddings → LanceDB (or Neo4j vector index)
   │
   ├─ Graphiti (real-time, temporal)
   │  ├─ add_episode() with message content
   │  ├─ Extracts temporal entities
   │  ├─ Creates temporal edges (valid_at/invalid_at)
   │  ├─ Checks for contradictions with prior episodes
   │  └─ Writes → Neo4j/temporal_memory
   │
   └─ LanceDB (direct)
      ├─ Store raw binary (screenshot, PDF, etc.)
      └─ Store embeddings with metadata (UUID, source_hash, timestamp)
   
5. TrinityRouter: Update write-status in DuckDB
   └─ Mark each tier as written_at with timestamp
```

## Data Flow: Batch Enrichment (Pass 2)

```
TRIGGER: Nightly cron, or after N documents, or manual

1. Python Bridge: Collect documents from DuckDB
   │  └─ Query normalized_messages for un-enriched docs
   │
2. Microsoft GraphRAG: build_index()
   │  ├─ Phase 1: Chunk text into TextUnits (1200 chars, 100 overlap)
   │  ├─ Phase 2: Link chunks to source documents
   │  ├─ Phase 3: Extract entities + relationships (LLM or NLP)
   │  │           Use "fast" method (NLP) for cost savings
   │  │           Use "standard" method (LLM) for high-value docs
   │  ├─ Phase 4: Leiden community detection (graspologic)
   │  │           Groups related entities into communities
   │  ├─ Phase 5: Generate community reports (LLM summarization)
   │  │           "This community of 12 entities relates to financial disputes..."
   │  └─ Phase 6: Generate text embeddings → LanceDB
   │
3. Parquet → Neo4j Import (CUSTOM SCRIPT)
   │  Uses Cypher UNWIND for batch import (per Bratanič's ms_graphrag_import.ipynb):
   │
   │  ├─ Read entities.parquet → CREATE (:__Entity__) nodes in semantic_facts
   │  │   UNWIND $data AS row
   │  │   MERGE (e:__Entity__ {id: row.id})
   │  │   SET e.name = row.name, e.type = row.type,
   │  │       e.description = row.description, e.human_readable_id = row.human_readable_id,
   │  │       e.text_unit_ids = row.text_unit_ids
   │  │
   │  ├─ Read relationships.parquet → CREATE [:RELATED] edges
   │  │   MATCH (source:__Entity__ {name: row.source})
   │  │   MATCH (target:__Entity__ {name: row.target})
   │  │   MERGE (source)-[r:RELATED]->(target)
   │  │   SET r.description = row.description, r.rank = row.rank, r.weight = row.weight
   │  │
   │  ├─ Read text_units.parquet → CREATE (:__Chunk__) nodes
   │  │   Link to entities via [:HAS_ENTITY] relationships
   │  │
   │  ├─ Read communities.parquet → CREATE (:__Community__) nodes
   │  │   SET .title, .summary, .full_content, .level, .rank, .weight
   │  │   Link entities via [:IN_COMMUNITY] relationships
   │  │
   │  └─ Create vector indexes on entity descriptions for local search:
   │     CREATE VECTOR INDEX entity_description_embedding FOR (e:__Entity__)
   │     ON (e.description_embedding) OPTIONS {indexConfig: {`vector.dimensions`: 768}}
   │
   │  NOTE: Entity resolution is NOT included in MS GraphRAG output.
   │  Must be done as post-import step using Bratanič's approach:
   │  k-NN on entity name embeddings → Weakly Connected Components (WCC) →
   │  word distance filtering → LLM evaluation for final merge decisions.
   │  Requires Neo4j GDS library.
   │
4. DuckDB: Mark documents as Pass 2 enriched
   └─ Update write-status with enrichment timestamp
```

## Data Flow: Query/Retrieval

```
1. Query arrives at MCP Gateway
   │  "Show me evidence of financial manipulation by John"
   │
2. TrinityRouter delegates to Python Bridge
   │
3. Neo4j GraphRAG ToolsRetriever receives query
   │  ├─ LLM analyzes query intent
   │  ├─ LLM selects best retriever(s):
   │  │
   │  ├─ OPTION A: VectorRetriever
   │  │  └─ Semantic similarity search in Neo4j vector index
   │  │     "Find messages semantically similar to 'financial manipulation'"
   │  │
   │  ├─ OPTION B: Text2CypherRetriever  
   │  │  └─ LLM generates Cypher query
   │  │     MATCH (p:Person {name: 'John'})-[:MENTIONED]->(e:Event)
   │  │     WHERE e.type = 'financial' RETURN e
   │  │
   │  ├─ OPTION C: MS GraphRAG Local Search
   │  │  └─ Entity-centric graph traversal from "John"
   │  │     Retrieves connected entities + relevant text units
   │  │
   │  ├─ OPTION D: MS GraphRAG Global Search
   │  │  └─ Map-reduce across ALL community reports
   │  │     "Summarize everything about financial manipulation"
   │  │
   │  ├─ OPTION E: MS GraphRAG DRIFT Search
   │  │  └─ Hybrid: entity traversal + community context
   │  │     Best general-purpose for complex queries
   │  │
   │  └─ OPTION F: Graphiti Temporal Search
   │     └─ Temporal queries with time-range constraints
   │        "What contradictions exist about John's finances?"
   │
4. Results aggregated and returned to MCP Gateway
   └─ Formatted as MCP content references
```

## Three-Database Neo4j Strategy

The dual-database Neo4j architecture gains a clear ownership model with GraphRAG:

```
Neo4j Instance
├─ semantic_facts (database)
│  ├─ OWNED BY: Neo4j GraphRAG SimpleKGPipeline (real-time writes)
│  ├─ ENRICHED BY: Microsoft GraphRAG (batch community detection)
│  ├─ QUERIED BY: VectorRetriever, Text2CypherRetriever, MS GraphRAG search
│  │
│  ├─ Node Types:
│  │  ├─ :Person, :Location, :Date, :Amount, :Event, :Claim  (SimpleKGPipeline)
│  │  ├─ :Community, :CommunityReport  (MS GraphRAG batch import)
│  │  └─ :Entity (generic, from MS GraphRAG extraction)
│  │
│  ├─ Edge Types:
│  │  ├─ :SENT_TO, :MENTIONED, :OCCURRED_AT  (SimpleKGPipeline)
│  │  ├─ :BELONGS_TO (entity → community)  (MS GraphRAG import)
│  │  └─ :CONTRADICTS, :PROMISED, :THREATENED  (SimpleKGPipeline domain-specific)
│  │
│  └─ Vector Indexes:
│     └─ evidence_vectors (768-dim, nomic-embed-text)
│
└─ temporal_memory (database)
   ├─ OWNED BY: Graphiti (real-time writes)
   ├─ QUERIED BY: Graphiti search, custom temporal queries
   │
   ├─ Node Types:
   │  ├─ :EpisodicNode (individual episodes/messages)
   │  └─ :EntityNode (temporal entity versions)
   │
   └─ Edge Types:
      ├─ :RELATES_TO (entity relationships with valid_at/invalid_at)
      ├─ :MENTIONS (episode → entity)
      └─ :CONTRADICTS (temporal contradiction detection)
```

## TrinityRouter: Before vs After

### Before (Current — 389 lines)

```typescript
class TrinityRouter {
  // Write orchestration (~120 lines)
  async storeEvidence(data) {
    await this.duckdb.insert(data);           // First touch
    await this.lancedb.store(data);            // Vectors
    await this.neo4j.writeEntities(data);      // Manual Cypher
    this.trackWriteStatus(data.id);            // Status
  }

  // Query routing (~100 lines)  
  async query(params) {
    switch (params.type) {                     // Hand-coded routing
      case 'semantic': return this.lancedb.search(params);
      case 'temporal': return this.graphiti.search(params);
      case 'relational': return this.neo4j.query(params);
      case 'hybrid': return this.mergeResults(/* all tiers */);
    }
  }

  // Enrichment dispatch (~80 lines)
  async enrichPass1(data) { /* custom NLP pipeline */ }
  async enrichPass2(data) { /* placeholder — not implemented */ }

  // Health + status (~89 lines)
  async healthCheck() { /* check all tiers */ }
  getWriteStatus(id) { /* lookup */ }
}
```

### After (Target — ~100 lines)

```typescript
class TrinityRouter {
  // DuckDB first touch — STAYS (forensic requirement)
  async ingest(data) {
    const hash = sha256(data.content);
    await this.duckdb.insert({ ...data, hash });
    this.trackWriteStatus(data.id);
    
    // Delegate everything else to Python bridge
    await this.pythonBridge.process({
      action: 'ingest',
      document: data,
      hash: hash,
    });
  }

  // Query — DELEGATES to ToolsRetriever
  async query(params) {
    return this.pythonBridge.query({
      action: 'search',
      query: params.query,
      // ToolsRetriever decides which retriever(s) to use
    });
  }

  // Batch enrichment — TRIGGERS MS GraphRAG
  async triggerBatchEnrichment(caseId) {
    return this.pythonBridge.process({
      action: 'batch_enrich',
      caseId: caseId,
      method: 'fast', // or 'standard' for high-value docs
    });
  }

  // Health + status — STAYS (operations concern)
  async healthCheck() { /* check all tiers */ }
  getWriteStatus(id) { /* lookup */ }
}
```

**Reduction: 389 lines → ~100 lines.** Most intelligence moves to the Python bridge where the three GraphRAG packages live.

## Patterns to Follow

### Pattern 1: Pipeline-per-Purpose
**What:** Each GraphRAG package owns one purpose. Don't mix responsibilities.
**When:** Always. This is the core architectural principle.
```
SimpleKGPipeline → real-time NER + graph writes (semantic_facts)
MS GraphRAG      → batch community detection + summarization
Graphiti         → temporal memory + contradiction detection (temporal_memory)
```

### Pattern 2: DuckDB-First, Always
**What:** Every document touches DuckDB first for SHA-256 + normalization. Then flows to GraphRAG packages.
**When:** Every ingestion. No exceptions.
**Why:** Chain of custody is a legal requirement. GraphRAG packages don't handle this.

### Pattern 3: BYOG Bridge
**What:** Use MS GraphRAG's BYOG (Bring Your Own Graph) to skip extraction when SimpleKGPipeline already extracted entities.
**When:** Batch enrichment (Phase 2). Feed SimpleKGPipeline's entities as input to MS GraphRAG community detection.
**How:** Export entities from Neo4j/semantic_facts → entities.parquet + relationships.parquet → MS GraphRAG runs only community detection phases.
```python
# Skip extraction, run only community detection
from graphrag.api import build_index

# BYOG: provide pre-extracted entities
build_index(
    config=config,
    # Only run these phases (skip entity extraction):
    # create_communities, create_community_reports, generate_text_embeddings
)
```

### Pattern 4: LLM-Routed Queries
**What:** Let the LLM decide which retriever handles a query via ToolsRetriever.
**When:** Every query. Don't hand-code routing rules.
**Why:** ToolsRetriever adapts to query intent. Hand-coded rules break on edge cases.
```python
from neo4j_graphrag.retrievers import ToolsRetriever

tools_retriever = ToolsRetriever(
    retrievers=[vector_retriever, cypher_retriever, graphrag_local, graphiti_search],
    llm=ollama_llm,
)
# LLM analyzes query → picks best retriever(s) → returns results
result = tools_retriever.search(query="evidence of financial manipulation by John")
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Dual Extraction to Same Database
**What:** Running BOTH SimpleKGPipeline AND MS GraphRAG entity extraction against the same document, writing both to semantic_facts.
**Why bad:** Duplicate entities with different schemas. Conflicting node types. Double LLM cost.
**Instead:** SimpleKGPipeline for real-time extraction → semantic_facts. MS GraphRAG BYOG for community detection using SimpleKGPipeline's entities.

### Anti-Pattern 2: Synchronous Batch Pipeline
**What:** Running MS GraphRAG build_index() synchronously during document ingestion.
**Why bad:** build_index() can take minutes-to-hours on large corpora. Blocks ingestion.
**Instead:** Ingest immediately (DuckDB + SimpleKGPipeline). Queue for batch enrichment. Run MS GraphRAG async (cron, threshold trigger, or manual).

### Anti-Pattern 3: Bypassing DuckDB
**What:** Sending documents directly to SimpleKGPipeline without DuckDB first touch.
**Why bad:** Breaks chain of custody. No SHA-256 hash. No deduplication. No write tracking.
**Instead:** ALWAYS DuckDB first → then delegate to Python bridge.

### Anti-Pattern 4: Custom Retriever Logic in TypeScript
**What:** Building query routing in TrinityRouter (TypeScript) instead of using ToolsRetriever (Python).
**Why bad:** Duplicates what ToolsRetriever does. Can't leverage LLM-driven routing. Two codebases to maintain.
**Instead:** TrinityRouter forwards queries to Python bridge → ToolsRetriever handles routing.

## Scalability Considerations

| Concern | Current (3 VPS, $24/mo) | At 10K Documents | At 100K Documents |
|---|---|---|---|
| **Ingestion speed** | SimpleKGPipeline: ~2-5 sec/doc via Ollama | Same (per-doc, scales linearly) | Same, but consider batching |
| **Batch enrichment** | MS GraphRAG fast: minutes | MS GraphRAG fast: ~1 hour | MS GraphRAG fast: 4-8 hours. Consider standard only for high-value docs. |
| **Neo4j graph size** | < 10K nodes, trivial | ~100K nodes, fine for Community Edition | ~1M nodes, may need Neo4j tuning (indexes, memory) |
| **LanceDB vectors** | < 10K vectors, trivial | ~100K vectors, fine | ~1M vectors, fine (LanceDB scales well) |
| **DuckDB** | < 100MB, trivial | ~1GB, fine (embedded) | ~10GB, still fine for DuckDB |
| **LLM cost (Ollama)** | $0 | $0 (local GPU) | $0 but GPU may bottleneck. Consider OpenRouter for overflow. |
| **Community detection** | Not meaningful on small data | Starting to find real patterns | Full value — communities of 10-50 entities surface behavioral clusters |

## Sources

- Context7: `/neo4j/neo4j-graphrag-python` — SimpleKGPipeline, ToolsRetriever architecture
- Context7: `/microsoft/graphrag` — 6-phase pipeline, BYOG, search modes
- Neo4j Blog: https://neo4j.com/blog/developer/microsoft-graphrag-neo4j/ — Full integration guide, Cypher import, retriever setup
- Medium (Bratanič): https://medium.com/neo4j/implementing-from-local-to-global-graphrag-with-neo4j-and-between-lines-d6571220d7e0 — Entity resolution approach, cost analysis, Leiden with Neo4j GDS
- GitHub: https://github.com/tomasonjo/blogs/tree/master/msft_graphrag — Import + retriever notebooks
- graphrag.com: https://graphrag.com/appendices/research/2404.16130 — Original paper, pattern catalog
- Existing codebase: systemRouter.ts (389 lines), STORAGE_ARCHITECTURE.md, INGESTION_ARCHITECTURE.md
- Existing codebase: graphiti-client.ts (752 lines, ~40% built)
