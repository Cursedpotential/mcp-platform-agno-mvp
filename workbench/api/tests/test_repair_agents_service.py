# Byline: Codex · GPT-5 · 2026-08-03
# Byline: Codex · GPT-5.6 · 2026-08-29 (AgentOS caller retirement)
"""Fail-closed repair-agent compatibility boundary tests."""

from __future__ import annotations

import pytest

from app.repo.spine_client import SpineError
from app.service import repair_agents


def test_no_agent_or_team_definitions_are_exposed() -> None:
    assert repair_agents.list_participants() == []


def test_agent_review_fails_closed_until_bounded_temporal_task_exists() -> None:
    with pytest.raises(SpineError) as error:
        repair_agents.run_review(
            participant_type="agent",
            participant_id="ingestion-orchestrator",
            path="/evidence/export.json",
            task="Review it",
            assessment={"status": "damaged"},
            session_id=None,
        )
    assert error.value.status_code == 503
    assert "bounded Temporal task" in error.value.detail
