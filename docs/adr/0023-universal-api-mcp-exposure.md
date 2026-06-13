# ADR-0023: Universal exposure — API-first, MCP-wrapped
- Status: Accepted
- Date: 2026-06-13
- _Byline: Claude Code · Opus 4.8 · 2026-06-13_

## Context
The platform must serve tools, agents, and workflows to both in-platform consumers and external/any-surface
consumers (Claude/Gemini/OpenCode/other agents), without bespoke integration per consumer. Owner principle:
"everything gets an API; every API gets an MCP."

## Decision
Every **tool, agent, and workflow** is atomically addressable and exposed two ways:
1. an **internal API** (FastAPI/HTTP) that in-platform ("platform-surface") callers use directly;
2. an **MCP wrapper over that API** for all external/any-surface callers, **federated by IBM ContextForge** (ADR-0025).

Tools compose into **workflows** (a workflow may declare a slot for a *variable set* of tools, resolved by
capability via the registry). Workflows themselves get the same API+MCP treatment, reachable inside or out.

**Implementation guardrails (so this scales, not sprawls):**
- **Generate the MCP, don't hand-roll it.** ContextForge wraps REST/OpenAPI endpoints as MCP automatically;
  author the API (with an OpenAPI spec) once and let the gateway mint the MCP. (Verify ContextForge's
  OpenAPI→MCP coverage when standing up Phase C.)
- **API-addressable ≠ one microservice per tool.** Many tools mount as routes on a shared FastAPI facade
  (the `platform-tools` tools-facade pattern) + the registry; agents/workflows use Agno's native AgentOS
  API + MCP-server. Avoid microservice sprawl (minimize-custom, ADR-0025).
- **Gates enforced at the API/MCP layer.** Universal reachability must NOT bypass custody/HITL/auth:
  evidence writes stay HITL-gated, the `evidence` schema stays write-once via custody, every surface
  authenticates (Agno JWT / ContextForge auth).
- **Hot inner loops stay in-process** (e.g., per-chunk embedding) — APIs are for orchestration-level calls.
- **Token-efficient exposure — progressive disclosure (designed-for; built down the road).** Dumping
  hundreds of tools' full schemas into an LLM context is prohibitively expensive. Layer the **proven
  dial-stack gateway pattern** (`dev-resources/Archives/dial-stack/server/mcp/gateway.ts`): expose a small
  set of **meta tools** + a **name/tag-only catalog** (no descriptions), then **`search_tools`** (compact
  cards) → **`describe_tool`** (full spec ON DEMAND) → **`invoke_tool`** → **`get_ref`** (content-addressed,
  paged returns for large outputs). Lazy-load specs per selection; group via ContextForge virtual-servers/
  tool-groups. Start minimal (search + bare list), enrich on demand. (Phase C work.)

## Consequences
- One consistent exposure contract; any MCP-capable surface consumes any tool/agent/workflow.
- Requires an OpenAPI spec per API surface and ContextForge as the federating tool gateway.
- The two gateways stay distinct: **LiteLLM = models**, **ContextForge = tools/APIs** (ADR-0025).

## Alternatives considered
- Hand-write an MCP server per tool — rejected (boilerplate/maintenance).
- One microservice per tool — rejected (deployment sprawl, latency, against minimize-custom).
- Direct (non-MCP) external integration per consumer — rejected (N×M integration cost).
