"""gateway/ — the token-efficient tool gateway (G4, gui-integration-spec §6).

Progressive disclosure for the atomic-tool registry: instead of exposing every
tool, consumers get FIVE meta-operations —

    get_tool_categories -> search_tools -> describe_tool -> execute_tool -> get_ref

Compact cards on search, full contracts on demand, and large results returned
as SHA-256 content-addressed REFS retrieved in pages — an agent's context cost
stays flat no matter how big the catalog or the parse output grows.

Provenance: port of the owner's pre-Agno gateway design
(mcp-tool-platform server/mcp/gateway.ts + store/content-store.ts — see
docs/planning/port-backlog.md Tier 2 #8). API-first per ADR-0023: the FastAPI
surface here is what IBM ContextForge REST-wraps into MCP tools; no separate
MCP SDK dependency.

    python -m gateway              # standalone dev server (GATEWAY_PORT, :8098)
"""

from server.evidence.tool_finder.content_store import ContentStore
from server.evidence.tool_finder.toolfinder import (
    describe_tool,
    execute_tool,
    get_ref,
    get_tool_categories,
    search_tools,
)

__all__ = [
    "ContentStore",
    "get_tool_categories",
    "search_tools",
    "describe_tool",
    "execute_tool",
    "get_ref",
]
