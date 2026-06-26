"""Shared SBV HTTP client (underscore prefix -> NOT a tool module; excluded
from registry auto-discovery, same convention as _common.py).

SBV = "SMS Backup Viewer" (ghcr.io/lowcarbdev/sbv, deployed git-0.1.11), a Go
microservice with a session-cookie-authenticated REST API. This client wraps
the auth + the `/api/` surface so both the primary parser (sbv_sms.py) and the
tools-facade SBV proxy talk to SBV through ONE place.

AUTH (cracked from sbv-upstream-main.zip internal/auth.go + verified live
2026-06-25): the API prefix is `/api/` (NOT `/api/v1/` — the old sbv-client.ts
is stale). Auth is a `session_id` HttpOnly cookie obtained from
`POST /api/auth/login` (or `/api/auth/register` — registration is OPEN). We
authenticate with a dedicated service account: login first, and if the user
doesn't exist yet, register it (idempotent bootstrap). Sessions last 30 days;
we just re-login whenever a call returns 401.

Endpoints (all under /api/, protected ones need the cookie):
  PUBLIC : GET /api/health, GET /api/version,
           POST /api/auth/{register,login,logout}
  COOKIE : POST /api/upload (multipart file=<xml>),
           GET  /api/messages, /api/conversations, /api/calls, /api/analytics,
           GET  /api/progress, /api/search, /api/media, /api/media-items,
           GET  /api/activity, /api/daterange, GET/PUT /api/settings
  (There is NO /api/export route in this build — the frontend exports
   client-side; export-as-a-function is served by the facade, not SBV.)

Uses only the stdlib (urllib) + json so it adds NO dependency to the slim
tools-facade image (which has just fastapi/uvicorn/pydantic).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

# Defaults match the deployed container (SBV listens on :8085 inside
# platform-tools). Override via env for local/proxy use.
SBV_BASE_URL = os.getenv("SBV_BASE_URL", "http://localhost:8085").rstrip("/")
SBV_API = f"{SBV_BASE_URL}/api"

# Service-account credentials. The integration registers/logs-in this account
# to obtain a session cookie. Override in the platform-tools env at cutover.
SBV_SERVICE_USER = os.getenv("SBV_SERVICE_USER", "mcp_service")
SBV_SERVICE_PASS = os.getenv("SBV_SERVICE_PASS", "")  # set in env at cutover

DEFAULT_TIMEOUT = float(os.getenv("SBV_TIMEOUT", "60"))


class SBVError(RuntimeError):
    """SBV API error (non-2xx or transport failure)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class SBVClient:
    """Minimal session-cookie SBV API client (stdlib only).

    Lifecycle: construct -> .login() (lazy, auto-called) -> call methods. The
    client holds the `session_id` cookie and re-authenticates on 401.
    """

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base = (base_url or SBV_BASE_URL).rstrip("/")
        self.api = f"{self.base}/api"
        self.username = username or SBV_SERVICE_USER
        self.password = password or SBV_SERVICE_PASS
        self.timeout = timeout
        self._session_id: str | None = None

    # -- transport ---------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        data: bytes | None = None,
        content_type: str | None = None,
        auth: bool = True,
        _retry: bool = True,
    ) -> tuple[int, bytes, dict[str, str]]:
        url = f"{self.api}{path}"
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url = f"{url}?{urllib.parse.urlencode(clean)}"

        body = data
        headers: dict[str, str] = {}
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif content_type:
            headers["Content-Type"] = content_type

        if auth:
            if self._session_id is None:
                self.login()
            headers["Cookie"] = f"session_id={self._session_id}"

        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            # session expired/invalid -> re-login once and retry
            if exc.code == 401 and auth and _retry:
                self._session_id = None
                self.login()
                return self._request(
                    method,
                    path,
                    params=params,
                    json_body=json_body,
                    data=data,
                    content_type=content_type,
                    auth=auth,
                    _retry=False,
                )
            raise SBVError(
                f"SBV {method} {path} -> HTTP {exc.code}: {payload[:300].decode('utf-8', 'replace')}",
                status=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise SBVError(f"SBV {method} {path} -> transport error: {exc.reason}") from exc

    @staticmethod
    def _json(raw: bytes) -> Any:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"_raw": raw.decode("utf-8", "replace")}

    @staticmethod
    def _session_from_response(raw: bytes, headers: dict[str, str]) -> str | None:
        """SBV returns the session id in the JSON body AND a Set-Cookie header.
        Prefer the body (explicit); fall back to parsing Set-Cookie."""
        data = SBVClient._json(raw)
        sess = (data or {}).get("session") or {}
        if isinstance(sess, dict) and sess.get("id"):
            return str(sess["id"])
        cookie = headers.get("Set-Cookie", "")
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith("session_id="):
                return part[len("session_id="):]
        return None

    # -- auth --------------------------------------------------------------

    def login(self) -> str:
        """Obtain a session cookie. Login first; if the service account does
        not exist yet, register it (open registration), then proceed. Returns
        the session id."""
        if not self.password:
            raise SBVError(
                "SBV service password not set (SBV_SERVICE_PASS) — cannot authenticate"
            )
        # try login
        try:
            status, raw, headers = self._request(
                "POST",
                "/auth/login",
                json_body={"username": self.username, "password": self.password},
                auth=False,
            )
            sid = self._session_from_response(raw, headers)
            if sid:
                self._session_id = sid
                return sid
        except SBVError as exc:
            # 401 == user/pass mismatch; only auto-register on "not found"-style
            # 401, which we can't distinguish — so fall through to register and
            # let a genuine bad-password surface as a register conflict/secondary
            # login failure.
            if exc.status not in (401,):
                raise
        # register (idempotent bootstrap) then it returns a session directly
        status, raw, headers = self._request(
            "POST",
            "/auth/register",
            json_body={"username": self.username, "password": self.password},
            auth=False,
        )
        sid = self._session_from_response(raw, headers)
        if not sid:
            raise SBVError("SBV register/login succeeded but no session id returned")
        self._session_id = sid
        return sid

    # -- public surface ----------------------------------------------------

    def health(self) -> bool:
        status, raw, _ = self._request("GET", "/health", auth=False)
        return status == 200

    def version(self) -> dict[str, Any]:
        _, raw, _ = self._request("GET", "/version", auth=False)
        return self._json(raw)

    # -- protected surface -------------------------------------------------

    def upload(self, file_path: str, filename: str | None = None) -> dict[str, Any]:
        """Upload an SMS backup XML as multipart/form-data (field name `file`)."""
        with open(file_path, "rb") as fh:
            content = fh.read()
        name = filename or os.path.basename(file_path)
        boundary = f"----sbvmcp{uuid.uuid4().hex}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
        _, raw, _ = self._request(
            "POST",
            "/upload",
            data=body,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        return self._json(raw)

    def progress(self) -> dict[str, Any]:
        _, raw, _ = self._request("GET", "/progress")
        return self._json(raw)

    def wait_for_processing(self, poll_s: float = 1.0, timeout_s: float = 600.0) -> dict[str, Any]:
        """Poll /api/progress until status is terminal (completed/error/idle)."""
        deadline = time.time() + timeout_s
        last: dict[str, Any] = {}
        while time.time() < deadline:
            last = self.progress()
            status = (last or {}).get("status")
            if status in ("completed", "error", "idle", None):
                # `idle` with processed>0 also means done; None == no job field
                if status == "error":
                    raise SBVError(f"SBV processing error: {last.get('error_message')}")
                if status in ("completed", "idle"):
                    return last
            time.sleep(poll_s)
        raise SBVError(f"SBV processing timed out after {timeout_s}s (last={last})")

    def messages(
        self,
        address: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Any:
        """GET /api/messages?address=<addr>. The deployed SBV (git-0.1.11)
        REQUIRES `address` (returns 400 without it) and uses `start`/`end`
        (RFC3339) — there is no "all messages" endpoint. Returns a bare
        []Message array. To fetch everything, use all_activity()."""
        _, raw, _ = self._request(
            "GET",
            "/messages",
            params={"address": address, "limit": limit, "offset": offset, "start": start_date, "end": end_date},
        )
        return self._json(raw)

    def conversations(self) -> Any:
        """GET /api/conversations -> bare []Conversation array."""
        _, raw, _ = self._request("GET", "/conversations")
        return self._json(raw)

    def all_messages(self, address: str | None = None) -> list[dict[str, Any]]:
        """All messages. If `address` is given, fetch that thread; otherwise
        walk every conversation (SBV has no list-all-messages endpoint)."""
        if address:
            data = self.messages(address=address)
            return data if isinstance(data, list) else (data.get("messages") or [])
        out: list[dict[str, Any]] = []
        convs = self.conversations()
        convs = convs if isinstance(convs, list) else (convs.get("conversations") or [])
        seen: set[str] = set()
        for conv in convs:
            addr = conv.get("address")
            if not addr or addr in seen:
                continue
            seen.add(addr)
            data = self.messages(address=addr)
            out.extend(data if isinstance(data, list) else (data.get("messages") or []))
        return out

    def calls(self, limit: int | None = None, offset: int | None = None) -> Any:
        """GET /api/calls -> bare []CallLog array (no address needed)."""
        _, raw, _ = self._request("GET", "/calls", params={"limit": limit, "offset": offset})
        return self._json(raw)

    def all_calls(self, page: int = 1000) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        offset = 0
        while True:
            data = self.calls(limit=page, offset=offset)
            batch = data if isinstance(data, list) else (data.get("calls") or [])
            out.extend(batch)
            if len(batch) < page:
                break
            offset += page
        return out

    def activity(self, limit: int | None = None, offset: int | None = None) -> Any:
        """GET /api/activity -> bare []ActivityItem array (messages + calls
        across ALL conversations, paginated). The clean 'get everything' path."""
        _, raw, _ = self._request("GET", "/activity", params={"limit": limit, "offset": offset})
        return self._json(raw)

    def all_activity(self, page: int = 1000) -> list[dict[str, Any]]:
        """Auto-paginate /api/activity until exhausted -> all messages + calls."""
        out: list[dict[str, Any]] = []
        offset = 0
        while True:
            data = self.activity(limit=page, offset=offset)
            batch = data if isinstance(data, list) else (data.get("activities") or [])
            out.extend(batch)
            if len(batch) < page:
                break
            offset += page
        return out

    def analytics(self) -> Any:
        _, raw, _ = self._request("GET", "/analytics")
        return self._json(raw)

    def search(self, query: str, limit: int | None = None) -> Any:
        _, raw, _ = self._request("GET", "/search", params={"q": query, "limit": limit})
        return self._json(raw)
