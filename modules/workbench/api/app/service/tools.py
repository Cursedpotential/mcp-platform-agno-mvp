# Byline: Claude Code · Sonnet (agent) · 2026-07-21 (C2.7: explicit description/inputSchema/annotations passthrough)
"""Aggregate tool listing + tool invocation across every configured MCP server.

Servers come from settings.mcp_servers_parsed (MCP_SERVERS json env — see
app/config/settings.py for the ContextForge-token-injection note). A server
that fails to respond becomes an {error} entry in list_tools(), never a
crash — the Tool Explorer should still render the servers that ARE
reachable even if one is down or misconfigured.

C2.7 (Tools page curation): the Essentials/search/description-rendering
work lives frontend-side (components/tools/*, lib/tools-essentials.ts) —
this module's job is just to guarantee the raw MCP tool dicts it hands the
frontend are never trimmed. `mcp_client.list_tools()` already returns each
server's `tools/list` entries completely unmodified (no field allowlist),
so `description`/`inputSchema` were already passing through untruncated;
`_passthrough_tool()` below makes that contract explicit and adds
`annotations` (MCP's optional per-tool hints object, e.g. readOnlyHint/
destructiveHint) to the guaranteed-present set when the source server sends
it, rather than leaving it as an implicit side effect of "we don't filter".
"""

from __future__ import annotations

import logging

from app.config import settings
from app.repo import mcp_client

logger = logging.getLogger(__name__)


class ToolsError(Exception):
    """Raised when a specific tool call cannot be attempted or fails."""

    def __init__(self, detail: str, status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _headers_for(server: dict) -> dict[str, str] | None:
    token = server.get("token")
    return {"Authorization": f"Bearer {token}"} if token else None


def _find_server(server_key: str) -> dict:
    for server in settings.mcp_servers_parsed:
        if server.get("key") == server_key:
            return server
    raise ToolsError(f"Unknown MCP server '{server_key}'", 404)


def _passthrough_tool(tool: dict) -> dict:
    """Explicit identity mapping for one raw `tools/list` entry.

    `name` and `inputSchema` are forwarded as-is (never truncated/summarized
    server-side — the whole point of the Tools-page curation work is that
    the operator sees the REAL description and schema, not a clipped one).
    `annotations` is forwarded only when the source server actually sent it
    — most MCP servers omit it, and the frontend `McpTool` type treats it as
    optional.
    """
    passthrough = {
        "name": tool.get("name"),
        "description": tool.get("description"),
        "inputSchema": tool.get("inputSchema"),
    }
    if "annotations" in tool:
        passthrough["annotations"] = tool["annotations"]
    # Preserve any other server-specific fields (e.g. a future MCP spec
    # addition) rather than dropping them — this stays additive, not a strict allowlist.
    for k, v in tool.items():
        passthrough.setdefault(k, v)
    return passthrough


def list_tools() -> list[dict]:
    """Return one entry per configured server: {key, label, tools} or {key, label, error}."""
    entries: list[dict] = []
    for server in settings.mcp_servers_parsed:
        key = server.get("key", "")
        label = server.get("label", key)
        url = server.get("url", "")
        try:
            raw_tools = mcp_client.list_tools(url, headers=_headers_for(server))
            tools = [_passthrough_tool(t) for t in raw_tools]
            entries.append({"key": key, "label": label, "tools": tools})
        except mcp_client.McpError as e:
            logger.warning("MCP server '%s' (%s) failed: %s", key, url, e.detail)
            entries.append({"key": key, "label": label, "error": e.detail})
        except Exception as e:  # never let one bad server crash the whole listing
            logger.warning("MCP server '%s' (%s) failed unexpectedly: %s", key, url, e, exc_info=True)
            entries.append({"key": key, "label": label, "error": str(e)})
    return entries


def call_tool(server_key: str, name: str, arguments: dict) -> dict:
    """Invoke `name` on the given server key with `arguments`. Raises ToolsError on failure."""
    server = _find_server(server_key)
    try:
        return mcp_client.call_tool(server["url"], name, arguments, headers=_headers_for(server))
    except mcp_client.McpError as e:
        raise ToolsError(e.detail, e.status_code) from e
