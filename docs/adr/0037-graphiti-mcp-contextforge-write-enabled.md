# ADR-0037: Graphiti MCP as a write-enabled ContextForge virtual server

> _Byline: Claude (Opus 4.8, chat) + owner · 2026-07-13 · DRAFT for review_

**Status:** **Accepted** — owner 2026-07-29 (Proposed 2026-07-13). The original BLOCKER (ContextForge federating a Streamable HTTP upstream) is cleared by lived evidence: a `graphiti` virtual server has been registered and serving in ContextForge since ≤2026-07-10 (DECISION_LOG D-028 lists it alongside `agno`/`coolify`/`exa`/`platform_tools`). Execution remainder: verify the registered surface is the full WRITE surface, and retire the standalone no-auth `:8071` nginx door.
**Supersedes/relates:** [ADR-0025](0025-gateway-topology-agno-contextforge-litellm.md) (gateway topology: Agno · ContextForge · LiteLLM), [ADR-0014](0014-neo4j-graphiti-temporal-memory.md), [ADR-0036](0036-dozerdb-multidb-rbac-memory-evidence-isolation.md). Retires the standalone read-only Graphiti door.

## Context

Graphiti's memory graph is meant to be **agent working memory** — read *and* write, shared across Agno agents and Claude clients (Desktop, Code). The architecture asymmetry is: agents write the memory graph freely; only the *evidence* graph is read-only to agents.

Current wiring (observed in the C4 console work): the workbench reaches Graphiti through a **standalone tailnet nginx sidecar** (`GRAPHITI_MCP_URL` → `:8071`), described in that config as *read-only, search/episodes only, no auth (tailnet-only)*. This door **bypasses ContextForge** — which is exactly why it is unauthenticated and read-only. ContextForge currently fronts `agentos` and `contextforge`, not Graphiti.

The goal is write-enabled, authenticated, shared access without building a second bespoke auth layer.

## Decision

Register the **write-enabled Graphiti MCP server (v1.0, Streamable HTTP)** as a **virtual server inside ContextForge**. ContextForge fronts authentication (bearer/JWT via `token_env`, per the existing gateway convention). **Retire the standalone no-auth nginx door** (`:8071`); `GRAPHITI_MCP_URL` is replaced by a ContextForge-registered entry.

- Transport: Streamable HTTP (SSE is deprecated upstream).
- Tools: full surface — writes (`add_memory`/`add_episode`, `add_triplet`, deletes) plus reads (`search_nodes`, `search_memory_facts`, `get_episodes`).
- Scope: tailnet clients (Agno, Claude Desktop, Claude Code) reach it via ContextForge. **claude.ai cloud clients remain out of scope** — a write-capable forensic memory graph is deliberately not exposed to cloud clients.
- Namespacing: partition by **case** (`group_id = case-<id>`) so memory is shared across agents/clients on the same case, not siloed per client.

## Consequences

- One auth layer for all MCP doors; no separate token proxy to build or maintain.
- The read-only limitation disappears — agents get the write access the memory-graph design always intended.
- Graphiti targets the `memory` database (ADR-0036); its ContextForge credentials map to the `graphiti_writer` role.

## Open

- **BLOCKER:** Does the deployed ContextForge version federate a **Streamable HTTP** upstream, or SSE-only? If SSE-only, a transport shim or ContextForge upgrade is required before this can be accepted. Verify against the ContextForge version/config in the repo.
- Concurrent multi-writer `group_id` behavior on Neo4j/DozerDB (assessed safe; confirm under load).
- Extraction-LLM choice is specified separately (ADR-0039).
