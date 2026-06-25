"""
agents/providers.py — Context Providers + LearningMachine -> PlatformContext
============================================================================

Builds the `ctx` object that `agents.factory.build_agent_team(ctx)` consumes.

Source access goes through Agno Context Providers (handoff §3.3b), not raw
tools. The evidence read-only guarantee is INFRASTRUCTURE-LEVEL: the read
provider's engine sets default_transaction_read_only=on, so its sub-agent
physically cannot write (ADR-0005).

API verified against the agno==2.6.9 wheel (2026-06-10):
  - WorkspaceContextProvider(root=..., id=...)
  - DatabaseContextProvider(*, id, sql_engine: Engine, readonly_engine: Engine,
        schema, mode, model, read, write)  — SYNC SQLAlchemy engines
  - LearningMachine(db=, model=, knowledge=, user_profile=, user_memory=,
        session_context=, entity_memory=, learned_knowledge=, namespace=)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import create_engine

from agno.context.database import DatabaseContextProvider
from agno.context.workspace import WorkspaceContextProvider

# Deferred to later goals (cloud cleanup / MCP fleet):
# from agno.context.gdrive import GoogleDriveContextProvider
# from agno.context.mcp import MCPContextProvider


@dataclass
class PlatformContext:
    """Runtime bundle handed to build_agent_team(ctx)."""

    model: Any
    db: Any
    knowledge: Any
    learning: Any
    source_tools: list[Any] = field(default_factory=list)
    code_tools: list[Any] = field(default_factory=list)
    readonly_db_tools: list[Any] = field(default_factory=list)
    drive_read_tools: list[Any] = field(default_factory=list)
    drive_write_tools: list[Any] = field(default_factory=list)


def _make_engine(url: str, readonly: bool = False):
    """Sync SQLAlchemy engine (DatabaseContextProvider expects sync Engine).

    readonly=True forces default_transaction_read_only=on at the connection —
    the infrastructure-level guarantee, not a prompt instruction.
    """
    connect_args = {"options": "-c default_transaction_read_only=on"} if readonly else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def build_context(model, db, knowledge, learning, db_url: str) -> PlatformContext:
    """Assemble Context Providers into the ctx the factory consumes."""

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

    # Source tools for the platform agents = codebase + DB access.
    # (TS/Py MCP servers join at Phase 7 via MCPTools/MCPContextProvider.)
    source_tools = [*code_tools, *db_tools]

    # Graphiti temporal graph memory (ADR-0014) — attached only when the
    # graph profile is up (GRAPHITI_MCP_URL set). AgentOS manages the MCP
    # lifecycle; never run uvicorn reload with this attached.
    import os

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


def build_learning(db, model, knowledge):
    """Native operational memory on the existing Postgres (ADR-0004).

    PROPOSE = agent proposes, human confirms — HITL-native capture for the
    high-stakes durable stores (Entity Memory, Learned Knowledge).
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
        entity_memory=EntityMemoryConfig(mode=LearningMode.PROPOSE),  # HITL
        learned_knowledge=LearnedKnowledgeConfig(  # HITL
            mode=LearningMode.PROPOSE,
            knowledge=knowledge,
            namespace="platform",
            agent_can_save=True,
            agent_can_search=True,
        ),
        namespace="platform",
    )
