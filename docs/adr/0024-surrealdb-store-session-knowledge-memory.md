# ADR-0024: SurrealDB as the store / session / Knowledge / memory layer
- Status: Accepted
- Date: 2026-06-13
- _Byline: Claude Code · Opus 4.8 · 2026-06-13_

## Context
The platform currently splits state across pg_duckdb/pgvector (sessions, Knowledge vectors), plus Agno
memory. Owner goal: minimize custom code, consolidate off-the-shelf. SurrealDB is multi-model (document +
relational + vector + graph + live queries) with **native bitemporal versioning** (valid time + transaction
time, time-travel via SurrealKV) — and **Agno supports it natively** as a database (agent/team/workflow
sessions+state), a vector store (Knowledge/RAG), and a memory backend.

## Decision
Adopt **SurrealDB** as the consolidated **store / session / Knowledge / memory** engine (Agno-native).
It also fits the **bitemporal evidence-record store** (native valid + transaction time → maps to
`NormalizedRecord` occurred_at / knowledge_time / disclosure_tier).

**Custom Graphiti STAYS** the bitemporal **cognition** substrate (VIP — NOT replaced). SurrealDB and
Graphiti operate at different altitudes: SurrealDB = bitemporal *storage*; Graphiti = bitemporal
*knowledge-graph cognition* (auto fact-invalidation on contradiction, episodic ingestion, entity
resolution, hybrid retrieval, point-in-time graph state — the Pass-1→final delta).

## Consequences
- One engine for sessions/Knowledge/memory + the evidence record store; less moving parts.
- Migration off pg_duckdb/pgvector is deliberate and **sequenced in Phase D** (weighed against the live
  ADR-0013 stack). Supersedes-in-part the pgvector-Knowledge approach (ADR-0010) for the Knowledge layer.
- Embeddings still routed per the embedder decisions; vector dims must match the chosen embedder.

## Alternatives considered
- Keep pg_duckdb + pgvector + separate memory — rejected (more custom glue, multiple stores).
- SurrealDB replaces Graphiti too — rejected (would re-implement Graphiti's KG cognition = heavy custom
  code on the most critical layer; Graphiti is a VIP and already works).
- Milvus/Qdrant self-hosted vector store — deferred (SurrealDB consolidates more, Agno-native).
