# Decision Log

## Format
Each entry: Date | Decision | Rationale | Reversible? | Reversal Criteria

---

## 2024-Q3: Project Inception

**2024-07:** Start building forensic evidence platform for Salem v. Kinzel litigation
- **Decision:** Build custom platform rather than use off-the-shelf eDiscovery tools
- **Rationale:** Off-the-shelf tools don't handle modern chat formats (Facebook, iMessage) well. Custom platform allows integration of Semantica NLP for behavioral analysis.
- **Reversible:** Yes, if litigation settles or requirements change
- **Reversal criteria:** Budget overrun >$50K or timeline slip >6 months

**2024-08:** Choose TypeScript/Node.js for initial platform
- **Decision:** Monolithic TypeScript application with tRPC API
- **Rationale:** Fast development, good ecosystem for NLP (compromise.js, Natural.js), single codebase
- **Reversible:** Yes — currently being refactored
- **Reversal criteria:** N/A — already being reversed into modular structure

---

## 2024-Q4: Alpha Completion

**2024-10:** Alpha 1 (mcp-tool-platform) reaches functional state
- **Decision:** Label as "alpha" and begin planning modular v2
- **Rationale:** Monolith has become hard to maintain. NLP pipeline needs Python. Parsers need dedicated tooling. Authentication and storage need proper isolation.
- **67 tools implemented, 45 working, 15 partial, 7 broken**

**2024-11:** Choose modular architecture for v2
- **Decision:** Separate MCP servers per language: TS (parsers/infrastructure), Py (NLP/analysis), JS (document conversion)
- **Rationale:** Each language excels at different tasks. TS for I/O-heavy parsing, Py for ML/NLP, JS for document conversion tools. Avoids language interop complexity.
- **Reversible:** Hard — repos already split
- **Reversal criteria:** Would require merging repos

---

## 2025-Q1: MCP_PLATFORM Current

**2025-01:** Choose FastMCP for MCP server framework
- **Decision:** Use FastMCP (Python) for all three servers
- **Rationale:** MCP is becoming standard for AI tool integration. FastMCP is the most mature Python implementation.
- **Reversible:** Medium — could switch to custom protocol
- **Reversal criteria:** If MCP spec changes significantly or better framework emerges

**2025-02:** Choose DuckDB for forensic vault
- **Decision:** DuckDB (local, embedded) for chain-of-custody and write tracking
- **Rationale:** Court evidence needs immutable audit trail. DuckDB's single-file model makes backup/transport easy. SHA-256 hashing provides integrity.
- **Reversible:** Hard — data already structured for DuckDB
- **Reversal criteria:** Performance issues with >100GB evidence

**2025-03:** Choose LanceDB for vector embeddings
- **Decision:** LanceDB (local, embedded) over ChromaDB (alpha's choice)
- **Rationale:** LanceDB has better performance for large-scale embeddings, integrates well with Arrow, supports hybrid search natively.
- **Reversible:** Medium — embeddings can be re-generated
- **Reversal criteria:** If LanceDB doesn't support required query patterns

---

## 2025-Q2: Agno Control Layer

**2025-04:** Choose Agno for agent framework
- **Decision:** Agno AgentOS over LangChain/LangGraph
- **Rationale:** Agno has native MCP support, built-in knowledge bases, simpler API for our use case. LangGraph is overkill for our workflow needs.
- **Reversible:** Medium — agents are thin wrappers around MCP tools
- **Reversal criteria:** If Agno doesn't support required agent patterns

**2025-04:** Choose pgvector for operational embeddings
- **Decision:** PostgreSQL + pgvector for learned_knowledge, transcript_insight, and platform_docs
- **Rationale:** Single database for operational state keeps MVP simple. pgvector supports 1536-dim embeddings (OpenAI compatible).
- **Reversible:** Easy — can split out later
- **Reversal criteria:** Performance issues with >1M embedded documents

**2025-05:** Add transcript_miner agent
- **Decision:** Dedicated agent for parsing chat transcripts, separate from ingestion
- **Rationale:** Raw transcripts are 50K-500K tokens of noise. Only one agent should read raw text; others get structured insights. Prevents context window exhaustion.
- **Reversible:** Easy — can merge into ingestion later
- **Reversal criteria:** If chunking/processing becomes a bottleneck

**2025-05-25:** Security audit and fixes
- **Decision:** Fix 5 CRITICAL + 10 HIGH + 10 MEDIUM issues found in audit
- **Specific fixes:** Path traversal protection, DB connection pooling, API key auth, MCP process cleanup, Docker hardening, multi-chunk transcript processing
- **Rationale:** MVP was not production-ready. Security issues in a forensic evidence platform are unacceptable.
- **Reversible:** N/A — these are fixes, not decisions

---

## Pending Decisions (Need Owner Approval)

| Date | Decision | Status | Blocked On |
|------|----------|--------|------------|
| TBD | Activate Facebook parser (remove 6-line rejection) | PENDING | Matt approval |
| TBD | Select embedding model (all-MiniLM-L6-v2 vs mpnet vs BGE) | PENDING | Matt decision (OQ-5) |
| TBD | Enable cloud AI services (LlamaParse, DocAI, etc.) | DEFERRED | Matt approval (OQ-4) |
| TBD | Multi-tenancy model (db-per-case vs schema-per-case) | PENDING | Matt decision (OQ-5-new) |
| TBD | Evidence retention policy | PENDING | Matt decision (OQ-6) |
| TBD | Frontend framework (pure React vs CopilotKit) | PENDING | Matt decision (OQ-7) |
| TBD | Testing strategy | PENDING | Matt decision (OQ-8) |
| TBD | OpenCode coding agent integration | PENDING | Matt decision (OQ-4) |
