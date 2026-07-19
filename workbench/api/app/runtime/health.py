# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""GET /health — cheap connectivity checks only, no heavy calls."""

from __future__ import annotations

from fastapi import APIRouter

from app.repo import check_connectivity, check_lancedb_connectivity

router = APIRouter()


@router.get("/health")
async def health():
    lancedb_ok = check_lancedb_connectivity()
    try:
        object_store_ok = check_connectivity()
    except Exception:
        object_store_ok = False
    return {
        "status": "ok" if (lancedb_ok and object_store_ok) else "degraded",
        "lancedb": lancedb_ok,
        "object_store": object_store_ok,
    }
