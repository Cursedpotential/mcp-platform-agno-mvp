"""agents/transcript_miner.py — Platform Ops: transcript parsing agent builder.

Provides ``build_transcript_miner()`` which delegates to the shared factory
in ``factory.py``. This module exists for progressive disclosure discoverability.
"""

from __future__ import annotations

from typing import Any

from agno.agent import Agent

# The transcript_miner agent is built directly in factory.py as a thin wrapper
# around the Ingestion Orchestrator pattern. When it needs custom logic, add it
# here and import from factory.py.


def build_transcript_miner(
    model: Any,
    db: Any,
    knowledge: Any,
    learning: Any,
    source_tools: list[Any],
) -> Agent:
    """Build the Transcript Miner agent.

    Currently delegates to ``build_ingestion_orchestrator`` — transcript mining
    uses the same custody -> parse -> normalize -> store pipeline. This function
    exists as the extension point when transcript-specific logic is needed.

    The delegate returns an agent carrying the ORCHESTRATOR's id/name, so the
    identity must be overridden here. AgentOS rejects a roster containing
    duplicate ids outright (``ValueError: Duplicate IDs found in AgentOS``) and
    the process then crash-loops — verified the hard way on 2026-08-04, the
    first time this agent was mounted.

    See ``agents.factory`` for parameter descriptions.
    """
    from server.agents.factory import build_ingestion_orchestrator

    agent = build_ingestion_orchestrator(model, db, knowledge, learning, source_tools)
    agent.id = "transcript-miner"
    agent.name = "Transcript Miner"
    agent.role = "Mine AI-chat transcripts for decisions, code artifacts and blockers."
    return agent
