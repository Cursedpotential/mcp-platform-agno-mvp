"""
agents/factory.py — executable constructors for the MCP Platform agents.

This file turns the prose specs from the handoff into REAL Agno agents/teams.
It uses native Agno HITL primitives (verified against the installed 2.6.13
wheel), not a hand-rolled approval workflow:

  - @approval + @tool(requires_confirmation=True) -> the run PAUSES before the
    tool executes AND a pending approval row is persisted natively
    (agno.run.approval.create_approval_from_pause). Resolve via
    POST /approvals/{id}/resolve, then continue the run — the continue path is
    gated by require_approval_resolved, so an unresolved approval blocks it.
  - UserControlFlowTools -> let an agent pause mid-run to ask the user a question
    (this is the "structured-question intake" the builder flow was promised).

Source access is via Context Providers (provider.get_tools()), memory via the
native LearningMachine on the shared Postgres `db`. Models come from the
provider-agnostic factory in config/settings.py (NO hard default).

Team topology:
  Platform OPS team  (coordinate) : Ingestion + Analysis + Review Gatekeeper
  Builder team       (coordinate) : Dev Copilot + Project PAL + Forensic Data
  Root Router        (route mode): sends a request to OPS vs BUILDER
  (Cloud Drive Cleanup: removed from the active topology 2026-06-12 — separate
   future feature, returns with the Drive/OneDrive MCP integration.)

NOTE ON MODE (correction to earlier handoff prose): the top-level dispatch is
`mode="route"` (leader routes to ONE family and returns its answer), not
"coordinate". Within each family we use "coordinate" (leader delegates +
synthesizes). See the Agno teams reference.
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


# ---------------------------------------------------------------------------
# HITL write tool (native @approval). The run pauses BEFORE this body runs and
# a pending approval row is persisted; on approve-and-continue the body
# executes the real write against the analysis engine. The `evidence` schema
# is protected twice: a statement guard here, plus the infrastructure-level
# read-only engine used by every read path (ADR-0005).
# ---------------------------------------------------------------------------

_write_engine = None  # lazy: created on first approved write, not at import


def _get_write_engine():
    global _write_engine
    if _write_engine is None:
        from db.url import db_url

        _write_engine = create_engine(db_url, pool_pre_ping=True)
    return _write_engine


_EVIDENCE_REF = re.compile(r"\bevidence\s*\.", re.IGNORECASE)


# agno's @approval is typed for a bare Callable; stacking it on a @tool-wrapped
# Function is the documented HITL pattern but trips the overload checker.
@approval  # type: ignore[call-overload]
@tool(requires_confirmation=True)
def apply_db_modification(statement: str, target_schema: str = "analysis") -> str:
    """Apply ONE approved SQL write to the `analysis` schema (never `evidence`).

    The run pauses for recorded human approval before this executes (native
    @approval flow). Single statement per call; unqualified table names
    resolve to the `analysis` schema via search_path.
    """
    if target_schema != "analysis":
        return f"REJECTED: target_schema must be 'analysis', got {target_schema!r}. No write performed."
    if _EVIDENCE_REF.search(statement):
        return "REJECTED: statement references the immutable `evidence` schema. No write performed."
    try:
        with _get_write_engine().begin() as conn:
            conn.execute(text("SET LOCAL search_path TO analysis"))
            result = conn.execute(text(statement))
            rowcount = result.rowcount if result.rowcount is not None else 0
        return f"OK: statement applied to `analysis` (rowcount={rowcount})."
    except Exception as exc:  # surface the DB error to the agent, never crash the run
        return f"ERROR: write failed and was rolled back: {exc}"


# ===========================================================================
# PLATFORM AGENTS
# ===========================================================================


def build_ingestion_orchestrator(model, db, knowledge, learning, source_tools: list[Any]) -> Agent:
    return Agent(
        id="ingestion-orchestrator",
        name="Ingestion Orchestrator",
        role="Coordinate ingestion: hash, parse, normalize, route source data via MCP tools.",
        model=model,
        db=db,
        knowledge=knowledge,
        learning=learning,
        tools=[*source_tools, apply_db_modification],  # writes pause for approval
        add_history_to_context=True,
        num_history_runs=10,
        instructions=[
            "Receive plain-language instructions; search Knowledge for relevant context first.",
            "Plan the exact MCP tool calls needed (parser, hash, normalize, destination).",
            "Any write to storage/config/schema MUST go through apply_db_modification "
            "(it pauses for human approval). Never write to the `evidence` schema.",
            "Report: tool plan, selected parser, hash status, record counts, "
            "destination stores, anomalies, rollback notes.",
        ],
        markdown=True,
    )


def build_analysis_orchestrator(model, db, knowledge, learning, source_tools: list[Any]) -> Agent:
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
        instructions=[
            "Operate only on data already in storage. Derived artifacts are written ONLY to "
            "the `analysis` schema, ONLY via apply_db_modification (pauses for approval).",
            "Report: facts, inferences, confidence notes, provenance summary, review recommendation.",
        ],
        markdown=True,
    )


def build_review_gatekeeper(model, db) -> Agent:
    return Agent(
        id="review-gatekeeper",
        name="Review Gatekeeper",
        role="Translate technical actions into plain-English approval requests; record decisions.",
        model=model,
        db=db,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=[
            "When a run pauses for confirmation, render the pending action in plain English: "
            "what it does, risk level (low/medium/high/critical), systems affected, and how to undo it.",
            "Decisions are recorded natively: resolving via the /approvals API persists who "
            "decided, when, and the resolution. If rejected, capture the reason in the "
            "resolution so the acting agent can choose a better approach.",
            "You never write to evidence or analysis data — approvals are your only surface.",
        ],
        markdown=True,
    )


def build_platform_ops_team(model, db, members: list[Agent]) -> Team:
    return Team(
        name="Platform Ops",
        role="Operate the platform: ingestion, analysis, and human approval.",
        model=model,
        db=db,
        members=members,  # type: ignore[arg-type]  # invariant list[Agent|Team]; list[Agent] is safe here
        mode=TeamMode.coordinate,  # leader delegates + synthesizes within the family
        show_members_responses=True,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=[
            "Route operational work to the right member. Ensure every write passes the "
            "Review Gatekeeper / confirmation gate before execution.",
        ],
        markdown=True,
    )


# ===========================================================================
# BUILDER AGENTS
# ===========================================================================


def build_dev_copilot(model, db, knowledge, learning, code_tools: list[Any]) -> Agent:
    return Agent(
        id="dev-copilot",
        name="Dev Copilot",
        role="Propose repo changes, migrations, interface contracts, and tests.",
        model=model,
        db=db,
        knowledge=knowledge,
        learning=learning,
        # UserControlFlowTools = the promised structured-question intake: the agent
        # can PAUSE and ask you clarifying questions before drafting a plan.
        tools=[*code_tools, UserControlFlowTools()],
        add_history_to_context=True,
        num_history_runs=10,
        instructions=[
            "Search Knowledge + LearningMachine before proposing anything.",
            "If the request is ambiguous, USE the user-input tool to ask focused clarifying "
            "questions (platform? audience? constraints?) before drafting — do not guess.",
            "Default to PROPOSALS, not production writes. Output: files to change, interfaces, "
            "assumptions, migration impact, testing plan, implementation order.",
            "Only enter assisted-coding (write) mode when explicitly switched, and gate it behind approval.",
        ],
        markdown=True,
    )


def build_project_pal(model, db, learning) -> Agent:
    return Agent(
        id="project-pal",
        name="Project PAL",
        role="Maintain rolling memory of goals, blockers, decisions, preferences, session context.",
        model=model,
        db=db,
        learning=learning,  # Session Context + User Memory stores do the work
        add_history_to_context=True,
        num_history_runs=10,
        instructions=[
            "Maintain the session goal/plan/progress (Session Context) and durable preferences "
            "(User Memory). Propose durable learnings under PROPOSE mode (human confirms).",
            "Output: concise progress summary, active blockers, next actions, newly recorded knowledge.",
        ],
        markdown=True,
    )


def build_forensic_data_agent(model, db, learning, readonly_db_tools: list[Any]) -> Agent:
    return Agent(
        id="forensic-data-agent",
        name="Forensic Data Agent",
        role="Explain schemas and query data through approved, read-only interfaces.",
        model=model,
        db=db,
        learning=learning,
        # readonly_db_tools come from DatabaseContextProvider's READ sub-agent
        # (readonly_engine -> `evidence`), which physically cannot write.
        tools=readonly_db_tools,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=[
            "Read-only. The connection physically cannot write — do not attempt schema changes.",
            "Save validated query patterns + schema gotchas to the LearningMachine Learned Knowledge store.",
            "Output: query rationale, safe query shape, result summary, confidence caveats.",
        ],
        markdown=True,
    )


def build_builder_team(model, db, members: list[Agent]) -> Team:
    return Team(
        name="Builder",
        role="Help build the platform: code proposals, memory, and forensic data access.",
        model=model,
        db=db,
        members=members,  # type: ignore[arg-type]  # invariant list[Agent|Team]; list[Agent] is safe here
        mode=TeamMode.coordinate,
        show_members_responses=True,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=["Delegate development work to the right member and synthesize a single answer."],
        markdown=True,
    )


# ===========================================================================
# ROOT ROUTER  (route mode: dispatch to ONE family, return its answer)
# ===========================================================================
# NOTE: the Cloud Drive Cleanup agent was REMOVED from the active topology
# (owner decision 2026-06-12) — it is a separate future feature, not part of
# the evidence platform. It returns, fully toolled, with the Drive/OneDrive
# MCP integration (docs/DEBT.md: cloud-cleanup feature).


def build_root_router(model, db, ops_team: Team, builder_team: Team) -> Team:
    """The missing 'routing agent'. mode='route' = pick the best-fit member and
    return its response directly (platform-operation vs platform-development).
    This is the correct router pattern (not 'coordinate')."""
    return Team(
        name="MCP Platform Router",
        role="Decide whether a request is platform-operation or platform-development.",
        model=model,
        db=db,
        members=[ops_team, builder_team],  # teams can be members
        mode=TeamMode.route,
        add_history_to_context=True,
        num_history_runs=10,
        instructions=[
            "Classify the request and route to exactly one member:",
            "- Platform Ops: ingest/parse/normalize/analyze existing-platform data.",
            "- Builder: propose code, migrations, tests, or maintain project memory.",
            "If genuinely ambiguous, prefer Builder (it can ask clarifying questions).",
        ],
        markdown=True,
    )


# ---------------------------------------------------------------------------
# Top-level assembly. `ctx` bundles the runtime pieces built elsewhere
# (model factory, db, knowledge, learning, and the Context Provider tool lists).
# ---------------------------------------------------------------------------


def build_agent_team(ctx) -> dict[str, Any]:
    """Return every agent/team keyed by stable public name (UI/tests depend on keys)."""
    m, db = ctx.model, ctx.db

    ingestion = build_ingestion_orchestrator(m, db, ctx.knowledge, ctx.learning, ctx.source_tools)
    analysis = build_analysis_orchestrator(m, db, ctx.knowledge, ctx.learning, ctx.source_tools)
    gatekeeper = build_review_gatekeeper(m, db)
    ops_team = build_platform_ops_team(m, db, [ingestion, analysis, gatekeeper])

    dev = build_dev_copilot(m, db, ctx.knowledge, ctx.learning, ctx.code_tools)
    pal = build_project_pal(m, db, ctx.learning)
    forensic = build_forensic_data_agent(m, db, ctx.learning, ctx.readonly_db_tools)
    builder_team = build_builder_team(m, db, [dev, pal, forensic])

    router = build_root_router(m, db, ops_team, builder_team)

    return {
        # platform
        "ingestion_orchestrator": ingestion,
        "analysis_orchestrator": analysis,
        "review_gatekeeper": gatekeeper,
        "platform_ops_team": ops_team,
        # builder
        "dev_copilot": dev,
        "project_pal": pal,
        "forensic_data_agent": forensic,
        "builder_team": builder_team,
        # root
        "router": router,
    }
