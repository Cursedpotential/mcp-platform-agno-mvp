# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""GET/PATCH /api/files — list, detail, and metadata edits over staged files."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.service.files import (
    StagedFileNotFoundError,
    StagedFileValidationError,
    get_staged_detail,
    list_staged,
    update_metadata,
)
from app.types.files import FilePatchRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["files"])


@router.get("/files")
async def list_files_endpoint(
    status: str | None = None,
    detected_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    try:
        return list_staged(status=status, detected_type=detected_type, limit=limit, offset=offset)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/files/{file_id}")
async def get_file_endpoint(file_id: str):
    try:
        return get_staged_detail(file_id)
    except StagedFileNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.patch("/files/{file_id}")
async def patch_file_endpoint(file_id: str, body: FilePatchRequest):
    try:
        # exclude_unset so "omitted" (leave alone) and "sent as null"
        # (explicitly clear) are distinguishable — see FilePatchRequest.
        return update_metadata(file_id, body.model_dump(exclude_unset=True))
    except StagedFileNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    except StagedFileValidationError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
