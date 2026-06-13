# dial-stack — Project Overview

> **dial-stack is the evolution of MCP_Tool_Platform.**
> The legacy `MCP_Tool_Platform/` directory is archived and read-only.

---

## What This Is

**dial-stack** is the next-generation forensic evidence processing platform. It replaces the rigid God Pipeline architecture with **AI DIAL orchestration** — dynamic, intelligent routing of evidence through federated MCP tool servers.

### Key Architectural Shifts from Legacy

| Aspect | Legacy (MCP_Tool_Platform) | Current (dial-stack) |
|--------|---------------------------|----------------------|
| **Orchestration** | TrinityRouter God Pipeline | AI DIAL Core dynamic routing |
| **Retrieval** | Single path (tool calls) | Dual (WunderGraph + DIAL native) |
| **Database** | 5-tier (MySQL Tier 5) | 4-tier (consolidated PostgreSQL) |
| **Graph** | Graphiti | Semantica + Neo4j |
| **Frontend** | DIAL Chat only | DIAL Chat + React/CopilotKit HITL |
| **Auth** | None | Keycloak OIDC |
| **LLM** | Local + API mixing | External APIs only (OpenRouter) |
| **Cache** | Redis | Dragonfly |

---

## Court Case Context

**Case:** Salem v. Kinzel, No. 2025-53985-DC
**Court:** Genesee County 7th Circuit Court, Family Division
**Litigant:** Matt Salem (pro se — self-represented)
**Child:** Kailah (age 5)
**Nature:** Custody dispute involving allegations of behavioral manipulation, coercive control, and parental alienation

### Evidence Processing Pipeline

```
Raw Evidence Files
    │
    ├── Format Detection (JS MCP)
    │
    ├── Parser Selection (TS/Py MCP)
    │   ├── SMS XML Parser
    │   ├── Facebook HTML Parser
    │   ├── WhatsApp TXT Parser
    │   ├── PDF iMessage Parser
    │   └── JSON/CSV Parser
    │
    ├── DuckDB (Tier 1) — SHA-256, UUIDv7, dedup
    │
    ├── PostgreSQL (Tier 4) — Normalized evidence records
    │
    ├── Semantica NLP (Py MCP)
    │   ├── Entity extraction → Neo4j nodes
    │   ├── Relation extraction → Neo4j edges
    │   └── Temporal facts → valid_from/valid_to
    │
    └── LanceDB (Tier 2) — Vector embeddings
```

---

## Project Structure

```
dial-stack/
├── CLAUDE.md                    # Agent instructions (read first)
├── AGENTS.md                    # Multi-agent orchestration guide
├── docs/
│   ├── ARCHITECTURE.md          # System design, data flow
│   ├── ROADMAP.md               # Phase progress tracking
│   ├── TOOL_CATALOG.md          # MCP tool inventory
│   ├── SPEC_DRIVEN_DEVELOPMENT.md
│   └── specs/                   # Module specifications
├── infrastructure/
│   ├── core/                    # DIAL Core config
│   ├── settings/                # Keycloak + DIAL settings
│   └── docker-compose.yml       # Full stack
├── mcp-servers/
│   ├── ts-mcp-server/           # Parsers, DuckDB, PostgreSQL
│   ├── py-mcp-server/           # Semantica, LanceDB, Neo4j
│   └── js-mcp-server/           # Utilities, adapters
├── client/                      # React + CopilotKit frontend
└── migrations/                   # Database migrations
```

---

## Current Development Phase

**Phase A: Foundation & Storage Tools** (~70% complete)

### Completed
- [x] TS MCP Server scaffolding with TypeScript MCP SDK
- [x] DuckDbVault tool (SHA-256, UUIDv7, dedup)
- [x] PostgresWriter tool
- [x] PostgreSQL init scripts with pgvector
- [x] Semantica NLP pipeline (11 tools in py-mcp-server)
- [x] LanceDB tools (vector search, upsert)
- [x] Neo4j tools (Cypher queries)

### In Progress
- [ ] Wire DuckDB → PostgreSQL ingestion pipeline
- [ ] Health check endpoints for all storage connections
- [ ] TS MCP dispatch refactor (registry pattern)
- [ ] Lazy singletons for database connections

### Planned
- [ ] WunderGraph Cosmo federation
- [ ] Keycloak container in docker-compose
- [ ] React + CopilotKit HITL dashboard

---

## Running the Stack

```bash
# Build and start all containers (from WSL)
wsl -u root podman-compose up -d --build

# Check container status
wsl -u root podman ps -a

# View logs
wsl -u root podman logs dial-stack_core_1
```

---

## Related Projects

| Project | Status | Relationship |
|---------|--------|--------------|
| `MCP_Tool_Platform/` | Archived | Legacy codebase (read-only reference) |
| `TraceIQ/` | Active | Location history processor (feeds into dial-stack) |
| `Evidence_Analysis/` | Resource | Pattern definitions and conflict scripts |

---

## GSD Status

| Phase | Status |
|-------|--------|
| Phase A: Foundation | 🔄 ~70% |
| Phase B: Parsers | 🔄 ~60% |
| Phase C: Semantica | 🔄 ~80% |
| Phase D: Enrichment | ⏳ Planned |
| Phase E: Security | 🔄 In Progress |
| Phase F: Federation | ⏳ Planned |
| Phase G: Frontend | ⏳ Planned |
| Phase H: Deployment | ⏳ Planned |

---

*Last updated: 2026-03-17*