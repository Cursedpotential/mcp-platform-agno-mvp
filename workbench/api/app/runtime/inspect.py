# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: record browser, hash verify, curation, corroboration flags)
"""GET/PATCH /api/records, GET /api/schemas, POST /api/verify/{sha},
POST/GET/PATCH /api/flags... — the C3 inspector routes.

Thin FastAPI wrappers over app/service/inspect.py + app/service/flags.py;
every SpineError becomes an HTTPException with the spine's own `detail`
message preserved verbatim (mirrors app/runtime/runs.py's error-translation
pattern), so a 404/409/422 raised by the c3-spine reaches the frontend
intact instead of collapsing into a generic 502.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.repo.spine_client import SpineError
from app.service import flags as flags_service
from app.service import inspect as inspect_service
from app.types.inspect import FlagCreateRequest, FlagUpdateRequest, RecordMetaPatchRequest

router = APIRouter(prefix="/api", tags=["inspect"])


# ---------------------------------------------------------------------------
# Records (parse-quality review + curation — addenda 1, 3)
# ---------------------------------------------------------------------------


@router.get("/records")
async def list_records_endpoint(
    artifact_id: str | None = None,
    run_id: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
):
    try:
        return inspect_service.list_records(artifact_id=artifact_id, run_id=run_id, q=q, limit=limit, offset=offset)
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.patch("/records/{record_id}/meta")
async def patch_record_meta_endpoint(record_id: str, payload: RecordMetaPatchRequest):
    try:
        return inspect_service.patch_record_meta(record_id, payload.model_dump(exclude_unset=True))
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


# ---------------------------------------------------------------------------
# Schemas (raw PG/Milvus inspection views)
# ---------------------------------------------------------------------------


@router.get("/schemas")
async def get_schemas_endpoint():
    try:
        return inspect_service.get_schemas()
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


# ---------------------------------------------------------------------------
# Verify (active hash verification — addendum 2)
# ---------------------------------------------------------------------------


@router.post("/verify/{sha256}")
async def verify_endpoint(sha256: str):
    try:
        return inspect_service.verify_sha256(sha256)
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


# ---------------------------------------------------------------------------
# Corroboration flags (addendum 6)
# ---------------------------------------------------------------------------


@router.post("/flags")
async def create_flag_endpoint(payload: FlagCreateRequest):
    try:
        return flags_service.create_flag(payload.model_dump(exclude_unset=True))
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/flags")
async def list_flags_endpoint(status: str | None = None, target_kind: str | None = None):
    try:
        return flags_service.list_flags(status=status, target_kind=target_kind)
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.patch("/flags/{flag_id}")
async def update_flag_endpoint(flag_id: str, payload: FlagUpdateRequest):
    try:
        return flags_service.update_flag(flag_id, payload.model_dump(exclude_unset=True))
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
