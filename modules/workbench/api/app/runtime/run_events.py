"""Authenticated Workbench SSE proxy for durable platform run progress.

Byline: Codex · GPT-5 · 2026-08-27
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.service.run_events import RunEventsError, open_run_event_stream

router = APIRouter(prefix="/api", tags=["runs"])


@router.get("/runs/{run_id}/events")
async def stream_run_events_endpoint(
    run_id: UUID,
    last_event_id: Annotated[int | None, Header(alias="Last-Event-ID", ge=0)] = None,
    after: Annotated[int | None, Query(ge=0)] = None,
    follow: bool = True,
    limit: Annotated[int, Query(ge=1, le=1000)] = 250,
) -> StreamingResponse:
    """Replay and follow safe structured run events through Workbench auth."""

    try:
        stream = await open_run_event_stream(
            run_id,
            last_event_id=last_event_id,
            after=after,
            follow=follow,
            limit=limit,
        )
    except RunEventsError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from None
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
