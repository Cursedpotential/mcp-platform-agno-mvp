"""Runtime Platform API bearer loading for Workbench-to-platform requests.

The secret is intentionally absent from process environment and application
settings. Every call reads the mounted file again, allowing Platform API bearer
rotation without rebuilding, redeploying, or restarting the Workbench.

Byline: Codex · GPT-5 · 2026-08-29
"""

from __future__ import annotations

from pathlib import Path
import re

from app.config import settings

_BEARER_TOKEN = re.compile(r"[A-Za-z0-9\-._~+/]+={0,}")
_MAX_TOKEN_BYTES = 4096
_SAFE_ERROR = "Platform API bearer secret is unavailable or invalid"


class PlatformAPIAuthError(RuntimeError):
    """Fail-closed credential error with no secret-bearing detail."""


def _bearer_headers(path_value: str) -> dict[str, str]:
    try:
        raw = Path(path_value).read_bytes()
    except OSError:
        raise PlatformAPIAuthError(_SAFE_ERROR) from None

    if not raw or len(raw) > _MAX_TOKEN_BYTES:
        raise PlatformAPIAuthError(_SAFE_ERROR)
    try:
        token = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise PlatformAPIAuthError(_SAFE_ERROR) from None
    if _BEARER_TOKEN.fullmatch(token) is None:
        raise PlatformAPIAuthError(_SAFE_ERROR)
    return {"Authorization": f"Bearer {token}"}


def platform_api_bearer_headers() -> dict[str, str]:
    """Read and validate the Platform API bearer for one request."""

    return _bearer_headers(settings.platform_api_bearer_secret_file)


def evidence_operator_bearer_headers() -> dict[str, str]:
    """Read the distinct owner-search capability for one request."""

    return _bearer_headers(settings.evidence_operator_bearer_secret_file)
