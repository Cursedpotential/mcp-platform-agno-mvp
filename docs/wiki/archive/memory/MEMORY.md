# dial-stack Project Memory

> This file persists context across sessions. Keep it concise — lines after 200 are truncated.

## Project Overview

**dial-stack** is the next-generation forensic evidence processing platform, evolving from `MCP_Tool_Platform`.

- **Type**: AI DIAL Gateway + 3 MCP Servers (TS, Python, JS)
- **Purpose**: Transform raw messaging exports into temporally-aware, forensically-hashed evidence
- **Court Case**: Salem v. Kinzel, No. 2025-53985-DC (Michigan family court custody)

## Architecture Quick Reference

```
AI DIAL Core (8080) → API Gateway
├── TS MCP Server (8081) — Parsers, DuckDB, PostgreSQL
├── Py MCP Server (8082) — Semantica, LanceDB, Neo4j
└── JS MCP Server (8083) — Utilities, format handlers

Storage Tiers:
- T1: DuckDB (SHA-256, UUIDv7, dedup, master clock)
- T2: LanceDB (vector embeddings, multimodal vault)
- T3: Neo4j (temporal knowledge graph, PROV-O provenance)
- T4: PostgreSQL (normalized evidence, app data)

Retrieval:
- WunderGraph Cosmo (audited, deterministic queries)
- DIAL native tool calls (exploratory, ad-hoc)
```

## Key Directories

| Path | Purpose |
|------|---------|
| `CLAUDE.md` | Agent instructions (READ FIRST) |
| `AGENTS.md` | Multi-agent orchestration guide |
| `docs/ROADMAP.md` | Phase progress tracking |
| `docs/ARCHITECTURE.md` | System design, data flow |
| `docs/TOOL_CATALOG.md` | MCP tool inventory |
| `mcp-servers/ts-mcp-server/` | TypeScript MCP (parsers, storage) |
| `mcp-servers/py-mcp-server/` | Python MCP (Semantica, Neo4j) |
| `infrastructure/core/` | DIAL Core config |
| `client/` | React + CopilotKit frontend |

## Critical Rules

1. **MCP_Tool_Platform is READ-ONLY** — Extract patterns, never modify
2. **No local LLM** — External APIs only (OpenRouter, etc.)
3. **Spec-Driven Development** — All code needs documented plan
4. **Chain of Custody** — SHA-256 at first touch, immutable Pass 1
5. **Lazy Initialization** — Heavy deps load on first use

## Legacy Reference

`MCP_Tool_Platform/` is at `C:\Users\matts\Projects\TheBigOne\MCP_Tool_Platform\`

Key docs to reference (read-only):
- `docs/MCP_TOOL_CATALOG.md` — Tool definitions
- `docs/SEMANTICA_INTEGRATION_GUIDE.md` — NLP patterns
- `docs/SPEC_DRIVEN_DEVELOPMENT.md` — Process

## Current Phase

**Phase A: Foundation & Storage Tools** (~70% complete)

Active work:
- DuckDB → PostgreSQL pipeline wiring
- Health check endpoints
- TS MCP dispatch refactor to registry pattern
- Lazy singletons for database connections

## Recent Sessions

### 2026-03-17
- Project initialized as git repo
- CLAUDE.md, AGENTS.md created
- Memory file established
- Context loaded from MCP_Tool_Platform legacy