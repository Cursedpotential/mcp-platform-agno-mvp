"""POST /v1/chat — Vercel AI SDK compatible neutral text stream.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.service.chat_gateway import ChatGatewayError, open_chat_stream
from app.types.chat import ChatRequest

router = APIRouter(tags=["chat"])


@router.post("/v1/chat")
async def chat_endpoint(body: ChatRequest, request: Request) -> StreamingResponse:
    """Stream plain text through Portkey; the browser uses TextStreamChatTransport."""
    principal = getattr(request.state, "principal", "owner")
    try:
        chunks, trace_id = await open_chat_stream(body, principal=principal)
    except ChatGatewayError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from None
    return StreamingResponse(
        chunks,
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-Horizon-Model-Route": "portkey",
            "X-Portkey-Trace-Id": trace_id,
        },
    )
