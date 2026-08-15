"""agents/factory.py — agent/team constructors for the MCP Platform.

Every Agent and Team is built by a ``build_<name>()`` function in this file.
The top-level ``build_agent_team(ctx)`` assembles the full topology and returns
a dict keyed by stable public name (UI/tests depend on these keys).

Architecture::

    Root Router (mode=route)
    +-- Platform Ops (mode=coordinate)
    |   +-- ingestion_orchestrator
    |   +-- analysis_orchestrator
    |   +-- review_gatekeeper
    |   +-- transcript_miner
    +-- Builder (mode=coordinate)
    |   +-- dev_copilot
    |   +-- project_pal
    |   +-- forensic_data_agent
    +-- document_digest  (conditional, GOOGLE_API_KEY)

Conventions:
- All functions use ``from __future__ import annotations`` + full type hints.
- Agent ``id=`` is a STABLE PUBLIC CONTRACT — never change it without updating
  every consumer (UI, tests, docs).
- Instructions come from ``agents/instructions.py`` via ``get_instructions(key)``.
- The HITL write tool (``apply_db_modification``) is the ONLY way agents write
  to the ``analysis`` schema. It pauses for human approval before executing.
"""
# Byline: Claude Code · Fable 5 · 2026-07-31 (enable_user_memories on Root Router + Project PAL; Weaviate docstring fix)
# Byline: Codex · GPT-5 · 2026-08-13 (type-safe audit hook attachment)
# Byline: Claude Code · glm-5.2:cloud · 2026-08-14 (docstring topology: add transcript_miner,
# mounted under Platform Ops since 2026-08-04 per the inline note at line ~479)

from __future__ import annotations

import os
import re
from typing import Any

from sqlalchemy import create_engine, text

from agno.agent import Agent
from agno.approval import approval
from agno.team.mode import TeamMode
from agno.team.team import Team
from agno.tools import tool
from agno.tools.file_generation import FileGenerationTools
from agno.tools.user_control_flow import UserControlFlowTools

from server.agents.instructions import get_instructions

# ---------------------------------------------------------------------------
# HITL write tool (native @approval)
# ---------------------------------------------------------------------------
# The run pauses BEFORE this body executes; a pending approval row is persisted.
# On approve-and-continue the body runs the real write. The ``evidence`` schema
# is protected twice: a statement guard here, plus the infrastructure-level
# read-only engine on every read path (ADR-0005).

_write_engine: Any = None  # lazy: created on first approved write, not at import


def _get_write_engine() -> Any:
    """Return (and lazily create) the SQLAlchemy engine for approved writes.

    The engine is created on first use — not at import time — so the factory
    can be imported in contexts where no DB is available (tests, tool-facade).
    """
    global _write_engine
    if _write_engine is None:
        from server.core.url import db_url

        _write_engine = create_engine(db_url, pool_pre_ping=True)
    return _write_engine


_EVIDENCE_REF = re.compile(r"\bevidence\s*\.", re.IGNORECASE)

# Schemas the approval-gated write tool may target. `evidence` is HARD-DENIED
# regardless of this list (immutable, infrastructure-enforced read-only) — the
# allowlist can grow via env, the evidence wall cannot be configured away.
_WRITE_SCHEMAS: frozenset[str] = frozenset(
    s.strip() for s in os.getenv("DB_WRITE_SCHEMAS", "analysis").split(",") if s.strip()
) - {"evidence"}
_SCHEMA_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


@approval  # type: ignore[call-overload]
@tool(requires_confirmation=True)
def apply_db_modification(statement: str, target_schema: str = "analysis") -> str:
    """Apply ONE approved SQL write to an allowlisted schema.

    The run pauses for recorded human approval before this executes (native
    ``@approval`` flow). Single statement per call; unqualified table names
    resolve to ``target_schema`` via ``search_path``.

    Parameters
    ----------
    statement:
        A single SQL statement. Must not reference the ``evidence`` schema.
    target_schema:
        Target schema. Allowed values come from the ``DB_WRITE_SCHEMAS`` env
        var (comma-separated; default ``"analysis"``). ``evidence`` is always
        rejected regardless of configuration.

    Returns
    -------
    str
        Status message (``OK: ...``, ``REJECTED: ...``, or ``ERROR: ...``).
    """
    if target_schema not in _WRITE_SCHEMAS or not _SCHEMA_NAME_RE.match(target_schema):
        return (
            f"REJECTED: target_schema must be one of {sorted(_WRITE_SCHEMAS)} "
            f"(DB_WRITE_SCHEMAS), got {target_schema!r}. No write performed."
        )
    if _EVIDENCE_REF.search(statement):
        return "REJECTED: statement references the immutable `evidence` schema. No write performed."
    try:
        with _get_write_engine().begin() as conn:
            conn.execute(text(f"SET LOCAL search_path TO {target_schema}"))
            result = conn.execute(text(statement))
            rowcount = result.rowcount if result.rowcount is not None else 0
        return f"OK: statement applied to `{target_schema}` (rowcount={rowcount})."
    except Exception as exc:
        return f"ERROR: write failed and was rolled back: {exc}"


# ===========================================================================
# PLATFORM OPS AGENTS
# ===========================================================================


def build_ingestion_orchestrator(
    model: Any,
    db: Any,
    knowledge: Any,
    learning: Any,
    source_tools: list[Any],
) -> Agent:
    """Build the Ingestion Orchestrator — coordinates hash → parse → normalize → store.

    Parameters
    ----------
    model:
        Agno model instance (from ``app/settings.build_model()``).
    db:
        Agno operational DB — **PostgresDb** since the 2026-08-04 flatten
        (ADR-0043 decision 3). Was ~~SurrealDB~~; see
        ``server.core.session.get_agno_db``.
    knowledge:
        Agno Knowledge instance (Weaviate-backed, ADR-0040).
    learning:
        Agno LearningMachine instance.
    source_tools:
        Tool list from ``WorkspaceContextProvider`` + ``DatabaseContextProvider``.
    """
    return Agent(
        id="ingestion-orchestrator",
        name="Ingestion Orchestrator",
        role=("Coordinate ingestion: hash, parse, normalize, route source data via MCP tools."),
        model=model,
        db=db,
        knowledge=knowledge,
        learning=learning,
        tools=[*source_tools, apply_db_modification],
        add_history_to_context=True,
        num_history_runs=10,
        instructions=get_instructions("ingestion"),
        markdown=True,
    )


def build_analysis_orchestrator(
    model: Any,
    db: Any,
    knowledge: Any,
    learning: Any,
    source_tools: list[Any],
) -> Agent:
    """Build the Analysis Orchestrator — runs analysis on stored data.

    Parameters
    ----------
    model, db, knowledge, learning, source_tools:
        See ``build_ingestion_orchestrator``.
    """
    return Agent(
        id="analysis-orchestrator",
        name="Analysis Orchestrator",
        role="Run analysis after data exists in storage; produce structured analytical artifacts.",
        model=model,
        db=db,
        knowledge=knowledge,
        learning=learning,
        tools=[*source_tools, apply_db_modification],
        add_history_to_context=True,
        num_history_runs=10,
        instructions=get_instructions("analysis"),
        markdown=True,
    )


def build_review_gatekeeper(model: Any, db: Any) -> Agent:
    """Build the Review Gatekeeper — translates technical actions into approval requests.

    Parameters
    ----------
    model:
        Agno model instance.
    db:
        Agno operational DB.
    """
    return Agent(
        id="review-gatekeeper",
        name="Review Gatekeeper",
        role=("Translate technical actions into plain-English approval requests; record decisions."),
        model=model,
        db=db,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=get_instructions("gatekeeper"),
        markdown=True,
    )


def build_platform_ops_team(model: Any, db: Any, members: list[Agent]) -> Team:
    """Build the Platform Ops team (coordinate mode).

    Parameters
    ----------
    model:
        Agno model instance.
    db:
        Agno operational DB.
    members:
        ``[ingestion_orchestrator, analysis_orchestrator, review_gatekeeper]``
    """
    return Team(
        name="Platform Ops",
        role="Operate the platform: ingestion, analysis, and human approval.",
        model=model,
        db=db,
        members=members,  # type: ignore[arg-type]
        mode=TeamMode.coordinate,
        show_members_responses=True,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=[
            "Route operational work to the right member. Ensure every write "
            "passes the Review Gatekeeper / confirmation gate before execution.",
            "If the request is actually platform DEVELOPMENT work (code changes, "
            "migrations, schema design, tooling), do not attempt it: reply with a "
            "first line of exactly `REROUTE: builder` plus one sentence of reason, "
            "so the Root Router re-dispatches it.",
        ],
        markdown=True,
    )


# ===========================================================================
# BUILDER AGENTS
# ===========================================================================


def build_dev_copilot(
    model: Any,
    db: Any,
    knowledge: Any,
    learning: Any,
    code_tools: list[Any],
) -> Agent:
    """Build the Dev Copilot — proposes code, migrations, and interface contracts.

    Includes ``UserControlFlowTools`` for structured-question intake (the agent
    can pause mid-run to ask clarifying questions before drafting) and
    ``FileGenerationTools`` (agno built-in) so proposals can be handed back as
    downloadable artifacts (patch files, generated docs/specs, code files)
    instead of only inline markdown. Default settings (``save_files=False``):
    generated files come back as in-memory ``File`` artifacts on the tool
    result, matching the read-only-workspace convention ``code_tools``
    already uses (``WorkspaceContextProvider`` never writes to ``/app``) —
    persisting to disk would need a writable sandbox mount that doesn't
    exist yet (``docker/sandbox`` has no repo mount, by design).

    Parameters
    ----------
    model, db, knowledge, learning:
        See ``build_ingestion_orchestrator``.
    code_tools:
        Tool list from ``WorkspaceContextProvider`` (codebase navigation).
    """
    return Agent(
        id="dev-copilot",
        name="Dev Copilot",
        role="Propose repo changes, migrations, interface contracts, and tests.",
        model=model,
        db=db,
        knowledge=knowledge,
        learning=learning,
        tools=[*code_tools, UserControlFlowTools(), FileGenerationTools()],
        add_history_to_context=True,
        num_history_runs=10,
        instructions=get_instructions("dev_copilot"),
        markdown=True,
    )


def build_project_pal(model: Any, db: Any, learning: Any, knowledge: Any = None) -> Agent:
    """Build the Project PAL — maintains rolling memory of goals and blockers.

    Parameters
    ----------
    model:
        Agno model instance.
    db:
        Agno operational DB.
    learning:
        Agno LearningMachine (Session Context + User Memory).
    knowledge:
        Knowledge base (optional, added 2026-08-04 per Codex A-09). PAL is
        configured with "what's the current project status / summarize recent
        decisions" quick-prompts, but had ONLY a db and the LearningMachine —
        no retrieval surface at all — so it could answer those only from what
        was already in session context or memory. With the platform knowledge
        base it can actually read the project's own docs. None is accepted so a
        boot-time vector-store outage degrades PAL rather than failing the
        build.
    """
    return Agent(
        id="project-pal",
        name="Project PAL",
        role=("Maintain rolling memory of goals, blockers, decisions, preferences, session context."),
        model=model,
        db=db,
        knowledge=knowledge,
        search_knowledge=knowledge is not None,
        learning=learning,
        add_history_to_context=True,
        num_history_runs=10,
        # Rolling memory IS this agent's role — capture user memories when it
        # runs directly (the Root Router covers the routed path).
        enable_user_memories=True,
        instructions=get_instructions("project_pal"),
        markdown=True,
    )


def build_forensic_data_agent(model: Any, db: Any, learning: Any, readonly_db_tools: list[Any]) -> Agent:
    """Build the Forensic Data Agent — read-only schema and data interface.

    Parameters
    ----------
    model:
        Agno model instance.
    db:
        Agno operational DB.
    learning:
        Agno LearningMachine.
    readonly_db_tools:
        Tool list from the read-only ``DatabaseContextProvider`` (evidence engine).
        These tools physically cannot write (``default_transaction_read_only=on``).
    """
    return Agent(
        id="forensic-data-agent",
        name="Forensic Data Agent",
        role="Explain schemas and query data through approved, read-only interfaces.",
        model=model,
        db=db,
        learning=learning,
        tools=readonly_db_tools,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=get_instructions("forensic"),
        markdown=True,
    )


def build_builder_team(model: Any, db: Any, members: list[Agent]) -> Team:
    """Build the Builder team (coordinate mode).

    Parameters
    ----------
    model:
        Agno model instance.
    db:
        Agno operational DB.
    members:
        ``[dev_copilot, project_pal, forensic_data_agent]``
    """
    return Team(
        name="Builder",
        role="Help build the platform: code proposals, memory, and forensic data access.",
        model=model,
        db=db,
        members=members,  # type: ignore[arg-type]
        mode=TeamMode.coordinate,
        show_members_responses=True,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=[
            "Delegate development work to the right member and synthesize a single answer.",
            "If the request is actually OPERATIONAL work on existing platform data "
            "(ingest, parse, analyze evidence), do not attempt it: reply with a first "
            "line of exactly `REROUTE: platform-ops` plus one sentence of reason, so "
            "the Root Router re-dispatches it.",
        ],
        markdown=True,
    )


# ===========================================================================
# ROOT ROUTER
# ===========================================================================


def build_root_router(model: Any, db: Any, ops_team: Team, builder_team: Team) -> Team:
    """Build the Root Router (route mode — picks ONE family, returns its answer).

    Parameters
    ----------
    model:
        Agno model instance.
    db:
        Agno operational DB.
    ops_team:
        The ``Platform Ops`` team.
    builder_team:
        The ``Builder`` team.
    """
    return Team(
        name="MCP Platform Router",
        role="Decide whether a request is platform-operation or platform-development.",
        model=model,
        db=db,
        members=[ops_team, builder_team],
        mode=TeamMode.route,
        add_history_to_context=True,
        num_history_runs=10,
        # Memory capture lives HERE (plus Project PAL) and nowhere else: the
        # router sees every user message, so one enable = one memory-extraction
        # pass per user run instead of one per member agent. Memories persist
        # to `db` (PostgresDb since the 2026-08-04 flatten, ADR-0043 decision 3;
        # was ~~SurrealDb~~ — table role `agno_memories`) and feed the panel
        # — which stayed empty because nothing ever wrote memories
        # (HANDOFF-2026-07-30 audit, confirmed live 2026-07-31).
        enable_user_memories=True,
        instructions=get_instructions("router"),
        markdown=True,
    )


# ===========================================================================
# TOP-LEVEL ASSEMBLY
# ===========================================================================


def build_agent_team(ctx: Any) -> dict[str, Any]:
    """Build every agent/team and return them keyed by stable public name.

    Parameters
    ----------
    ctx:
        ``PlatformContext`` (from ``providers.py``) with attributes:
        ``model``, ``db``, ``knowledge``, ``learning``, ``source_tools``,
        ``code_tools``, ``readonly_db_tools``.

    Returns
    -------
    dict[str, Any]
        Stable key → Agent/Team instance. Keys are a PUBLIC CONTRACT:
        ``ingestion_orchestrator``, ``analysis_orchestrator``,
        ``review_gatekeeper``, ``platform_ops_team``, ``dev_copilot``,
        ``project_pal``, ``forensic_data_agent``, ``builder_team``, ``router``.
    """
    m, db = ctx.model, ctx.db

    ingestion = build_ingestion_orchestrator(m, db, ctx.knowledge, ctx.learning, ctx.source_tools)
    analysis = build_analysis_orchestrator(m, db, ctx.knowledge, ctx.learning, ctx.source_tools)
    gatekeeper = build_review_gatekeeper(m, db)
    ops_team = build_platform_ops_team(m, db, [ingestion, analysis, gatekeeper])

    # Transcript Miner: the module and its config quick-prompts existed since
    # 2026-07, but build_agent_team never returned it — so config.yaml
    # advertised `transcript-miner` prompts pointing at an agent that was not
    # in the runtime roster (Codex A-08: "configuration must not advertise
    # absent agents"). Mounted 2026-08-04 under Platform Ops, where its
    # custody->parse->store pipeline belongs.
    from server.agents.transcript_miner import build_transcript_miner

    miner = build_transcript_miner(m, db, ctx.knowledge, ctx.learning, ctx.source_tools)
    ops_team = build_platform_ops_team(m, db, [ingestion, analysis, gatekeeper, miner])

    dev = build_dev_copilot(m, db, ctx.knowledge, ctx.learning, ctx.code_tools)
    # PAL gets the knowledge handle (Codex A-09): it is configured to answer
    # "what's the project status / what decisions were made", but had only a db
    # and the LearningMachine — no way to retrieve anything not already in
    # session context or memory, so those quick-prompts could not be honored.
    pal = build_project_pal(m, db, ctx.learning, ctx.knowledge)
    forensic = build_forensic_data_agent(m, db, ctx.learning, ctx.readonly_db_tools)
    builder_team = build_builder_team(m, db, [dev, pal, forensic])

    router = build_root_router(m, db, ops_team, builder_team)

    # AgentOS raises `ValueError: Duplicate IDs found in AgentOS` and the
    # process crash-loops if two entries share an id — which is exactly what
    # happened on 2026-08-04 when Transcript Miner was mounted while still
    # carrying the Ingestion Orchestrator's id (it delegates to that builder).
    # Fail HERE, at assembly, with the offending id named, instead of after
    # AgentOS has been constructed: the message is actionable and the failure
    # surfaces in tests rather than in a restart loop.
    _built = [ingestion, analysis, gatekeeper, miner, dev, pal, forensic]
    _ids = [getattr(a, "id", None) for a in _built]
    _dupes = {i for i in _ids if i and _ids.count(i) > 1}
    if _dupes:
        raise ValueError(
            f"duplicate agent id(s) in the roster: {sorted(_dupes)} — every agent "
            "needs its own stable id (a builder that delegates to another must "
            "override id/name)"
        )

    roster = {
        # Platform Ops
        "ingestion_orchestrator": ingestion,
        "analysis_orchestrator": analysis,
        "review_gatekeeper": gatekeeper,
        "transcript_miner": miner,
        "platform_ops_team": ops_team,
        # Builder
        "dev_copilot": dev,
        "project_pal": pal,
        "forensic_data_agent": forensic,
        "builder_team": builder_team,
        # Root
        "router": router,
    }

    # ===========================================================================
    # S5 AUDIT-EVERYTHING INTEGRATION POINT (ADR-0047 / D-042) — every tool
    # call made by every Agent/Team this factory builds gets logged to
    # ops.audit_ledger. ONE agno-native tool_hooks wrapper
    # (server/core/audit.py::audit_tool_hook), attached here rather than
    # threaded through every build_*() constructor above: agno reads
    # `Agent.tool_hooks` / `Team.tool_hooks` when it resolves each object's
    # tools into Function objects (agno/agent/_tools.py, agno/team/_tools.py
    # — verified against installed agno==2.8.7), and that resolution reads
    # the attribute fresh, so setting it post-construction here is
    # equivalent to passing `tool_hooks=[audit_tool_hook]` into every
    # constructor call without touching any of them. `roster` already holds
    # every Agent/Team this function builds (agents WITHOUT tools simply
    # never trigger the hook — it only fires on an actual tool call).
    # Appends rather than overwrites so a future builder that sets its own
    # tool_hooks is not silently clobbered.
    from server.core.audit import audit_tool_hook

    for _obj_value in roster.values():
        _obj: Any = _obj_value
        _obj.tool_hooks = [*(getattr(_obj, "tool_hooks", None) or []), audit_tool_hook]

    return roster
