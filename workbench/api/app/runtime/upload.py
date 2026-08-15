# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""POST /api/upload — stream to a temp file, hash, stage. Never chunks/embeds."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile

from app.config import settings
from app.runtime.metrics import record_upload
from app.service.upload import UploadError, stage_upload
from app.types.upload import StagedUploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])

_CHUNK_SIZE = 1024 * 1024  # 1MB


@router.post("/upload", response_model=StagedUploadResponse)
async def upload(file: UploadFile):
    max_bytes = settings.max_upload_bytes
    hasher = hashlib.sha256()
    size = 0

    fd, tmp_path = tempfile.mkstemp(prefix="workbench-upload-")
    try:
        with os.fdopen(fd, "wb") as tmp:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    record_upload(success=False)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Max size: {settings.max_upload_mb}MB",
                    )
                hasher.update(chunk)
                tmp.write(chunk)

        try:
            result = stage_upload(tmp_path, hasher.hexdigest(), size, file.filename or "")
        except UploadError as e:
            logger.warning("Upload rejected: %s", e.detail)
            record_upload(success=False)
            raise HTTPException(status_code=e.status_code, detail=e.detail) from None
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    record_upload(success=True)
    logger.info(
        "File staged: id=%s name=%s size=%d duplicate=%s",
        result.get("id"),
        result.get("name"),
        result.get("size"),
        result.get("duplicate"),
    )
    return result
