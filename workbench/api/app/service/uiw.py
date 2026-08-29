"""Authenticated pass-through to the Universal Import Workflow starter.

Byline: Codex · GPT-5 · 2026-08-28.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings
from app.repo.object_store_client import (
    CASEBIBLE_SORTED_PREFIX,
    list_casebible_sorted_objects,
)
from app.types.uiw import (
    UIWDecisionRequest,
    UIWDecisionResponse,
    UIWPreviewResponse,
    UIWStartRequest,
    UIWStartResponse,
    UIWSourceBrowserResponse,
    UIWSourceObject,
    UIWSourcePrefix,
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


def browse_sources(
    *, prefix: str = "", continuation_token: str | None = None, filter_text: str = "", page_size: int = 100
) -> UIWSourceBrowserResponse:
    """Browse the fixed Case Bible Sorted bucket without exposing provider choices."""
    normalized_prefix = prefix.strip()
    if normalized_prefix.startswith("/") or "\\" in normalized_prefix or ".." in normalized_prefix.split("/"):
        raise UIWError("source prefix is outside the Case Bible Sorted root", 422)
    normalized_filter = filter_text.strip().casefold()
    try:
        page = list_casebible_sorted_objects(
            prefix=CASEBIBLE_SORTED_PREFIX + normalized_prefix,
            continuation_token=continuation_token,
            max_keys=page_size,
        )
    except RuntimeError as error:
        raise UIWError(str(error), 503) from error

    prefixes = []
    for row in page.get("CommonPrefixes", []):
        child_prefix = str(row.get("Prefix", ""))
        name = child_prefix.rstrip("/").rsplit("/", 1)[-1]
        if child_prefix and (not normalized_filter or normalized_filter in name.casefold()):
            prefixes.append(UIWSourcePrefix(prefix=child_prefix, name=name))
    objects = []
    for row in page.get("Contents", []):
        key = str(row.get("Key", ""))
        name = key.rsplit("/", 1)[-1]
        if not key or key.endswith("/") or (normalized_filter and normalized_filter not in key.casefold()):
            continue
        objects.append(
            UIWSourceObject(
                key=key,
                name=name,
                byte_length=int(row.get("Size", 0)),
                last_modified=row.get("LastModified"),
                etag=str(row["ETag"]).strip('"') if row.get("ETag") else None,
            )
        )
    return UIWSourceBrowserResponse(
        prefix=normalized_prefix,
        filter=filter_text.strip(),
        filter_applied=bool(normalized_filter),
        page_size=page_size,
        is_truncated=bool(page.get("IsTruncated", False)),
        continuation_token=page.get("NextContinuationToken"),
        prefixes=prefixes,
        objects=objects,
    )


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
