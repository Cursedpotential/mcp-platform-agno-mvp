# AI DIAL Stack — Agent Instructions

**Project**: AI DIAL MCP Tool Stack
**Type**: Forensic evidence processing platform with federated MCP tool servers
**Architecture**: AI DIAL Gateway + 3 MCP Servers (TS, Python, JS)
**Development Process**: Spec-Driven (see `docs/SPEC_DRIVEN_DEVELOPMENT.md`)

---

## STOP — Read Before Doing Anything

### Critical Rules

> **RULE 1: `MCP_Tool_Platform` is ARCHIVED and STRICTLY READ-ONLY.**
> - DO NOT delete, modify, move, or restructure ANY files in `../MCP_Tool_Platform/`
> - You may only READ from it to extract patterns and data
> - This is NON-NEGOTIABLE

> **RULE 2: This project is a SIBLING directory.**
> - `dial-stack/` lives at `C:\Users\matts\Projects\TheBigOne\dial-stack\`
> - It is NEVER nested inside `MCP_Tool_Platform`
> - Never create new code inside the legacy directory

> **RULE 3: No local LLM hosting.**
> - The user has limited GPU resources
> - All LLM inference uses external APIs (OpenAI, Azure, Bedrock, etc.)
> - AI DIAL Core acts as the API gateway to hosted models

> **RULE 4: No deletions anywhere.**
> - Do not delete files from `MCP_Tool_Platform` or any other existing project
> - Build new, don't destroy old

### Mandatory Reading Before ANY Work

1. **`docs/SPEC_DRIVEN_DEVELOPMENT.md`** — The development process
2. **`docs/ROADMAP.md`** — Phase-level progress and requirement traceability
3. **`docs/ARCHITECTURE.md`** — System design, data flow, tier definitions
4. **`docs/PIPELINE_DECISION.md`** — Processing pipeline architecture decision (Option 2)
5. **`docs/TOOL_CATALOG.md`** — Complete tool inventory across all MCP servers
6. **`docs/DATA_SOURCES.md`** — External data sources (D: drive, mono-repo layout)

---

## Architecture Quick Reference

### Infrastructure
- **AI DIAL Core** (port 8080) — OpenAI-compatible API gateway
- **AI DIAL Chat** (port 3000) — Web UI frontend
- **Dragonfly** (port 6379) — Redis-compatible cache
- **DIAL Themes** (port 3001) — UI theming service
- **Keycloak** (port 8180) — OIDC identity provider, JWT auth
- **WunderGraph Cosmo** (port 4000) — GraphQL federation across all storage tiers
- **React + CopilotKit** (port 3002) — HITL evidence review dashboard

### MCP Tool Servers
- **TS MCP Server** (port 8081) — Parsers, DuckDB, PostgreSQL
- **Py MCP Server** (port 8082) — Semantica, LanceDB, Neo4j
- **JS MCP Server** (port 8083) — Docling, Pandoc, legacy JS tools

### Storage Tiers

| Tier | Technology | What It Stores | Role |
|------|-------------|----------------|------|
| **Shared** | FileSystem | ONE COPY of binaries | Source of truth |
| **T1** | DuckDB | Transformations, hashes, metadata | First drop, forensic processing |
| **T2** | PostgreSQL | Normalized relational data | Canonical UUID mapping |
| **T3** | LanceDB | Vector embeddings | Semantic search |
| **T4** | Neo4j | Entities, relationships | Knowledge graph (via Semantica) |

### Processing Pipeline (Option 2)

```
DuckDB (T1) → PostgreSQL (T2) → [LanceDB (T3) + Neo4j (T4)] PARALLEL
```

**Why PostgreSQL First:** See `docs/PIPELINE_DECISION.md` for full rationale.

### Key Changes from Legacy
- MySQL (Tier 5) **consolidated into PostgreSQL**
- LangChain/LangGraph **dropped** — native MCP + DIAL orchestration
- Supabase **dropped** — self-hosted PostgreSQL
- Graphiti **deprecated** — Semantica handles all graph operations
- TrinityRouter **deprecated** — DIAL handles routing dynamically

### Dual Retrieval Architecture

- **WunderGraph Cosmo** — Primary retrieval layer for deterministic, auditable, cross-tier queries
- **DIAL Native Tool Calls** — Secondary layer for ad-hoc exploratory queries
- **Promotion Workflow**: Ad-hoc DIAL queries that prove useful get promoted into WunderGraph federated schemas
- Both layers coexist — WunderGraph for production/legal queries, DIAL for discovery

### Authentication

- **Keycloak** provides OIDC/JWT authentication for all services
- Roles: `admin`, `default`, `readonly`
- DIAL Core validates JWT tokens via Keycloak JWKS endpoint
- React frontend uses Keycloak OIDC login flow

### Frontend Architecture

- **DIAL Chat** (port 3000) — Dev/admin interface for direct tool interaction
- **React + CopilotKit** (port 3002) — Analyst-facing HITL dashboard for evidence review, entity resolution, timeline viewing
- Both frontends coexist serving different user roles

---

## Running the Stack

```bash
# Build and start all containers (from WSL)
wsl -u root podman-compose up -d --build

# Check container status
wsl -u root podman ps -a

# View logs for a specific service
wsl -u root podman logs dial-stack_core_1

# Stop everything
wsl -u root podman-compose down
```

Access the Chat UI at `http://localhost:3000`

---

## Development Patterns

### Adding a New Tool to TS MCP Server

1. Create the tool file in `mcp-servers/ts-mcp-server/src/tools/YourTool.ts`
2. Follow the `*Parser` or `*Writer` naming convention
3. Export it from `mcp-servers/ts-mcp-server/src/index.ts`
4. Add entry to `docs/TOOL_CATALOG.md`
5. Update `infrastructure/core/config.json` if needed

### Adding a New Tool to Py MCP Server

1. Create the tool file in `mcp-servers/py-mcp-server/src/your_tools.py`
2. Use `@mcp.tool()` decorator from FastMCP
3. Register in `mcp-servers/py-mcp-server/src/server.py`
4. Add entry to `docs/TOOL_CATALOG.md`

### Lazy Loading Pattern

Heavy dependencies must be initialized on first use, not at import time:

```typescript
// ✅ CORRECT — Lazy initialization
let duckdbInstance: Database | null = null;
async function getDuckDb() {
  if (!duckdbInstance) {
    const duckdb = await import('duckdb');
    duckdbInstance = new duckdb.Database(':memory:');
  }
  return duckdbInstance;
}

// ❌ WRONG — Eager initialization
import duckdb from 'duckdb';
const db = new duckdb.Database(':memory:'); // blocks server startup
```

---

## Common Pitfalls

| Pitfall | Why It's Wrong |
|---------|---------------|
| Nesting code inside `MCP_Tool_Platform` | Violates separation of concerns |
| Using Graphiti | Deprecated — use Semantica |
| Using LangChain | Dropped — use native MCP |
| Direct database access (bypassing tools) | Bypasses chain of custody |
| Hosting LLMs locally | User has limited GPU |
| Modifying Pass 1 results | Violates WORM immutability |
| Forgetting to update TOOL_CATALOG.md | Tools become undiscoverable |
| Using Ollama or local LLMs in production | Contradicts Rule 3 — use external APIs |
| Skipping WunderGraph for legal/audit queries | Deterministic queries need federation layer |

---

## Mandatory: Skill Creation for New Dependencies

> **RULE 5: Every adopted library, tool, or 3rd-party application MUST have a corresponding skill document.**
>
> When bringing any new library or external tool into the ecosystem:
> 1. Create a skill document in `docs/wiki/skills/<category>/<tool-name>.md`
> 2. Include: purpose, version, configuration, API patterns, integration points, common pitfalls
> 3. Store a local copy of key documentation excerpts (not full docs — just essential reference)
> 4. Update `docs/wiki/INDEX.md` with the new entry
> 5. This is NON-NEGOTIABLE — undocumented dependencies create invisible risk

### Skill Document Template

```markdown
# <Tool Name> — Skill Reference

## Overview
- **What**: One-line description
- **Version**: Current version in use
- **Category**: infrastructure | database | nlp | frontend | orchestration | security | utility
- **Installed In**: Which MCP server or service uses this

## Configuration
Key env vars, config files, connection strings.

## API Patterns
Most-used API calls and patterns specific to this project.

## Integration Points
How this tool connects to other components in the stack.

## Common Pitfalls
Known gotchas specific to our usage.

## References
- Official docs URL
- Local reference: `docs/wiki/references/<tool>/`
```

---

**Last Updated:** March 12, 2026
**Architecture:** AI DIAL + 3 Federated MCP Servers + WunderGraph Cosmo + Keycloak + CopilotKit
**Current Phase:** Phase A (Foundation & Storage Tools) — See ROADMAP.md
**Process:** Spec-Driven — See docs/SPEC_DRIVEN_DEVELOPMENT.md
