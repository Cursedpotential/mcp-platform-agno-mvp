// Byline: Claude Code · Sonnet (agent) · 2026-07-21
/**
 * Config-driven "Essentials" curation for the Tool Explorer (C2.7 —
 * requirements addendum 8 / owner directive #2). Matches by (server key,
 * tool name); everything that doesn't match stays in its normal per-server
 * group.
 *
 * Two curation strategies, one per server key, because the two configured
 * MCP surfaces (see workbench/api/app/config/settings.py::mcp_servers)
 * differ in how stable/enumerable their tool names are:
 *
 * - "agentos" (:8000/mcp, mounted on agentos-api — standalone :8001 service
 *   retired 2026-07-23, agno 2.8.0 fixed the mounted-/mcp bug it worked
 *   around) exposes Agno's own fixed AgentOS-operation set
 *   (per docs/BUILD_PLAN.md: "AgentOS's native MCP surface exposes only
 *   ~19 AgentOS operations, never granular @tool functions" — verified
 *   from agno source `agno/os/app.py:588-595`). An EXACT allowlist is safe
 *   here because that name set doesn't churn. The 6 names below were
 *   cross-checked against this session's own `agno-gateway` MCP connector
 *   (mcp__agno-gateway__agno-platform-*), which speaks to the same AgentOS
 *   instance and confirmed all 6 exist verbatim: run_agent, run_team,
 *   run_workflow, get_sessions, create_session, get_agentos_config.
 *
 * - "contextforge" (:4444/mcp) federates several virtual servers behind one
 *   endpoint (agno/coolify/graphiti/exa/platform_tools per
 *   docs/COORDINATION.md) whose full aggregated tool list could NOT be
 *   live-inspected while building this branch — this is an isolated git
 *   worktree with no server/network actions permitted (see the C2.7 build
 *   report for what static evidence WAS available instead: 11 sbv_* REST
 *   routes + 3 generic tool routes in docker/tools/tools/facade.py = the
 *   14 tools ADR-0035/COORDINATION.md say are registered into CF's
 *   `platform_tools` virtual server; this session's own `graphiti` MCP
 *   connector showing tool names "graphiti-search-memory-facts" and
 *   "graphiti-search-nodes"). A REGEX is used instead of an allowlist for
 *   this server so tools land in Essentials automatically as they're
 *   registered — including ones that don't exist yet, like the addendum-2
 *   custody hash-verify endpoint or the C4 Milvus knowledge-search tool.
 *   No anchors, so it matches the substring anywhere regardless of
 *   whatever prefix CF's federation layer applies to a given tool name.
 */

export const AGENTOS_ESSENTIALS = new Set<string>([
  "run_agent",
  "run_team",
  "run_workflow",
  "get_sessions",
  "create_session",
  "get_agentos_config",
]);

/** Confirmed-live today (2026-07-21): "sbv" (all 14 platform_tools CF
 * entries carry it) and "graphiti-search" (graphiti-search-memory-facts,
 * graphiti-search-nodes). "knowledge"/"custody"/"evidence" match nothing
 * yet — kept forward-looking, see module doc comment above. */
export const CONTEXTFORGE_ESSENTIALS_RE = /sbv|graphiti[-_]?search|knowledge|custody|evidence/i;

/** True if (serverKey, toolName) should render in the pinned "Essentials"
 * shelf. Servers other than the two curated keys never contribute
 * essentials — they only ever appear in their own per-server group. */
export function isEssential(serverKey: string, toolName: string): boolean {
  if (serverKey === "agentos") return AGENTOS_ESSENTIALS.has(toolName);
  if (serverKey === "contextforge") return CONTEXTFORGE_ESSENTIALS_RE.test(toolName);
  return false;
}
