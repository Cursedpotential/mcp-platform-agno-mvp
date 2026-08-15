"""Mandatory inbound authentication for the operator Workbench.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

import base64
import binascii
import secrets
from collections.abc import Awaitable, Callable

from app.config import settings
from fastapi import Request, Response
from fastapi.responses import JSONResponse

_OWNER = "owner"
_BASIC_CHALLENGE = 'Basic realm="Knowledge Workbench", charset="UTF-8"'


def _constant_time_match(candidate: str, expected: str) -> bool:
    """Compare credentials without leaking a useful length/timing signal."""
    return secrets.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def _valid_basic(credentials: str, expected_key: str) -> bool:
    try:
        decoded = base64.b64decode(credentials, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    username, separator, password = decoded.partition(":")
    username_valid = _constant_time_match(username, _OWNER)
    password_valid = _constant_time_match(password, expected_key)
    return bool(separator and username_valid and password_valid)


def _is_authorized(authorization: str | None, expected_key: str) -> bool:
    if not authorization:
        return False
    scheme, separator, credentials = authorization.partition(" ")
    if not separator or not credentials:
        return False
    if scheme.lower() == "bearer":
        return _constant_time_match(credentials, expected_key)
    if scheme.lower() == "basic":
        return _valid_basic(credentials, expected_key)
    return False


async def authentication_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Authenticate every Workbench surface except the exact health path."""
    if request.url.path == "/health":
        return await call_next(request)

    expected_key = settings.workbench_api_key
    if not expected_key:
        return JSONResponse(
            status_code=503,
            content={"detail": "Workbench authentication is not configured"},
        )

    if not _is_authorized(request.headers.get("authorization"), expected_key):
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": _BASIC_CHALLENGE},
        )

    request.scope.setdefault("state", {})["principal"] = _OWNER
    return await call_next(request)
