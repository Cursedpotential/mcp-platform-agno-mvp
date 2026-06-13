# dial-stack Skills & Architecture Reference

This wiki documents the **core dependencies** that power the dial-stack — a production-grade agentic RAG system for temporal knowledge graphs and conflict detection.

## Quick Navigation

### Infrastructure
Foundation services that keep the system running.

- **[AI DIAL Core](skills/infrastructure/ai-dial-core.md)** — OpenAI-compatible API gateway, model routing, application orchestration
- **[Docker Compose](skills/infrastructure/docker-compose.md)** — Service orchestration, networking, volumes
- **[Caddy](skills/infrastructure/caddy.md)** — Reverse proxy with auto-TLS and auth fallback
- **[Dragonfly](skills/infrastructure/dragonfly.md)** — Redis-compatible cache for sessions and embeddings

### Database Tier
Layered data architecture: analytics → relational → graph → vectors.

- **[DuckDB](skills/database/duckdb.md)** — Master analytics layer, hashing, temporal indexing
- **[PostgreSQL](skills/database/postgresql.md)** — Unified relational store with pgvector
- **[Neo4j](skills/database/neo4j.md)** — Graph layer for knowledge relationships and temporal facts
- **[LanceDB](skills/database/lancedb.md)** — Vector store for embedding similarity search

### NLP & Processing
Semantics extraction and tool integration.

- **[Semantica](skills/nlp/semantica.md)** — Custom NLP pipeline: NER, relations, temporal facts, conflict detection
- **[FastMCP](skills/nlp/fastmcp.md)** — Python SDK for building MCP tool servers

### Frontend & UI
User-facing interfaces and interaction frameworks.

- **[DIAL Chat](skills/frontend/dial-chat.md)** — AI DIAL Chat UI (v0.26.0), theming, admin portal
- **[CopilotKit](skills/frontend/copilotkit.md)** — React HITL framework for evidence review workflows
- **[React](skills/frontend/react.md)** — React 19 + Vite + Tailwind for analyst dashboard

### Orchestration & Integration
Cross-tier query patterns and tool protocols.

- **[WunderGraph Cosmo](skills/orchestration/wundergraph-cosmo.md)** — GraphQL federation, subgraph composition
- **[MCP Protocol](skills/orchestration/mcp-protocol.md)** — Model Context Protocol for tool discovery and invocation

### Security & Identity
Authentication and authorization.

- **[Keycloak](skills/security/keycloak.md)** — OIDC provider, JWT, realm configuration

### Gateway & Federation
MCP gateway, protocol translation, plugin system.

- **[IBM ContextForge](IBM_CONTEXTFORGE.md)** — MCP gateway, federation, 40+ plugins (PII, moderation, secrets)
- **[ContextForge Implementation Analysis](CONTEXTFORGE_IMPLEMENTATION_ANALYSIS.md)** — Detailed integration options for dial-stack
- **[Proposed Architecture](PROPOSED_ARCHITECTURE_CONTEXTFORGE_DIAL.md)** — ContextForge + DIAL integration with workflow simulations

### Utilities
External integrations and helpers.

- **[OpenRouter](skills/utility/openrouter.md)** — Multi-model LLM API router

### Parsers & Format Detection
Convert source documents and messages into standardized ingestion formats.

- **[ChatGPT JSON Parser](skills/utility/parsers/chatgpt-json-parser.md)** — Parse ChatGPT export JSON
- **[Facebook HTML Parser](skills/utility/parsers/facebook-html-parser.md)** — Extract Facebook message threads from HTML exports
- **[Google Timeline Parser](skills/utility/parsers/google-timeline-parser.md)** — Parse Google Location Timeline JSON
- **[iMessage PDF Parser](skills/utility/parsers/imessage-pdf-parser.md)** — Extract iMessage conversations from PDF
- **[SMS XML Parser](skills/utility/parsers/sms-xml-parser.md)** — Parse Android SMS/MMS XML backups
- **[WhatsApp TXT Parser](skills/utility/parsers/whatsapp-txt-parser.md)** — Parse WhatsApp chat exports (text format)

### Document Processing
File conversion, chunking, and format detection utilities.

- **[Archive Extractor](skills/utility/document-processing/archive-extractor.md)** — Extract ZIP, TAR, 7z archives
- **[Chunker](skills/utility/document-processing/chunker.md)** — Split documents into overlapping semantic chunks
- **[Format Detector](skills/utility/document-processing/format-detector.md)** — Identify file type and encoding
- **[Pandoc](skills/utility/document-processing/pandoc.md)** — Universal document converter (PDF, DOCX, HTML, Markdown)
- **[Docling](skills/utility/document-processing/docling.md)** — PDF to Markdown extraction with layout preservation
- **[MinerU](skills/utility/document-processing/mineru.md)** — Deep learning PDF parsing with OCR

### Pending Integrations
Planned utilities for future integration.

- **[GCP Document AI](skills/utility/pending/gcp-document-ai.md)** — Structured document understanding (invoices, forms)
- **[GCP Natural Language](skills/utility/pending/gcp-natural-language.md)** — Cloud-based NER, sentiment, entity linking
- **[GCP Vision](skills/utility/pending/gcp-vision.md)** — OCR and image text extraction
- **[Archive Extractor (Pending)](skills/utility/pending/archive-extractor.md)** — Enhanced archive support
- **[Chunker (Pending)](skills/utility/pending/chunker.md)** — Advanced chunking strategies
- **[Format Detector (Pending)](skills/utility/pending/format-detector.md)** — Expanded format detection

### MCP Tool Documentation
Complete tool reference for all three MCP servers.

- **[TS MCP Server Tools](tools/ts-mcp-server.md)** — 18 built tools: parsers, vault/storage, admin, review queue
- **[Py MCP Server Tools](tools/py-mcp-server.md)** — 22 built tools: semantica, vector search, graph query, DPK, voice, workflows
- **[JS MCP Server Tools](tools/js-mcp-server.md)** — 1 built (placeholder), 4 planned: Docling, Pandoc, parsers

---

## Architecture Layers

```
┌─────────────────────────────────────────────────┐
│ Frontend (React 19 + DIAL Chat + CopilotKit)    │
├─────────────────────────────────────────────────┤
│ Orchestration (Cosmo GraphQL + MCP)             │
├─────────────────────────────────────────────────┤
│ NLP Processing (Semantica + FastMCP)            │
├─────────────────────────────────────────────────┤
│ Database Tier (DuckDB → PG → Neo4j → Lance)     │
├─────────────────────────────────────────────────┤
│ Infrastructure (DIAL Core + Docker + Caddy)     │
└─────────────────────────────────────────────────┘
```

---

## Getting Started

1. **Set up services**: See [Docker Compose](skills/infrastructure/docker-compose.md)
2. **Understand the DB architecture**: [DuckDB](skills/database/duckdb.md) → [PostgreSQL](skills/database/postgresql.md)
3. **Build NLP pipelines**: [Semantica](skills/nlp/semantica.md) + [FastMCP](skills/nlp/fastmcp.md)
4. **Connect the frontend**: [DIAL Chat](skills/frontend/dial-chat.md) + [CopilotKit](skills/frontend/copilotkit.md)
5. **Federate APIs**: [Cosmo](skills/orchestration/wundergraph-cosmo.md) + [MCP](skills/orchestration/mcp-protocol.md)

---

*Last updated: 2026-03-12*
