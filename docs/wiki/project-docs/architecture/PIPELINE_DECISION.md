# Processing Pipeline Architecture Decision

**Decision Date:** 2026-03-16  
**Status:** APPROVED  
**Decision ID:** ARCH-001

---

## Summary

The Dial Stack uses **Option 2: PostgreSQL First, Then Parallel** for processing forensic evidence through the storage tiers.

---

## Architecture Diagram

```
                    ┌─────────────┐
                    │   DuckDB    │
                    │  (Tier 1)   │
                    │ transforms  │
                    └──────┬──────┘
                           │
                           ↓
                    ┌─────────────┐
                    │ PostgreSQL  │
                    │  (Tier 2)   │
                    │  normalize  │
                    └──────┬──────┘
                           │
           ┌───────────────┴───────────────┐
           ↓                               ↓
    ┌─────────────┐                 ┌─────────────┐
    │  LanceDB    │                 │   Neo4j     │
    │  (Tier 3)   │                 │  (Tier 4)   │
    │  embed      │                 │  graph      │
    └─────────────┘                 └─────────────┘
```

---

## Workflow Timing

```
Time →
[====DuckDB====] 
                [====PostgreSQL====]
                                    [===LanceDB===]
                                    [====Neo4j====]  ← PARALLEL
```

---

## Why This Approach

| # | Reason | Details |
|---|--------|---------|
| 1 | **Forensic integrity** | PostgreSQL provides canonical UUIDv7 → hash mapping |
| 2 | **Cosmo federation** | All subgraphs query PostgreSQL for entity resolution |
| 3 | **Simpler error handling** | If PostgreSQL fails, downstream doesn't run |
| 4 | **Referential integrity** | LanceDB and Neo4j reference PostgreSQL UUIDs |
| 5 | **Performance** | PostgreSQL write is FAST with COPY + index rebuild |

---

## Storage Tier Responsibilities

| Tier | Technology | What It Stores | Role |
|------|-------------|----------------|------|
| **Shared** | FileSystem | ONE COPY of binaries | Source of truth |
| **T1** | DuckDB | Transformations, hashes, metadata | First drop, forensic processing |
| **T2** | PostgreSQL | Normalized relational data | Canonical UUID mapping |
| **T3** | LanceDB | Vector embeddings | Semantic search |
| **T4** | Neo4j | Entities, relationships | Knowledge graph (via Semantica) |

---

## Bottleneck Analysis

| System | Primary Bottleneck | Mitigation |
|--------|-------------------|------------|
| **DuckDB** | File I/O (reading binaries) | Parallel readers, memory-mapped files |
| **PostgreSQL** | Write throughput (INSERTs) | COPY command, disable indexes during load |
| **LanceDB** | Embedding generation (GPU/CPU) | Batch processing, GPU acceleration |
| **Neo4j** | Entity extraction (NLP/ML) | Batch processing, model caching |

---

## WunderGraph Cosmo Integration

```yaml
federated_graph: traceiq-forensic
namespace: production

subgraphs:
  - evidence-ingestion (PostgreSQL + DuckDB) - port 4011
  - knowledge-graph (Neo4j + Semantica) - port 4012  
  - rules-engine (MySQL via mysql_fdw) - port 4013

mcp_gateway:
  enabled: true
  expose_tools:
    - ingest_evidence, verify_custody_chain (evidence-ingestion)
    - query_timeline, detect_platform_hops, resolve_entities (knowledge-graph)
    - flag_behavioral_patterns, get_severity_classification (rules-engine)
```

**Local Router Setup:**
```bash
wgc router compose -i compose.yaml -o router.json
```

---

## Directus Integration

- **Database:** PostgreSQL (via Knex.js, SQL-only)
- **Extension:** pg_duckdb FDW makes DuckDB visible to Directus
- **Upload Flow:** Webhooks trigger processing pipeline after file upload
- **No Duplication:** Everything references shared directory (ONE COPY)

---

## Rejected Alternatives

### Option 1: Full Parallel

```
DuckDB → [PostgreSQL, LanceDB, Neo4j] (all at once)
```

**Why Rejected:**
- No coordination leads to conflicting entity IDs
- Inconsistent state window causes queries to fail during race conditions
- Not suitable for forensic chain-of-custody requirements

### Option 3: Hybrid (DuckDB Feeds All)

```
DuckDB → [PostgreSQL (async), LanceDB (async), Neo4j (async)]
```

**Why Rejected:**
- Data duplication risk (LanceDB and Neo4j create entities before PostgreSQL)
- UUID mismatches break Cosmo federation queries
- Complex error handling without clear canonical source

---

## Cosmo Federation Query Example

```graphql
query GetEvidenceTimeline($caseId: UUIDv7!) {
  evidence(caseId: $caseId) {           # evidence-ingestion subgraph (PG)
    hash
    platform
    timestamp
    entities {                          # knowledge-graph subgraph (Neo4j)
      name
      type
      relationships
    }
    similarEvidence {                  # LanceDB resolver (vector search)
      hash
      similarity_score
    }
  }
}
```

**This query REQUIRES:**
1. PostgreSQL holds canonical `hash` + `caseId` mapping
2. Neo4j references PostgreSQL UUIDs for entities
3. LanceDB references PostgreSQL UUIDs for similar evidence search

---

## Performance Notes

- **PostgreSQL write:** FAST with COPY command + index rebuild (100K+ rows/sec)
- **LanceDB + Neo4j:** Run fully parallel after PostgreSQL completes
- **Main bottlenecks:** Embedding generation (LanceDB) and entity extraction (Neo4j)

---

## Decision Log

| Date | Author | Change |
|------|--------|--------|
| 2026-03-16 | claude-opus@claude-code | Initial decision documented |