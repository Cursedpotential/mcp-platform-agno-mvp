"""Streaming proxy for PostgreSQL-authoritative platform run events.

The Workbench owns the platform bearer. Browsers receive only the safe SSE
contract and never see that credential. The proxy consumes and yields one
line at a time so upstream backpressure is preserved without accumulating a
run in Workbench memory.

Byline: Codex · GPT-5 · 2026-08-27
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
from uuid import UUID

import httpx

from app.config import settings


class RunEventsError(Exception):
    """An upstream configuration, transport, or protocol failure."""

    def __init__(self, detail: str, status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _upstream_headers(last_event_id: int | None) -> dict[str, str]:
    headers = {"Accept": "text/event-stream"}
    if settings.agentos_api_token:
        headers["Authorization"] = f"Bearer {settings.agentos_api_token}"
    if last_event_id is not None:
        headers["Last-Event-ID"] = str(last_event_id)
    return headers


async def _error_detail(response: httpx.Response) -> str:
    payload = (await response.aread())[:500]
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return payload.decode("utf-8", errors="replace")
    if isinstance(parsed, dict) and isinstance(parsed.get("detail"), str):
        return parsed["detail"]
    return payload.decode("utf-8", errors="replace")


async def open_run_event_stream(
    run_id: UUID,
    *,
    last_event_id: int | None = None,
    after: int | None = None,
    follow: bool = True,
    limit: int = 250,
    client: httpx.AsyncClient | None = None,
) -> AsyncIterator[bytes]:
    """Open the platform stream before returning an incremental iterator.

    Platform events use their domain ``event_type`` as the SSE dispatch name.
    Browser EventSource has no wildcard listener, so the Workbench changes only
    that dispatch line to the stable ``run-event`` name. The complete original
    event, including ``event_type`` and sequence, remains in ``data`` and the
    durable SSE ``id`` is passed through unchanged for automatic reconnects.
    """

    owned_client = client is None
    active_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(connect=15.0, read=None, write=15.0, pool=15.0)
    )
    url = f"{settings.agentos_api_url.rstrip('/')}/v1/runs/{run_id}/events"
    params = {
        "follow": str(follow).lower(),
        "limit": str(limit),
    }
    if after is not None:
        params["after"] = str(after)
    request = active_client.build_request(
        "GET",
        url,
        headers=_upstream_headers(last_event_id),
        params=params,
    )
    try:
        response = await active_client.send(request, stream=True)
    except httpx.HTTPError as error:
        if owned_client:
            await active_client.aclose()
        raise RunEventsError(f"platform run-event stream is unreachable: {error}") from error

    if not response.is_success:
        detail = await _error_detail(response)
        await response.aclose()
        if owned_client:
            await active_client.aclose()
        raise RunEventsError(detail or "platform rejected the run-event stream", response.status_code)

    content_type = response.headers.get("content-type", "").lower()
    if "text/event-stream" not in content_type:
        await response.aclose()
        if owned_client:
            await active_client.aclose()
        raise RunEventsError("platform returned a non-SSE run-event response")

    async def lines() -> AsyncIterator[bytes]:
        try:
            async for line in response.aiter_lines():
                if line.startswith("event:"):
                    line = "event: run-event"
                yield f"{line}\n".encode("utf-8")
        finally:
            await response.aclose()
            if owned_client:
                await active_client.aclose()

    return lines()
