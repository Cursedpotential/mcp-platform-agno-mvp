# Architecture Overview: MCP_PLATFORM Ecosystem

## Three Repositories

| Repository | Role | State |
|------------|------|-------|
| **mcp-platform-agno-mvp** (this repo) | Agno control layer — agents, orchestration, HITL | MVP v0.1.1, just audited and fixed |
| **MCP_PLATFORM** (current) | Modular MCP servers — TS/Py/JS, databases, infra | Partially built, heavily gated on approvals |
| **mcp-tool-platform** (alpha) | Monolithic working platform — 67 tools, 45 working | Legacy, being ported piece by piece |

## How They Connect

```
┌──────────────────────────────────────────────────────────────┐
│                    AGNO CONTROL LAYER                         │
│  (this repo — FastAPI + AgentOS + 7 agents)                  │
│                                                               │
│  Platform Agents: ingestion, analysis, review, transcript    │
│  Builder Agents: dev_copilot, project_pal, forensic_data     │
└──────────────┬────────────────────────────────┬──────────────┘
               │ MCPTools(command=...)          │ MCPTools(command=...)
               ▼                                ▼
┌─────────────────────────────┐  ┌─────────────────────────────────────┐
│   TS MCP SERVER (port 8081) │  │   PY MCP SERVER (port 8082)         │
│   TypeScript / FastMCP      │  │   Python / FastMCP                  │
│                             │  │                                     │
│   • parse_sms_xml ✅        │  │   • semantica_extract_entities ✅    │
│   • parse_facebook_export ⚠️│  │   • semantica_build_graph ✅         │
│   • parse_imessage_pdf ❌   │  │   • semantica_generate_embeddings ✅ │
│   • vault_log_ingestion ✅  │  │   • lancedb_vector_search ✅         │
│   • postgres_write_record ✅│  │   • neo4j_cypher_query ✅            │
│   • review_queue ✅         │  │   • dpk_hap_score ✅                 │
│   • EvidenceIngestor ⚠️     │  │   • dpk_pii_redact ✅                │
│   • Pass1Runner ⚠️          │  │   • fingerprint_voice ✅             │
│   • MessageChunker ✅       │  │   • user_darvo_detection ✅          │
│                               │  │   • workflow_list/run ✅             │
└──────────────┬────────────────┘  └────────────────────┬────────────────┘
               │                                        │
               ▼                                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         DATA STORES                                   │
│                                                                       │
│   PostgreSQL + pgvector — evidence records, approvals, embeddings    │
│   DuckDB — forensic vault with SHA-256 hashes, chain of custody      │
│   Neo4j — semantic knowledge graphs (empty — needs population)       │
│   LanceDB — vector embeddings for semantic search                     │
└──────────────────────────────────────────────────────────────────────┘
```

Legend: ✅ working | ⚠️ partial/blocked | ❌ stub/missing

## Key Architectural Decisions (Already Made)

1. **Modular MCP servers per language** — TS for parsers/infrastructure, Py for NLP/analysis, JS for document conversion. Decided to avoid language interop hell.
2. **Agno AgentOS as control layer** — Agents orchestrate via MCPTools rather than calling APIs directly. Keeps tool discovery uniform.
3. **PostgreSQL + pgvector for operational state** — Single DB for approvals, agent runs, learned knowledge, transcript insights. Keeps MVP simple.
4. **Human-in-the-loop for all writes** — No automated evidence modification without approval. Risk levels: low/medium/high/critical.
5. **SHA-256 at first touch** — Every evidence file is hashed before any processing. Chain of custody is non-negotiable.
6. **W3C PROV-O for provenance** — All analysis outputs must include provenance metadata for court admissibility.

## What "Porting" Means

Porting a tool from alpha to current means:
1. Extract the tool logic from the alpha monolith
2. Reimplement it as an MCP tool in the appropriate language server (TS for parsers, Py for NLP)
3. Wire it into the server's tool registration (FastMCP `server.add_tool()`)
4. Add integration tests
5. Update the PARITY_MATRIX.md
6. Update GROUND_TRUTH.md if behavior changes

Porting is NOT a blind copy-paste. The modular structure has different interfaces:
- Alpha uses tRPC routers with Zod validation
- Current uses FastMCP with Python-style tool registration
- Storage backends have different client APIs (ChromaDB in alpha → LanceDB/pgvector in current)
