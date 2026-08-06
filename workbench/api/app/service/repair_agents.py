# Byline: Codex · GPT-5 · 2026-08-03
"""Real AgentOS participants for governed repair and processing review."""

from __future__ import annotations

import json
from typing import Any, Literal

from app.repo.spine_client import SpineError, spine_json

_RECOMMENDED_AGENTS = {"ingestion-orchestrator", "analysis-orchestrator", "review-gatekeeper", "forensic-data-agent"}


def list_participants() -> list[dict[str, Any]]:
    """List live agents and teams from AgentOS; never maintain a shadow roster."""
    participants: list[dict[str, Any]] = []
    for kind, path in (("agent", "/agents"), ("team", "/teams")):
        for item in spine_json("GET", path):
            participant_id = str(item.get("id", ""))
            participants.append(
                {
                    "type": kind,
                    "id": participant_id,
                    "name": item.get("name") or participant_id,
                    "role": item.get("role") or item.get("description") or "",
                    "recommended": participant_id in _RECOMMENDED_AGENTS or item.get("name") == "Platform Ops",
                    "is_factory": bool(item.get("is_factory")),
                }
            )
    return participants


def run_review(
    *,
    participant_type: Literal["agent", "team"],
    participant_id: str,
    path: str,
    task: str,
    assessment: dict[str, Any] | None,
    session_id: str | None,
) -> dict[str, Any]:
    """Run one persisted AgentOS review with repair-specific HITL constraints."""
    if not participant_id.strip():
        raise SpineError("participant_id is required", 400)
    endpoint = "agents" if participant_type == "agent" else "teams"
    context = json.dumps(assessment or {}, ensure_ascii=False, default=str)[:12000]
    prompt = f"""You are participating in the Repair and Processing Workbench.

Operator task: {task}
Server-visible source path: {path}
Existing automatic assessment: {context}

Use the registered repair tools to inspect facts. You MAY automatically call only read-only operations:
repair.capabilities, repair.detect, repair.preview, repair.pdf-inspect, repair.quarantine-plan, and repair.audit-verify.
Do NOT call repair.write-derived, repair.pdf-derived, repair.flag-damaged, or repair.quarantine-copy in this run.
For any write, return a PROPOSAL specifying the exact tool, payload, risk, expected hashes, and why it is needed.
The operator will approve or reject that proposal through the Workbench. Never claim a proposed write occurred.
Report anomalies, lossy transformations, unresolved companion files, and the audit operation/chain identifiers you observed.
"""
    form: dict[str, str] = {
        "message": prompt,
        "stream": "false",
        "background": "false",
        "user_id": "workbench-operator",
    }
    if session_id:
        form["session_id"] = session_id
    return spine_json("POST", f"/{endpoint}/{participant_id}/runs", data=form)
