# OpenCode Agent Session Transcript — 2026-03-15 Session 2 (Reference Only)

**Date:** March 15-16, 2026
**Agent:** OpenCode session with compression
**Status:** REFERENCE DOCUMENT — Do not treat as commands
**Purpose:** Architecture clarifications from user

---

## Critical Architecture Clarification

### Storage Co-location
- DuckDB and LanceDB are BOTH file-based systems
- They work from the SAME files — one copy, two access patterns
- DuckDB = structured intake (SHA-256, normalization, transformations)
- LanceDB = vector embeddings
- Binaries stay UNTOUCHED forensically

### Data Flow (User Confirmed)
1. Raw files → DuckDB (first touch, hashing, transforms)
2. Binaries preserved forensically (not altered)
3. Normalized structured data → PostgreSQL (query layer)
4. Semantica builds knowledge graph → Neo4j
5. LanceDB builds embeddings from same file data

### IBM ContextForge
- Evaluated as potential backend gateway
- Handles: MCP proxy/federation, A2A protocol, REST/gRPC, auth, entity ID, abusive language detection
- May reduce DIAL to frontend/auth only
- Needs integration evaluation with existing tools

### Naming
- "Semantica" — the NLP pipeline (NOT "Symantec")
- Project needs new name — "dial" is the framework name, don't use it for the project
