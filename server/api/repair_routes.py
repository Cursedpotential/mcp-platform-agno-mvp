# Byline: Codex · GPT-5 · 2026-08-03
"""Authenticated operator-only execution door for approval-gated repairs.

The agent-facing generic tool gateway cannot set ``approval_granted``.  This
base-app route is protected by AgentOS's normal security-key middleware and is
the sole remote path that can authorize a repair tool with write side effects.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.tools.gateway.content_store import ContentStore
from server.tools.gateway.toolfinder import execute_tool

router = APIRouter(prefix="/v1/repairs", tags=["repairs"])
_store = ContentStore()


class ApprovedRepairRequest(BaseModel):
    """One operator-reviewed atomic repair invocation."""

    tool_id: str = Field(pattern=r"^repair\.")
    payload: dict[str, Any] = Field(default_factory=dict)
    approved: bool
    operation_id: str | None = None


@router.post("/execute")
async def execute_approved_repair(body: ApprovedRepairRequest) -> dict[str, Any]:
    """Execute after an authenticated operator explicitly approves the call."""
    if not body.approved:
        raise HTTPException(status_code=409, detail="Explicit operator approval is required")
    payload = dict(body.payload)
    payload["_execution_mode"] = "manual"
    payload["_operation_id"] = body.operation_id or str(uuid4())
    payload["approved"] = True
    try:
        return execute_tool(body.tool_id, payload, store=_store, approval_granted=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown repair tool: {body.tool_id}") from exc
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
