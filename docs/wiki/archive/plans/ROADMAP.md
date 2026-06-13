# AI DIAL Stack — Development Roadmap

> [!CAUTION]
> **`MCP_Tool_Platform` is ARCHIVED and STRICTLY READ-ONLY.**
> We only extract data and patterns from it. We never modify, delete, or restructure legacy files.

## Overview

This roadmap converts the legacy 8-phase `MCP_Tool_Platform` plan into the new AI DIAL architecture. The core mission remains: transform raw messaging exports into temporally-aware, forensically-hashed evidence with a knowledge graph. The difference is that **AI DIAL now orchestrates everything dynamically** instead of a rigid God Pipeline.

## Legacy → DIAL Phase Mapping

| Legacy Phase | Legacy Goal | DIAL Equivalent | Status |
|---|---|---|---|
| Phase 1: Compilation Foundation | Fix 292 TS errors | **Not needed** — fresh codebase | ✅ Bypassed |
| Phase 2: Database Architecture | 5-tier init | **Phase A**: PostgreSQL + DuckDB + LanceDB + Neo4j init in MCP tools | 🔄 ~70% done |
| Phase 3: Ingestion End-to-End | Full pipeline flow | **Phase B**: Atomic parser tools + DIAL orchestration | 🔄 ~60% done |
| Phase 4: Python Memory Service | FastAPI scaffolding | **Phase C**: Py MCP Server (FastMCP replaces FastAPI) | 🔄 ~80% done |
| Phase 5: Semantica Knowledge Graph | Temporal KG in Neo4j | **Phase C**: Semantica tools in Py MCP Server | 🔄 ~80% done |
| Phase 6: Pass 1 Enrichment | Blind NLP classification | **Phase D**: Enrichment tools (NER, sentiment, embeddings) | ⏳ Planned |
| Phase 7: Infrastructure Deployment | Hetzner VPS via Coolify | **Phase H**: Finalized docker-compose → VPS deployment | ⏳ Planned |
| Phase 8: Pass 2 Hindsight | Longitudinal analysis | **Phase D & I**: Contradiction detection, gaslighting analysis | ⏳ Planned |

---

## Current Development Phases

### Phase A: Foundation & Storage Tools *(Current — ~70% done)*

**Goal**: All storage tiers accessible as atomic MCP tools via AI DIAL

#### Tasks
- [x] Scaffold `ts-mcp-server` with TypeScript MCP SDK
- [x] Create `DuckDbVault` tool (SHA-256 hashing, UUIDv7, dedup, audit trail)
- [x] Create `PostgresWriter` tool (unified PG for evidence + app data)
- [x] PostgreSQL init scripts with pgvector
- [ ] Wire DuckDB → PostgreSQL ingestion pipeline as composable tools
- [ ] Create DuckDB query/read tool for retrieval
- [ ] Health check endpoints for all storage connections
- [ ] Refactor TS MCP dispatch from if-chain to registry pattern
- [ ] Implement lazy singletons for DuckDbVault and PostgresWriter (currently creates new instances per call)

#### Legacy Source Files (READ-ONLY reference)
- `server/mcp/storage/duckdb.ts` → extracted into `mcp-servers/ts-mcp-server/src/services/DuckDbService.ts`
- `server/mcp/storage/lancedb.ts` → patterns for LanceDB tool
- `server/mcp/storage/neo4j/` → patterns for Neo4j tools
- `drizzle/evidence/schema.ts` → PostgreSQL schema reference

---

### Phase B: Parser & Ingestion Tools *(~60% done)*

**Goal**: All format parsers wrapped as independent, confidence-scored MCP tools

#### Tasks
- [x] Create `SmsXmlParser` tool (wraps `loaders/xml-sms-parser.ts`)
- [x] Create `FacebookHtmlParser` tool (wraps `loaders/facebook-parser.ts`)
- [x] Create `PdfParser` tool (wraps `loaders/pdf-imessage-parser.ts`)
- [ ] Create `ChatGptJsonParser` tool (wraps `Evidence_Analysis/Scripts/chatgpt_parser.py`)
- [ ] Create `GoogleTimelineParser` tool (wraps `Evidence_Analysis/Scripts/parser.py`)
- [ ] Create `FormatDetector` tool (confidence-scored format detection)
- [ ] Create `ArchiveExtractor` tool (.zip extraction with R2 linking)
- [ ] Create `WhatsAppTxtParser` tool (wraps `readers/WhatsAppTxtReader.ts`)

#### Legacy Source Files (READ-ONLY reference)
- `server/mcp/loaders/xml-sms-parser.ts`
- `server/mcp/loaders/facebook-parser.ts`
- `server/mcp/loaders/pdf-imessage-parser.ts`
- `server/mcp/ingest/readers/WhatsAppTxtReader.ts`
- `server/mcp/ingest/readers/SmsXmlReader.ts`
- `server/mcp/ingest/format-detection.ts`
- `server/mcp/ingest/validation.ts`
- `Evidence_Analysis/Scripts/chatgpt_parser.py`
- `Evidence_Analysis/Scripts/parser.py`

---

### Phase C: Semantica & Knowledge Graph Tools *(~80% done)*

**Goal**: Full Semantica NLP pipeline exposed as MCP tools

#### Tasks
- [x] Full Semantica NLP pipeline (11 tools in py-mcp-server)
- [x] Create `semantica_tools.py` (NER, graph building, temporal facts, conflicts, embeddings, provenance)
- [x] Create `lancedb_tools.py` (vector search, upsert, collection management)
- [x] Create `neo4j_tools.py` (Cypher queries, graph traversal)
- [ ] End-to-end test: entity extraction on real evidence
- [ ] End-to-end test: temporal graph building
- [ ] End-to-end test: contradiction detection pipeline

#### Legacy Source Files (READ-ONLY reference)
- `python-tools/memory_service.py`
- `docs/SEMANTICA_INTEGRATION_GUIDE.md`
- `.planning/semantica-research/`

---

### Phase D: Enrichment Tools *(Planned)*

**Goal**: Two-pass enrichment system as composable MCP tools

#### Tasks
- [ ] Create `Pass1BlindClassifier` tool (sentiment, intent, entities — 24hr context window)
- [ ] Create `EmbeddingGenerator` tool (768-dim vectors → LanceDB)
- [ ] Create `Pass2HindsightAnalyzer` tool (longitudinal patterns, gaslighting detection)
- [ ] Create `ContradictionDetector` tool (Pass 1 vs Pass 2 comparison)
- [ ] Implement Pass 1 WORM (Write Once, Read Many) enforcement

#### Legacy Source Files (READ-ONLY reference)
- `server/mcp/pipelines/production-pipeline.ts` (two-pass logic)
- `.planning/REQUIREMENTS.md` (ENR-01 through ENR-03)

---

### Phase E: Authentication & Security *(In Progress — Keycloak added)*

**Goal**: Secure identity verification and role-based access control

#### Tasks
- [x] Keycloak identity provider configured in settings.json
- [ ] Keycloak container added to docker-compose
- [ ] JWT verification enabled for DIAL Core
- [ ] Role-based access control (admin/default/readonly) enforced
- [ ] Caddy HTTPS with auto-certs
- [ ] Caddy basic auth for pre-Keycloak fallback

#### Legacy Source Files (READ-ONLY reference)
- `.planning/REQUIREMENTS.md` (INF-04 for configuration)

---

### Phase F: WunderGraph Cosmo (Retrieval Federation) *(Planned)*

**Goal**: Unified GraphQL federation across all storage tiers

#### Tasks
- [ ] WunderGraph Cosmo container in docker-compose (port 4000)
- [ ] PostgreSQL subgraph schema
- [ ] Neo4j subgraph schema
- [ ] LanceDB subgraph schema (via proxy)
- [ ] DuckDB subgraph schema (via proxy)
- [ ] Federated supergraph composition
- [ ] `evidence_federated_query` MCP tool wrapping WunderGraph
- [ ] Query promotion workflow documented

#### Legacy Source Files (READ-ONLY reference)
- `drizzle/evidence/schema.ts` (for PostgreSQL subgraph)

---

### Phase G: React Frontend + CopilotKit (HITL UI) *(Planned)*

**Goal**: Human-in-the-loop review and evidence management interface

#### Tasks
- [ ] React app scaffolding (Vite + React 19 + Tailwind)
- [ ] CopilotKit integration with DIAL Core API
- [ ] HITL review dashboard (pending items, approve/reject)
- [ ] Evidence timeline viewer
- [ ] Entity resolution UI
- [ ] Ingestion status dashboard
- [ ] Keycloak OIDC login flow in React app

#### Legacy Source Files (READ-ONLY reference)
- `.planning/UI_REQUIREMENTS.md` (if exists)

---

### Phase H: Infrastructure & Deployment *(Planned)*

**Goal**: Production-ready deployment to VPS with Tailscale & Cloudflare R2

#### Tasks
- [ ] Finalize docker-compose.yml with all services
- [ ] Cloudflare R2 storage integration
- [ ] Tailscale VPC for secure access
- [ ] Hetzner VPS deployment
- [ ] LibreChat as alternative frontend (via DIAL API)

#### Legacy Source Files (READ-ONLY reference)
- `.planning/REQUIREMENTS.md` (INF-01 through INF-04)

---

### Phase I: Advanced Forensic Analysis *(Future)*

**Goal**: Forensic-grade analysis tools for legal evidence preparation

#### Tasks
- [ ] Create `GaslightingDetector` tool
- [ ] Create `CoerciveControlAnalyzer` tool
- [ ] Create `TimelineGenerator` tool
- [ ] Create `LegalEvidencePackager` tool
- [ ] Create `SeverityScorer` tool

#### Legacy Source Files (READ-ONLY reference)
- `docs/MCP_TOOL_CATALOG.md` (forensics.* tool definitions)
- `Evidence_Analysis/` (conflict analysis scripts)

---

## Requirements Traceability

All 25 original requirements from `.planning/REQUIREMENTS.md` are preserved:

| Req ID | Category | DIAL Phase | Status |
|--------|----------|-----------|--------|
| DB-01 | Database Architecture | Phase A | 🔄 In Progress |
| DB-02 | Drizzle Schemas | Phase A | ✅ Bypassed (fresh codebase) |
| DB-03 | PostgreSQL Evidence Schema | Phase A | 🔄 In Progress |
| DB-04 | MySQL App Schema | Phase A | ✅ Consolidated into PG |
| ING-01 | Watcher Daemon | Phase B | ✅ Complete (legacy) |
| ING-02 | Stream SHA-256 | Phase B | ✅ Complete (legacy) |
| ING-03 | DuckDB Holding Tank | Phase A | ✅ Complete (legacy) |
| ING-04 | 5-Tier Write | Phase B | 🔄 In Progress |
| MEM-01 | Python Service | Phase C | 🔄 In Progress |
| MEM-02 | REST Endpoints | Phase C | 🔄 In Progress |
| MEM-03 | Semantica KG | Phase C | 🔄 In Progress |
| MEM-04 | PROV-O Provenance | Phase C | ⏳ Planned |
| MEM-05 | UUIDv7 Linkage | Phase C | ⏳ Planned |
| MEM-06 | Fire-and-Forget | Phase C | ✅ Bypassed (DIAL handles) |
| INF-01 | Docker Compose | Phase H | 🔄 In Progress |
| INF-02 | Container Stack | Phase H | 🔄 In Progress |
| INF-03 | Block Storage | Phase H | ⏳ Planned |
| INF-04 | Env Variables | Phase E | 🔄 In Progress |
| ENR-01 | Pass 1 Blind | Phase D | ⏳ Planned |
| ENR-02 | Pass 2 Hindsight | Phase D & I | ⏳ Planned |
| ENR-03 | Gaslighting Detection | Phase I | ⏳ Planned |
| COC-01 | SHA-256 First Touch | Phase A | 🔄 In Progress |
| COC-02 | Hash in All Tiers | Phase B | ⏳ Planned |
| COC-03 | PROV-O in Neo4j | Phase C | ⏳ Planned |
| COC-04 | Pass 1 WORM | Phase D | ⏳ Planned |

---

## Status Legend

- ✅ **Complete** — Task fully finished
- 🔄 **In Progress** — Active development
- ⏳ **Planned** — Scheduled for future implementation
- 🛑 **Blocked** — Awaiting dependency or decision
