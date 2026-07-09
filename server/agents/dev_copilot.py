"""agents/dev_copilot.py — Builder: dev assistant agent builder.

Provides ``build_dev_copilot()`` which delegates to the shared factory
in ``factory.py``. This module exists for progressive disclosure discoverability.
"""

from __future__ import annotations

from typing import Any

from agno.agent import Agent

from server.agents.factory import build_dev_copilot as _build


def build_dev_copilot(
    model: Any,
    db: Any,
    knowledge: Any,
    learning: Any,
    code_tools: list[Any],
) -> Agent:
    """Build the Dev Copilot agent.

    See ``agents.factory.build_dev_copilot`` for the full docstring
    and parameter descriptions.
    """
    return _build(model, db, knowledge, learning, code_tools)
