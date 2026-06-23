"""
AgentOS Entrypoint — v9 (AgentOS-owned app; NO base_app)
=======================================================

The spine (handoff §8.2 / EXECUTION_PLAN Phase 6):

  Context Providers -> ctx -> build_agent_team(ctx) -> AgentOS(...).get_app()

Hard rules (handoff §4 + 2026-06-20 MCP fix):
  - Do NOT pass base_app. AgentOS's base_app path double-creates the FastMCP app
    (mounts instance #1 in __init__, lifespans instance #2 in get_app) → /mcp 500
    "task group not initialized". Letting AgentOS own the app mounts AND lifespans
    the SAME instance, so MCP works. Custom routes are added to get_app()'s result.
  - NO uvicorn reload — breaks the MCP lifespan under AgentOS
  - the root Router (mode="route") is the primary entry point
  - agno 2.6.13 quirk: its TrailingSlashMiddleware 500s the list endpoints with the
    MCP mount at "/" — stripped from the stack after build (see _build_app).
"""

from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path

from fastapi import FastAPI

from agno.os import AgentOS
from agno.team.team import Team
from agno.utils.log import log_info

from agents.factory import build_agent_team
from agents.providers import build_context, build_learning
from app.settings import build_model
from db import create_knowledge, get_agno_db
from db.url import db_url

# ---------------------------------------------------------------------------
# MCP note (2026-06-21): do NOT monkeypatch agno's _combine_app_lifespans with an
# AsyncExitStack. anyio task groups (FastMCP's StreamableHTTP session manager uses
# one) MUST be held open by a structured `async with` block — AsyncExitStack's
# deferred enter/exit corrupts the task group, so /mcp 500s "task group not
# initialized". agno's native combiner already uses proper nested `async with`,
# which is correct. Combined with NO base_app (same FastMCP instance mounted AND
# lifespanned), that is what makes /mcp work.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
runtime_env = getenv("RUNTIME_ENV", "dev")
scheduler_base_url = getenv("AGENTOS_URL", "http://127.0.0.1:8000")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):  # type: ignore[no-untyped-def]
    log_info("AgentOS lifespan: startup")
    # Ensure the pg_duckdb R2 secret exists on every boot (survives DB recreate).
    from db import ensure_duckdb_r2_secret

    log_info(f"pg_duckdb R2 secret ensured: {ensure_duckdb_r2_secret()}")
    try:
        yield
    finally:
        log_info("AgentOS lifespan: shutdown")


# ---------------------------------------------------------------------------
# Custom routes (registered on the base app BEFORE AgentOS wraps it)
#
# HITL approvals are NATIVE as of agno 2.6.13: @approval tools persist a
# pending row on pause, AgentOS auto-mounts GET/POST /approvals (+ /resolve),
# and the run-continue endpoints are gated by require_approval_resolved.
# The former custom approval_request table + /v1/approval-requests routes are
# gone (superseded; see docs/DEBT.md "Agno-native audit").
# ---------------------------------------------------------------------------
def register_knowledge_routes(app: FastAPI, knowledge) -> None:
    @app.post("/v1/knowledge/reindex")
    async def reindex_knowledge():  # type: ignore[no-untyped-def]
        from scripts.ingest_knowledge import ingest_all

        count = await ingest_all(knowledge)
        return {"indexedDocumentCount": count, "status": "completed"}


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def _build_app():
    model = build_model()
    db = get_agno_db()
    knowledge = create_knowledge("platform", "platform_knowledge")
    learning = build_learning(db, model, knowledge)

    ctx = build_context(model, db, knowledge, learning, db_url)
    agents = build_agent_team(ctx)

    # Gemini long-context digest specialist (task 13) — present only when
    # GOOGLE_API_KEY is set; deterministic evidence ops stay in the pipeline.
    from agents.document_digest import build_document_digest

    digest = build_document_digest(db, knowledge)
    if digest is not None:
        agents["document_digest"] = digest

    teams = [v for v in agents.values() if isinstance(v, Team)]
    solo_agents = [v for v in agents.values() if not isinstance(v, Team)]
    # Router first: it is the primary entry point (routes to Ops / Builder / Cleanup)
    teams.sort(key=lambda t: t.name != "MCP Platform Router")

    # NO base_app — let AgentOS build its own FastAPI app. The base_app path
    # double-creates the FastMCP app (mounts instance #1 in __init__, lifespans
    # instance #2 in get_app) → /mcp 500 "task group not initialized". The standard
    # path mounts AND lifespans the SAME instance, so MCP works. Our one custom
    # route (knowledge reindex) is registered on the built app afterward.
    agent_os = AgentOS(
        name="AgentOS",
        id="mcp-forensic-platform",
        db=db,
        agents=solo_agents,
        teams=teams,
        knowledge=[knowledge],
        enable_mcp_server=True,  # serve the OS (agents/teams/knowledge) as an MCP server at /mcp
        # scheduler DISABLED (2026-06-21): the scheduler<->SurrealDB "Error claiming
        # schedule" fires DURING lifespan startup, nested in the same task-group tree
        # as FastMCP's StreamableHTTP session manager — prime suspect for nulling the
        # MCP task group (/mcp 500 "task group not initialized"). It's broken+unused
        # anyway. Re-enable once the SurrealDB scheduler store is fixed.
        scheduler=False,
        tracing=True,
        authorization=False,  # local/dev; JWT when multi-user (handoff non-goal)
        # Browser origins allowed to call this API directly (control plane + chat UI).
        # NOTE: this agno build REPLACES the default origins with this list (it does
        # NOT merge), so os.agno.com must be listed explicitly or the control plane
        # shows "connected but not active" (browser fetch of /config is CORS-blocked).
        cors_allowed_origins=[
            "https://chat.mitechconsult.com",
            "https://os.agno.com",
            "https://app.agno.com",
            "https://agno.com",
            "https://www.agno.com",
            "https://os-stg.agno.com",
            "http://localhost:3000",
        ],
        lifespan=lifespan,
        config=str(Path(__file__).parent / "config.yaml"),
    )
    built = agent_os.get_app()

    # Our custom route(s), registered on the AgentOS-owned app post-build.
    register_knowledge_routes(built, knowledge)

    # --- agno 2.6.13 workaround: drop the buggy TrailingSlashMiddleware -------
    # AgentOS unconditionally adds a TrailingSlashMiddleware (a Starlette
    # BaseHTTPMiddleware). With the MCP app mounted at "/" (enable_mcp_server),
    # that BaseHTTPMiddleware raises RuntimeError("No response returned.") on the
    # list endpoints (/agents, /teams) — which 500s the os.agno.com GUI's agent
    # and team views. We don't rely on trailing-slash normalisation, so strip it
    # from the stack and force a rebuild. Also lets the mounted MCP (SSE/stream)
    # app handle requests without the BaseHTTPMiddleware buffering them.
    built.user_middleware = [
        m
        for m in built.user_middleware
        if getattr(m.cls, "__name__", "") != "TrailingSlashMiddleware"
    ]
    built.middleware_stack = built.build_middleware_stack()
    return built


app = _build_app()


if __name__ == "__main__":
    import uvicorn

    # reload must stay OFF: MCP lifespan breaks under reload (handoff §4 #4)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
