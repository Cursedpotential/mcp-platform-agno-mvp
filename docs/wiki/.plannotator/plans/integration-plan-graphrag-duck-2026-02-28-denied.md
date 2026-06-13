# Integration Plan: GraphRAG + DuckDB + Graphiti

## Architecture Overview

### Real-Time Ingestion Flow
```
Document
  │
  ▼
DuckDB (ALWAYS FIRST)
  ├─ SHA-256 hash
  ├─ Dedup check
  ├─ Metadata extraction
  ├─ Staging tables
  │
  ├──► LanceDB (parallel)
  │    └─ Raw binary + 768-dim embeddings
  │
  ├──► Graphiti (parallel)
  │    ├─ Entity extraction (temporal)
  │    ├─ Contradiction detection
  │    └─ → Neo4j temporal_memory
  │
  └──► Mark "pending_batch" in write_status
```

### Batch Enrichment Pipeline (scheduled)
```
DuckDB query: WHERE batch_status = 'pending'
  │
  ▼
MS GraphRAG Pipeline
  ├─ Text chunking
  ├─ LLM entity/relationship extraction
  ├─ Leiden community detection
  ├─ Community summarization
  │
  ▼
Parquet Output
  │
  ▼
Cypher UNWIND Import → Neo4j semantic_facts
  ├─ __Entity__ nodes
  ├─ __Chunk__ nodes
  ├─ __Community__ nodes
  ├─ RELATED, HAS_ENTITY, IN_COMMUNITY edges
  │
  ▼
Entity Resolution (post-import)
  ├─ k-NN on name embeddings
  ├─ WCC via Neo4j GDS
  ├─ Word distance filtering
  └─ LLM evaluation for merge
```

## Component Responsibility Matrix

| Responsibility | Owner | Package | Database |
|---|---|---|---|
| SHA-256 hashing | DuckDB client | Custom (STAYS) | DuckDB |
| Deduplication | DuckDB client | Custom (STAYS) | DuckDB |
| Write tracking | DuckDB client | Custom (STAYS) | DuckDB |
| Metadata staging | DuckDB client | Custom (STAYS) | DuckDB |
| Raw binary storage | LanceDB client | Custom (STAYS) | LanceDB |
| Vector embeddings | LanceDB client | Custom (STAYS) | LanceDB |
| Temporal entity extraction | Graphiti | graphiti-core | Neo4j temporal_memory |
| Contradiction detection | Graphiti | graphiti-core | Neo4j temporal_memory |
| Episode management | Graphiti | graphiti-core | Neo4j temporal_memory |
| Batch entity extraction | MS GraphRAG | graphrag v3.0.5 | Parquet → Neo4j |
| Community detection | MS GraphRAG | graphrag + Neo4j GDS | Neo4j semantic_facts |
| Community summarization | MS GraphRAG | graphrag v3.0.5 | Neo4j semantic_facts |
| Parquet → Neo4j import | Custom script | Custom (~50 lines) | Neo4j semantic_facts |
| Entity resolution | Custom script | Custom (~100 lines) | Neo4j semantic_facts |
| Local search (entity→chunks) | Neo4j GraphRAG Python | neo4j-graphrag-python | Neo4j semantic_facts |
| Global search (communities) | Neo4j GraphRAG Python | neo4j-graphrag-python | Neo4j semantic_facts |
| Query routing | TrinityRouter | Custom (~100 lines) | All |

## Custom Code Budget

| Component | Before | After | Change |
|---|---|---|---|
| DuckDB client (duckdb.ts) | 416 lines | 416 lines | UNCHANGED |
| LanceDB client (lancedb.ts) | 389 lines | 389 lines | UNCHANGED |
| TrinityRouter (systemRouter.ts) | 388 lines | ~100 lines | -288 lines |
| graphiti-client.ts | 752 lines | ~200 lines | -552 lines (delegates to graphiti-core) |
| python-bridge.ts | 427 lines | 427 lines | UNCHANGED (still needed for spaCy/NLTK) |
| semantic_facts.ts | MISSING | ~80 lines | NEW |
| parquet_import.py | — | ~50 lines | NEW |
| entity_resolution.py | — | ~100 lines | NEW |
| graphrag_config.py | — | ~30 lines | NEW |
| batch_scheduler.ts | — | ~60 lines | NEW |
| **TOTAL** | 2,372 | ~1,852 | **-520 lines (~22%)** |

## Neo4j Database Layout

### semantic_facts (MS GraphRAG managed)
```
(__Entity__ {id, name, type, description, description_embedding})
  -[:RELATED {description, rank, weight}]-> (__Entity__)
  <-[:HAS_ENTITY]- (__Chunk__ {id, text, n_tokens, document_ids})
  -[:IN_COMMUNITY]-> (__Community__ {title, summary, full_content, level, rank, weight})
```

### temporal_memory (Graphiti managed)
```
(Entity {name, entity_type, valid_at, invalid_at})
  -[:TEMPORAL_EDGE {fact, valid_at, invalid_at, confidence}]-> (Entity)
  <-[:MENTIONED_IN]- (Episode {content, timestamp, source})
```

## Custody Domain Entity Types

| Type | Examples | Used By |
|---|---|---|
| person | "Matt", "Matthew S.", "Dad", "Respondent" | Both (need entity resolution) |
| communication | text message, email, phone call | MS GraphRAG + Graphiti |
| event | custody exchange, court hearing, incident | Both |
| location | home address, school, courthouse | MS GraphRAG |
| organization | school, DHHS, court, therapy office | MS GraphRAG |
| legal_proceeding | motion, hearing, FOC complaint | MS GraphRAG |

## Claim Extraction → MCL 722.23 Mapping

MS GraphRAG claim extraction maps directly to custody behavioral patterns:

| Claim Type | MCL Factor | Example |
|---|---|---|
| substance_use | (j) Substance abuse | "He was drinking again when he picked up the kids" |
| custody_interference | (j) Willful interference | "She refused the exchange again" |
| false_allegation | (l) DV allegations | "She told CPS I hit her but I wasn't even there" |
| neglect_indicator | (b) Capacity to provide | "Kids hadn't eaten all day" |
| coercive_control | (c) Capacity to provide love | "She monitors all my texts with the kids" |

## Query Routing (Simplified TrinityRouter)

```typescript
async routeQuery(query: string, type: QueryType): Promise<QueryResult> {
  // DuckDB: Always check provenance first
  const provenance = await this.duckdb.getProvenance(query);
  
  switch (type) {
    case 'temporal':
      // "What changed between 2023 and 2024?"
      return this.graphiti.queryTemporal(query);
    
    case 'global':
      // "Summarize all communication patterns"
      return this.neo4jGraphRAG.globalSearch(query);
    
    case 'local':
      // "What happened at the Jan 15 exchange?"
      return this.neo4jGraphRAG.localSearch(query);
    
    case 'similarity':
      // "Find messages similar to this one"
      return this.lancedb.vectorSearch(query);
    
    default:
      // Auto-route based on query analysis
      return this.autoRoute(query);
  }
}
```

## 5-Phase Implementation

### Phase A: Foundation Wiring (Week 1-2)
- Create `semantic_facts.ts` (bridge to Neo4j semantic_facts DB)
- Wire `TrinityRouter.initializeAll()` in `server/core/index.ts`
- Verify DuckDB + LanceDB clients work at startup
- **DuckDB role:** Confirmed working, just needs startup wiring
- **Graphiti role:** Client exists, needs startup wiring

### Phase B: Graphiti Integration (Week 2-3)
- Wire existing graphiti-client.ts into real-time ingestion path
- Verify temporal_memory writes work end-to-end
- Test contradiction detection on sample messages
- Slim graphiti-client.ts from 752 → ~200 lines (delegate to graphiti-core)
- **DuckDB role:** First-touch before Graphiti gets the document
- **Graphiti role:** PRIMARY focus of this phase

### Phase C: MS GraphRAG Batch Pipeline (Week 3-5)
- Install graphrag package, configure settings.yaml
- Create graphrag_config.py with custody entity types
- Run MS GraphRAG on sample evidence corpus
- Create parquet_import.py (Cypher UNWIND into semantic_facts)
- Create entity_resolution.py (k-NN + WCC + LLM eval)
- Create batch_scheduler.ts for scheduled runs
- **DuckDB role:** Provides batch query (WHERE batch_status = 'pending')
- **Graphiti role:** Unaffected — runs on separate path

### Phase D: Retrieval Layer (Week 5-6)
- Install neo4j-graphrag-python, configure retrievers
- Implement local search (entity embeddings → graph traversal)
- Implement global search (community summary map-reduce)
- Simplify TrinityRouter (388 → ~100 lines)
- Wire query routing: temporal→Graphiti, global/local→Neo4j GraphRAG Python
- **DuckDB role:** Provenance lookup always runs first in query path
- **Graphiti role:** Handles temporal queries directly

### Phase E: Two-Pass Enrichment (Week 6-8)
- Pass 1: Real-time (DuckDB → LanceDB + Graphiti, parallel)
- Pass 2: Batch (MS GraphRAG → parquet → Neo4j → entity resolution)
- Wire claim extraction for MCL 722.23 behavioral patterns
- End-to-end testing with real evidence samples
- **DuckDB role:** Orchestrates pass tracking (pending_pass1/pass2, completed)
- **Graphiti role:** Provides temporal context for Pass 2 synthesis

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LanceDB version conflict (MS GraphRAG pins different version) | Medium | High | Test in isolated venv first, pin compatible version |
| Ollama JSON malformation during GraphRAG indexing | High | Medium | Use `fast` NLP method (spaCy) for extraction, Ollama only for summarization |
| Entity resolution false positives (merge wrong people) | Medium | High | LLM evaluation step before merge, human review for ambiguous cases |
| Neo4j GDS not available on Aura tier | Low | High | Fall back to community Neo4j with GDS plugin locally |
| Graphiti + SimpleKGPipeline dual extraction duplicates | Medium | Medium | Sequential flow: Graphiti for temporal, MS GraphRAG for batch — never same text simultaneously |
| Cost explosion from LLM entity extraction | Medium | High | Use `fast` NLP method, batch during off-peak, set token budget limits |
| Python Bridge latency for batch operations | Low | Low | Batch operations are scheduled, not real-time — latency acceptable |

## Files Summary

### New Files (6)
1. `server/mcp/storage/neo4j/semantic_facts.ts` — Neo4j semantic_facts DB client
2. `server/mcp/storage/batch_scheduler.ts` — Scheduled batch GraphRAG runs
3. `server/python-tools/graphrag/graphrag_config.py` — MS GraphRAG settings
4. `server/python-tools/graphrag/parquet_import.py` — Parquet → Neo4j import
5. `server/python-tools/graphrag/entity_resolution.py` — Post-import entity merging
6. `server/python-tools/graphrag/claim_extraction_config.py` — MCL 722.23 claim mapping

### Modified Files (5)
1. `server/core/index.ts` — Add TrinityRouter.initializeAll() call
2. `server/mcp/storage/systemRouter.ts` — Simplify 388 → ~100 lines
3. `server/mcp/storage/graphiti-client.ts` — Slim 752 → ~200 lines
4. `server/mcp/storage/index.ts` — Export new modules
5. `package.json` — Add graphrag-related dependencies

### Unchanged Files (4)
1. `server/mcp/storage/duckdb.ts` — 416 lines, STAYS AS-IS
2. `server/mcp/storage/lancedb.ts` — 389 lines, STAYS AS-IS
3. `server/mcp/python-bridge.ts` — 427 lines, STAYS AS-IS
4. `server/mcp/storage/neo4j/temporal_memory.ts` — 280 lines, STAYS AS-IS

## Success Metrics

| Metric | Target |
|---|---|
| DuckDB first-touch on every ingestion | 100% |
| Graphiti temporal edges created per message | ≥1 |
| MS GraphRAG communities detected on 100-doc corpus | ≥5 |
| Entity resolution reduces duplicate entities by | ≥50% |
| Query routing accuracy (temporal vs global vs local) | ≥90% |
| Custom code reduction | ≥20% |
| End-to-end ingestion time (single document) | &lt;5 seconds |
| Batch pipeline throughput | ≥100 docs/hour |
| Pass 2 enrichment coverage | 100% of ingested docs |

---

# Plan Feedback

I've reviewed this plan and have 1 piece of feedback:

## 1. General feedback about the plan
> we are missing semantica  
Hawksight-AI/semantica

---
