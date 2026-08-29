"""Inbound authentication for the Traefik+Authentik-protected operator Workbench.

Byline: Codex · GPT-5 · 2026-08-15
Byline: Codex · GPT-5 · 2026-08-29 (passwordless direct-tailnet owner access)
Byline: Codex · GPT-5 · 2026-08-29 (strict trusted-proxy + Authentik identity headers)
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Awaitable, Callable

from app.config import settings
from fastapi import Request, Response
from fastapi.responses import JSONResponse

_AUTHENTIK_UID_HEADER = "x-authentik-uid"
_AUTHENTIK_USERNAME_HEADER = "x-authentik-username"
_MAX_HEADER_VALUE_LEN = 256
_CTRL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _client_ip(request: Request) -> str | None:
    """Return the socket peer IP. Forwarded headers are intentionally ignored."""
    if request.client is None:
        return None
    return request.client.host


def _ip_in_cidrs(ip_str: str, cidrs: list[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> bool:
    """Check if an IP address is within any of the configured CIDR networks."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(ip in cidr for cidr in cidrs)


def _validate_identity_header(value: str | None) -> str | None:
    """Validate Authentik identity header: non-empty, no control chars, length limit."""
    if not value:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > _MAX_HEADER_VALUE_LEN:
        return None
    if _CTRL_CHARS_RE.search(stripped):
        return None
    return stripped


async def authentication_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Authenticate every Workbench surface except the exact health path.

    1. /health is the only public exception.
    2. Every other request must have socket peer inside explicitly configured
       trusted proxy CIDRs (fail-closed on empty/invalid config).
    3. Only after trusted peer verification, require Authentik identity headers
       (X-authentik-uid, X-authentik-username). Both non-blank, no control chars.
    4. Store principal (username) and immutable subject UID in request.state.
    5. Reject direct tailnet clients, untrusted peers, missing identity, blank
       identity, spoofed identity from untrusted peers. Ignore X-Forwarded-For.
    """
    if request.url.path == "/health":
        return await call_next(request)

    # Trusted proxy CIDR check (fail-closed)
    trusted_cidrs = settings.trusted_auth_proxy_cidrs_parsed
    if not trusted_cidrs:
        return JSONResponse(
            status_code=403,
            content={"detail": "Authentication gateway not configured"},
        )

    client_ip = _client_ip(request)
    if not client_ip or not _ip_in_cidrs(client_ip, trusted_cidrs):
        return JSONResponse(
            status_code=403,
            content={"detail": "Untrusted proxy"},
        )

    # Authentik identity headers (case-insensitive via Starlette Headers)
    uid_raw = request.headers.get(_AUTHENTIK_UID_HEADER)
    username_raw = request.headers.get(_AUTHENTIK_USERNAME_HEADER)

    uid = _validate_identity_header(uid_raw)
    username = _validate_identity_header(username_raw)

    if not uid or not username:
        return JSONResponse(
            status_code=403,
            content={"detail": "Missing or invalid Authentik identity"},
        )

    # Store principal and immutable subject UID
    request.state.principal = username
    request.state.subject_uid = uid

    return await call_next(request)
