# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""GET /api/documents/stats — staging-table counts.

Rewired from the donor kit's vector-store /documents/stats + /documents/search
+ /documents/{id}/chunks endpoints, all of which required chunking/embeddings
this app never does. Only the "give me stats" concept survives, now
reporting on the staging table instead of a chunks table.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.service.documents import get_staging_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("/stats")
async def document_stats():
    try:
        return get_staging_stats()
    except Exception:
        logger.exception("Failed to get staging stats")
        raise HTTPException(status_code=503, detail="Staging store unavailable") from None
