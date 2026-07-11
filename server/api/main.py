"""app/main.py — AgentOS entrypoint (base_app pattern, v8.1).

Assembly pipeline::

    Context Providers -> ctx -> build_agent_team(ctx) -> AgentOS(base_app=app)

Architecture:
- FastAPI app wraps custom routes (knowledge reindex).
- AgentOS wraps the FastAPI app (base_app pattern, NEVER app.mount).
- Root Router (mode="route") dispatches to Platform Ops / Builder teams.
- Gemini Document Digest agent attaches conditionally (GOOGLE_API_KEY).

Hard rules:
- AgentOS(base_app=app) + agentos.get_app() — NEVER app.mount(...)
- NO uvicorn reload — breaks the MCP lifespan under AgentOS.
- Custom routes registered on the FastAPI app BEFORE wrapping;
  on_route_conflict="preserve_base_app" so they win on collision.
- The root Router (mode="route") is the primary entry point.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from agno.os import AgentOS
from agno.team.team import Team
from agno.utils.log import log_info

from server.agents.factory import build_agent_team
from server.agents.providers import build_context, build_learning
from server.core.settings import build_model
from server.core import create_knowledge, get_agno_db
from server.core.url import db_url

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
runtime_env: str = getenv("RUNTIME_ENV", "dev")
scheduler_base_url: str = getenv("AGENTOS_URL", "http://127.0.0.1:8000")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: Any) -> Any:
    """AgentOS lifespan: ensure pg_duckdb R2 secret on startup, log shutdown."""
    log_info("AgentOS lifespan: startup")
    from server.core import ensure_duckdb_r2_secret

    log_info(f"pg_duckdb R2 secret ensured: {ensure_duckdb_r2_secret()}")
    try:
        yield
    finally:
        log_info("AgentOS lifespan: shutdown")


# ---------------------------------------------------------------------------
# Custom routes (registered on the base app BEFORE AgentOS wraps it)
# ---------------------------------------------------------------------------

# HITL approvals are NATIVE as of agno 2.6.13: @approval tools persist a
# pending row on pause, AgentOS auto-mounts GET/POST /approvals (+ /resolve),
# and the run-continue endpoints are gated by require_approval_resolved.
# The former custom approval_request table + /v1/approval-requests routes are
# gone (superseded; see docs/DEBT.md "Agno-native audit").


def register_knowledge_routes(app: FastAPI, knowledge: Any) -> None:
    """Register knowledge management routes on the FastAPI app.

    Parameters
    ----------
    app:
        The FastAPI application instance.
    knowledge:
        Agno Knowledge instance used for reindexing.
    """

    @app.post("/v1/knowledge/reindex")
    async def reindex_knowledge() -> dict[str, Any]:
        """Trigger a full reindex of the knowledge base.

        Returns
        -------
        dict
            ``{"indexedDocumentCount": <int>, "status": "completed"}``
        """
        from scripts.ingest_knowledge import ingest_all

        count = await ingest_all(knowledge)
        return {"indexedDocumentCount": count, "status": "completed"}


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _build_app() -> Any:
    """Build and return the AgentOS-wrapped FastAPI application.

    Assembly order:
    1. Build model (provider-agnostic, credential-driven).
    2. Build Agno DB connections (SurrealDB operational store).
    3. Build Knowledge instance (Milvus-backed).
    4. Build LearningMachine (operational memory).
    5. Build context providers (workspace, database, MCP).
    6. Build agent team (all agents + teams + router).
    7. Conditionally attach Document Digest agent.
    8. Wrap FastAPI app with AgentOS.

    Returns
    -------
    Any
        The AgentOS-wrapped ASGI application.
    """
    model = build_model()
    db = get_agno_db()
    knowledge = create_knowledge("platform", "platform_knowledge")
    learning = build_learning(model, knowledge)  # learning persists to PG (D-030); db (SurrealDb) keeps sessions

    ctx = build_context(model, db, knowledge, learning, db_url)
    agents = build_agent_team(ctx)

    # Gemini long-context digest specialist — present only when
    # GOOGLE_API_KEY is set; deterministic evidence ops stay in the pipeline.
    from server.agents.document_digest import build_document_digest

    digest = build_document_digest(db, knowledge)
    if digest is not None:
        agents["document_digest"] = digest

    app = FastAPI(title="MCP Platform Assistant — AgentOS")
    register_knowledge_routes(app, knowledge)

    teams = [v for v in agents.values() if isinstance(v, Team)]
    solo_agents = [v for v in agents.values() if not isinstance(v, Team)]
    # Router first: it is the primary entry point.
    teams.sort(key=lambda t: t.name != "MCP Platform Router")

    agent_os = AgentOS(
        name="AgentOS",
        id="mcp-forensic-platform",
        db=db,
        agents=solo_agents,
        teams=teams,  # type: ignore[arg-type]  # invariant list[Team|...]; list[Team] is safe here
        knowledge=[knowledge],
        base_app=app,
        enable_mcp_server=True,  # serve the OS as an MCP server at /mcp (extracted standalone by app/mcp_main.py — mounted /mcp 500s, see that file)
        on_route_conflict="preserve_base_app",
        scheduler=True,
        scheduler_base_url=scheduler_base_url,
        tracing=True,
        authorization=False,  # local/dev; JWT when multi-user
        lifespan=lifespan,
        config=str(Path(__file__).parent / "config.yaml"),
    )
    return agent_os.get_app()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

app = _build_app()

if __name__ == "__main__":
    import uvicorn

    # reload must stay OFF: MCP lifespan breaks under reload (handoff correction #4).
    uvicorn.run("server.api.main:app", host="0.0.0.0", port=8000, reload=False)
