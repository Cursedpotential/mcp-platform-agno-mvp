# AI DIAL Stack — Architecture Reference

> [!CAUTION]
> **`MCP_Tool_Platform` is ARCHIVED and STRICTLY READ-ONLY.**
> We only extract data and patterns from it. We never modify, delete, or restructure legacy files.

## System Context

```
/mnt/TheBigOne/
├── MCP_Tool_Platform/      ← ARCHIVED legacy codebase (read-only)
├── dial-stack/             ← THIS PROJECT (new, active development)
│   ├── infrastructure/core/               ← DIAL Core config (OpenAI-compatible gateway)
│   ├── client/             ← React+CopilotKit custom frontend (port 5173)
│   ├── mcp-servers/ts-mcp-server/      ← TypeScript MCP Server (port 8081)
│   ├── mcp-servers/py-mcp-server/      ← Python MCP Server (port 8082)
│   ├── mcp-servers/js-mcp-server/      ← JavaScript MCP Server (port 8083)
│   ├── infrastructure/interceptors/       ← WunderGraph Cosmo federation layer (port 4000)
│   ├── infrastructure/settings/           ← Keycloak config + DIAL settings
│   ├── infrastructure/init/               ← Init scripts for Keycloak & PostgreSQL
│   ├── docker-compose.yml  ← Full stack orchestration
│   └── infrastructure/Caddyfile           ← Reverse proxy (HTTPS, routing)
├── TraceIQ/                ← Separate forensic evidence tracing tool
└── Evidence_Analysis/      ← Conflict analysis scripts (Python)
```

---

## High-Level Architecture

AI DIAL Core acts as the **orchestration gateway**. It presents a unified Chat UI, a custom React frontend with human-in-the-loop capabilities, and an OpenAI-compatible API that routes requests intelligently to either **federated GraphQL queries (WunderGraph Cosmo)** or **ad-hoc MCP tool calls** across three MCP servers. The LLM itself is hosted externally (OpenAI, Anthropic, etc. via OpenRouter) — **no local GPU required**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 CADDY REVERSE PROXY                          │
│                    HTTPS Termination + Routing (port 80/443)                 │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                       │                    │
                    ▼                       ▼                    ▼
        ┌───────────────────┐    ┌──────────────────┐  ┌──────────────────┐
        │  DIAL CHAT        │    │  CUSTOM REACT    │  │  DIAL CORE       │
        │  (port 3000)      │    │  + CopilotKit    │  │  (port 8080)     │
        │  Dev/Admin Chat   │    │  (port 5173)     │  │  OpenAI API      │
        │                   │    │  HITL Review     │  │  Gateway         │
        └───────────────────┘    └──────────────────┘  └──────────────────┘
                                                              │
                      ┌───────────────────────────────────────┼─────────────────────────────────┐
                      │                                       │                                 │
                      ▼                                       ▼                                 ▼
        ┌─────────────────────────┐        ┌──────────────────────────┐    ┌──────────────────┐
        │  EXTERNAL LLM ROUTERS   │        │  DUAL RETRIEVAL LAYER    │    │  KEYCLOAK        │
        │                         │        │                          │    │  (port 8080)     │
        │ • OpenRouter            │        │ WunderGraph Cosmo (4000) │    │  OIDC Provider   │
        │   - OpenAI              │        │ ↓                        │    │  JWT Validation  │
        │   - Anthropic           │        │ Federated queries        │    │                  │
        │   - DeepSeek            │        │ (deterministic, audited) │    └──────────────────┘
        │   - etc.                │        │                          │
        │                         │        │ DIAL Native Tool Calls   │
        │• Azure OpenAI           │        │ ↓                        │
        │                         │        │ Ad-hoc exploratory       │
        └─────────────────────────┘        │ (promotion workflow)     │
                                            └──────────────────────────┘
                                                    │
                ┌───────────────────────────────────┼───────────────────────────────┐
                │                                   │                               │
                ▼                                   ▼                               ▼
    ┌─────────────────────┐        ┌──────────────────────┐        ┌──────────────────┐
    │  TS MCP Server      │        │  Py MCP Server       │        │  JS MCP Server   │
    │  (port 8081)        │        │  (port 8082)         │        │  (port 8083)     │
    │                     │        │                      │        │                  │
    │ • DuckDB Vault      │        │ • Semantica NER      │        │ • Text utilities │
    │ • PostgreSQL Write  │        │ • Graph Builder      │        │ • Format handlers│
    │ • SMS Parser        │        │ • LanceDB Vectors    │        │ • API adapters   │
    │ • Facebook Parser   │        │ • Neo4j Cypher       │        │ • Custom logic   │
    │ • WhatsApp Parser   │        │ • Temporal Extractor │        │                  │
    │ • PDF iMessage      │        │                      │        │                  │
    │ • Format Detector   │        │                      │        │                  │
    └─────────────────────┘        └──────────────────────┘        └──────────────────┘
            │                               │                               │
            └───────────────────────────────┼───────────────────────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
            ┌───────────────┐       ┌──────────────┐        ┌────────────────┐
            │  DuckDB       │       │  PostgreSQL  │        │  Neo4j         │
            │  (Tier 1)     │       │  (Tier 4)    │        │  (Tier 3)      │
            │               │       │              │        │                │
            │ • SHA-256     │       │ • Evidence   │        │ • Temporal KG  │
            │ • Master      │       │   messages   │        │ • PROV-O prov  │
            │   clock       │       │ • Conv data  │        │ • Entities     │
            │ • Dedup       │       │ • Auth data  │        │ • Relations    │
            │ • ETL state   │       │              │        │                │
            └───────────────┘       └──────────────┘        └────────────────┘
                                            │
                                            ▼
                                    ┌──────────────┐
                                    │  LanceDB     │
                                    │  (Tier 2)    │
                                    │              │
                                    │ • Embeddings │
                                    │ • Multimodal │
                                    │   vault      │
                                    │              │
                                    └──────────────┘
```

### Service Ports Summary

| Service | Port | Role |
|---------|------|------|
| Caddy Reverse Proxy | 80, 443 | HTTPS termination, routing |
| DIAL Chat | 3000 | Official DIAL UI (dev/admin) |
| Custom React + CopilotKit | 5173 | HITL review interface |
| DIAL Core | 8080 | OpenAI-compatible API gateway |
| Keycloak | 8180 | OIDC provider |
| TS MCP Server | 8081 | Parsers, PostgreSQL, DuckDB |
| Py MCP Server | 8082 | Semantica, Neo4j, LanceDB |
| JS MCP Server | 8083 | Custom logic, adapters |
| WunderGraph Cosmo | 4000 | GraphQL federation gateway |
| PostgreSQL | 5432 | Evidence + app data |
| Neo4j | 7687 | Knowledge graph |
| Dragonfly (Redis) | 6379 | Session cache |
| Ollama | 11434 | Local embeddings (optional) |

---

## Storage Tiers

A **4-tier architecture** provides intelligent data locality and retrieval patterns:

| Tier | Technology | Purpose | Managed By | Write Model | Query Pattern |
|------|-----------|---------|-----------|-------------|---------------|
| 1 | **DuckDB** | Master clock, SHA-256 fingerprints, ETL state, deduplication | TS MCP | Append-only WORM | Time-series scans |
| 2 | **LanceDB** | Multimodal vault (binary storage + vector embeddings) | Py MCP | Vector index | Semantic similarity |
| 3 | **Neo4j** | Temporal knowledge graph, entities, PROV-O provenance chains | Py MCP | Graph transactions | Cypher queries, traversals |
| 4 | **PostgreSQL** | Relational evidence (messages, conversations, user data, auth) | TS MCP | ACID transactions | SQL, joins, aggregations |

> **KEY CHANGE:** MySQL (legacy Tier 5) was consolidated into PostgreSQL. There is now a **single relational database** for both application metadata and evidence, reducing operational complexity and improving ACID guarantees.

---

## Dual Retrieval Architecture

The system supports **two complementary retrieval modes**, each optimized for different query patterns:

### 1. WunderGraph Cosmo (Deterministic, Auditable)

**Purpose:** Execute **known, proven queries** with full federation and auditability.

- **What:** Federated GraphQL gateway over multiple sources (PostgreSQL, Neo4j, LanceDB)
- **When:** Queries that have been validated and are executed repeatedly
- **Guarantees:**
  - ✅ Auditable execution (full query log in database)
  - ✅ Deterministic results (same input → same output)
  - ✅ Performance optimized (query planning, caching)
  - ✅ Access control enforced at GraphQL schema level
  - ✅ Cost transparent (can measure exact data flows)

**Example:** "Retrieve all messages from this conversation with entity annotations"
→ Proven valuable → Move to a `ConversationMessages` GraphQL operation

### 2. DIAL Native Tool Calls (Exploratory, Ad-hoc)

**Purpose:** Execute **one-off, exploratory queries** without prior schema definition.

- **What:** Direct MCP tool invocation through DIAL orchestration
- **When:** Novel queries, experimental analysis, unpredictable user requests
- **Characteristics:**
  - ✅ Flexible (any tool, any time)
  - ✅ Fast to implement (no schema changes)
  - ❌ Not auditable (bypasses federation layer)
  - ❌ Non-deterministic (depends on tool implementation)

**Example:** "Find all references to a specific date across all chats"
→ User explores → Useful pattern emerges → Move to WunderGraph operation

### Promotion Workflow

```
User Query (ad-hoc)
  ↓
DIAL native tool call execution
  ↓
Pattern matches multiple similar queries?
  ↓
YES → Create WunderGraph operation (schema + resolvers)
  ↓
Future identical queries → Use WunderGraph
```

**Benefits:**
- Start fast with tool calls, graduate to federation
- Audit trail only for critical, repeated queries
- Clear separation: exploratory vs. production
- Easy to promote queries based on usage patterns

---

## Data Flow Diagrams

### Ingestion Flow

```
Raw Evidence Files (PDF, SMS, WhatsApp, iMessage, JSON, etc.)
  │
  ├─→ Format Detector (JS MCP)
  │    └─→ Identify file type
  │
  ├─→ Parser (TS/Py MCP)
  │    ├─ SMS XML Parser
  │    ├─ Facebook HTML Parser
  │    ├─ WhatsApp TXT Parser
  │    ├─ PDF iMessage Parser
  │    └─ JSON/CSV Parser
  │
  ├─→ DuckDB (Tier 1)
  │    └─ SHA-256 fingerprint assigned
  │    └─ Master clock timestamp
  │    └─ Dedup check
  │
  ├─→ PostgreSQL (Tier 4)
  │    └─ Evidence records inserted
  │    └─ Metadata indexed
  │
  ├─→ Semantica NER (Py MCP)
  │    └─ Extract entities (people, places, dates)
  │    └─ Entity linking
  │
  ├─→ Neo4j (Tier 3)
  │    └─ Create nodes (Entity, Event, Document)
  │    └─ Build temporal graph
  │    └─ Store PROV-O provenance
  │
  └─→ LanceDB (Tier 2)
       └─ Vectorize text (via Ollama or external embedding API)
       └─ Store multimodal embeddings
       └─ Enable semantic search
```

### Retrieval Flow

```
User Query (via DIAL Chat or Custom React App)
  │
  ├─→ Keycloak Validation
  │    └─ Verify JWT token
  │    └─ Enforce access roles
  │
  ├─→ DIAL Core Decision Engine
  │    │
  │    ├─ Is this a known WunderGraph operation?
  │    │   YES → Route to WunderGraph Cosmo (port 4000)
  │    │         └─→ Execute federated GraphQL query
  │    │         └─→ Log audit trail
  │    │         └─→ Return deterministic result
  │    │
  │    └─ Is this ad-hoc/exploratory?
  │        YES → Route to DIAL native tool call
  │              ├─→ MCP Tool Dispatch
  │              │   ├─ Tool routing (TS/Py/JS MCP)
  │              │   └─ Parallel tool execution
  │              ├─→ Query Execution
  │              │   ├─ DuckDB scans (time-series)
  │              │   ├─ Neo4j Cypher (graph traversal)
  │              │   ├─ PostgreSQL SQL (joins)
  │              │   └─ LanceDB vectors (similarity)
  │              └─→ Return flexible result
  │
  └─→ Frontend Display
       ├─ DIAL Chat (for developers)
       ├─ Custom React (for analysts with CopilotKit HITL)
       └─ Both support streaming responses + evidence UI
```

---

## Authentication & Security

### OIDC with Keycloak

1. **User Login**
   - Browser → Keycloak (port 8180)
   - Keycloak issues JWT token
   - Token stored in browser localStorage / HttpOnly cookie

2. **Token Validation**
   - Requests to DIAL Core include `Authorization: Bearer {jwt}`
   - DIAL Core validates token against Keycloak JWKS endpoint
   - Role extraction from JWT: `realm_access.roles`

3. **Role-Based Access Control (RBAC)**
   - Roles defined in Keycloak realm
   - Examples: `admin`, `analyst`, `readonly`
   - Enforced at DIAL Core level + optional GraphQL schema level

4. **Configuration** (in `infrastructure/settings/settings.json`)
   ```json
   {
     "identityProviders": {
       "keycloak": {
         "jwksUrl": "http://keycloak:8080/realms/dial/protocol/openid-connect/certs",
         "issuerPattern": "^http://localhost:8080/realms/dial$",
         "rolePath": "realm_access.roles",
         "disableJwtVerification": false
       }
     }
   }
   ```

### API Key Roles

For programmatic access (scripts, integrations):

| Role | Permissions | Use Case |
|------|-----------|----------|
| `admin` | Full read/write, schema changes, user management | Development, operations |
| `default` | Read/write evidence, execute tools | Standard analysts |
| `readonly` | Read-only access to all data | Auditors, viewers |

### HTTPS & Reverse Proxy

- **Caddy** (port 80/443) terminates HTTPS
- Automatic self-signed cert generation (development)
- Routes all traffic through `/chat`, `/api` prefixes
- Protects internal services from direct exposure

---

## Frontend Architecture

### 1. DIAL Chat (port 3000)

Official DIAL Chat UI provided by EPAM. Best for:
- Development and debugging
- Admin tasks
- Quick exploration
- Team collaboration

**Capabilities:**
- Conversation history
- Prompt templates
- Model selection
- Application marketplace
- File attachments

### 2. Custom React App + CopilotKit (port 5173)

Custom single-page application built in-house. Best for:
- **Human-in-the-Loop (HITL) review workflows**
- Evidence analysis with AI assistance
- Interactive evidence tagging
- Custom evidence UI
- Parallel analysis comparisons

**CopilotKit Integration:**
- Provides in-context AI assistance for analysts
- Allows AI to suggest next steps
- Supports custom "copilot actions" for tool integration
- Evidence UI can request AI help on demand
- Maintains chat context while staying in analysis flow

**Stack:**
- React 19
- Vite (dev server on 5173)
- TailwindCSS + Radix UI components
- CopilotKit `@copilotkit/react-core` + `@copilotkit/react-ui`
- Wouter for routing

### Routing Decision

```
User accesses app
  ├─→ HTTPS on localhost:443
  │   └─ Caddy routes to appropriate service
  │
  ├─→ /chat/* → DIAL Chat (port 3000)
  │   └─ Official DIAL for dev/admin
  │
  └─→ / (root) → Custom React App (port 5173)
      └─ HITL evidence analysis interface
```

---

## Key Design Principles

1. **Atomic Tools**
   Each MCP tool does ONE thing well. Composition happens at DIAL orchestration level.

2. **Lazy Loading**
   Heavy dependencies (models, databases) initialized on first use, not startup.

3. **External LLMs Only**
   All inference via hosted APIs (OpenRouter, OpenAI, Azure, Anthropic). No local GPU required, reduces ops burden.

4. **Spec-Driven Development**
   No code without a documented plan (see `SPEC_DRIVEN_DEVELOPMENT.md`). Specs define tool signatures, data schemas, API contracts.

5. **Chain of Custody**
   - SHA-256 fingerprint at first touch
   - UUIDv7 assignment
   - WORM (Write-Once-Read-Many) Pass 1
   - Full provenance recorded in Neo4j (PROV-O)

6. **Dual Retrieval**
   - WunderGraph for deterministic, auditable queries
   - DIAL native for ad-hoc exploration
   - Queries promoted from native → federation based on usage

7. **HITL via CopilotKit**
   - Analysts drive analysis
   - AI provides context-aware suggestions
   - Evidence tagged and reviewed by humans
   - AI learns from corrections

---

## Component Details

### WunderGraph Cosmo

Located at `/dial-stack/infrastructure/interceptors/` (planned).

**Role:** GraphQL federation gateway

**Responsibilities:**
- Accept GraphQL queries
- Route sub-queries to multiple backends (PostgreSQL, Neo4j, LanceDB)
- Merge results
- Log audit trail
- Apply access control

**Deployment:**
```yaml
service: cosmo
image: cosmo-router  # WunderGraph Cosmo image
port: 4000
environment:
  - GRAPHQL_SCHEMA=/etc/cosmo/schema.graphql
  - BACKENDS=postgres://...,neo4j://...
```

### MCP Servers

Each server is a **self-contained microservice** running independently.

#### TS MCP Server (8081)

**Technology:** Node.js + TypeScript + Express

**Tools:**
- `parse_sms_xml` — Extract SMS conversations
- `parse_facebook_json` — Extract Facebook messages
- `parse_whatsapp_txt` — Parse WhatsApp exports
- `parse_pdf_imessage` — Extract iMessage PDFs
- `detect_format` — Identify file type
- `fingerprint_file` — SHA-256 + metadata
- `write_evidence` — Insert into PostgreSQL

**Database Access:**
- PostgreSQL (write evidence records)
- DuckDB (read/write fingerprints, dedup state)

#### Py MCP Server (8082)

**Technology:** Python + FastAPI

**Tools:**
- `extract_entities` — Named Entity Recognition (Semantica)
- `build_graph` — Create temporal KG (Neo4j)
- `semantic_search` — Vector similarity (LanceDB)
- `cypher_query` — Execute Neo4j graph traversals
- `extract_temporal_facts` — Identify events + dates

**Database Access:**
- Neo4j (read/write graph)
- LanceDB (write embeddings, read vectors)
- PostgreSQL (read evidence for analysis)

#### JS MCP Server (8083)

**Technology:** Node.js + JavaScript + Express

**Tools:**
- `transform_text` — Text manipulation utilities
- `extract_regex` — Pattern matching
- `format_json` — JSON transformation
- `call_external_api` — HTTP adapter
- Custom logic hooks

**Database Access:**
- None (stateless, pure logic)

### Semantica NLP Engine

Remains the **primary NLP backbone** for:
- Entity extraction (people, places, organizations, dates)
- Entity linking (resolving duplicate mentions)
- Relationship extraction
- Graph construction
- Temporal reasoning

**Integration Points:**
- Invoked by Py MCP Server
- Results stored in Neo4j + PostgreSQL
- Embeddings sent to LanceDB

---

## Environment Variables

### Mandatory

```bash
# OpenRouter API key (multi-model router)
OPENROUTER_API_KEY=sk-or-v1-...

# PostgreSQL credentials
POSTGRES_USER=dial
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=evidence
DATABASE_URL=postgresql://dial:your_password@postgres:5432/evidence

# Keycloak credentials
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=your_admin_password
```

### Optional (with Defaults)

```bash
# Neo4j (Tier 3)
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

# LanceDB (Tier 2)
LANCEDB_PATH=./data/lancedb/multimodal_vault

# DuckDB (Tier 1)
DUCKDB_PATH=./data/duckdb/forensic_vault.db

# Semantica NLP models
SEMANTICA_NER_MODEL=en_core_web_sm
SEMANTICA_EMBEDDING_MODEL=all-MiniLM-L6-v2
SEMANTICA_CONFIDENCE_THRESHOLD=0.7

# Cloudflare R2 (object storage for large binaries)
R2_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=dial-storage
```

---

## Key Changes from Legacy (MCP_Tool_Platform)

| Component | Legacy | Current | Reason |
|-----------|--------|---------|--------|
| **GraphQL** | WunderGraph deprecated | WunderGraph Cosmo added back | Deterministic, auditable retrieval required |
| **Frontend** | DIAL Chat only | DIAL Chat + Custom React + CopilotKit | HITL analyst workflows + in-context AI |
| **Auth** | None in legacy | Keycloak OIDC | Enterprise auth, multi-user support |
| **LLM** | Local + API mixing | External APIs only (OpenRouter) | Simpler ops, cost transparency, no GPU |
| **ORM** | LangChain | Native MCP + DIAL orchestration | Lighter, faster, more explicit control |
| **Databases** | 5 tiers (MySQL Tier 5) | 4 tiers (consolidated) | Reduced complexity, single ACID store |
| **Knowledge Graph** | Graphiti legacy | Semantica + Neo4j | Modern NLP, cleaner architecture |
| **Retrieval** | Single path (tool calls) | Dual retrieval (WG + DIAL native) | Balance between audit and exploration |
| **Reverse Proxy** | nginx | Caddy | Simpler config, automatic HTTPS |
| **Cache** | Redis | Dragonfly | Drop-in Redis replacement, better perf |

---

## Deployment

### Local Development

```bash
# Start the full stack
docker-compose up -d

# Access services
DIAL Chat:  http://localhost:3000
Custom App: http://localhost:5173
DIAL Core:  http://localhost:8080
Keycloak:   http://localhost:8180
```

### Production (Kubernetes / Cloud)

- Containerize each service
- Use StatefulSets for databases
- Ingress controller for Caddy replacement
- Persistent volumes for DuckDB, LanceDB, PostgreSQL
- Secrets manager for API keys

---

## Debugging & Observability

### Logs

```bash
# DIAL Core logs
docker-compose logs -f core

# MCP Server logs
docker-compose logs -f ts-mcp-server
docker-compose logs -f py-mcp-server
docker-compose logs -f js-mcp-server

# Keycloak logs
docker-compose logs -f keycloak
```

### Database Inspection

```bash
# PostgreSQL
psql postgresql://dial:password@localhost:5432/evidence

# Neo4j Browser
http://localhost:7687

# DuckDB CLI
duckdb ./data/duckdb/forensic_vault.db

# LanceDB Python
python -c "import lancedb; db = lancedb.connect('./data/lancedb'); print(db.table_names())"
```

### Performance Monitoring

- **Dragonfly** (Redis): Monitor cache hit rate
- **PostgreSQL**: Query explain plans, slow log
- **Neo4j**: Graph stats, query profiling
- **WunderGraph Cosmo**: GraphQL query logs
- **DIAL Core**: Request latency, tool call counts

---

## Related Documentation

- **Spec-Driven Development:** `docs/SPEC_DRIVEN_DEVELOPMENT.md`
- **Tool Catalog:** `docs/TOOL_CATALOG.md`
- **Data Sources:** `docs/DATA_SOURCES.md`
- **Architecture Decisions:** `docs/adr/`
- **Roadmap:** `docs/ROADMAP.md`

---

## Version History

- **v2.0** (2026-03-12): Added WunderGraph Cosmo, CopilotKit, Keycloak, dual retrieval, custom React frontend, consolidated MySQL into PostgreSQL
- **v1.0** (2026-03-01): Initial architecture with TS/Py/JS MCP servers, 5 storage tiers, DIAL Chat
