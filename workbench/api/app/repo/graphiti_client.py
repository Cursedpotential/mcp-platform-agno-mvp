# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (C4: Knowledge browser + Graphiti pane)
"""Thin repo-layer wrapper around app.repo.mcp_client for the Graphiti
knowledge-graph memory server (Neo4j-backed), reached over the SAME
streamable-HTTP MCP JSON-RPC transport app/repo/mcp_client.py already speaks
(agentos-mcp/ContextForge's Tool Explorer proxy).

Server: settings.graphiti_mcp_url (default http://100.119.96.29:8071/mcp) —
the tailnet "graphiti-hostfix" nginx sidecar defined in
compose.data-graphiti.yaml, NOT graphiti-mcp directly. That sidecar owns the
published port and forwards to graphiti-mcp with the Host header REWRITTEN
to "localhost:8071" server-side, because upstream FastMCP's constructor
hardcodes `allowed_hosts=["127.0.0.1:*","localhost:*"]` (an env override is
silently ignored) — any request arriving with Host=<tailnet-ip>:8071 gets a
421 "Invalid Host header" straight from graphiti-mcp. Net effect for THIS
client: no special Host header handling is needed here — plain httpx against
the sidecar's own host:port sends whatever Host that URL implies, and the
sidecar's nginx config does the rewrite before the request ever reaches
graphiti-mcp. Verified by reading compose.data-graphiti.yaml's
`graphiti-hostfix` service + hostfix.conf, and cross-checked against the
graphiti-client skill's `grc` CLI (~/.claude/skills/graphiti-client/scripts/
grc.py), which also sends no custom Host header and talks to the same
sidecar successfully.

Read-only wiring ONLY (search_memory_facts / search_nodes / get_episodes) —
this console-facing client never calls add_memory/clear_graph/delete_* frm
here; those stay CLI-only (`grc`) per the graphiti-client skill's owner
write-discipline (one focused episode per durable fact, never console-driven).

Tool-result unwrapping mirrors grc.py's McpClient.call_tool(): MCP's
`content[0].text` (a JSON string) is the reliable payload; `structuredContent`
sometimes double-wraps as `{"result": {...}}` for get_episodes/add_memory
(verified live — see the graphiti-client skill's references/failure-modes.md
gotcha #1) — prefer the text block, same as grc.

Never imports app.service/app.runtime — repo is the lowest SDK-touching
layer (see tests/test_structure.py).
"""

from __future__ import annotations

import json
import logging

from app.repo import mcp_client
from app.repo.mcp_client import McpError

logger = logging.getLogger(__name__)

__all__ = ["McpError", "call_tool"]


def _unwrap(result: dict) -> dict:
    """Unwrap one MCP tools/call result the same way grc.py's McpClient does
    (see this module's docstring): prefer content[0].text (JSON), fall back
    to structuredContent (unwrapping its {"result": ...} envelope when
    present), else return the raw result dict as-is."""
    if result.get("isError"):
        content = result.get("content", [])
        text = content[0].get("text", "") if content else ""
        raise McpError(f"graphiti tool call returned isError: {text[:400]}")

    content = result.get("content", [])
    if content and content[0].get("type") == "text":
        try:
            return json.loads(content[0]["text"])
        except (json.JSONDecodeError, ValueError):
            return {"text": content[0]["text"]}
    if "structuredContent" in result:
        structured = result["structuredContent"]
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        return structured
    return result


def call_tool(url: str, name: str, arguments: dict, timeout: float = 30.0) -> dict:
    """initialize -> tools/call(name, arguments) -> unwrapped payload dict.

    Reuses mcp_client.call_tool() for the transport (handshake, SSE-or-JSON
    parsing, error translation into McpError) and applies the graphiti-
    specific unwrap on top — mcp_client itself stays generic and doesn't know
    about graphiti's structuredContent double-wrap quirk.
    """
    raw = mcp_client.call_tool(url, name, arguments, timeout=timeout)
    return _unwrap(raw)
