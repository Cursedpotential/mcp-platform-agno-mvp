"""Workbench BFF routes for the Universal Import Workflow starter.

Byline: Codex · GPT-5 · 2026-08-28.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse

from app.service.uiw import (
    UIWError,
    browse_sources,
    decide,
    open_preview_event_stream,
    open_upload_stream,
    preview,
    preview_messages,
    start,
    validated_preview_events,
)
from app.types.uiw import (
    UIWDecisionActor,
    UIWDecisionRequest,
    UIWDecisionResponse,
    UIWPreviewMessagesResponse,
    UIWPreviewResponse,
    UIWSourceBrowserResponse,
    UIWStartRequest,
    UIWStartResponse,
)

router = APIRouter(prefix="/api/uiw", tags=["uiw"])


def _translate(error: UIWError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


@router.get("/sources", response_model=UIWSourceBrowserResponse)
def sources_endpoint(
    prefix: str = "", continuation_token: str | None = None, filter: str = "", page_size: int = 100
):
    if page_size < 1 or page_size > 500:
        raise HTTPException(status_code=422, detail="page_size must be between 1 and 500")
    try:
        return browse_sources(
            prefix=prefix,
            continuation_token=continuation_token,
            filter_text=filter,
            page_size=page_size,
        )
    except UIWError as error:
        raise _translate(error) from None


@router.post("/start", response_model=UIWStartResponse, status_code=201)
async def start_endpoint(body: UIWStartRequest):
    try:
        return await start(body)
    except UIWError as error:
        raise _translate(error) from None


@router.post("/upload")
async def upload_endpoint(request: Request):
    try:
        client, response = await open_upload_stream(
            request.stream(),
            content_type=request.headers.get("content-type"),
            content_length=request.headers.get("content-length"),
        )
    except UIWError as error:
        raise _translate(error) from None

    async def body():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    headers = {key: value for key, value in response.headers.items() if key.lower() in {"content-type", "content-length"}}
    return StreamingResponse(body(), status_code=response.status_code, headers=headers)


PreviewHandle = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{32,128}$")]


@router.post("/previews/{preview_handle}/decision", response_model=UIWDecisionResponse)
async def decision_endpoint(preview_handle: PreviewHandle, body: UIWDecisionRequest, request: Request):
    if not body.approved and not body.reason.strip():
        raise HTTPException(status_code=422, detail="a rejection decision requires a non-empty reason")
    subject_uid = str(getattr(request.state, "subject_uid", "")).strip()
    username = str(getattr(request.state, "principal", "")).strip()
    if not subject_uid or not username:
        raise HTTPException(status_code=401, detail="authenticated subject identity is unavailable")
    try:
        return await decide(
            preview_handle,
            body,
            UIWDecisionActor(subject_uid=subject_uid, username=username),
        )
    except UIWError as error:
        raise _translate(error) from None


@router.get("/previews/{preview_handle}", response_model=UIWPreviewResponse)
async def preview_endpoint(preview_handle: PreviewHandle):
    try:
        return await preview(preview_handle)
    except UIWError as error:
        raise _translate(error) from None


@router.get("/previews/{preview_handle}/messages", response_model=UIWPreviewMessagesResponse)
async def preview_messages_endpoint(
    preview_handle: PreviewHandle,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=250)] = 100,
):
    try:
        return await preview_messages(preview_handle, cursor=cursor, limit=limit)
    except UIWError as error:
        raise _translate(error) from None


@router.get("/previews/{preview_handle}/events")
async def preview_events_endpoint(
    preview_handle: PreviewHandle,
    last_event_id_header: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
):
    last_event_id: int | None = None
    if last_event_id_header is not None:
        try:
            last_event_id = int(last_event_id_header)
        except ValueError:
            raise HTTPException(status_code=422, detail="Last-Event-ID must be a non-negative integer") from None
        if last_event_id < 0:
            raise HTTPException(status_code=422, detail="Last-Event-ID must be a non-negative integer")
    try:
        client, response = await open_preview_event_stream(
            preview_handle, last_event_id=last_event_id
        )
    except UIWError as error:
        raise _translate(error) from None

    async def body():
        try:
            async for event in validated_preview_events(
                response, preview_handle=preview_handle, last_event_id=last_event_id
            ):
                yield event
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
