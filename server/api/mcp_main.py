"""
DEPRECATED 2026-07-23 — retired, kept for historical reference only.
=====================================================================
Byline: Claude Code · Sonnet · 2026-07-23

Owner decision: retire the standalone `agentos-mcp` service. The mounted
`/mcp` sub-app on agentos-api (:8000) is fixed in agno 2.8.0 — verified via a
clean JSON-RPC `initialize` + `tools/list` round-trip (see
C:\\Users\\matts\\OneDrive\\AI Space\\agno-upgrade-result.md, "agentos-mcp
retirement" section, and item (d) of that doc's verification matrix). This
module's workaround is no longer wired into compose.exec.yaml (the
`agentos-mcp` service block was removed the same day) and is not imported by
any live code path. It is NOT deleted — never-delete-move-to-stale convention
— because the docstring below documents a real, empirically-proven pattern
(mounted-ASGI-sub-app lifespan doesn't survive mounting; running the sub-app
standalone as uvicorn's main target does) that may be salvageable if a future
agno regression or a similar mounted-FastMCP integration needs it again.

--- Original header (historical, describes the now-fixed problem) ---

Standalone MCP entrypoint — serves AgentOS's FastMCP app as its OWN ASGI app.
============================================================================

agno's `enable_mcp_server` MOUNTS the FastMCP app inside the REST app. But
FastMCP's StreamableHTTP session-manager uses an anyio task group created in the
app lifespan, and that task group does NOT survive being a *mounted* sub-app
under uvicorn → every /mcp request 500s "task group was not initialized".

Served STANDALONE (as the main ASGI app) uvicorn runs the MCP app's own lifespan
natively, `session_manager.run()` stays active, and /mcp works reliably. This was
verified empirically (mounted = 0/5, standalone = 5/5) after six in-place fixes
(base_app, lifespan combiner, mounted-instance lifespan, non-base_app, agno 2.6.18,
scheduler off) all failed — the mount is the root cause.

Run:  uvicorn server.api.mcp_main:mcp_app --host 0.0.0.0 --port 8001

This reuses server.api.main's fully-built AgentOS (agents/teams/knowledge/db) and just
extracts + serves the FastMCP sub-app. Was deployed as the separate `agentos-mcp`
service (compose.exec.yaml); Traefik routed Host(agentos.*)+PathPrefix(/mcp) here.
As of agno 2.8.0 the mounted /mcp on agentos-api works natively — this module and
its service are retired, not needed for that endpoint anymore.
"""

import server.api.main as _m  # builds the AgentOS app (with enable_mcp_server mounting)
from agno.utils.log import log_info

# The mounted FastMCP app (fastmcp StarletteWithLifespan). Serving THIS as the
# main ASGI app makes uvicorn run its lifespan (session_manager.run()) natively.
mcp_app = next(route.app for route in _m.app.routes if type(route.app).__name__ == "StarletteWithLifespan")

log_info("Standalone MCP entrypoint: serving the FastMCP app as the main ASGI app")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.api.mcp_main:mcp_app", host="0.0.0.0", port=8001, reload=False)
