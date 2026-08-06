# Byline: Codex · GPT-5 · 2026-08-03
"""Workbench repair discovery, manual execution, automatic assessment, and agent review."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.repo.spine_client import SpineError
from app.service import repair_agents, repairs
from app.service.tools import ToolsError
from app.types.repairs import AutoRepairRequest, RepairAgentRunRequest, RepairCallRequest

router = APIRouter(prefix="/api/repairs", tags=["repairs"])


@router.get("/tools")
async def repair_tools():
    try:
        return repairs.list_repair_tools()
    except ToolsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("/tools/{tool_id}")
async def repair_tool(tool_id: str):
    try:
        return repairs.describe_repair_tool(tool_id)
    except ToolsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.post("/execute")
async def execute_repair(body: RepairCallRequest):
    try:
        return repairs.execute_manual(body.tool_id, body.payload, body.approved)
    except ToolsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.post("/automatic-assessment")
async def assess_repair(body: AutoRepairRequest):
    try:
        return repairs.automatic_assessment(body.path, body.format, body.sample_limit)
    except ToolsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("/participants")
async def repair_participants():
    try:
        return repair_agents.list_participants()
    except SpineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.post("/agent-review")
async def repair_agent_review(body: RepairAgentRunRequest):
    try:
        return repair_agents.run_review(
            participant_type=body.participant_type,
            participant_id=body.participant_id,
            path=body.path,
            task=body.task,
            assessment=body.assessment,
            session_id=body.session_id,
        )
    except SpineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
