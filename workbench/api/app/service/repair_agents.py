# Byline: Codex · GPT-5 · 2026-08-03
# Byline: Codex · GPT-5.6 · 2026-08-29 (AgentOS caller retirement)
"""Disabled compatibility boundary for future bounded repair-agent tasks.

AgentOS's generic agents/teams/run surface is retired.  Repair agents may only
return through an explicitly registered Temporal task contract; none is active
yet, so this boundary must expose no participant definitions and fail closed.
"""

from __future__ import annotations

from typing import Any, Literal

from app.repo.spine_client import SpineError


def list_participants() -> list[dict[str, Any]]:
    """Expose no agents until a bounded Temporal task is explicitly activated."""
    return []


def run_review(
    *,
    participant_type: Literal["agent", "team"],
    participant_id: str,
    path: str,
    task: str,
    assessment: dict[str, Any] | None,
    session_id: str | None,
) -> dict[str, Any]:
    """Fail closed until a governed Temporal repair-review task exists."""
    del participant_type, participant_id, path, task, assessment, session_id
    raise SpineError(
        "Agent-assisted repair review is unavailable until a bounded Temporal task is explicitly activated",
        503,
    )
