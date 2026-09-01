"""Authenticated BFF routes for immediate fixed-source preview and hashing.

Byline: Codex · GPT-5.6-Sol · 2026-08-30.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.service.source_inspection import (
    SourceInspectionError,
    inspect_source,
    open_source_content,
    stream_source_content,
)
from app.service.source_context import create_source_context
from app.service.uiw import UIWError
from app.types.source_context import SourceContextCreateRequest, SourceContextReceipt
from app.types.source_inspection import SourceInspectionRequest, SourceInspectionResponse
from app.types.uiw import UIWDecisionActor


router = APIRouter(prefix="/api/uiw", tags=["uiw"])


def _translate(error: SourceInspectionError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


def _actor(request: Request) -> UIWDecisionActor:
    subject_uid = str(getattr(request.state, "subject_uid", "")).strip()
    username = str(getattr(request.state, "principal", "")).strip()
    if not subject_uid or not username:
        raise HTTPException(status_code=401, detail="authenticated subject identity is unavailable")
    return UIWDecisionActor(subject_uid=subject_uid, username=username)


@router.post("/source-inspection", response_model=SourceInspectionResponse)
def source_inspection_endpoint(body: SourceInspectionRequest):
    try:
        return inspect_source(body)
    except SourceInspectionError as error:
        raise _translate(error) from None


@router.post("/source-contexts", response_model=SourceContextReceipt, status_code=201)
async def source_context_endpoint(body: SourceContextCreateRequest, request: Request):
    try:
        return await create_source_context(body, _actor(request))
    except UIWError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from None


@router.get("/source-content")
def source_content_endpoint(
    key: Annotated[str, Query(min_length=1, max_length=1024)],
    etag: Annotated[str, Query(min_length=1, max_length=512)],
    range_header: Annotated[str | None, Header(alias="Range")] = None,
):
    try:
        content = open_source_content(key, etag, range_header)
    except SourceInspectionError as error:
        raise _translate(error) from None
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store",
        "Content-Length": str(content.content_length),
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "ETag": content.etag,
        "X-Content-Type-Options": "nosniff",
    }
    if content.content_range:
        headers["Content-Range"] = content.content_range
    return StreamingResponse(
        stream_source_content(content),
        status_code=content.status_code,
        media_type=content.content_type,
        headers=headers,
    )
