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
    uses the same custody → parse → normalize → store pipeline. This function
    exists as the extension point when transcript-specific logic is needed.

    See ``agents.factory`` for parameter descriptions.
    """
    from server.agents.factory import build_ingestion_orchestrator

    return build_ingestion_orchestrator(model, db, knowledge, learning, source_tools)
