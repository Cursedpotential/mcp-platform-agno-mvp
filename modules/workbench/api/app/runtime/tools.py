# Byline: Claude Code · Sonnet (agent) · 2026-07-20
"""GET /api/tools and POST /api/tools/call — proxy to configured MCP servers.

Backs the C1 console's Tool Explorer page. The server list itself is
config-driven (settings.mcp_servers_parsed / MCP_SERVERS env) — this router
has no server names baked in.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.service.tools import ToolsError, call_tool, list_tools
from app.types.tools import ToolCallRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tools"])


@router.get("/tools")
async def list_tools_endpoint():
    return list_tools()


@router.post("/tools/call")
async def call_tool_endpoint(body: ToolCallRequest):
    try:
        return call_tool(body.server, body.name, body.arguments)
    except ToolsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
