"""Workbench BFF routes for the Universal Import Workflow starter.

Byline: Codex · GPT-5 · 2026-08-28.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.service.uiw import UIWError, decide, open_upload_stream, preview, start
from app.types.uiw import UIWDecisionRequest, UIWStartRequest

router = APIRouter(prefix="/api/uiw", tags=["uiw"])


def _translate(error: UIWError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


@router.post("/start", response_model=None, status_code=201)
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


@router.post("/{workflow_id}/decision", response_model=None)
async def decision_endpoint(workflow_id: str, body: UIWDecisionRequest):
    if not body.approved and not body.reason.strip():
        raise HTTPException(status_code=422, detail="a rejection decision requires a non-empty reason")
    try:
        return await decide(workflow_id, body)
    except UIWError as error:
        raise _translate(error) from None


@router.get("/{workflow_id}/preview", response_model=None)
async def preview_endpoint(workflow_id: str):
    try:
        return await preview(workflow_id)
    except UIWError as error:
        raise _translate(error) from None
