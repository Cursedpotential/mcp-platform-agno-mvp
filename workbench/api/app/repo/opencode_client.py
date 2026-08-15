# Byline: Claude Code · Sonnet (agent) · 2026-07-21
"""httpx client for the platform's headless OpenCode server (ovh-app :4096).

Request/response shapes below are reused VERBATIM from the proven-live `oc`
CLI (C:/Users/matts/.claude/skills/opencode-ops/scripts/oc.py, byline
2026-07-20) — that tool already talks to this exact server and its shapes
were spot-checked against it, so this module does not re-derive them from
opencode's own OpenAPI doc. Key facts carried over from `oc.py`:

- `POST /session[?directory=<dir>]` `{}` -> `{"id": "<session_id>", ...}`.
- `POST /session/{id}/message[?directory=<dir>]`
  `{"model": {"providerID": ..., "modelID": ...},
    "parts": [{"type": "text", "text": <prompt>}]}`
  -> per `oc.py`'s `cmd_run`, the server BLOCKS until the assistant finishes
  and returns the final message directly:
  `{"info": {"error": {...}?}, "parts": [{"type": "text", "text": ...}, ...]}`.
  No separate "poll until idle" round-trip is needed for the common case —
  `oc.py` reads the reply straight off this one response. As a DEFENSIVE
  fallback only (the C2.5 brief asked for "poll session messages until
  idle/finish", and a future opencode build could switch to an async 202),
  `send_message` below retries `GET /session/{id}/message` if the initial
  response comes back with neither text nor an error — an ASSUMED, NOT
  live-verified, sub-resource shape (REST convention off `/session/{id}`,
  not confirmed against oc.py or opencode's docs). It degrades to "no extra
  text found" rather than raising if that endpoint doesn't exist.
- `GET /provider` -> `{"connected": [...], "default": {...},
  "all": [{"id", "name", "models": {...}, "key"?}]}`. `key` is a live
  provider secret on unauthenticated deployments (see the C2.5 build
  brief's key-leak fix) — this module never reads or forwards it; callers
  that need it redacted should only ever copy out `id`/`name`/`models`.
- `GET /session/{id}` -> `{"id", "title", "directory", "cost", "tokens"}`.
- `GET /` -> plain 200 liveness, no body contract assumed.

Auth: HTTP Basic, native to `opencode serve` via
OPENCODE_SERVER_USERNAME/OPENCODE_SERVER_PASSWORD (see compose.gateway.yaml)
— sent only when settings.opencode_password is set. An empty password means
no Authorization header at all, matching the pre-redeploy unauthenticated
tailnet state this module was first built against.

Never imports app.service/app.runtime — repo is the lowest SDK-touching
layer (see tests/test_structure.py).
"""

from __future__ import annotations

import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 30.0
_POLL_INTERVAL_S = 2.0


class OpenCodeError(Exception):
    """Raised when the OpenCode server can't be reached or returns an error."""

    def __init__(self, detail: str, status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _auth() -> httpx.BasicAuth | None:
    if settings.opencode_password:
        return httpx.BasicAuth(settings.opencode_username, settings.opencode_password)
    return None


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body=None,
    timeout: float = _DEFAULT_TIMEOUT_S,
) -> dict:
    url = f"{settings.opencode_url}{path}"
    try:
        with httpx.Client(timeout=timeout, auth=_auth()) as client:
            response = client.request(method, url, params=params, json=json_body)
    except httpx.HTTPError as e:
        raise OpenCodeError(f"OpenCode server unreachable ({url}): {e}", 502) from e
    if response.status_code >= 400:
        raise OpenCodeError(
            f"OpenCode server {url} returned HTTP {response.status_code}: {response.text[:500]}",
            response.status_code,
        )
    try:
        return response.json() if response.text.strip() else {}
    except ValueError as e:
        raise OpenCodeError(f"OpenCode server {url} returned non-JSON: {e}", 502) from e


def check_liveness(timeout: float = _DEFAULT_TIMEOUT_S) -> bool:
    """GET / — plain liveness probe. Returns False rather than raising."""
    try:
        with httpx.Client(timeout=timeout, auth=_auth()) as client:
            response = client.get(f"{settings.opencode_url}/")
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def list_providers(timeout: float = _DEFAULT_TIMEOUT_S) -> dict:
    """GET /provider -> {"connected": [...], "default": {...}, "all": [...]}.

    Caller is responsible for never forwarding a provider's "key" field —
    see module docstring.
    """
    return _request("GET", "/provider", timeout=timeout)


def create_session(directory: str | None = None, timeout: float = _DEFAULT_TIMEOUT_S) -> str:
    """POST /session[?directory=...] -> new session id."""
    params = {"directory": directory} if directory else None
    doc = _request("POST", "/session", params=params, json_body={}, timeout=timeout)
    session_id = doc.get("id")
    if not session_id:
        raise OpenCodeError(f"session create returned no id: {doc}", 502)
    return session_id


def get_session(session_id: str, timeout: float = _DEFAULT_TIMEOUT_S) -> dict:
    """GET /session/{id}."""
    return _request("GET", f"/session/{session_id}", timeout=timeout)


def _list_messages(session_id: str, timeout: float) -> list[dict]:
    """GET /session/{id}/message — ASSUMED shape, not live-verified (see
    module docstring); used only as the idle-poll fallback. Never raises —
    an unsupported endpoint just yields no extra messages to check."""
    try:
        doc = _request("GET", f"/session/{session_id}/message", timeout=timeout)
    except OpenCodeError:
        return []
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        return doc.get("messages", [])
    return []


def extract_reply(doc: dict) -> tuple[str, str | None]:
    """(text, error_message) out of a /session/{id}/message-shaped response
    — same logic as oc.py's `cmd_run`: the error comes off `info.error`,
    the text is every `type: "text"` part joined with newlines."""
    info = doc.get("info", {}) if isinstance(doc, dict) else {}
    err = info.get("error")
    error_message = None
    if err:
        name = err.get("name", "Error")
        message = (err.get("data") or {}).get("message", "")
        error_message = f"{name}: {message}" if message else name
    parts = doc.get("parts", []) if isinstance(doc, dict) else []
    text = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
    return text, error_message


def send_message(
    session_id: str,
    provider_id: str,
    model_id: str,
    prompt: str,
    directory: str | None = None,
    timeout: float = 180.0,
) -> tuple[str, str | None]:
    """POST /session/{id}/message — blocks until the assistant replies (see
    module docstring). Returns (text, error_message); a model/server-side
    failure (bad model id, provider error, ...) comes back as error_message
    rather than an OpenCodeError, so the caller can surface it to the
    operator as a normal reply instead of a generic 502.
    """
    params = {"directory": directory} if directory else None
    body = {
        "model": {"providerID": provider_id, "modelID": model_id},
        "parts": [{"type": "text", "text": prompt}],
    }
    deadline = time.monotonic() + timeout
    doc = _request("POST", f"/session/{session_id}/message", params=params, json_body=body, timeout=timeout)
    text, error = extract_reply(doc)

    # Defensive idle-poll fallback — only triggers if the blocking POST came
    # back with neither text nor an error, which hasn't been observed live
    # against this deployment but would mean an async server build.
    remaining = deadline - time.monotonic()
    while not text and not error and remaining > 0:
        time.sleep(min(_POLL_INTERVAL_S, remaining))
        for message in reversed(_list_messages(session_id, timeout=min(remaining, _DEFAULT_TIMEOUT_S))):
            text, error = extract_reply(message)
            if text or error:
                break
        remaining = deadline - time.monotonic()

    return text, error
