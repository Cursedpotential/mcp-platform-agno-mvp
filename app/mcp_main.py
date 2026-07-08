"""
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

Run:  uvicorn app.mcp_main:mcp_app --host 0.0.0.0 --port 8001

This reuses app.main's fully-built AgentOS (agents/teams/knowledge/db) and just
extracts + serves the FastMCP sub-app. Deployed as the separate `agentos-mcp`
service (compose.exec.yaml); Traefik routes Host(agentos.*)+PathPrefix(/mcp) here.
"""

import app.main as _m  # builds the AgentOS app (with enable_mcp_server mounting)
from agno.utils.log import log_info

# The mounted FastMCP app (fastmcp StarletteWithLifespan). Serving THIS as the
# main ASGI app makes uvicorn run its lifespan (session_manager.run()) natively.
mcp_app = next(
    route.app
    for route in _m.app.routes
    if type(route.app).__name__ == "StarletteWithLifespan"
)

log_info("Standalone MCP entrypoint: serving the FastMCP app as the main ASGI app")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.mcp_main:mcp_app", host="0.0.0.0", port=8001, reload=False)
