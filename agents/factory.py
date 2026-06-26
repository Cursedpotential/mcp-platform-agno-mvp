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

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import create_engine, text

from agno.agent import Agent
from agno.approval import approval
from agno.team.mode import TeamMode
from agno.team.team import Team
from agno.tools import tool
from agno.tools.user_control_flow import UserControlFlowTools

from agents.instructions import get_instructions

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
        from db.url import db_url

        _write_engine = create_engine(db_url, pool_pre_ping=True)
    return _write_engine


_EVIDENCE_REF = re.compile(r"\bevidence\s*\.", re.IGNORECASE)


@approval
@tool(requires_confirmation=True)
def apply_db_modification(statement: str, target_schema: str = "analysis") -> str:
    """Apply ONE approved SQL write to the ``analysis`` schema.

    The run pauses for recorded human approval before this executes (native
    ``@approval`` flow). Single statement per call; unqualified table names
    resolve to the ``analysis`` schema via ``search_path``.

    Parameters
    ----------
    statement:
        A single SQL statement. Must not reference the ``evidence`` schema.
    target_schema:
        Target schema — currently only ``"analysis"`` is allowed.

    Returns
    -------
    str
        Status message (``OK: ...``, ``REJECTED: ...``, or ``ERROR: ...``).
    """
    if target_schema != "analysis":
        return (
            f"REJECTED: target_schema must be 'analysis', got {target_schema!r}. "
            "No write performed."
        )
    if _EVIDENCE_REF.search(statement):
        return (
            "REJECTED: statement references the immutable `evidence` schema. "
            "No write performed."
        )
    try:
        with _get_write_engine().begin() as conn:
            conn.execute(text("SET LOCAL search_path TO analysis"))
            result = conn.execute(text(statement))
            rowcount = result.rowcount if result.rowcount is not None else 0
        return f"OK: statement applied to `analysis` (rowcount={rowcount})."
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
        Agno operational DB (SurrealDB).
    knowledge:
        Agno Knowledge instance (Milvus-backed).
    learning:
        Agno LearningMachine instance.
    source_tools:
        Tool list from ``WorkspaceContextProvider`` + ``DatabaseContextProvider``.
    """
    return Agent(
        id="ingestion-orchestrator",
        name="Ingestion Orchestrator",
        role=(
            "Coordinate ingestion: hash, parse, normalize, route source data "
            "via MCP tools."
        ),
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
        role=(
            "Translate technical actions into plain-English approval requests; "
            "record decisions."
        ),
        model=model,
        db=db,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=get_instructions("gatekeeper"),
        markdown=True,
    )


def build_platform_ops_team(
    model: Any, db: Any, members: list[Agent]
) -> Team:
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
        members=members,
        mode=TeamMode.coordinate,
        show_members_responses=True,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=[
            "Route operational work to the right member. Ensure every write "
            "passes the Review Gatekeeper / confirmation gate before execution.",
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
    can pause mid-run to ask clarifying questions before drafting).

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
        tools=[*code_tools, UserControlFlowTools()],
        add_history_to_context=True,
        num_history_runs=10,
        instructions=get_instructions("dev_copilot"),
        markdown=True,
    )


def build_project_pal(model: Any, db: Any, learning: Any) -> Agent:
    """Build the Project PAL — maintains rolling memory of goals and blockers.

    Parameters
    ----------
    model:
        Agno model instance.
    db:
        Agno operational DB.
    learning:
        Agno LearningMachine (Session Context + User Memory).
    """
    return Agent(
        id="project-pal",
        name="Project PAL",
        role=(
            "Maintain rolling memory of goals, blockers, decisions, preferences, "
            "session context."
        ),
        model=model,
        db=db,
        learning=learning,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=get_instructions("project_pal"),
        markdown=True,
    )


def build_forensic_data_agent(
    model: Any, db: Any, learning: Any, readonly_db_tools: list[Any]
) -> Agent:
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


def build_builder_team(
    model: Any, db: Any, members: list[Agent]
) -> Team:
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
        members=members,
        mode=TeamMode.coordinate,
        show_members_responses=True,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=[
            "Delegate development work to the right member and synthesize a single answer."
        ],
        markdown=True,
    )


# ===========================================================================
# ROOT ROUTER
# ===========================================================================

def build_root_router(
    model: Any, db: Any, ops_team: Team, builder_team: Team
) -> Team:
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

    ingestion = build_ingestion_orchestrator(
        m, db, ctx.knowledge, ctx.learning, ctx.source_tools
    )
    analysis = build_analysis_orchestrator(
        m, db, ctx.knowledge, ctx.learning, ctx.source_tools
    )
    gatekeeper = build_review_gatekeeper(m, db)
    ops_team = build_platform_ops_team(m, db, [ingestion, analysis, gatekeeper])

    dev = build_dev_copilot(m, db, ctx.knowledge, ctx.learning, ctx.code_tools)
    pal = build_project_pal(m, db, ctx.learning)
    forensic = build_forensic_data_agent(m, db, ctx.learning, ctx.readonly_db_tools)
    builder_team = build_builder_team(m, db, [dev, pal, forensic])

    router = build_root_router(m, db, ops_team, builder_team)

    return {
        # Platform Ops
        "ingestion_orchestrator": ingestion,
        "analysis_orchestrator": analysis,
        "review_gatekeeper": gatekeeper,
        "platform_ops_team": ops_team,
        # Builder
        "dev_copilot": dev,
        "project_pal": pal,
        "forensic_data_agent": forensic,
        "builder_team": builder_team,
        # Root
        "router": router,
    }
