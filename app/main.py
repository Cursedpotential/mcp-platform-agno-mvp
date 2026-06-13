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
from db import create_knowledge, get_postgres_db
from db.url import db_url

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
    db = get_postgres_db()
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
        scheduler=True,
        scheduler_base_url=scheduler_base_url,
        tracing=True,
        authorization=False,  # local/dev; JWT when multi-user (handoff non-goal)
        lifespan=lifespan,
        config=str(Path(__file__).parent / "config.yaml"),
    )
    return agent_os.get_app()


app = _build_app()


if __name__ == "__main__":
    import uvicorn

    # reload must stay OFF: MCP lifespan breaks under reload (handoff §4 #4)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
