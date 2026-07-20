# Byline: Claude Code · Sonnet (agent) · 2026-07-20
"""Aggregate tool listing + tool invocation across every configured MCP server.

Servers come from settings.mcp_servers_parsed (MCP_SERVERS json env — see
app/config/settings.py for the ContextForge-token-injection note). A server
that fails to respond becomes an {error} entry in list_tools(), never a
crash — the Tool Explorer should still render the servers that ARE
reachable even if one is down or misconfigured.
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


def list_tools() -> list[dict]:
    """Return one entry per configured server: {key, label, tools} or {key, label, error}."""
    entries: list[dict] = []
    for server in settings.mcp_servers_parsed:
        key = server.get("key", "")
        label = server.get("label", key)
        url = server.get("url", "")
        try:
            tools = mcp_client.list_tools(url, headers=_headers_for(server))
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
