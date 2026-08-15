"""agents/providers.py — context providers, learning, and MCP wiring.

Builds the ``PlatformContext`` runtime bundle consumed by
``agents.factory.build_agent_team(ctx)``.

Context-provider architecture::

    WorkspaceContextProvider  → codebase navigation tools (read-only).
    DatabaseContextProvider   → DB tools (split: write engine for ``analysis``,
                                readonly engine for ``evidence``).
    LearningMachine           → operational memory (session context, user memory,
                                entity memory, learned knowledge).

The evidence read-only guarantee is INFRASTRUCTURE-LEVEL: the readonly engine
sets ``default_transaction_read_only=on`` at the connection level, so sub-agents
physically cannot write to the ``evidence`` schema (ADR-0005).

MCP servers (Graphiti, future tools) are wired here and appended to the
``source_tools`` list on ``PlatformContext``.

Public entry points:
- ``build_context(model, db, knowledge, learning, db_url) -> PlatformContext``
- ``build_learning(db, model, knowledge) -> LearningMachine``
"""
# Byline: Claude Code · Fable 5 · 2026-07-31 (Weaviate docstring fix (ADR-0040))

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import create_engine

from agno.context.database import DatabaseContextProvider
from agno.context.workspace import WorkspaceContextProvider

from server.agents.tools.gateway_tools import GATEWAY_TOOLS
from server.agents.tools.realization_tools import REALIZATION_TOOLS
from server.agents.tools.sbv_tools import SBV_TOOLS

# Deferred to later goals (cloud cleanup / MCP fleet):
# from agno.context.gdrive import GoogleDriveContextProvider
# from agno.context.mcp import MCPContextProvider


# ---------------------------------------------------------------------------
# PlatformContext
# ---------------------------------------------------------------------------


@dataclass
class PlatformContext:
    """Runtime bundle handed to ``factory.build_agent_team(ctx)``.

    Attributes
    ----------
    model:
        Agno model instance.
    db:
        Agno operational DB — **PostgresDb** since the 2026-08-04 flatten
        (ADR-0043 decision 3). Was ~~SurrealDB~~; see
        ``server.core.session.get_agno_db``.
    knowledge:
        Agno Knowledge instance (Weaviate-backed, ADR-0040).
    learning:
        Agno LearningMachine instance.
    source_tools:
        Tools available to platform agents (codebase + DB access).
    code_tools:
        Codebase-only tools (for Dev Copilot).
    readonly_db_tools:
        Read-only DB tools (for Forensic Data Agent).
    drive_read_tools:
        Google Drive read tools (populated when cloud-cleanup goal arrives).
    drive_write_tools:
        Google Drive write tools (populated when cloud-cleanup goal arrives).
    """

    model: Any
    db: Any
    knowledge: Any
    learning: Any
    source_tools: list[Any] = field(default_factory=list)
    code_tools: list[Any] = field(default_factory=list)
    readonly_db_tools: list[Any] = field(default_factory=list)
    drive_read_tools: list[Any] = field(default_factory=list)
    drive_write_tools: list[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------


def _make_engine(url: str, readonly: bool = False) -> Any:
    """Create a sync SQLAlchemy engine for ``DatabaseContextProvider``.

    Parameters
    ----------
    url:
        Database URL (from ``db/url.py``).
    readonly:
        When ``True``, forces ``default_transaction_read_only=on`` at the
        connection level — the infrastructure-level read guarantee.
    """
    connect_args = {"options": "-c default_transaction_read_only=on"} if readonly else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------


def build_context(
    model: Any,
    db: Any,
    knowledge: Any,
    learning: Any,
    db_url: str,
) -> PlatformContext:
    """Assemble context providers into the ``PlatformContext`` the factory consumes.

    Parameters
    ----------
    model:
        Agno model instance.
    db:
        Agno operational DB.
    knowledge:
        Agno Knowledge instance.
    learning:
        Agno LearningMachine instance.
    db_url:
        PostgreSQL connection string.

    Returns
    -------
    PlatformContext
        Fully wired runtime bundle.
    """
    # Live codebase — read-only navigation via a scoped sub-agent (query_workspace).
    workspace = WorkspaceContextProvider(root="/app", id="workspace", model=model)
    code_tools = workspace.get_tools()

    # Evidence (read-only) vs analysis (write, approval-gated) — one provider,
    # infrastructure read/write split: reads ride the readonly engine.
    analysis_engine = _make_engine(db_url)
    evidence_engine = _make_engine(db_url, readonly=True)

    db_provider = DatabaseContextProvider(
        id="database",
        sql_engine=analysis_engine,  # write sub-agent -> analysis schema
        readonly_engine=evidence_engine,  # read sub-agent  -> cannot write
        model=model,
    )
    db_tools = db_provider.get_tools()

    # Strictly-read provider for the Forensic Data Agent: write tools never built.
    evidence_provider = DatabaseContextProvider(
        id="evidence",
        sql_engine=evidence_engine,  # even the "write" slot is read-only
        readonly_engine=evidence_engine,
        model=model,
        write=False,  # query_evidence only
    )
    readonly_db_tools = evidence_provider.get_tools()

    # Drive/OneDrive providers arrive with the cloud-cleanup goal.
    drive_read_tools: list[Any] = []
    drive_write_tools: list[Any] = []

    # Source tools for the platform agents = codebase + DB access + the G4
    # parser gateway (server.tools registry, wrapped as 5 meta-op tools) +
    # SBV's REST toolkit (facade-collapse Batch A, docs/planning/facade-
    # collapse-plan.md §1/§2) — additive, does not touch the tools-facade.
    # (TS/Py MCP servers join at Phase 7 via MCPTools/MCPContextProvider.)
    #
    # REALIZATION_TOOLS (W1.5 lane binding, ADR-0045 §A.4): the realization-event
    # writer surface. ``realization_propose`` is a plain @tool — PROPOSING is
    # inert (a 'proposed' row visible_from never reads), so every agent may
    # propose freely, in bulk (analysis / ingest lanes). ``realization_approve``
    # + ``realization_supersede`` are @approval + requires_confirmation=True —
    # APPROVING/SUPERSEDING moves visible_from, so the run PAUSES for a recorded
    # human (owner) approval before the body runs. The @approval gate IS the
    # lane boundary, so which agent holds the tool does not change enforcement:
    # any call pauses for the owner. OPEN owner refinement (not enforcement):
    # scope approve/supersede to the review_gatekeeper only (needs per-agent
    # tool customization in factory.py, which currently passes one uniform
    # source_tools to every agent). Deferred — the @approval backstop holds.
    source_tools = [*code_tools, *db_tools, *GATEWAY_TOOLS, *SBV_TOOLS, *REALIZATION_TOOLS]

    # Graphiti temporal graph memory (ADR-0014) — attached only when the
    # graph profile is up (GRAPHITI_MCP_URL set). AgentOS manages the MCP
    # lifecycle; never run uvicorn reload with this attached.
    graphiti_url = os.getenv("GRAPHITI_MCP_URL", "")
    if graphiti_url:
        from agno.tools.mcp import MCPTools

        source_tools.append(
            MCPTools(
                url=graphiti_url,
                transport="streamable-http",
                tool_name_prefix="graphiti",
                refresh_connection=True,
                # Graphiti's MCP SDK enforces Host-header DNS-rebinding
                # protection (only localhost allowed) — override the Host
                # so in-network calls pass (verified 2026-06-10).
                header_provider=lambda: {"Host": "localhost:8000"},
            )
        )

    return PlatformContext(
        model=model,
        db=db,
        knowledge=knowledge,
        learning=learning,
        source_tools=source_tools,
        code_tools=code_tools,
        readonly_db_tools=readonly_db_tools,
        drive_read_tools=drive_read_tools,
        drive_write_tools=drive_write_tools,
    )


# ---------------------------------------------------------------------------
# Learning machine
# ---------------------------------------------------------------------------


def build_learning(db: Any, model: Any, knowledge: Any) -> Any:
    """Build the native operational memory on Postgres (ADR-0004).

    ``PROPOSE`` mode = agent proposes, human confirms — HITL-native capture for
    the high-stakes durable stores (Entity Memory, Learned Knowledge).

    Parameters
    ----------
    db:
        A db whose backend IMPLEMENTS agno's learning protocol — in this
        platform that means ``get_postgres_db()`` (the admin-plane
        PostgresDb). Never pass the SurrealDb operational store: its
        learning methods all raise NotImplementedError, which
        LearningMachine's broad exception handling turns into a silent
        no-op on every lane (root-caused 2026-08-02).
    model:
        Agno model instance.
    knowledge:
        Agno Knowledge instance.

    Returns
    -------
    LearningMachine
        Configured learning machine with session context, user memory,
        entity memory, and learned knowledge stores.
    """
    from agno.learn import (
        EntityMemoryConfig,
        LearnedKnowledgeConfig,
        LearningMachine,
        LearningMode,
        SessionContextConfig,
        UserMemoryConfig,
        UserProfileConfig,
    )

    return LearningMachine(
        db=db,
        model=model,
        knowledge=knowledge,
        user_profile=UserProfileConfig(mode=LearningMode.ALWAYS),
        user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
        session_context=SessionContextConfig(mode=LearningMode.ALWAYS, enable_planning=True),
        # AGENTIC is the ONLY mode entity memory supports. This was PROPOSE
        # until 2026-08-01, intending a human gate — but there is no extraction
        # pass behind entity memory, so PROPOSE could never have worked: the
        # agent records entities through its tools or not at all. agno 2.8.0
        # accepted the value and silently did nothing; 2.8.6 added a
        # ``__post_init__`` that raises, which made ANY upgrade past 2.8.0 fail
        # at import of ``server.api.main``. Verified against both versions.
        # LearningMode.PROPOSE is documented "learned_knowledge only"
        # (agno/learn/config.py:41); the entity-memory gate has to come from the
        # working-layer review flow instead, not from this config.
        entity_memory=EntityMemoryConfig(mode=LearningMode.AGENTIC),
        # PROPOSE is genuinely implemented here — the store builds an approval
        # prompt and LearningMachine keeps chat history for the confirmation
        # turn. This one is a real human gate; leave it.
        learned_knowledge=LearnedKnowledgeConfig(
            mode=LearningMode.PROPOSE,
            knowledge=knowledge,
            namespace="platform",
            agent_can_save=True,
            agent_can_search=True,
        ),
        namespace="platform",
    )
