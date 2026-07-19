# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""POST /api/promote/{id} and /api/promote-all — push staged files through the spine."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.service.promote import PromoteError, promote, promote_all

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["promote"])


@router.post("/promote/{file_id}")
async def promote_endpoint(file_id: str):
    try:
        return promote(file_id)
    except PromoteError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/promote-all")
async def promote_all_endpoint():
    # Bare array, not {"results": [...]} — matches the workbench/web frontend's
    # `apiFetch<PromoteResult[]>("/api/promote-all")` contract.
    return promote_all()
