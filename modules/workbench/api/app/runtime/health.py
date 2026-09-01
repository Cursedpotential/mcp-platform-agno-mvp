# Byline: Claude Code · Sonnet (agent) · 2026-07-21 (C2.6: GET /api/health/deps added)
# Byline: Codex · GPT-5 · 2026-08-29 (runtime-read Platform API bearer file)
"""GET /health — cheap connectivity checks only, no heavy calls.

GET /api/health/deps (C2.6 requirement 4) — the console header's dependency
health strip. Merges THIS app's own lancedb/object_store checks (same
functions /health above already uses) with a proxy of the spine's
GET /v1/health/deps (pg + Milvus, each with a 3s timeout server-side)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter

from app.config import settings
from app.repo import check_connectivity, check_lancedb_connectivity
from app.repo.platform_api_auth import platform_api_bearer_headers

router = APIRouter()
logger = logging.getLogger("workbench")

# Padded above the spine's own 3s-per-check timeout so a slow (not hung)
# spine still gets a real answer back instead of this proxy racing it.
_SPINE_DEPS_TIMEOUT_S = 4.0


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


def _spine_deps() -> dict[str, Any]:
    """GET the spine's own /v1/health/deps (pg + milvus). A network failure
    or non-2xx here reports BOTH as 'error' with the same message — the
    workbench can't tell which spine-side dep is actually down if the
    spine itself is unreachable."""
    try:
        headers = platform_api_bearer_headers()
        with httpx.Client(timeout=_SPINE_DEPS_TIMEOUT_S) as client:
            resp = client.get(f"{settings.platform_api_url}/v1/health/deps", headers=headers)
        resp.raise_for_status()
        body = resp.json()
        return {
            "pg": body.get("pg") or {"status": "error", "error": "missing 'pg' key in spine response"},
            "milvus": body.get("milvus") or {"status": "error", "error": "missing 'milvus' key in spine response"},
        }
    except Exception as exc:
        logger.warning("spine /v1/health/deps unreachable", exc_info=True)
        err = {"status": "error", "error": str(exc)[:300]}
        return {"pg": err, "milvus": err}


@router.get("/api/health/deps")
async def health_deps() -> dict[str, Any]:
    """Console header's dependency chip strip (C2.6 requirement 4):
    ``{lancedb, object_store, pg, milvus}`` (each ``{"status": "ok"|"error",
    "error"?: str}``) + ``checked_at``."""
    lancedb_ok = check_lancedb_connectivity()
    try:
        object_store_ok = check_connectivity()
    except Exception:
        object_store_ok = False
    spine = _spine_deps()
    return {
        "lancedb": {"status": "ok" if lancedb_ok else "error"},
        "object_store": {"status": "ok" if object_store_ok else "error"},
        **spine,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
