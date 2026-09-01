# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Response shape for POST /api/upload."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.types.documents import DetectedType, StagedFileMeta, StagedStatus


class StagedUploadResponse(BaseModel):
    """A staged_files row plus whether this upload was a dedupe hit."""

    id: str
    name: str
    size: int
    mime: str
    detected_type: DetectedType
    text: str = ""
    meta: StagedFileMeta = StagedFileMeta()
    r2_key: str
    status: StagedStatus = StagedStatus.staged
    promote_result: dict | None = None
    created_at: datetime
    updated_at: datetime
    duplicate: bool = False
