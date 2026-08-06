# Byline: Codex · GPT-5 · 2026-08-03
"""Typed requests for the Workbench repair control surface."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RepairCallRequest(BaseModel):
    """Invoke one registered repair tool as an explicit operator action."""

    tool_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    approved: bool = False


class AutoRepairRequest(BaseModel):
    """Run the non-destructive automatic assessment policy for one source."""

    path: str
    format: str | None = None
    sample_limit: int = Field(default=25, ge=1, le=250)


class RepairAgentRunRequest(BaseModel):
    """Ask a live AgentOS agent/team to review a repair assessment."""

    participant_type: Literal["agent", "team"]
    participant_id: str
    path: str
    task: str = "Review this source and recommend the safest processing path."
    assessment: dict[str, Any] | None = None
    session_id: str | None = None
