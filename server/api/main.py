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
# Byline: Codex · GPT-5 · 2026-08-13 (ADR-0053 alignment; ADR-0054 optional Langfuse OTLP export)
# Byline: Codex · GPT-5 · 2026-08-16 (framework-neutral ingest and canonical knowledge routes)
# Byline: Claude Code · Opus 5 · 2026-08-05 (SurrealDB→Postgres doc-drift cleanup — the
#   2026-08-04 flatten (ADR-0043 decision 3) moved the operational store to Postgres, but
#   these comments still described the pre-flatten two-backend split)
# DEPLOY NOTE (2026-08-01): exec-tier auto-deploys from `main` via the Coolify
# GitHub App (`cursedpotential`, app_id 4047891, installation 140142795;
# Coolify source_id=2). Watch paths are `compose.exec.yaml`, `Dockerfile`,
# `server/**` — a change confined to `docs/` will NOT redeploy the API.

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import partial
from os import getenv
from pathlib import Path
from typing import Any

from agno.os import AgentOS
from agno.registry import Registry
from agno.team.team import Team
from agno.utils.log import log_info, log_warning
from agno.workflow.factory import WorkflowFactory
from agno.workflow.remote import RemoteWorkflow
from agno.workflow.workflow import Workflow
from fastapi import FastAPI

from server.agents.factory import build_agent_team
from server.agents.providers import build_context, build_learning
from server.api.workflow_registry import registered_workflows
from server.core import create_knowledge, get_agno_db, get_postgres_db
from server.core.knowledge_handle import KnowledgeHandle
from server.core.model_registry import build_catalog_models, load_available_models
from server.core.session import DB_ID
from server.core.settings import build_model
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
_knowledge_handle = KnowledgeHandle(partial(create_knowledge, "platform", "platform_knowledge"))

# Named knowledge bases — the SIX-LANE architecture (ADR-0050, 2026-08-10).
# AgentOS takes a LIST; each entry becomes its own selectable base.
#
# Storage (ADR-0050 Phase 1): each base gets its OWN contents table (per-table
# PostgresDb cache in session.py, all sharing id="agentos-db") AND its own
# Weaviate collection — the embedder is a pinned per-collection contract
# (ADR-0010; all lanes currently nv-embed-v1 per owner ruling 2026-08-10,
# per-lane embedders are a future experiment) and mixing corpora in one
# collection silently destroys retrieval margin. Evidence isolation is
# STRUCTURAL: a missed filter can never leak evidence into other lanes.
#
# Each base gets its OWN handle so a vector-store outage degrades one base
# instead of all of them (same boot-resilience contract as the platform handle).
_KNOWLEDGE_BASES: dict[str, str] = {
    "legal": "legal_knowledge",  # strategy + documents ONLY (owner 2026-08-10)
    "evidence": "evidence_knowledge",  # custody-approved records ONLY; horizon-gated retrieval
    "personal_history": "personal_history_knowledge",  # ADR-0053: includes relationship history
    "context": "platform_context",  # AI chats (ADR-0044 context corpus; existing collection)
}
_extra_knowledge_handles: dict[str, KnowledgeHandle] = {
    name: KnowledgeHandle(partial(create_knowledge, name, table)) for name, table in _KNOWLEDGE_BASES.items()
}


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
    for label, handle in (("platform", _knowledge_handle), *_extra_knowledge_handles.items()):
        if not handle.ready:
            log_info(
                f"knowledge base {label!r} was NOT ready at boot ({handle.last_error}) — "
                "starting background reconnect (retries every 60s)"
            )
            handle.start_background_retry()
    try:
        yield
    finally:
        for handle in (_knowledge_handle, *_extra_knowledge_handles.values()):
            handle.stop_background_retry()
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
        Retained for source compatibility while callers migrate. Folder-walk
        ingestion no longer depends on an Agno Knowledge instance.
    """

    @app.post("/v1/knowledge/reindex")
    async def reindex_knowledge() -> dict[str, Any]:
        """Run the framework-neutral folder walker into canonical PostgreSQL.

        Returns
        -------
        dict
            ``{"indexedDocumentCount": <int>, "status": "completed"}``

        Folder-walk canonical ingestion is independent of vector-store health.
        """
        from scripts.ingest_knowledge import ingest_all

        count = await ingest_all()
        return {"indexedDocumentCount": count, "status": "completed", "store": "postgresql"}


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _assert_agno_version() -> None:
    """One authoritative answer to "which agno is running" (Codex A-01).

    requirements.txt pins the deployed agno; uv.lock and the local venv have
    both been observed drifting (2.8.0 declared vs 2.8.6 imported), and 2.8.6
    changes LearningMachine validation. A silent skew means every behavior we
    verified was verified against the wrong wheel. Logged as CRITICAL rather
    than raised: the local venv drifts deliberately (`uv run --no-sync` is the
    documented workaround), so a hard crash would break dev; in prod the
    container installs from requirements.txt, so a mismatch there is a real
    build problem this line makes impossible to miss.
    """
    import logging
    import re

    import agno

    req = Path(__file__).resolve().parents[2] / "requirements.txt"
    pinned = ""
    try:
        m = re.search(r"^agno==([0-9][\w.]*)$", req.read_text(encoding="utf-8"), re.M)
        pinned = m.group(1) if m else ""
    except OSError:
        pass
    running = getattr(agno, "__version__", "unknown")
    if pinned and running != pinned:
        logging.getLogger(__name__).critical(
            "AGNO VERSION SKEW: running %s but requirements.txt pins %s — "
            "behavior verified against the pin does NOT transfer. "
            "(Local dev: use `uv run --no-sync`. Prod: rebuild the image.)",
            running,
            pinned,
        )
    else:
        logging.getLogger(__name__).info("agno %s (matches requirements pin)", running)


def _build_app() -> Any:
    """Build and return the AgentOS-wrapped FastAPI application.

    Assembly order:
    1. Build model (provider-agnostic, credential-driven).
    2. Build Agno DB connections (**Postgres** operational store — was
       ~~SurrealDB~~ until the 2026-08-04 flatten, ADR-0043 decision 3).
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
    _assert_agno_version()
    model = build_model()
    db = get_agno_db()
    # AgentOS's OWN admin-plane db (agno 2.7+: service accounts, schedules,
    # approvals, components; also the tracing write-sink).
    #
    # ⚠ POST-FLATTEN (2026-08-04, ADR-0043 decision 3): this is now the SAME
    # PostgresDb singleton as `db` above — `get_agno_db()` delegates to
    # `get_postgres_db()`. Both names are kept because they express different
    # ROLES (operational store vs admin plane) and agno takes them in
    # different parameters, but they are one object and one `db.id`. That is
    # deliberate: agno keys its db registry by `db.id` and counts KEYS, so
    # two ids would arm the multi-db gate and make every route that omits
    # `db_id` return 400.
    #
    # ~~Pre-flatten rationale, kept because it is why the admin plane had to
    # be Postgres in the first place:~~ agno's admin routers
    # (agno/os/routers/service_accounts, schedules, approvals, components)
    # all key off `AgentOS(db=...)` alone via `os_db=self.db` — there is no
    # per-feature override — and SurrealDb's backend does not implement the
    # service-account methods (`create_service_account` etc. simply don't
    # exist on it), so the router 503s with "Service accounts not supported
    # by the configured database". PostgresDb does implement them, and agno's
    # own `_create_all_tables()` (auto_provision_dbs=True, the default)
    # provisions `ai.agno_service_accounts` natively — no hand-DDL — via the
    # SAME auto-provisioning pass already triggered by the Knowledge
    # contents_db below (verified live: table exists, columns match
    # `agno.db.schemas.service_accounts.ServiceAccount`).
    admin_db = get_postgres_db()
    _knowledge_handle.try_connect_now()  # never raises — see server/core/knowledge_handle.py
    knowledge = _knowledge_handle.instance  # may be None; agents/AgentOS get this ONE-TIME snapshot (see docstring)
    # The named bases connect the same guarded way — one failing base cannot
    # take down the others or the process.
    for _label, _handle in _extra_knowledge_handles.items():
        _handle.try_connect_now()
        log_info(
            f"knowledge base {_label!r}: " + ("connected" if _handle.ready else f"NOT ready ({_handle.last_error})")
        )
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
    from server.api.case_management_routes import register_case_management_routes
    from server.api.inspect_routes import register_inspect_routes
    from server.api.ingest_routes import register_ingest_routes
    from server.api.repair_routes import router as repair_router
    from server.api.run_routes import register_run_routes

    # ADR-0050 Phase 1: messaging evidence (sms-xml) vectors into the EVIDENCE
    # lane's handle — evidence_knowledge gets its first writer and stops
    # leaking into the platform collection. evidence_routes is the
    # chat-transcript vertical (CONTEXT per ADR-0044 §1) and stays on the
    # platform handle until Phase 2 routes it to the context lane.
    register_evidence_routes(app, _knowledge_handle)
    register_run_routes(app, _knowledge_handle, evidence_knowledge=_extra_knowledge_handles["evidence"])
    register_inspect_routes(app, _knowledge_handle)
    register_ingest_routes(app)
    register_case_management_routes(app)
    app.include_router(repair_router)

    teams = [v for v in agents.values() if isinstance(v, Team)]
    solo_agents = [v for v in agents.values() if not isinstance(v, Team)]
    # Router first: it is the primary entry point.
    teams.sort(key=lambda t: t.name != "MCP Platform Router")

    # --- Studio model picker -------------------------------------------------
    # `GET /models` is agno's *usage report* — the distinct models already
    # attached to agents/teams (agno/os/router.py::get_models, unchanged in
    # 2.8.0). All our agents share one `build_model()` object, so it returns a
    # single entry and there is no config-driven path into it.
    #
    # The documented Studio picker source is the Registry: Studio's agent
    # builder shows "Model: select from registered models"
    # (docs.agno.com /agent-os/studio/agents) and the Registry is documented as
    # the home for "model provider instances" Studio depends on
    # (/agent-os/studio/registry), served at `GET /registry?resource_type=model`.
    # So we hand agno a Registry built from the SAME verified catalog that
    # `AgentOSConfig.available_models` (config.yaml) publishes — one source of
    # truth, and the agent roster the user sees is untouched.
    config_path = Path(__file__).parent / "config.yaml"
    registry = Registry(
        name="Platform Model Catalog",
        description="Verified-reachable models for this deployment (see scripts/update_available_models.py).",
        models=build_catalog_models(load_available_models(config_path)),
    )

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
        # Every connected base is registered, so the UI lists Platform, Legal
        # and Evidence as separate selectable knowledge bases rather than the
        # single "platform" entry the owner kept hitting. A base that failed to
        # connect is simply absent until its background retry succeeds.
        knowledge=[k for k in (knowledge, *(h.instance for h in _extra_knowledge_handles.values())) if k is not None],
        # The evidence workflows existed but were never handed to AgentOS, so
        # `GET /workflows` returned [] and `POST /workflows/{id}/runs` did not
        # exist — the Studio Workflows panel was empty and the only way to run
        # an ingest was the CLI. Registered as WorkflowFactory (not Workflow)
        # because the builders close over a per-request file path; agno invokes
        # the factory per request with the caller's validated input.
        # `registered_workflows` never raises — registration is a convenience
        # surface and must not be able to crash-loop the boot path.
        workflows=list[Workflow | RemoteWorkflow | WorkflowFactory](registered_workflows(db, knowledge)),
        base_app=app,
        enable_mcp_server=True,  # serve the OS as an MCP server at /mcp (extracted standalone by app/mcp_main.py — mounted /mcp 500s, see that file)
        on_route_conflict="preserve_base_app",
        scheduler=True,
        scheduler_base_url=scheduler_base_url,
        tracing=True,
        authorization=False,  # local/dev; JWT when multi-user
        lifespan=lifespan,
        config=str(config_path),
        # Feeds `GET /registry?resource_type=model` — the Studio picker. See
        # the block above `agent_os = AgentOS(` for why this, not `/models`.
        registry=registry,
    )
    final_app = agent_os.get_app()

    # Optional diagnostic mirror. AgentOS's Postgres trace store and the
    # platform-owned durable run reports stay authoritative when absent/down.
    from server.observability.langfuse import configure_langfuse_exporter

    configure_langfuse_exporter()

    # ~~The registry now holds THREE ids (agentos-db / agentos-admin-db /
    # agentos-contents-db)~~ — since the 2026-08-04 flatten (ADR-0043 decision
    # 3) `DB_ID`, `ADMIN_DB_ID` and `CONTENTS_DB_ID` are all the SAME string
    # ("agentos-db") backed by ONE PostgresDb, so agno's `len(dbs) > 1` guard
    # is no longer armed and no route can 400 for a missing `db_id`.
    #
    # The default is kept anyway, deliberately: it is now a cheap no-op that
    # makes routing EXPLICIT rather than implicit, and it is the guard that
    # keeps a future second db (a second Knowledge base needs its own id — see
    # the flatten note in server/core/session.py) from silently re-arming the
    # 400. Clients that send their own `db_id`/`knowledge_id` are untouched.
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
