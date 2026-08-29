"""Inbound authentication for the tailnet-bound operator Workbench.

Byline: Codex · GPT-5 · 2026-08-15
Byline: Codex · GPT-5 · 2026-08-29 (passwordless direct-tailnet owner access)
"""

from __future__ import annotations

import ipaddress
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

_OWNER = "owner"
_TAILNET = ipaddress.ip_network("100.64.0.0/10")


def _is_direct_tailnet_client(request: Request) -> bool:
    """Accept only the socket peer; forwarded headers are intentionally ignored."""
    if request.client is None:
        return False
    try:
        return ipaddress.ip_address(request.client.host) in _TAILNET
    except ValueError:
        return False


async def authentication_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Authenticate every Workbench surface except the exact health path."""
    if request.url.path == "/health":
        return await call_next(request)

    if not _is_direct_tailnet_client(request):
        return JSONResponse(
            status_code=403,
            content={"detail": "Direct tailnet access required"},
        )

    request.scope.setdefault("state", {})["principal"] = _OWNER
    return await call_next(request)
