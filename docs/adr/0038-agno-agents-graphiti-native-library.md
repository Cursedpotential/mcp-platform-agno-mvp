# ADR-0038: Agno agents use Graphiti natively (library); MCP door for GUI clients only

> _Byline: Claude (Opus 4.8, chat) + owner · 2026-07-13 · DRAFT for review_

**Status:** **Accepted** — owner 2026-07-29 (Proposed 2026-07-13). Consistent with ADR-0041's later "orchestration settled Agno-native" ruling.
**Supersedes/relates:** [ADR-0024](0024-surrealdb-store-session-knowledge-memory.md) (SurrealDB for session/knowledge/memory), [ADR-0037](0037-graphiti-mcp-contextforge-write-enabled.md).

## Context

Agno agents are Python, on-tailnet, co-located with Neo4j/DozerDB. Reaching Graphiti through the MCP door adds a network hop, the server's async write-queue latency, MCP session fragility, and duplicated LLM/embedder config. The MCP door exists primarily for clients that **cannot** import Python (Claude Desktop, Claude Code, this Claude).

## Decision

- **Agno agents call `graphiti-core` in-process** (library) to read/write the memory graph directly against DozerDB `memory`.
- The **ContextForge-fronted MCP door (ADR-0037) serves only the GUI Claude clients**, not the Agno agents.
- **Session/run state stays in SurrealDB** (ADR-0024). Graphiti is **semantic/graph memory only** — the two memory concerns stay separate.

## Consequences

- Lower latency, fewer moving parts for the agents; no dependence on the MCP queue for agent memory.
- No official Agno↔Graphiti integration exists — the library wiring is hand-rolled and owned by us.
- Two clear memory lanes: session state (SurrealDB) vs. semantic memory (Graphiti), consistent with the truth/cognition separation principle.

## Open

- Shared `group_id` convention (partition by case) shared with ADR-0037.
- Whether any Agno agent ever needs the MCP path (default: no).
