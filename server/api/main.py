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
# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3 spine boot resilience — KnowledgeHandle wired in place of a direct create_knowledge() call; register_inspect_routes added)
# Byline: Claude Code · Sonnet · 2026-07-23 (agno 2.8 service accounts — AgentOS admin-plane db switched from SurrealDb to a dedicated PostgresDb; agents/teams keep SurrealDb unchanged)
# Byline: Claude Code · Fable 5 · 2026-07-31 (Milvus→Weaviate doc-drift cleanup (ADR-0040))
# DEPLOY NOTE (2026-08-01): exec-tier auto-deploys from `main` via the Coolify
# GitHub App (`cursedpotential`, app_id 4047891, installation 140142795;
# Coolify source_id=2). Watch paths are `compose.exec.yaml`, `Dockerfile`,
# `server/**` — a change confined to `docs/` will NOT redeploy the API.

from __future__ import annotations

from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from agno.os import AgentOS
from agno.team.team import Team
from agno.utils.log import log_info, log_warning

from server.agents.factory import build_agent_team
from server.agents.providers import build_context, build_learning
from server.core.knowledge_handle import KnowledgeHandle, resolve_knowledge
from server.core.settings import build_model
from server.core import create_knowledge, get_agno_db, get_postgres_db
from server.api.workflow_registry import registered_workflows
from server.core.session import DB_ID
from server.core.url import db_url

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
runtime_env: str = getenv("RUNTIME_ENV", "dev")
scheduler_base_url: str = getenv("AGENTOS_URL", "http://127.0.0.1:8000")

# C3 spine boot resilience (operator-console-requirements.md addendum 9's
# boot-time follow-through — see server/core/knowledge_handle.py's module
# docstring for the full ground-truth investigation: agno's
# `Knowledge.__post_init__` synchronously calls `vector_db.exists()`, which
# used to crash the WHOLE agentos-api process if the vector store was unreachable at
# boot. `_build_app()` below calls `try_connect_now()` inside a try/except
# instead of constructing Knowledge directly; module-level so the lifespan
# (which only receives the ASGI `app`, not `_build_app`'s locals) can start
# the background retry loop after the app object exists.
_knowledge_handle = KnowledgeHandle(lambda: create_knowledge("platform", "platform_knowledge"))


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: Any) -> Any:
    """AgentOS lifespan: ensure pg_duckdb R2 secret on startup, start the
    knowledge-handle background reconnect if boot-time connect failed, log
    shutdown."""
    log_info("AgentOS lifespan: startup")
    from server.core import ensure_duckdb_r2_secret

    log_info(f"pg_duckdb R2 secret ensured: {ensure_duckdb_r2_secret()}")
    if not _knowledge_handle.ready:
        log_info(
            f"knowledge store was NOT ready at boot ({_knowledge_handle.last_error}) — "
            "starting background reconnect (retries every 60s)"
        )
        _knowledge_handle.start_background_retry()
    try:
        yield
    finally:
        _knowledge_handle.stop_background_retry()
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
        Agno Knowledge instance used for reindexing. C3 (spine boot
        resilience): may be a `KnowledgeHandle` — resolved fresh on every
        request via `resolve_knowledge()`, so this genuinely-knowledge-
        dependent route 503s with `{"detail": "knowledge store unavailable"}`
        while the handle isn't ready yet, and starts working again the
        instant a background reconnect succeeds — no restart needed.
    """

    @app.post("/v1/knowledge/reindex")
    async def reindex_knowledge() -> dict[str, Any]:
        """Trigger a full reindex of the knowledge base.

        Returns
        -------
        dict
            ``{"indexedDocumentCount": <int>, "status": "completed"}``

        503 ``{"detail": "knowledge store unavailable"}`` if the knowledge
        handle isn't connected yet (C3 addendum 9 — spine boot resilience).
        """
        live_knowledge = resolve_knowledge(knowledge)
        if live_knowledge is None:
            from fastapi import HTTPException

            raise HTTPException(503, "knowledge store unavailable")
        from scripts.ingest_knowledge import ingest_all

        count = await ingest_all(live_knowledge)
        return {"indexedDocumentCount": count, "status": "completed"}


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _build_app() -> Any:
    """Build and return the AgentOS-wrapped FastAPI application.

    Assembly order:
    1. Build model (provider-agnostic, credential-driven).
    2. Build Agno DB connections (SurrealDB operational store).
    3. Build Knowledge instance (Weaviate-backed, ADR-0040) — via
       `_knowledge_handle` (C3 addendum 9, spine boot resilience): a single
       guarded connect attempt that CANNOT raise (see
       server/core/knowledge_handle.py) — a vector-store outage at boot no
       longer takes down the whole process.
    4. Build LearningMachine (operational memory).
    5. Build context providers (workspace, database, MCP).
    6. Build agent team (all agents + teams + router).
    7. Conditionally attach Document Digest agent.
    8. Wrap FastAPI app with AgentOS.

    Returns
    -------
    Any
        The AgentOS-wrapped ASGI application.

    LIMITATION (documented, accepted — see knowledge_handle.py's module
    docstring for the full explanation): steps 3-6 below read
    `_knowledge_handle.instance` ONCE, synchronously, at boot. If Weaviate was
    down at that moment, every agent's knowledge-search tool and AgentOS's
    OWN built-in `/knowledge*` routes run with NO knowledge base for the
    lifetime of THIS process — a later successful background reconnect does
    NOT retroactively rewire already-built agents/AgentOS internals (that
    would need AgentOS's own resync machinery, deliberately not attempted
    here as too invasive for what C3 asks). What DOES benefit from the live
    swap: register_run_routes/register_evidence_routes/register_knowledge_routes
    below are handed `_knowledge_handle` itself (not a snapshotted instance),
    so runs/evidence-imports/reindex started AFTER a background reconnect
    succeeds see the real knowledge engine without a process restart.
    """
    model = build_model()
    db = get_agno_db()
    # AgentOS's OWN admin-plane db (agno 2.7+: service accounts, schedules,
    # approvals, components; also the tracing write-sink) — separate from
    # `db` above, which is what every agent/team explicitly sets as ITS OWN
    # `db=` (SurrealDb, the operational store; unaffected by this). agno's
    # admin routers (agno/os/routers/service_accounts, schedules, approvals,
    # components) all key off `AgentOS(db=...)` alone via `os_db=self.db`
    # — there is no per-feature override — and SurrealDb's backend does not
    # implement the service-account methods (`create_service_account` etc.
    # simply don't exist on it), so the router 503s with "Service accounts
    # not supported by the configured database". PostgresDb does implement
    # them, and agno's own `_create_all_tables()` (auto_provision_dbs=True,
    # the default) already provisions `ai.agno_service_accounts` natively —
    # no hand-DDL — via the SAME auto-provisioning pass already triggered by
    # the Knowledge contents_db below (verified live: table exists, 0 rows,
    # columns match `agno.db.schemas.service_accounts.ServiceAccount`).
    # Sessions/traces stay visible: their routers aggregate across every
    # registered db (`self.dbs`), and SurrealDb stays registered because
    # each agent/team keeps its own explicit `db=db` (SurrealDb) below —
    # this only redirects the OS-level admin surface + future trace writes.
    admin_db = get_postgres_db()
    _knowledge_handle.try_connect_now()  # never raises — see server/core/knowledge_handle.py
    knowledge = _knowledge_handle.instance  # may be None; agents/AgentOS get this ONE-TIME snapshot (see docstring)
    # Learning MUST ride the Postgres admin db, never SurrealDb: agno's
    # SurrealDb raises NotImplementedError on every learning method
    # (get/upsert/delete/get_learnings), and LearningMachine catches broad
    # Exception around every store call — so on SurrealDb every lane was a
    # SILENT no-op (the long-documented prod bug, root-caused against agno
    # 2.8.0 source 2026-08-02). PostgresDb implements the full protocol.
    learning = build_learning(admin_db, model, knowledge)

    ctx = build_context(model, db, knowledge, learning, db_url)
    agents = build_agent_team(ctx)

    # Gemini long-context digest specialist — present only when
    # GOOGLE_API_KEY is set; deterministic evidence ops stay in the pipeline.
    from server.agents.document_digest import build_document_digest

    digest = build_document_digest(db, knowledge)
    if digest is not None:
        agents["document_digest"] = digest

    # Claude Code as an AgentOS agent (owner sign-off 2026-08-02: "integrate
    # the Claude Code Agent SDK and use the long-lived OAuth token").
    # Standalone solo agent, NOT inside the Router topology — least
    # disruptive slot; promotion into Builder is a later ADR if wanted.
    # Auth: the Claude Agent SDK subprocess inherits this process's env, and
    # CLAUDE_CODE_OAUTH_TOKEN is the native long-lived subscription token
    # (`claude setup-token`) the bundled binary consumes directly. Personal
    # single-owner platform per the usage-scope decision; defaults stay
    # read-only + permission_mode="plan" so the HITL posture holds.
    import os as _os

    from server.agents.claude_code_agent import build_claude_code_agent, claude_code_available

    if claude_code_available() and _os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        agents["claude_code"] = build_claude_code_agent(db=admin_db)

    app = FastAPI(title="MCP Platform Assistant — AgentOS")
    # These three registries get the LIVE HANDLE (not `knowledge`, the
    # one-time snapshot above) so they benefit from a later background
    # reconnect — see the docstring LIMITATION note above.
    register_knowledge_routes(app, _knowledge_handle)

    from server.api.evidence_routes import register_evidence_routes
    from server.api.inspect_routes import register_inspect_routes
    from server.api.run_routes import register_run_routes

    register_evidence_routes(app, _knowledge_handle)
    register_run_routes(app, _knowledge_handle)
    register_inspect_routes(app, _knowledge_handle)

    teams = [v for v in agents.values() if isinstance(v, Team)]
    solo_agents = [v for v in agents.values() if not isinstance(v, Team)]
    # Router first: it is the primary entry point.
    teams.sort(key=lambda t: t.name != "MCP Platform Router")

    agent_os = AgentOS(
        name="AgentOS",
        id="mcp-forensic-platform",
        db=admin_db,  # OS admin plane (service accounts/schedules/approvals/components) — see note above `admin_db = get_postgres_db()`
        agents=solo_agents,
        teams=teams,  # type: ignore[arg-type]  # invariant list[Team|...]; list[Team] is safe here
        # C3 addendum 9: `knowledge` is the one-time boot snapshot (may be
        # None if Weaviate was down at boot — see the docstring LIMITATION
        # note above). AgentOS wants a list; pass [] rather than [None] so
        # `_auto_discover_knowledge_instances`'s isinstance(k, Knowledge)
        # filter doesn't have to special-case a None entry.
        knowledge=[knowledge] if knowledge is not None else [],
        # The evidence workflows existed but were never handed to AgentOS, so
        # `GET /workflows` returned [] and `POST /workflows/{id}/runs` did not
        # exist — the Studio Workflows panel was empty and the only way to run
        # an ingest was the CLI. Registered as WorkflowFactory (not Workflow)
        # because the builders close over a per-request file path; agno invokes
        # the factory per request with the caller's validated input.
        # `registered_workflows` never raises — registration is a convenience
        # surface and must not be able to crash-loop the boot path.
        workflows=registered_workflows(db, knowledge),
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
    final_app = agent_os.get_app()

    # The registry now holds THREE ids (agentos-db / agentos-admin-db /
    # agentos-contents-db, see server/core/session.py). That is correct, but it
    # arms agno's `len(dbs) > 1` guard: `db_id` is optional on every route that
    # takes one, so a client omitting it would get a 400 instead of the
    # silently-wrong 200 it used to get. Neither is right — default it to the
    # SurrealDb operational store so routing is DELIBERATE. Clients that send
    # their own `db_id` (or `knowledge_id`) are untouched.
    from server.api.db_id_middleware import install_db_id_default

    defaulted = install_db_id_default(final_app, DB_ID)
    if defaulted:
        log_info(f"db_id default installed on {defaulted} routes -> {DB_ID}")
    else:
        log_warning("db_id default installed on NO routes — agno route signatures may have changed")

    return final_app


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

app = _build_app()

if __name__ == "__main__":
    import uvicorn

    # reload must stay OFF: MCP lifespan breaks under reload (handoff correction #4).
    uvicorn.run("server.api.main:app", host="0.0.0.0", port=8000, reload=False)
