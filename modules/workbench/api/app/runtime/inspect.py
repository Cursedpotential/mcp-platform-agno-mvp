# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: record browser, hash verify, curation, corroboration flags)
# Byline: Codex · GPT-5 · 2026-08-16 (Data Explorer table/vector detail routes)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (third-party approval route)
# Byline: Codex · GPT-5 · 2026-08-18 (authenticated review and entity routes)
"""GET/PATCH /api/records, GET /api/schemas, POST /api/verify/{sha},
POST/GET/PATCH /api/flags... — the C3 inspector routes.

Thin FastAPI wrappers over app/service/inspect.py + app/service/flags.py;
every SpineError becomes an HTTPException with the spine's own `detail`
message preserved verbatim (mirrors app/runtime/runs.py's error-translation
pattern), so a 404/409/422 raised by the c3-spine reaches the frontend
intact instead of collapsing into a generic 502.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.repo.spine_client import SpineError
from app.service import flags as flags_service
from app.service import inspect as inspect_service
from app.types.inspect import (
    EntityCreateRequest,
    FlagCreateRequest,
    FlagUpdateRequest,
    RecordMetaPatchRequest,
    ThirdPartyApprovalRequest,
)

router = APIRouter(prefix="/api", tags=["inspect"])


def _authenticated_owner(request: Request) -> str:
    principal = getattr(request.state, "principal", None)
    if principal != "owner":
        raise HTTPException(status_code=401, detail="authenticated owner required")
    return principal


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


@router.post("/third-party-conversations/{conversation_id}/approve")
async def approve_third_party_conversation_endpoint(
    conversation_id: UUID, payload: ThirdPartyApprovalRequest, request: Request
):
    try:
        _authenticated_owner(request)
        review = payload.model_dump(mode="json")
        return inspect_service.approve_third_party_conversation(
            str(conversation_id),
            review,
        )
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/entities")
async def list_entities_endpoint(q: str | None = None, limit: int = Query(20, ge=1, le=100)):
    try:
        return inspect_service.list_entities(query=q, limit=limit)
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/entities", status_code=201)
async def create_entity_endpoint(payload: EntityCreateRequest, request: Request):
    # request.state.principal is deliberately consulted here even though the
    # upstream contract accepts no actor: unauthenticated test/app wiring fails
    # closed instead of silently turning browser input into authored identity.
    _authenticated_owner(request)
    try:
        return inspect_service.create_entity(payload.model_dump(mode="json"))
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


# ---------------------------------------------------------------------------
# Data Explorer (raw PG + Weaviate read-only inspection views)
# ---------------------------------------------------------------------------


@router.get("/schemas")
async def get_schemas_endpoint():
    try:
        return inspect_service.get_schemas()
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/schemas/postgresql/{schema}/{table_name}")
async def get_table_detail_endpoint(schema: str, table_name: str, limit: int = Query(5, ge=1, le=25)):
    try:
        return inspect_service.get_table_detail(schema, table_name, limit=limit)
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/schemas/weaviate/{collection_name}")
async def get_vector_detail_endpoint(collection_name: str, limit: int = Query(5, ge=1, le=10)):
    try:
        return inspect_service.get_vector_detail(collection_name, limit=limit)
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
