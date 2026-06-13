# Sprint Handoff: MCP Tool Platform
## Date: 2026-03-04 | Reviewed by: Claude Opus 4.6 (Sonnet agents for code review)

---

## Architecture Overview

```
Raw File → Coordinator (format detect → right parser)
         → DuckDB    (Tier 1: hash, UUID, dedup, audit trail)
         → Semantica (Neo4j Tier 3: entities, relations, conflicts, provenance, knowledge graph)
         → PostgreSQL (Tier 4: normalized messages, cross-platform reassembly)
         → LanceDB   (Tier 2: embeddings for semantic search)
         → GraphQL   (Retrieval layer: fans out to all tiers, assembles unified response)
```

### Tier Roles (Simplified)

| Tier | Engine | Role | Status |
|------|--------|------|--------|
| 1 | DuckDB | Landing zone. Hash, UUID, dedup. Forensic audit trail | **Working** |
| 2 | LanceDB | Embeddings + semantic search | **Working** (zero-vector placeholder) |
| 3 | Neo4j + Semantica | Entity extraction, relationships, conflicts, provenance, temporal KG | **Python pipeline complete**, not called from Node.js |
| 4 | PostgreSQL | Normalized messages, conversations, cross-platform reassembly | **Schema complete**, write path missing |
| 5 | MySQL | App metadata: users, API keys, settings, behavioral pattern defs | **Working** |
| - | GraphQL | Retrieval orchestrator across all tiers | **Tonight's TODO** |

### Key Design Decisions

- **TrinityRouter is deprecated.** Replace with a simple sequential coordinator (`processDocument()`). No complex routing abstraction needed.
- **Semantica replaces Graphiti** for all Neo4j operations. Graphiti imports must be removed.
- **GraphQL is the retrieval layer**, not a storage tier. Resolvers fan out to each backend and assemble unified responses.
- **One Neo4j database** (`evidence_graph`), not two. Code currently references `temporal_memory` and `semantic_facts` — consolidate.

---

## SPRINT: Immediate (Message Processing End-to-End)

### S1. Build Ingestion Coordinator (replaces TrinityRouter) - VIP PRIORITY

**⚠️ CHAIN OF CUSTODY IS COURT-ADMISSIBLE EVIDENCE - NON-NEGOTIABLE**

**File:** Create `server/mcp/ingest/coordinator.ts` (replaces `server/mcp/storage/systemRouter.ts`)

**What it does:**
1. **SHA-256 hash at first touch** — hash BEFORE any transformation (court admissibility requirement)
2. **UUIDv7 assignment** — time-sortable, globally unique, linked to hash
3. **Deduplication check** — query DuckDB by hash, skip if already exists, return existing UUID if duplicate
4. **Write tracking** — log which tiers successfully received the evidence
5. **Format detection** — examine file extension + magic bytes to determine platform/format
6. **Parser selection** — route to the correct reader (XML SMS, HTML Facebook, PDF iMessage, etc.)
7. **DuckDB landing** — hash (SHA-256), assign UUIDv7, dedup check, log ingestion
8. **Fire to Semantica** — HTTP POST to Python FastAPI service (fire-and-forget, 202 Accepted)
9. **Write to PostgreSQL** — normalized messages into `messagingMessages`, conversations into `messagingConversationsEnhanced`, behaviors into `messagingBehaviors`
10. **Generate embeddings to LanceDB** — use real embeddings from Semantica instead of zero-vectors

**Chain of Custody Requirements (VIP):**
- SHA-256 hash generated **at first touch** (before any transformation)
- Hash stored in DuckDB + LanceDB metadata + Neo4j node properties + PostgreSQL records
- UUIDv7 links all tiers
- Write status tracked per tier
- Never modify original evidence
- Pass 1 enrichment is WORM (Write Once Read Many)
- Forensic audit trail for court admissibility

**Key principles:**
1. **Chain of custody is VIP priority** - hash/ID/tracking MUST be correct
2. **Everything is modular** - each parser, each tier, each step can run independently
3. **Workflows are composable** - can run different flows based on file type, schema, platform
4. **Components are pluggable** - can swap parsers, swap extractors, swap embedders
5. **No dependencies unless needed** - if a step fails, log and continue (except hash/ID which is mandatory)
6. **Format-specific workflows** - SMS XML workflow ≠ Facebook HTML workflow ≠ WhatsApp TXT workflow

**Modular Architecture:**
```
Coordinator
    ├── Format Detector (pluggable, extensible)
    │   ├── SMS XML detector
    │   ├── Facebook HTML detector
    │   ├── WhatsApp TXT detector
    │   └── [add more formats]
    │
    ├── Parsers Registry (each parser independent)
    │   ├── SmsXmlParser
    │   ├── FacebookHtmlParser
    │   ├── ChatgptJsonParser
    │   └── [add more parsers]
    │
    ├── Extractors Pipeline (each extractor independent, configurable)
    │   ├── BehavioralFlagExtractor (regex)
    │   ├── GlinerExtractor (NER)
    │   ├── RecognizersExtractor (dates/phones)
    │   └── [add more extractors]
    │
    ├── Storage Backends (each tier independent, swappable)
    │   ├── DuckDBBackend (hash, UUID, dedup)
    │   ├── PostgreSQLBackend (messages, conversations)
    │   ├── LanceDBBackend (embeddings)
    │   └── Neo4jBackend (knowledge graph via Semantica)
    │
    └── Workflow Engine (configurable per format)
        ├── SMS XML workflow (parse → extract → store → embed)
        ├── Facebook HTML workflow (parse → extract → store → embed)
        └── [create custom workflows]
```

**Each module can:**
- Run standalone (test parser without full pipeline)
- Run in any order (reorder extractors, skip steps)
- Be replaced (swap GLiNER for spaCy NER)
- Be disabled (skip embeddings if not needed for this format)

**References:**
- Current working ingest: `server/mcp/ingest/index.ts` (lines 58-134)
- Memory service client (already written, never called): `server/mcp/memory-service-client.ts`
- PG schema: `server/drizzle/message-schemas.ts`
- DuckDB client: `server/mcp/storage/duckdb.ts`
- LanceDB client: `server/mcp/storage/lancedb.ts`
- PG client: `server/core/db.postgres.ts` and `server/core/db.evidence.ts`

---

### S2. Build Format Readers (Beyond XML)

**Current state:** Only `server/mcp/ingest/readers/SmsXmlReader.ts` exists.

**Readers needed for this sprint:**

| Format | Source | File to Create | Notes |
|--------|--------|----------------|-------|
| XML (SMS Backup & Restore) | Android | `SmsXmlReader.ts` | **EXISTS, working** |
| HTML (Facebook export) | Facebook | `FacebookHtmlReader.ts` | Old `FacebookHTMLParser` exists in `production-pipeline.ts` — extract and modernize |
| JSON (ChatGPT export) | ChatGPT | `ChatgptJsonReader.ts` | Standard OpenAI export format |
| TXT (WhatsApp export) | WhatsApp | `WhatsappTxtReader.ts` | Line-by-line timestamp/sender/message parsing |

**Format detection logic** (for coordinator):
```
.xml → check root element: <smses> = SMS, <thread> = Facebook XML
.html → check for Facebook export markers
.json → check for ChatGPT conversation structure
.txt → check for WhatsApp timestamp patterns
.pdf → iMessage PDF export (future)
```

**Each reader must output a unified `ParsedMessage[]` array:**
```typescript
interface ParsedMessage {
  platform: string;           // 'sms' | 'facebook' | 'whatsapp' | etc.
  sender: string;
  senderNormalized?: string;  // E.164 for phone numbers
  recipient?: string;
  body: string;
  timestamp: Date;
  direction: 'inbound' | 'outbound' | 'unknown';
  messageType: string;        // 'text' | 'mms' | 'photo' | etc.
  rawData: Record<string, any>;  // Original platform-specific data
  attachments?: ParsedAttachment[];
}
```

---

### S3. Wire PostgreSQL Write Path

**Current state:** Schema is 100% complete in `server/drizzle/message-schemas.ts` (718 lines). Tables defined for 9 platforms + unified tables. **No code writes to them.**

**What to build:**
1. After format reader produces `ParsedMessage[]`, write each message to `messagingMessages` table
2. Group messages into conversations, write to `messagingConversationsEnhanced`
3. Run behavioral flag extraction, write flags to `messagingBehaviors`
4. Track source file in `messagingDocuments` (chain of custody)

**PostgreSQL tables to populate (in order):**
1. `messagingDocuments` — source file metadata, hash, chain of custody
2. `messagingConversationsEnhanced` — conversation threads (grouped by participants + time windows)
3. `messagingMessages` — individual messages with sender, body, timestamp, behavior flags
4. `messagingAttachments` — MMS/media linked to messages
5. `messagingBehaviors` — detected behavioral patterns per message

**Key fields on `messagingMessages` that enable cross-platform reassembly:**
- `conversationClusterId` — groups messages across platforms into logical conversations
- `senderNormalized` — E.164 phone numbers / normalized emails for identity matching
- `contentHash` — SHA-256 of body for dedup across platform exports
- `direction` — inbound/outbound relative to the case subject

**Existing identity service:** `server/mcp/forensics/identity-service.ts` handles participant normalization and deterministic conversation ID generation. Use this.

---

### S4. Wire Node.js → Python Semantica Bridge

**Current state:** `server/mcp/memory-service-client.ts` is a **complete, well-written HTTP client** for the Python FastAPI service. It has `ingestMessage()`, `queryMemory()`, `processEvidence()`, `healthCheck()`. **Nothing imports or calls it.**

**What to do:**
1. Import `memory-service-client.ts` into the coordinator
2. After DuckDB landing + PG write, call `processEvidence()` (fire-and-forget)
3. The Python service (`python-tools/memory_service.py`) receives the POST and runs the Semantica pipeline

**Fix in Python service first:**
- `python-tools/memory_service.py` lines 33-35: Remove unconditional `from graphiti_core import Graphiti` — **this crashes on startup** because `graphiti_core` isn't in `requirements.txt`
- Make Semantica the primary engine, not an optional add-on
- Ensure `NEO4J_DATABASE` defaults to `evidence_graph` (not `temporal_memory` or `semantic_facts`)

**Environment variables needed:**
```
MEMORY_SERVICE_URL=http://localhost:8100  # or whatever port the FastAPI service runs on
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<password>
NEO4J_DATABASE=evidence_graph
```

---

### S5. Fix Real Embeddings (Replace Zero-Vectors)

**Current state:** `server/mcp/ingest/index.ts` line 127: `new Float32Array(768)` — all LanceDB embeddings are zeros.

**What to do:**
- Option A: Have the Python Semantica pipeline generate embeddings (Stage 7 of `semantica_pipeline.py`) and POST them back to Node.js for LanceDB storage
- Option B: Call an embedding API directly from Node.js (e.g., OpenAI `text-embedding-3-small` or local model)
- Option C: Have the coordinator wait for Semantica's response before writing to LanceDB (breaks fire-and-forget but simpler)

**Recommended:** Option A — Semantica already generates 768-dim embeddings in Stage 7. Add a callback endpoint in Node.js that receives embeddings and writes to LanceDB. This preserves fire-and-forget for the main pipeline.

---

### S6. GraphQL Retrieval Layer

**Current state:** `server/mcp/graphql/schema.ts` and `server/mcp/graphql/resolvers.ts` exist but resolvers have stubs.

**What resolvers need to do:**
1. **Message queries** — query PG `messagingMessages` with filters (date range, platform, sender, behavior flags)
2. **Semantic search** — query LanceDB for similar messages by embedding
3. **Entity/relationship queries** — query Neo4j via Semantica for entities, relationships, conflicts
4. **Conversation reconstruction** — join across `messagingConversationsEnhanced` → `messagingMessages` → `messagingBehaviors` to rebuild full threaded conversations
5. **Evidence assembly** — pull `messagingEvidenceItems` + `messagingFactorCitations` for court-ready output

**The `extractEntities` resolver** (currently returns "Semantica pipeline integration pending") should query Neo4j for entities linked to a message ID.

---

### S7. Remove Dead Graphiti References

**Active files still importing deprecated Graphiti:**

| File | Issue | Fix |
|------|-------|-----|
| `server/mcp/plugins/graph-analytics.ts:12` | Broken import — file was archived | Remove import, stub or rewire to Semantica |
| `server/api/index.ts:23` | Imports `graphitiRouter` | Remove from API router registration |
| `server/api/routers/graphiti.ts` | Entire router for deprecated system | Delete or archive |
| `server/mcp/storage/neo4j/temporal_memory.ts` | Class named `GraphitiTemporalClient` | Rename, point to `evidence_graph` DB |
| `server/mcp/pipelines/production-pipeline.ts` | References Chroma + old 4-tier system | Archive entire file |
| `python-tools/memory_service.py:33-35` | `from graphiti_core import Graphiti` | **CRASHES ON STARTUP** — remove |
| `server/mcp/memory-service-client.ts:274` | Health response includes `graphiti: boolean` | Update type |

---

### S8. Consolidate Neo4j to Single Database

**Current state:** 3 different database names across 4 files.

| File | Database | Should Be |
|------|----------|-----------|
| `server/mcp/storage/neo4j/temporal_memory.ts` | `temporal_memory` | `evidence_graph` |
| `server/mcp/storage/neo4j/semantic_facts.ts` | `semantic_facts` | `evidence_graph` |
| `python-tools/semantica_pipeline.py` | `evidence_graph` (correct) | `evidence_graph` |
| `python-tools/memory_service.py` | `temporal_memory` + `semantic_facts` | `evidence_graph` |

**Fix:** All Neo4j connections use `NEO4J_DATABASE=evidence_graph`. One database, multiple node labels.

---

## BACKLOG: Nice-to-Have / Future Sprint

### B1. Docker Microservices (External Tools)
- **csvdb** (Rust) - Export evidence databases to CSV/Parquet, version control data
- **pg-index-health** (Java) - PostgreSQL schema linting, anti-pattern detection
- **simple-ddl-parser** (Python) - Extract schema metadata from DDL files
- **omniparser** (Go) - Complex format parsing (EDI, fixed-width, unknown formats)
- **Integration path:** Docker → FastAPI → Meta MCP → Platform API / LLM atomic tools
- **Priority:** Low - not needed for message processing, useful for future schema analysis

### B2. Agent Memory System (`agent-memory.ts`)
- 9 commented-out graphitiClient TODOs
- Provides agent-to-agent coordination, working memory between sessions
- Not needed for message processing — this is for AI agent orchestration
- **Priority:** Low until multi-agent workflows are built

### B2. Additional Format Readers
- PDF iMessage exports
- Instagram DM exports (JSON)
- Snapchat exports
- Google Takeout full archive processing
- Email .mbox/.eml parsing
- Voice transcription files

### B3. Dataset Loader (`python-tools/dataset_loader.py`)
- File is truncated at line 55 — `DatasetLoader` class body is missing
- Should load `.ttl` ontology files using rdflib at startup
- Ontology files exist and are valid (`mcl_722_23.ttl`, `behavioral_patterns.ttl`)
- **Priority:** Medium — ontologies work without this loader, but dynamic ontology loading enables custom case-specific patterns

### B4. Approval System / HITL
- `server/mcp/approval/approval-system.ts` exists (543 lines)
- Human-in-the-loop for reviewing AI-detected behavioral patterns
- **Priority:** Medium — useful for court admissibility but not blocking message processing

### B5. Real-Time Embeddings Pipeline
- Replace zero-vector placeholders with actual embedding generation
- Could use Semantica Stage 7 callback or direct API call
- **Priority:** Medium — semantic search won't work without this, but message processing and storage works fine

### B6. MCP Gateway Dynamic Tool Registration
- `server/mcp/gateway.ts` — dynamic MCP server management
- External MCP tool registration (weather, web search, etc.)
- **Priority:** Low — platform feature, not message processing

### B7. LiteLLM / LLM Proxy Integration
- `config/litellm_config.yaml` exists
- Routes LLM calls through subscription proxying
- **Priority:** Low — cost optimization, not functionality

### B8. Desktop Frontend (ConflictAnalysisApp)
- MCP Client that connects to this platform
- HITL conflict resolution UI
- **Priority:** Future sprint after backend is solid

### B9. Dead Code Cleanup
- `server/mcp/storage/duckdb-forensic-vault.ts` — duplicate DuckDB impl using old API, never imported
- `server/mcp/storage/graphiti-client (2).ts` — draft file with space in name
- `server/mcp/storage/supabase-client.ts` — stub saying "replaced"
- `server/mcp/pipelines/production-pipeline.ts` — old pipeline routing to Supabase/Chroma
- `server/mcp/storage/ingestion-log.ts` + `provenance-chain.ts` — schema stubs, never imported
- **Priority:** Low — doesn't affect functionality, just cleanliness

### B10. Tier Numbering Standardization
- CLAUDE.md says 5-tier, code comments say 6-tier
- MySQL/PostgreSQL tier numbers are swapped between spec and code
- **Priority:** Low — cosmetic, but fix to prevent confusion

---

## Files Reference (Quick Lookup)

### Core Pipeline (Sprint Focus)
| File | Purpose | Status |
|------|---------|--------|
| `server/mcp/ingest/index.ts` | Current ingestion entry point | Working (XML only) |
| `server/mcp/ingest/readers/SmsXmlReader.ts` | XML SMS parser | Working |
| `server/mcp/storage/duckdb.ts` | DuckDB client (Tier 1) | Working |
| `server/mcp/storage/lancedb.ts` | LanceDB client (Tier 2) | Working (zero-vectors) |
| `server/core/db.postgres.ts` | PostgreSQL connection | Working |
| `server/core/db.evidence.ts` | PG evidence database helper | Working |
| `server/drizzle/message-schemas.ts` | Full PG message schema (718 lines) | Complete, unused |
| `server/mcp/memory-service-client.ts` | HTTP client for Python service | Complete, never called |
| `python-tools/semantica_pipeline.py` | 7-stage Semantica pipeline (935 lines) | Complete |
| `python-tools/memory_service.py` | FastAPI service | Crashes (graphiti import) |
| `server/mcp/graphql/schema.ts` | GraphQL type definitions | Exists, needs work |
| `server/mcp/graphql/resolvers.ts` | GraphQL resolvers | Stubs |
| `server/mcp/storage/systemRouter.ts` | TrinityRouter (DEPRECATED) | All stubs — replace with coordinator |

### Ontologies
| File | Purpose | Status |
|------|---------|--------|
| `data/ontologies/mcl_722_23.ttl` | MCL 722.23 best interest factors | Complete, valid OWL |
| `data/ontologies/behavioral_patterns.ttl` | Gaslighting, DARVO, coercive control patterns | Complete, valid OWL |
| `python-tools/dataset_loader.py` | Ontology loader | Truncated — class body missing |

### Supporting Services
| File | Purpose | Status |
|------|---------|--------|
| `server/mcp/forensics/identity-service.ts` | Participant normalization, conversation ID generation | Working |
| `server/mcp/forensics/behavior-service.ts` | Behavioral pattern detection service | Exists |
| `server/mcp/ingest/extractors/BehavioralFlagExtractor.ts` | Regex-based behavioral flags | Working |
| `server/mcp/ingest/extractors/GlinerExtractor.ts` | GLiNER NER extraction | Working |
| `server/mcp/ingest/extractors/RecognizersExtractor.ts` | Microsoft Recognizers extraction | Working |
| `server/mcp/storage/neo4j/semantic_facts.ts` | Neo4j semantic facts client | Exists (wrong DB name) |
| `server/mcp/storage/neo4j/temporal_memory.ts` | Neo4j temporal memory client | Exists (wrong DB name) |
