"""
AgentOS Entrypoint — v8.1 (base_app pattern)
============================================

The spine (handoff §8.2 / EXECUTION_PLAN Phase 6):

  Context Providers -> ctx -> build_agent_team(ctx) -> AgentOS(base_app=app)

Hard rules (handoff §4 corrections):
  - AgentOS(base_app=app) + agent_os.get_app() — NEVER app.mount(...)
  - NO uvicorn reload — breaks the MCP lifespan under AgentOS
  - custom routes registered on the FastAPI app BEFORE wrapping;
    on_route_conflict="preserve_base_app" so they win on collision
  - the root Router (mode="route") is the primary entry point
"""

from contextlib import AsyncExitStack, asynccontextmanager
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
# agno 2.6.13 lifespan-combiner fix (monkeypatch — MUST run before get_app())
# ---------------------------------------------------------------------------
# agno's _combine_app_lifespans nests app lifespans with async-generator
# recursion (`async for _ in _run_nested(i): yield`). That breaks FastMCP's
# StreamableHTTP session-manager task group: it gets started inside a nested
# generator frame and is NOT alive when requests hit /mcp → 500
# "FastMCP's StreamableHTTPSessionManager task group was not initialized".
# Replace the combiner with an AsyncExitStack that enters every lifespan in the
# SAME task and holds them open for the app's lifetime. get_app() resolves
# `_combine_app_lifespans` from module globals at call time, so patching the
# module attribute here takes effect. (Also stabilises the scheduler lifespan.)
import agno.os.app as _agno_os_app  # noqa: E402


def _combine_app_lifespans_exitstack(lifespans):
    if not lifespans:
        return None
    if len(lifespans) == 1:
        return lifespans[0]

    @asynccontextmanager
    async def _combined(app):  # type: ignore[no-untyped-def]
        async with AsyncExitStack() as stack:
            for _lifespan in lifespans:
                await stack.enter_async_context(_lifespan(app))
            yield

    return _combined


_agno_os_app._combine_app_lifespans = _combine_app_lifespans_exitstack

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

    app = FastAPI(title="MCP Platform Assistant — AgentOS")
    register_knowledge_routes(app, knowledge)

    teams = [v for v in agents.values() if isinstance(v, Team)]
    solo_agents = [v for v in agents.values() if not isinstance(v, Team)]
    # Router first: it is the primary entry point (routes to Ops / Builder / Cleanup)
    teams.sort(key=lambda t: t.name != "MCP Platform Router")

    agent_os = AgentOS(
        name="AgentOS",
        id="mcp-forensic-platform",
        db=db,
        agents=solo_agents,
        teams=teams,
        knowledge=[knowledge],
        base_app=app,
        on_route_conflict="preserve_base_app",
        enable_mcp_server=True,  # serve the OS (agents/teams/knowledge) as an MCP server at /mcp
        scheduler=True,
        scheduler_base_url=scheduler_base_url,
        tracing=True,
        authorization=False,  # local/dev; JWT when multi-user (handoff non-goal)
        # Allow the self-hosted agent-ui origin (chat.mitechconsult.com) to call this
        # API from the browser. Merged with agno's defaults (agno.com/os.agno.com).
        cors_allowed_origins=["https://chat.mitechconsult.com"],
        lifespan=lifespan,
        config=str(Path(__file__).parent / "config.yaml"),
    )
    built = agent_os.get_app()

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

    # --- agno 2.6.13 workaround: run the MOUNTED MCP app's lifespan -----------
    # In the base_app path AgentOS double-creates the FastMCP app: __init__ mounts
    # instance #1 (app.mount("/", _mcp_app)), then get_app() overwrites _mcp_app
    # with instance #2 and only runs #2's lifespan. So the app that actually serves
    # /mcp (#1) never has its StreamableHTTP session-manager task group started →
    # /mcp 500s "task group was not initialized". Fix: find the actually-mounted
    # FastMCP sub-app and run ITS lifespan around the existing combined lifespan,
    # so the served instance's session manager is initialised for the app lifetime.
    from starlette.routing import Mount

    mounted_mcp = None
    for route in built.routes:
        if isinstance(route, Mount) and type(getattr(route, "app", None)).__name__ == "StarletteWithLifespan":
            mounted_mcp = route.app
            break

    if mounted_mcp is not None and hasattr(mounted_mcp, "lifespan"):
        _inner_lifespan = built.router.lifespan_context

        @asynccontextmanager
        async def _lifespan_with_mounted_mcp(app):  # type: ignore[no-untyped-def]
            async with mounted_mcp.lifespan(app):
                if _inner_lifespan is not None:
                    async with _inner_lifespan(app):
                        yield
                else:
                    yield

        built.router.lifespan_context = _lifespan_with_mounted_mcp
        log_info("MCP fix: wired mounted FastMCP app lifespan (session manager)")

    return built


app = _build_app()


if __name__ == "__main__":
    import uvicorn

    # reload must stay OFF: MCP lifespan breaks under reload (handoff §4 #4)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
