# Byline: Claude Code · Sonnet (agent) · 2026-07-20
"""Proxy to the spine's run pipeline (POST /v1/runs, GET /v1/runs[/{id}]).

New in the workbench — the C1 Operator Console's replacement for the
promote-as-a-blind-box UX (service/promote.py). This module never touches
Milvus/Postgres/LanceDB-chunks itself; it only forwards to the spine's own
HTTP API (a parallel build, contract assumed per the build brief — see
module-level docstrings below for the exact assumptions) and returns the
spine's response verbatim.

Two ways to start a run:
- `staged_id` — an existing LanceDB `staged_files` row; its original bytes
  are fetched from the object store (repo/object_store_client) and
  forwarded as the multipart file.
- `file_bytes` + `filename` — a fresh upload forwarded directly, without
  ever landing in the staging table (the New-run dialog's "drop a file"
  path can skip staging entirely).
"""

from __future__ import annotations

import json
import logging

import httpx

from app.config import settings
from app.repo import get_object
from app.repo import staging

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT_S = 120.0


class RunsError(Exception):
    """Raised when a run cannot be started, listed, or fetched."""

    def __init__(self, detail: str, status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _auth_headers() -> dict[str, str]:
    if settings.agentos_api_token:
        return {"Authorization": f"Bearer {settings.agentos_api_token}"}
    return {}


def _extract_detail(response: httpx.Response) -> str:
    """Pull FastAPI's `{"detail": ...}` out of an error body, if present.

    The spine's own validation errors (`HTTPException(422, "unknown workflow
    ...")`, `HTTPException(404, f"run {run_id!r} not found")`) are exactly
    this shape — surfacing `detail` directly avoids double-JSON-wrapping the
    error when this module's own RunsError gets turned into another
    HTTPException by runtime/runs.py.
    """
    try:
        body = response.json()
    except ValueError:
        return response.text[:500]
    if isinstance(body, dict) and "detail" in body:
        detail = body["detail"]
        return detail if isinstance(detail, str) else json.dumps(detail)
    return response.text[:500]


def _spine_request(method: str, path: str, **kwargs) -> httpx.Response:
    """One request against the spine, with uniform error handling.

    A connection failure or non-2xx status becomes a RunsError; the caller
    is spared from three different try/except shapes per call site.
    """
    url = f"{settings.agentos_api_url}{path}"
    headers = {**_auth_headers(), **kwargs.pop("headers", {})}
    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT_S) as client:
            response = client.request(method, url, headers=headers, **kwargs)
    except httpx.HTTPError as e:
        raise RunsError(f"spine unreachable: {e}", 502) from e

    if response.status_code >= 400:
        raise RunsError(_extract_detail(response), response.status_code)
    return response


def start_run(
    *,
    workflow: str,
    domain: str | None,
    mode: str = "auto",
    source_meta: dict | None = None,
    staged_id: str | None = None,
    file_bytes: bytes | None = None,
    filename: str | None = None,
) -> dict:
    """Start a spine run. Provide either `staged_id` or (`file_bytes` + `filename`).

    Returns the spine's 202 response body: {run_id, workflow, mode}.
    """
    if not workflow:
        raise RunsError("workflow is required", 400)

    if staged_id:
        record = staging.get(staged_id)
        if record is None:
            raise RunsError(f"Staged file '{staged_id}' not found", 404)
        try:
            file_bytes = get_object(record["r2_key"])
        except Exception as e:
            raise RunsError(f"Failed to fetch staged file bytes: {e}", 502) from e
        filename = record["name"]
        merged_meta = dict(source_meta or {})
        merged_meta.setdefault("sha256", record["id"])
        merged_meta.setdefault("staged_id", staged_id)
        source_meta = merged_meta

    if not file_bytes or not filename:
        raise RunsError("a file is required: pass staged_id or an uploaded file", 400)

    form = {"workflow": workflow, "domain": domain or "", "mode": mode or "auto"}
    if source_meta is not None:
        form["source_meta"] = json.dumps(source_meta)

    response = _spine_request(
        "POST",
        "/v1/runs",
        files={"file": (filename, file_bytes, "application/octet-stream")},
        data=form,
    )
    return response.json()


def list_runs(status: str | None = None, limit: int | None = None) -> list[dict]:
    """GET /v1/runs passthrough."""
    params: dict[str, str | int] = {}
    if status:
        params["status"] = status
    if limit:
        params["limit"] = limit
    response = _spine_request("GET", "/v1/runs", params=params)
    return response.json()


def get_run(run_id: str) -> dict:
    """GET /v1/runs/{id} passthrough."""
    response = _spine_request("GET", f"/v1/runs/{run_id}")
    return response.json()
