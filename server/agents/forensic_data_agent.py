"""agents/forensic_data_agent.py — Builder: read-only data interface agent builder.

Provides ``build_forensic_data_agent()`` which delegates to the shared factory
in ``factory.py``. This module exists for progressive disclosure discoverability.
"""

from __future__ import annotations

from typing import Any

from agno.agent import Agent

from server.agents.factory import build_forensic_data_agent as _build


def build_forensic_data_agent(model: Any, db: Any, learning: Any, readonly_db_tools: list[Any]) -> Agent:
    """Build the Forensic Data Agent.

    See ``agents.factory.build_forensic_data_agent`` for the full docstring
    and parameter descriptions.
    """
    return _build(model, db, learning, readonly_db_tools)
