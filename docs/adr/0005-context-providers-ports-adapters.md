# ADR-0005: Context Providers as the source-access layer (ports-and-adapters)
- Status: Accepted
- Date: 2026-06-01

## Context
Attaching raw MCP/SQL tools to agents causes tool sprawl, name collisions, and system-prompt bloat.
The handoff's core principle is thin agents + capability in the MCP servers — i.e. ports-and-adapters.
Agno's Context Providers wrap each source as `query_<id>`/`update_<id>` behind a scoped sub-agent.

## Decision
All source access goes through **Context Providers** (the adapter layer); agents (the policy core) talk
to providers, not raw tools. Use: `WorkspaceContextProvider` (codebase), `DatabaseContextProvider`
(evidence read-only via `readonly_engine`, analysis via `sql_engine` — **infrastructure-level read/write
split**), `MCPContextProvider` over `MCPToolbox` (DB fleet), per-account `GoogleDriveContextProvider`
and OneDrive `MCPContextProvider` (read), and a custom **ChatLogs** provider wrapping ChatMiner.
Providers are assembled into a `ctx` object consumed by `build_agent_team(ctx)`.

## Consequences
- Evidence read-only is an infrastructure guarantee, not a prompt instruction.
- New sources = new providers; agents stay thin.
- `agents/providers.py` is the single place providers are built.

## Alternatives considered
- Raw MCPTools/SQL tools on agents — rejected (sprawl, collisions, weak read-only).
