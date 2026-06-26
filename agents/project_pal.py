"""agents/project_pal.py — Builder: project memory agent builder.

Provides ``build_project_pal()`` which delegates to the shared factory
in ``factory.py``. This module exists for progressive disclosure discoverability.
"""

from __future__ import annotations

from typing import Any

from agno.agent import Agent

from agents.factory import build_project_pal as _build


def build_project_pal(model: Any, db: Any, learning: Any) -> Agent:
    """Build the Project PAL agent.

    See ``agents.factory.build_project_pal`` for the full docstring
    and parameter descriptions.
    """
    return _build(model, db, learning)
