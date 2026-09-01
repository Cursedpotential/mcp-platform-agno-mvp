# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: inspectors — records/schemas/verify/flags)
# Byline: Codex · GPT-5 · 2026-08-29 (runtime-read Platform API bearer file)
"""Shared bearer-authenticated client for Platform API proxy calls.

Factored out of app/service/runs.py's private `_spine_request`/`_extract_detail`
(C1/C2) so the C3 inspectors (records/schemas/verify — app/service/inspect.py,
corroboration flags — app/service/flags.py) don't each reinvent the same
httpx boilerplate. The older runs service retains its response translation,
while both clients now share the same runtime bearer-file reader.

Never imports app.service/app.runtime — repo is the lowest SDK-touching
layer (see tests/test_structure.py).
"""

from __future__ import annotations

import json
import logging

import httpx

from app.config import settings
from app.repo.platform_api_auth import PlatformAPIAuthError, platform_api_bearer_headers

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_S = 120.0


class SpineError(Exception):
    """Raised when a spine call fails — connection error or non-2xx status."""

    def __init__(self, detail: str, status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _extract_detail(response: httpx.Response) -> str:
    """Pull FastAPI's `{"detail": ...}` out of an error body, if present.

    Mirrors app/service/runs.py::_extract_detail — the spine's own
    validation errors are exactly this shape, and surfacing `detail`
    directly avoids double-JSON-wrapping the error when SpineError becomes
    an HTTPException at the runtime layer.
    """
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]
    if isinstance(body, dict) and "detail" in body:
        detail = body["detail"]
        return detail if isinstance(detail, str) else json.dumps(detail)
    return response.text[:500]


def spine_request(method: str, path: str, **kwargs) -> httpx.Response:
    """One request against the spine, with uniform error handling.

    A connection failure or non-2xx status becomes a SpineError; callers are
    spared from repeating the same try/except shape at every call site.
    """
    url = f"{settings.platform_api_url}{path}"
    try:
        headers = {**kwargs.pop("headers", {}), **platform_api_bearer_headers()}
    except PlatformAPIAuthError as error:
        raise SpineError(str(error), 503) from None
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT_S) as client:
            response = client.request(method, url, headers=headers, **kwargs)
    except httpx.HTTPError as e:
        raise SpineError(f"spine unreachable: {e}", 502) from e

    if response.status_code >= 400:
        raise SpineError(_extract_detail(response), response.status_code)
    return response


def spine_json(method: str, path: str, **kwargs):
    """`spine_request()` + `.json()` — the common case for every C3 proxy call."""
    return spine_request(method, path, **kwargs).json()
