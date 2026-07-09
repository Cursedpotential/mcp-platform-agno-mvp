"""agents/review_gatekeeper.py — Platform Ops: human-approval interface agent builder.

Provides ``build_review_gatekeeper()`` which delegates to the shared factory
in ``factory.py``. This module exists for progressive disclosure discoverability.
"""

from __future__ import annotations

from typing import Any

from agno.agent import Agent

from server.agents.factory import build_review_gatekeeper as _build


def build_review_gatekeeper(model: Any, db: Any) -> Agent:
    """Build the Review Gatekeeper agent.

    See ``agents.factory.build_review_gatekeeper`` for the full docstring
    and parameter descriptions.
    """
    return _build(model, db)
