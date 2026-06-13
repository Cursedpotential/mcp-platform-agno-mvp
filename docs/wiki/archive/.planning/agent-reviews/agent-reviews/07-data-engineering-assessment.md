# Data Engineering Assessment Report

**Agent:** Data Engineering
**Date:** February 28, 2026
**Project:** MCP_Tool_Platform

---

## Executive Summary

The MCP_Tool_Platform implements a **sophisticated 5-tier storage architecture** designed for forensic evidence processing with temporal knowledge graphs. The architecture has undergone a significant pivot from a 4-tier design to a merged 5-tier architecture centered on **DuckDB as the master clock** and **LanceDB as the multimodal vault**.

---

## 5-Tier Storage Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ TIER 1: DUCKDB — Master Clock & ETL Engine                      │
│ ├─ Embedded (zero external service dependency)                  │
│ ├─ SHA-256 hashing at first touch                               │
│ ├─ Ingestion log, normalized messages, write tracking           │
│ └─ Schema: ingestion_log, normalized_messages, write_tracking   │
├─────────────────────────────────────────────────────────────────┤
│ TIER 2: LANCEDB — Multimodal Vault                              │
│ ├─ Raw binary storage (screenshots, PDFs, audio)                │
│ ├─ Vector embeddings (768-dim, nomic-embed-text)                │
│ ├─ Tables: embeddings, raw_binaries                             │
│ └─ Zero-copy Arrow ↔ DuckDB integration                         │
├─────────────────────────────────────────────────────────────────┤
│ TIER 3: NEO4J — Dual Database                                   │
│ ├─ semantic_facts (Semantica-managed) - Validated entities      │
│ └─ temporal_memory (Graphiti-managed) - Temporal edges          │
├─────────────────────────────────────────────────────────────────┤
│ TIER 4: MYSQL — Application Metadata (Drizzle ORM)              │
│ └─ Users, API keys, workflows, patterns ONLY                    │
├─────────────────────────────────────────────────────────────────┤
│ TIER 5: CHROMADB — Deprecated (Legacy)                          │
│ └─ May be removed in future versions                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Critical Issues

### 1. Dialect Mismatch

**Files:** `drizzle.config.ts` vs `db.mysql.ts`

**Issue:**
```typescript
// drizzle.config.ts shows:
dialect: "postgresql"

// But db.mysql.ts shows MySQL is being used
```

Pattern migrations use PostgreSQL-specific features (JSONB, PostGIS, GIST indexes) but the application uses MySQL.

**Impact:** Configuration inconsistency that needs resolution

**Fix:** Align Drizzle configuration with actual MySQL usage or migrate fully to PostgreSQL

---

### 2. Missing semantic_facts Client

**File:** `server/mcp/storage/neo4j/semantic_facts.ts`

**Status:** Referenced by TrinityRouter but **NOT IMPLEMENTED**

**Impact:** Runtime errors when TrinityRouter initializes

---

### 3. Phase 1 Incomplete

From `STORAGE_ARCHITECTURE.md`:

| Component | Status | Notes |
|-----------|--------|-------|
| DuckDB Master Clock | Phase 1 | Initialization defined but not wired |
| LanceDB Multimodal Vault | Phase 1 | Schema defined, Arrow integration planned |
| Neo4j Dual Database | Phase 2 | Configuration defined, integration pending |
| Two-Pass Enrichment | Phase 4/7 | Architecture defined, not implemented |

**Critical Gap:** Storage tiers are not initialized at application startup

---

## Data Ingestion Pipelines

### Three Ingestion Pathways

| Pathway | Route | Purpose |
|---------|-------|---------|
| Pathway 1 | Agent/LLM → MCP Gateway → TrinityRouter | LLM-driven ingestion |
| Pathway 2 | User Upload → Platform UI → Directus | Manual web uploads |
| Pathway 3 | USB/Local → Directus Import | Bulk imports |

### Two-Pass Enrichment Architecture

**Pass 1 (Blind Classification):**
- 24-hour context window only
- Sentiment, intent, entity extraction (Duckling + spaCy)
- Real embeddings via Ollama (nomic-embed-text)
- **Immutable** - locked with SHA-256 reference
- Captures: "How it felt at the time"

**Pass 2 (Hindsight Synthesis):**
- Longitudinal analysis (months/years)
- Microsoft GraphRAG community detection
- Graphiti contradiction detection
- Creates CONTRADICTS edges in Neo4j temporal_memory
- Captures: Patterns invisible to original participant

---

## Connection Pooling & Performance

### Current Configuration

**MySQL:**
```typescript
_pool = mysql.createPool({
    connectionLimit: 10,  // Fixed limit
    waitForConnections: true,
    queueLimit: 0,
});
```

**PostgreSQL Migration Runner:**
```typescript
return postgres(process.env.DATABASE_URL, {
  max: 10,              // Connection pool size
  idle_timeout: 20,     // Seconds
  connect_timeout: 10,  // Seconds
});
```

### Performance Concerns

- **No connection pool monitoring** implemented
- **No query timeout configuration** for long-running analytical queries
- **No read replicas** configured
- **No caching layer** for frequently accessed patterns (Redis available but not integrated)

---

## Data Quality & Validation

### Chain of Custody

- SHA-256 hash generated at **first touch**
- Hash stored in DuckDB + LanceDB + Neo4j
- Provenance chain tracks all transformations
- Pass 1 data is **immutable** (forensic integrity)

### Write Tracking Schema

```sql
CREATE TABLE write_tracking (
  id VARCHAR PRIMARY KEY,
  ingestion_id VARCHAR NOT NULL UNIQUE,
  duckdb_written BOOLEAN DEFAULT false,
  lancedb_written BOOLEAN DEFAULT false,
  neo4j_semantic_written BOOLEAN DEFAULT false,
  neo4j_temporal_written BOOLEAN DEFAULT false,
  mysql_written BOOLEAN DEFAULT false,
  last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Data Quality Gaps

- No explicit data validation schema
- No Great Expectations or similar framework
- No automated anomaly detection
- Limited data profiling capabilities

---

## Key Files

**Configuration:**
- `drizzle.config.ts` - Drizzle ORM configuration
- `drizzle/schema.ts` - Database schema definitions
- `server/core/db.ts` - Database connection router
- `server/core/db.mysql.ts` - MySQL connection pool

**Storage Implementation:**
- `server/mcp/storage/duckdb.ts` - DuckDB client
- `server/mcp/storage/lancedb.ts` - LanceDB client
- `server/mcp/storage/systemRouter.ts` - TrinityRouter
- `server/mcp/storage/graphiti-client.ts` - Neo4j temporal memory

**Documentation:**
- `STORAGE_ARCHITECTURE.md` - 5-tier design
- `INGESTION_ARCHITECTURE.md` - Pipeline design

---

## Recommendations

### Immediate (P0)

1. **Resolve Dialect Inconsistency**
   - Align Drizzle configuration with actual MySQL usage
   - Or migrate fully to PostgreSQL

2. **Add Semantic Facts Client**
   - Implement missing `semantic_facts.ts` file
   - Wire into TrinityRouter

3. **Complete Phase 1 Implementation**
   - Finish DuckDB initialization
   - Finish LanceDB Arrow integration
   - Add comprehensive error handling

### Short-term (P1)

4. **Implement Connection Pool Monitoring**
   - Add metrics for pool utilization
   - Add query latency tracking
   - Add connection health checks

5. **Add Caching Layer**
   - Implement Redis caching for patterns
   - Cache entity lookups
   - Cache health check results

6. **Add Data Quality Framework**
   - Implement automated validation
   - Add data lineage tracking
   - Add data freshness monitoring

### Long-term (P2)

7. **Consider ClickHouse**
   - For multi-TB forensic datasets
   - Evaluate alongside DuckDB for analytical workloads

8. **Add Observability**
   - Prometheus metrics for storage tier health
   - Query performance metrics
   - Data pipeline monitoring/alerting