"""Shared runtime-file authentication for Platform API owner routes.

The bearer is intentionally read for every check so rotation takes effect on
the next request without rebuilding or redeploying either API or Workbench.

Byline: Codex · GPT-5.6-Sol · 2026-08-29
"""

from __future__ import annotations

import hmac
from pathlib import Path
import re

from fastapi import HTTPException, Request

_PLATFORM_API_BEARER_FILE = Path("/run/secrets/platform-api-bearer")
_BEARER_TOKEN = re.compile(r"[A-Za-z0-9\-._~+/]+={0,}")
_MAX_TOKEN_BYTES = 4096


def read_platform_api_bearer() -> str | None:
    """Return the current mounted bearer, or ``None`` when unavailable."""

    try:
        raw = _PLATFORM_API_BEARER_FILE.read_bytes()
    except OSError:
        return None
    if not raw or len(raw) > _MAX_TOKEN_BYTES:
        return None
    try:
        credential = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    if _BEARER_TOKEN.fullmatch(credential) is None:
        return None
    return credential


def require_platform_owner(request: Request) -> None:
    """Enforce the runtime-file bearer for a route-local defense-in-depth check."""

    expected = read_platform_api_bearer()
    if not expected:
        raise HTTPException(503, "platform API authorization is not configured")
    scheme, separator, credential = request.headers.get("authorization", "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not hmac.compare_digest(credential.encode(), expected.encode()):
        raise HTTPException(401, "authentication required", headers={"WWW-Authenticate": "Bearer"})
