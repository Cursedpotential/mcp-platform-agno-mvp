"""Authenticated pass-through to the Universal Import Workflow starter.

Byline: Codex · GPT-5 · 2026-08-28.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings
from app.types.uiw import (
    UIWDecisionRequest,
    UIWDecisionResponse,
    UIWPreviewResponse,
    UIWStartRequest,
    UIWStartResponse,
)


class UIWError(Exception):
    def __init__(self, detail: str, status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _detail(response: httpx.Response) -> str:
    try:
        payload: Any = response.json()
    except (ValueError, json.JSONDecodeError):
        return response.text[:500]
    if isinstance(payload, dict) and isinstance(payload.get("detail"), str):
        return payload["detail"]
    return response.text[:500]


async def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    if not settings.uiw_starter_url.strip():
        raise UIWError("UIW starter is not configured", 503)
    headers = {
        key: value
        for key, value in dict(kwargs.pop("headers", {})).items()
        if key.lower() != "authorization"
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                method, f"{settings.uiw_starter_url.rstrip('/')}{path}", headers=headers, **kwargs
            )
    except httpx.HTTPError as error:
        raise UIWError(f"UIW starter unreachable: {error}") from error
    if response.status_code >= 400:
        raise UIWError(_detail(response) or "UIW starter rejected the request", response.status_code)
    return response


async def start(request: UIWStartRequest) -> UIWStartResponse:
    response = await _request("POST", "/reference-import/start", json=request.model_dump(mode="json"))
    return UIWStartResponse.model_validate(response.json())


async def decide(workflow_id: str, request: UIWDecisionRequest) -> UIWDecisionResponse:
    response = await _request(
        "POST", f"/reference-import/{workflow_id}/decision", json=request.model_dump()
    )
    return UIWDecisionResponse.model_validate(response.json())


async def preview(workflow_id: str) -> UIWPreviewResponse:
    response = await _request("GET", f"/reference-import/{workflow_id}/preview")
    return UIWPreviewResponse.model_validate(response.json())


async def open_upload_stream(
    body: AsyncIterator[bytes], *, content_type: str | None, content_length: str | None
) -> tuple[httpx.AsyncClient, httpx.Response]:
    """Open a streaming acquisition upload; caller owns response/client closure."""
    if not settings.uiw_starter_url.strip():
        raise UIWError("UIW acquisition upload is not configured", 503)
    headers: dict[str, str] = {}
    if content_type:
        headers["Content-Type"] = content_type
    if content_length:
        headers["Content-Length"] = content_length
    client = httpx.AsyncClient(timeout=httpx.Timeout(connect=15.0, read=None, write=30.0, pool=15.0))
    request = client.build_request(
        "POST", f"{settings.uiw_starter_url.rstrip('/')}/acquisition/upload", headers=headers, content=body
    )
    try:
        response = await client.send(request, stream=True)
    except httpx.HTTPError as error:
        await client.aclose()
        raise UIWError(f"UIW acquisition upload unreachable: {error}") from error
    if response.status_code >= 400:
        detail = await _detail_async(response)
        await response.aclose()
        await client.aclose()
        raise UIWError(detail or "UIW acquisition upload rejected the request", response.status_code)
    return client, response


async def _detail_async(response: httpx.Response) -> str:
    payload = (await response.aread())[:500]
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return payload.decode("utf-8", errors="replace")
    if isinstance(parsed, dict) and isinstance(parsed.get("detail"), str):
        return parsed["detail"]
    return payload.decode("utf-8", errors="replace")
