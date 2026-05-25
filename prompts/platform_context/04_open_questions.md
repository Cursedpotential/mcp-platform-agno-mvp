# Open Questions Register

**Rule:** Every entry has a Q-ID, question, context, options, recommendation, and owner. No question stays open forever — each session must resolve at least one.

---

## OQ-1: Embedding Model Selection

| Field | Value |
|-------|-------|
| **Q-ID** | OQ-5 (inherited from GROUND_TRUTH) |
| **Question** | Which sentence-transformers model should be the default for evidence embeddings? |
| **Context** | Currently using `all-MiniLM-L6-v2` (384-dim). Options include larger models with better quality but slower inference. Evidence embeddings are critical for semantic search — once chosen, re-embedding all evidence is expensive. |
| **Options** | A) `all-MiniLM-L6-v2` — fast, 384-dim, good enough (current) | B) `all-mpnet-base-v2` — better quality, 768-dim, slower | C) `BAAI/bge-large-en-v1.5` — best quality, 1024-dim, much slower | D) OpenAI `text-embedding-3-small` — best quality, requires API key |
| **Recommendation** | Start with `all-MiniLM-L6-v2` for MVP. Plan upgrade path to `all-mpnet-base-v2` before production. Keep embedding dimension configurable. |
| **Owner** | Matt |
| **Status** | BLOCKING PY-001 |

---

## OQ-2: Internal API Design

| Field | Value |
|-------|-------|
| **Q-ID** | OQ-7 (inherited from GROUND_TRUTH) |
| **Question** | What should the internal API between Agno control layer and MCP servers look like? |
| **Context** | Currently using MCPTools(command=...) which spawns stdio subprocesses. We could also use HTTP/SSE, gRPC, or GraphQL. The choice affects deployment model, latency, and scalability. |
| **Options** | A) Keep stdio (simplest, works now) | B) HTTP/SSE (FastMCP supports this, works across network) | C) gRPC (best performance, more complex) | D) GraphQL via WunderGraph (already configured in docker-compose) |
| **Recommendation** | HTTP/SSE for production. Stdio for local dev. Implement both in MCPTools configuration so the same code works in both modes. |
| **Owner** | Matt |
| **Status** | BLOCKS Agno/n8n/Directus integration |

---

## OQ-3: Cloud API Approval Gate

| Field | Value |
|-------|-------|
| **Q-ID** | OQ-4 (inherited) |
| **Question** | Which cloud AI services (if any) should be enabled? |
| **Context** | Seven Google Cloud Document AI plugins are deferred. Each requires: API key, billing setup, data privacy review (court evidence going to cloud), and per-engine approval. |
| **Options** | A) None — keep everything local (current) | B) LlamaParse only — best PDF parsing | C) Google DocAI only — best document understanding | D) All — enable everything with budget caps |
| **Recommendation** | Start with none for MVP. Court evidence has strict chain-of-custody requirements that cloud APIs may violate. Evaluate LlamaParse for non-sensitive preprocessing only. |
| **Owner** | Matt |
| **Status** | DEFERRED |

---

## OQ-4: OpenCode Coding Agent Integration

| Field | Value |
|-------|-------|
| **Q-ID** | OQ-10 (inherited) |
| **Question** | Should OpenCode (or similar AI coding agent) be integrated for automated code generation? |
| **Context** | The dev_copilot agent currently proposes changes as text. An integrated coding agent could actually write and test code. |
| **Options** | A) No — keep dev_copilot advisory only | B) OpenCode with approval gates — writes code, requires HITL approval | C) Full automation — OpenCode writes and commits directly |
| **Recommendation** | Option B. OpenCode for automated implementation with mandatory review_gatekeeper approval for any code changes. Never auto-commit to main. |
| **Owner** | Matt |
| **Status** | NOT STARTED |

---

## OQ-5: Multi-Tenancy Model

| Field | Value |
|-------|-------|
| **Q-ID** | NEW |
| **Question** | How should multiple cases/litigations be isolated in the platform? |
| **Context** | Currently no tenant isolation. PostgreSQL, DuckDB, Neo4j are shared. For a platform holding evidence from multiple cases, this is a legal liability. |
| **Options** | A) Database-per-case (strong isolation, more overhead) | B) Schema-per-case (moderate isolation, shared resources) | C) Row-level security with case_id (lightweight, less isolation) | D) Single shared database with access control (simplest, least isolation) |
| **Recommendation** | Schema-per-case for MVP. Strong enough for court requirements, manageable overhead. Plan database-per-case for production. |
| **Owner** | Matt |
| **Status** | NOT STARTED |

---

## OQ-6: Evidence Retention Policy

| Field | Value |
|-------|-------|
| **Q-ID** | NEW |
| **Question** | How long should processed evidence be retained? What about embeddings and derived analysis? |
| **Context** | Alpha used 72-hour TTL for ChromaDB working memory. Court proceedings may span months or years. Storage costs grow with retention. |
| **Options** | A) Indefinite — keep everything forever | B) Case-duration — retain until case closes + appeal period | C) Tiered — hot (30 days), warm (case duration), cold (archive post-case) | D) Evidence-only — keep raw evidence forever, purge derived data |
| **Recommendation** | Option C with tiered storage. Raw evidence = indefinite (legal requirement). Derived analysis = case duration + 2 years. Working memory = 30 days TTL. |
| **Owner** | Matt |
| **Status** | NOT STARTED |

---

## OQ-7: Frontend Framework for HITL UI

| Field | Value |
|-------|-------|
| **Q-ID** | NEW |
| **Question** | Should the HITL UI be React (already scaffolded) or should we use CopilotKit for AI-native interactions? |
| **Context** | React client exists with 6 pages but no CopilotKit. CopilotKit would give the UI native AI capabilities (inline suggestions, streaming responses). |
| **Options** | A) Pure React — simpler, more control | B) React + CopilotKit — AI-native UX, more dependencies | C) OpenWebUI / LibreChat (planned in GROUND_TRUTH) — full chat interface |
| **Recommendation** | Start with pure React for approval workflow (simplest). Add CopilotKit later for the builder agent chat interface. Evaluate OpenWebUI for end-user chat. |
| **Owner** | Matt |
| **Status** | NOT STARTED |

---

## OQ-8: Testing Strategy

| Field | Value |
|-------|-------|
| **Q-ID** | NEW |
| **Question** | What's the minimum viable testing approach? Zero tests exist across all repos. |
| **Context** | For a forensic evidence platform, test coverage is legally and practically critical. But writing comprehensive tests for 67 tools is months of work. |
| **Options** | A) Integration tests only — test end-to-end pipelines with fixture data | B) Unit + integration — test each tool + pipeline | C) Property-based testing — generate random evidence, verify invariants | D) All of the above — comprehensive (expensive) |
| **Recommendation** | Start with A: integration tests for each parser pipeline (input file → parsed → hashed → stored). These give the most value per hour. Add unit tests for complex logic (pattern analyzer, NLP). |
| **Owner** | Matt |
| **Status** | NOT STARTED |

---

## Resolved Questions

| Q-ID | Question | Resolution | Date |
|------|----------|------------|------|
| OQ-1 | Modular vs monolithic MCP servers | Modular per language | 2024 |
| OQ-2 | Agno vs LangChain vs custom | Agno AgentOS | 2024 |
| OQ-3 | PostgreSQL vs other for operational state | PostgreSQL + pgvector | 2024 |
| OQ-6 | HITL required for all writes? | Yes — mandatory | 2024 |
| OQ-9 | SHA-256 at first touch? | Yes — non-negotiable | 2024 |
