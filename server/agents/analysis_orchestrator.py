"""agents/analysis_orchestrator.py — Platform Ops: analysis agent builder.

Provides ``build_analysis_orchestrator()`` which delegates to the shared
factory in ``factory.py``. This module exists so that the ``agents/`` package
has a discoverable home for each agent's module (progressive disclosure).
"""

from __future__ import annotations

from typing import Any

from agno.agent import Agent

from server.agents.factory import build_analysis_orchestrator as _build


def build_analysis_orchestrator(
    model: Any,
    db: Any,
    knowledge: Any,
    learning: Any,
    source_tools: list[Any],
) -> Agent:
    """Build the Analysis Orchestrator agent.

    See ``agents.factory.build_analysis_orchestrator`` for the full docstring
    and parameter descriptions.
    """
    return _build(model, db, knowledge, learning, source_tools)
