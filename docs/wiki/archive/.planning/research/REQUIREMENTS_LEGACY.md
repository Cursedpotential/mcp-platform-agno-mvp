# MCP Tool Platform — v1 Requirements (5-Tier Architecture, Semantica replaces Graphiti)

**Project:** MCP Tool Platform
**Generated:** March 1, 2026
**Updated:** March 2, 2026 — Architecture simplified from 6-Tier to 5-Tier (Graphiti archived, Semantica handles all graph operations)
**Architecture:** 5-Tier (DuckDB + LanceDB + Neo4j/Semantica + PostgreSQL + MySQL + Python Memory Service)
**Core Value:** Raw messaging exports → temporally-aware, forensically-hashed evidence with bidirectional LLM/Portal/API access

---

## Architecture Overview

### 5-Tier Storage Architecture

| Tier | Technology           | Purpose                                       | Managed By              |
| ---- | -------------------- | --------------------------------------------- | ----------------------- |
| 1    | DuckDB               | Master clock, SHA-256, ETL                    | TrinityRouter (Node.js) |
| 2    | LanceDB              | Multimodal vault (binaries + embeddings)      | TrinityRouter (Node.js) |
| 3    | Neo4j                | Temporal KG, validated entities, PROV-O       | Semantica (Python)      |
| 4    | PostgreSQL           | Relational evidence (messages, conversations) | TrinityRouter (Node.js) |
| 5    | MySQL                | Application metadata (users, API keys)        | Drizzle ORM (Node.js)   |

**Note:** Graphiti (formerly Tier 4) has been archived to `server/mcp/storage/archived_graphiti/`. Semantica now handles ALL graph operations including temporal knowledge graphs, episodic memory, contradiction detection, and PROV-O provenance — features previously split between Graphiti and Semantica.

### Database Separation Rules (STRICT)

- **App Layer (Tier 5):** MySQL — Users, API keys, App settings, Behavioral Pattern configs
- **Evidence Relational (Tier 4):** PostgreSQL — Messages, Conversations, Files metadata, GPS
- **Evidence Analytics (Tier 1):** DuckDB — Ingestion log, SHA-256 hashes, write tracking
- **Evidence Multimodal (Tier 2):** LanceDB — Raw binaries, vector embeddings
- **Knowledge Graph (Tier 3):** Neo4j — Semantica temporal KG (entities, provenance, decisions, temporal edges, contradictions)

### Data Flow

```
Node.js TrinityRouter
        │
        ├──► DuckDB (Tier 1): SHA-256 hash, ingestion log
        ├──► PostgreSQL (Tier 4): Store message
        ├──► LanceDB (Tier 2): Store binary + embeddings
        │
        │ HTTP POST (fire-and-forget)
        ▼
Python Memory Service (FastAPI)
        │
        └──► Semantica → Neo4j (Tier 3)
             ├─ Temporal knowledge graph
             ├─ Entity validation + PROV-O
             ├─ Episodic memory
             ├─ Contradiction detection
             └─ Decision tracking
```

---

## v1.0 Requirements

### 1. Database Architecture (5-Tier)

- [ ] **DB-01**: The system must simultaneously initialize and maintain connections to:
  - MySQL (Tier 5: App Control Plane)
  - PostgreSQL (Tier 4: Evidence Relational Data Plane)
  - DuckDB (Tier 1: Master Clock - embedded)
  - LanceDB (Tier 2: Multimodal Vault - embedded)
  - Neo4j (Tier 3: Semantica Knowledge Graph)

- [ ] **DB-02**: The legacy Drizzle schemas must compile cleanly:
  - MySQL schema (`drizzle/schema.ts`) for application tables
  - PostgreSQL schema (`drizzle/evidence/schema.ts`) for evidence tables
  - No collisions between app and evidence schemas

- [ ] **DB-03**: PostgreSQL evidence schema must include:
  - `messages` table with JSONB content column
  - `conversations` table with participant tracking
  - `files` table linking to LanceDB binaries
  - Full-text search indexes on message content

- [x] **DB-04**: MySQL application schema must include:
  - `users`, `apiKeys`, `apiKeyUsageLogs`
  - `behavioralPatterns` (303 patterns), `patternCategories`
  - `workflows`, `workflowTemplates`, `systemPrompts`

---

### 2. Async Memory Service

- [ ] **MEM-01**: The system must run a dedicated Python FastAPI service (`mcp-memory-service`) alongside Node.js to handle heavy semantic/graph processing asynchronously.

- [ ] **MEM-02**: The Python service must expose REST endpoints:
  - `POST /memory/ingest` — Ingest evidence to temporal/semantic memory
  - `POST /memory/query` — Query temporal/semantic facts
  - `GET /memory/contradictions` — Retrieve detected contradictions
  - `GET /health` — Health check endpoint

- [ ] **MEM-03**: The Python service must integrate **Semantica** to:
  - Automatically build temporal knowledge graphs from text chunks
  - Create temporal edges (`valid_from`/`valid_to`) for entity relationships
  - Detect contradictions across time via `analyze_evolution()`
  - Support `query_at_time()` for point-in-time entity state
  - Build episodic memory from conversations
  - Write all graph data to Neo4j (Tier 3)

- [ ] **MEM-04**: The Python service must use **Semantica** to:
  - Validate extracted entities
  - Create W3C PROV-O provenance chains
  - Track analysis decisions with audit trail
  - Perform conflict detection between sources

- [ ] **MEM-05**: Every Node, Edge, and Decision created by Semantica must retain unbreakable UUIDv7 links back to:
  - The original text chunk (via `chunk_id`)
  - The document hash (via `document_id`)
  - The DuckDB ingestion log entry

- [ ] **MEM-06**: Node.js TrinityRouter must use **fire-and-forget** pattern:
  - POST to Python service without awaiting response
  - Return 202 Accepted immediately to client
  - Process asynchronously in Python service
  - Update write tracking when complete

---

### 3. Large File Ingestion (4GB Pipeline)

- [x] **ING-01**: A background watcher daemon must monitor the local block storage for completed file transfers (via Rclone).

- [x] **ING-02**: The ingestion pipeline must use stream-based processing to calculate SHA-256 hashes for massive files without loading them into RAM.

- [x] **ING-03**: DuckDB must serve as the Tier 1 "Holding Tank" to:
  - Chunk massive files
  - Assign UUIDv7s
  - Log ingestion metadata
  - Hand off to async memory service

- [ ] **ING-04**: The pipeline must write to all 5 tiers:
  - Tier 1 (DuckDB): SHA-256 hash, ingestion log
  - Tier 2 (LanceDB): Raw binary, embeddings
  - Tier 4 (PostgreSQL): Message content, relationships
  - Tier 3 (Neo4j): Via Python Memory Service (Semantica)

---

### 4. Infrastructure & Deployment

- [ ] **INF-01**: The platform must be deployable via a unified `docker-compose` file designed for Coolify.

- [ ] **INF-02**: The deployment must include:
  - Node.js MCP Platform container
  - Python Memory Service container
  - MySQL container (Tier 5)
  - PostgreSQL container (Tier 4)
  - Neo4j container (Tier 3)
  - Tailscale sidecar for secure VPC access

- [ ] **INF-03**: The architecture must explicitly support mounting a 50GB Block Storage volume for the Cloudflare R2 / Rclone evidence drop.

- [ ] **INF-04**: Environment variables must support all 5 tiers:
  - `DATABASE_URL` (MySQL - Tier 5)
  - `EVIDENCE_DATABASE_URL` (PostgreSQL - Tier 4)
  - `DUCKDB_PATH` (Tier 1)
  - `LANCEDB_PATH` (Tier 2)
  - `NEO4J_URL`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` (Tier 3)
  - `MEMORY_SERVICE_URL` (Python service)

---

### 5. Two-Pass Enrichment

- [ ] **ENR-01**: Pass 1 (Blind Classification) must:
  - Use only 24-hour context window
  - Extract sentiment, intent, entities
  - Generate embeddings (768-dim)
  - Store results in DuckDB (immutable)
  - Lock with SHA-256 reference

- [ ] **ENR-02**: Pass 2 (Hindsight Synthesis) must:
  - Be user-triggered (not automatic)
  - Use full longitudinal context
  - Run Microsoft GraphRAG community detection
  - Query Python Memory Service for contradictions
  - Create annotations (never modify Pass 1)

- [ ] **ENR-03**: Gaslighting detection must compare:
  - Pass 1 sentiment ("how it felt at the time")
  - Pass 2 longitudinal patterns ("what actually happened")
  - Create CONTRADICTS edges in Neo4j

---

### 6. Chain of Custody

- [ ] **COC-01**: SHA-256 hash must be computed at first touch (before any transformation).

- [ ] **COC-02**: Hash must be stored in:
  - DuckDB ingestion_log
  - LanceDB metadata
  - Neo4j node properties
  - PostgreSQL message records

- [ ] **COC-03**: W3C PROV-O provenance must be attached to every Neo4j node created by Semantica.

- [ ] **COC-04**: Pass 1 results must be WORM (Write Once, Read Many) — never modified after creation.

---

## Traceability

| Requirement | Phase   | Status    |
| ----------- | ------- | --------- |
| DB-01       | Phase 2 | In Progress |
| DB-02       | Phase 1 | Pending   |
| DB-03       | Phase 2 | Pending   |
| DB-04       | —       | Complete  |
| ING-01      | —       | Complete  |
| ING-02      | —       | Complete  |
| ING-03      | —       | Complete  |
| ING-04      | Phase 3 | Pending   |
| MEM-01      | Phase 4 | Pending   |
| MEM-02      | Phase 4 | Pending   |
| MEM-03      | Phase 5 | Pending   |
| MEM-04      | Phase 5 | Pending   |
| MEM-05      | Phase 5 | Pending   |
| MEM-06      | Phase 4 | Pending   |
| INF-01      | Phase 7 | Pending   |
| INF-02      | Phase 7 | Pending   |
| INF-03      | Phase 7 | Pending   |
| INF-04      | Phase 7 | Pending   |
| ENR-01      | Phase 6 | Pending   |
| ENR-02      | Phase 8 | Pending   |
| ENR-03      | Phase 8 | Pending   |
| COC-01      | Phase 2 | Pending   |
| COC-02      | Phase 2 | In Progress |
| COC-03      | Phase 5 | Pending   |
| COC-04      | Phase 6 | Pending   |

---

---

## Spec Module Mapping

| Requirement Group | Spec Module | Spec File |
|-------------------|------------|-----------|
| DB-01 to DB-04 | Module 1: Storage Foundation | `docs/specs/MODULE_1_STORAGE.md` |
| COC-01, COC-02 | Module 2: TrinityRouter & Ingestion | `docs/specs/MODULE_2_TRINITY_ROUTER.md` |
| ING-04, MEM-06 | Module 2: TrinityRouter & Ingestion | `docs/specs/MODULE_2_TRINITY_ROUTER.md` |
| MEM-01 to MEM-05 | Module 4: Python Memory Service | `docs/specs/MODULE_4_MEMORY_SERVICE.md` |
| COC-03 | Module 4: Python Memory Service | `docs/specs/MODULE_4_MEMORY_SERVICE.md` |
| ENR-01, COC-04 | Module 5: Two-Pass Enrichment | `docs/specs/MODULE_5_ENRICHMENT.md` |
| ENR-02, ENR-03 | Module 5: Two-Pass Enrichment | `docs/specs/MODULE_5_ENRICHMENT.md` |
| INF-01 to INF-04 | Phase 7 (Infrastructure) | TBD |

---

## Development Process

**All changes to this codebase follow Spec-Driven Development.**
See `docs/SPEC_DRIVEN_DEVELOPMENT.md` for the mandatory process.

**Key rule:** No code changes without a documented plan and spec.

---

**Last Updated:** March 3, 2026
**Architecture:** 5-Tier (Semantica replaces Graphiti)
**Development Process:** Spec-Driven
**Version:** 2.1