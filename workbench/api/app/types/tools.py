# Byline: Claude Code · Sonnet (agent) · 2026-07-20
"""Request shape for POST /api/tools/call.

The response bodies of GET /api/tools and POST /api/tools/call are
deliberately NOT modeled here — they're passthrough JSON from arbitrary MCP
servers (tool lists, inputSchema, raw tool-call results), which is exactly
the kind of open-ended shape pydantic response_model would fight rather than
help. See app/service/tools.py for what actually comes back.
"""

from __future__ import annotations

from pydantic import BaseModel


class ToolCallRequest(BaseModel):
    """POST /api/tools/call body."""

    server: str
    name: str
    arguments: dict = {}
