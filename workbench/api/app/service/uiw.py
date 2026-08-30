"""Authenticated pass-through to the Universal Import Workflow starter.

Byline: Codex · GPT-5 · 2026-08-28.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import stat
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import settings
from app.repo.object_store_client import (
    CASEBIBLE_SORTED_PREFIX,
    list_casebible_sorted_objects,
)
from app.types.uiw import (
    UIWDecisionRequest,
    UIWDecisionActor,
    UIWDecisionResponse,
    UIWRepairDecisionRequest,
    UIWRepairDecisionResponse,
    UIWPreviewEvent,
    UIWPreviewMessagesResponse,
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


_SERVICE_TOKEN = re.compile(r"[A-Za-z0-9\-._~+/]+={0,}")
_MIN_SERVICE_TOKEN_BYTES = 32
_MAX_SERVICE_TOKEN_BYTES = 4096
_MAX_SERVICE_TOKEN_FILE_BYTES = _MAX_SERVICE_TOKEN_BYTES + 2
_SAFE_SERVICE_AUTH_ERROR = "UIW service authentication is unavailable or invalid"


def _service_authorization_headers() -> dict[str, str]:
    """Read and validate the mounted UIW service token for one request."""
    path = Path(settings.uiw_service_token_file)
    if not path.is_absolute():
        raise UIWError(_SAFE_SERVICE_AUTH_ERROR, 503)
    try:
        file_info = path.lstat()
        if not stat.S_ISREG(file_info.st_mode) or not (
            _MIN_SERVICE_TOKEN_BYTES <= file_info.st_size <= _MAX_SERVICE_TOKEN_FILE_BYTES
        ):
            raise UIWError(_SAFE_SERVICE_AUTH_ERROR, 503)
        with path.open("rb") as secret_file:
            raw = secret_file.read(_MAX_SERVICE_TOKEN_FILE_BYTES + 1)
    except OSError:
        raise UIWError(_SAFE_SERVICE_AUTH_ERROR, 503) from None
    raw = raw.rstrip(b"\r\n")
    if not (_MIN_SERVICE_TOKEN_BYTES <= len(raw) <= _MAX_SERVICE_TOKEN_BYTES) or b"\x00" in raw:
        raise UIWError(_SAFE_SERVICE_AUTH_ERROR, 503)
    try:
        token = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise UIWError(_SAFE_SERVICE_AUTH_ERROR, 503) from None
    if _SERVICE_TOKEN.fullmatch(token) is None:
        raise UIWError(_SAFE_SERVICE_AUTH_ERROR, 503)
    return {"Authorization": f"Bearer {token}"}


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
    headers = {key: value for key, value in dict(kwargs.pop("headers", {})).items() if key.lower() != "authorization"}
    headers.update(_service_authorization_headers())
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
    return _validated(
        UIWStartResponse,
        _json_payload(response, "start response"),
        "start response",
    )


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


def _validated(model, payload: Any, label: str):
    try:
        return model.model_validate(payload)
    except (ValidationError, ValueError, TypeError) as error:
        raise UIWError(f"UIW starter returned an invalid {label}", 502) from error


def _json_payload(response: httpx.Response, label: str) -> Any:
    """Normalize malformed upstream JSON to the BFF's fail-closed 502 contract."""
    try:
        return response.json()
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError, TypeError) as error:
        raise UIWError(f"UIW starter returned malformed JSON for {label}", 502) from error


async def decide(
    preview_handle: str,
    request: UIWDecisionRequest,
    actor: UIWDecisionActor,
) -> UIWDecisionResponse:
    response = await _request(
        "POST",
        f"/reference-import/previews/{preview_handle}/decision",
        json=request.model_dump(mode="json"),
        headers={
            "X-authentik-uid": actor.subject_uid,
            "X-authentik-username": actor.username,
        },
    )
    result = _validated(
        UIWDecisionResponse,
        _json_payload(response, "decision response"),
        "decision response",
    )
    if result.preview_handle != preview_handle:
        raise UIWError("UIW decision response correlation failed", 502)
    return result


def _repair_idempotency_key(
    preview_handle: str,
    request: UIWRepairDecisionRequest,
    actor: UIWDecisionActor,
) -> str:
    """Bind repair retries to handle, immutable subject, and canonical choice."""
    canonical = json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256(f"{preview_handle}\x00{actor.subject_uid}\x00{canonical}".encode()).hexdigest()
    return f"uiw-repair:{digest}"


async def decide_repair(
    preview_handle: str,
    request: UIWRepairDecisionRequest,
    actor: UIWDecisionActor,
) -> UIWRepairDecisionResponse:
    response = await _request(
        "POST",
        f"/reference-import/previews/{preview_handle}/repair-decision",
        json=request.model_dump(mode="json"),
        headers={
            "X-authentik-uid": actor.subject_uid,
            "X-authentik-username": actor.username,
            "Idempotency-Key": _repair_idempotency_key(preview_handle, request, actor),
        },
    )
    result = _validated(
        UIWRepairDecisionResponse,
        _json_payload(response, "repair decision response"),
        "repair decision response",
    )
    if result.preview_handle != preview_handle:
        raise UIWError("UIW repair decision response correlation failed", 502)
    return result


async def preview(preview_handle: str) -> UIWPreviewResponse:
    response = await _request("GET", f"/reference-import/previews/{preview_handle}")
    result = _validated(
        UIWPreviewResponse,
        _json_payload(response, "preview snapshot"),
        "preview snapshot",
    )
    if result.preview_handle != preview_handle:
        raise UIWError("UIW preview snapshot correlation failed", 502)
    return result


async def preview_messages(preview_handle: str, *, cursor: str | None, limit: int) -> UIWPreviewMessagesResponse:
    params: dict[str, str | int] = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    response = await _request("GET", f"/reference-import/previews/{preview_handle}/messages", params=params)
    result = _validated(
        UIWPreviewMessagesResponse,
        _json_payload(response, "preview message page"),
        "preview message page",
    )
    if result.preview_handle != preview_handle:
        raise UIWError("UIW preview message correlation failed", 502)
    return result


async def open_preview_event_stream(
    preview_handle: str, *, last_event_id: int | None
) -> tuple[httpx.AsyncClient, httpx.Response]:
    """Open the dedicated UIW event stream; legacy run events are never consulted."""
    if not settings.uiw_starter_url.strip():
        raise UIWError("UIW starter is not configured", 503)
    headers = {"Accept": "text/event-stream", **_service_authorization_headers()}
    if last_event_id is not None:
        headers["Last-Event-ID"] = str(last_event_id)
    client = httpx.AsyncClient(timeout=httpx.Timeout(connect=15.0, read=None, write=15.0, pool=15.0))
    request = client.build_request(
        "GET",
        f"{settings.uiw_starter_url.rstrip('/')}/reference-import/previews/{preview_handle}/events",
        headers=headers,
    )
    try:
        response = await client.send(request, stream=True)
    except httpx.HTTPError as error:
        await client.aclose()
        raise UIWError(f"UIW preview event stream unreachable: {error}") from error
    if response.status_code >= 400:
        detail = await _detail_async(response)
        await response.aclose()
        await client.aclose()
        raise UIWError(detail or "UIW preview event stream rejected the request", response.status_code)
    if "text/event-stream" not in response.headers.get("content-type", "").casefold():
        await response.aclose()
        await client.aclose()
        raise UIWError("UIW starter did not return a preview event stream", 502)
    return client, response


async def validated_preview_events(
    response: httpx.Response, *, preview_handle: str, last_event_id: int | None
) -> AsyncIterator[str]:
    """Validate and re-emit monotonic, replayable UIW events."""
    previous = last_event_id if last_event_id is not None else -1
    data_lines: list[str] = []
    upstream_id: int | None = None
    async for line in response.aiter_lines():
        if line.startswith(":"):
            continue
        if line.startswith("id:"):
            try:
                upstream_id = int(line[3:].strip())
            except ValueError as error:
                raise UIWError("UIW preview event stream returned a malformed event id", 502) from error
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
        elif not line:
            if not data_lines:
                upstream_id = None
                continue
            try:
                payload = json.loads("\n".join(data_lines))
            except json.JSONDecodeError as error:
                raise UIWError("UIW preview event stream returned malformed JSON", 502) from error
            event = _validated(UIWPreviewEvent, payload, "preview event")
            if event.preview_handle != preview_handle or upstream_id != event.event_id:
                raise UIWError("UIW preview event correlation failed", 502)
            if event.event_id <= previous:
                raise UIWError("UIW preview event sequence is not monotonic", 502)
            previous = event.event_id
            yield f"id: {event.event_id}\nevent: uiw.preview\ndata: {event.model_dump_json()}\n\n"
            upstream_id = None
            data_lines = []


async def open_upload_stream(
    body: AsyncIterator[bytes], *, content_type: str | None, content_length: str | None
) -> tuple[httpx.AsyncClient, httpx.Response]:
    """Open a streaming acquisition upload; caller owns response/client closure."""
    if not settings.uiw_starter_url.strip():
        raise UIWError("UIW acquisition upload is not configured", 503)
    headers: dict[str, str] = _service_authorization_headers()
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
