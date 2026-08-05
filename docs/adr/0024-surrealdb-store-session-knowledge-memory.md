# ADR-0024: SurrealDB as the store / session / Knowledge / memory layer
- Status: ~~Accepted~~ **Superseded** — vector/Knowledge role by ADR-0027 (2026-06-16, then
  ADR-0040 → Weaviate); store/session/memory role by **ADR-0043 decision 3** (accepted
  2026-08-02, flatten executed 2026-08-04). SurrealDB is now parked read-only and off the
  critical path; the Agno operational store is PostgresDb. **Nothing of this ADR remains in
  force.** Kept in full for provenance — it was correct when decided.
- Date: 2026-06-13
- _Byline: Claude Code · Opus 4.8 · 2026-06-13_
- _Superseded-marking byline: Claude Code · Opus 5 · 2026-08-05_

> **Why it was reversed** (short version; full reasoning in ADR-0043 and
> `docs/reference/agno-memory-and-storage/07-platform-mapping.md`): agno's SurrealDb backend
> raises `NotImplementedError` on every LearningMachine method, and LearningMachine swallows
> the exception — so `user_profile` / `user_memory` / `session_context` / `entity_memory` were
> **silent no-ops in production for months**. Separately, registering a second `db.id` armed
> agno's multi-db gate, making every route that omitted `db_id` return 400. The consolidation
> this ADR sought was real, but it landed on Postgres, not SurrealDB.

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
