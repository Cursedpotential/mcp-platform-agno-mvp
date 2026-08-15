# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Promote a staged file through the EXISTING platform ingestion API.

New in the workbench (no donor equivalent — the donor kit chunked/embedded
in-process instead of promoting through a separate spine). Two paths, keyed
off `detected_type`:

- "doc" -> POST {AGENTOS_API_URL}/knowledge/content, then poll
  GET /knowledge/content/{content_id}/status until completed/failed.
- "chat_export" -> POST {AGENTOS_API_URL}/v1/evidence/import
  (workflow=chat-transcript).

Both spine endpoints may not be deployed yet (P3 work) — a 404 from either is
handled as a clear "not deployed yet" failure, not a crash. This module never
touches Milvus/Postgres/LanceDB-chunks directly; it only calls the spine's own
HTTP API and records the spine's response verbatim in `promote_result`.
"""

from __future__ import annotations

import json
import logging
import time

import httpx

from app.config import settings
from app.repo import get_object
from app.repo import staging

logger = logging.getLogger(__name__)

_POLL_INTERVAL_S = 2
_POLL_TIMEOUT_S = 60
_HTTP_TIMEOUT_S = 120.0


class PromoteError(Exception):
    """Raised when a promote request cannot even be attempted (e.g. bad id)."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _auth_headers() -> dict[str, str]:
    if settings.agentos_api_token:
        return {"Authorization": f"Bearer {settings.agentos_api_token}"}
    return {}


def _load_file_bytes(record: dict) -> tuple[bytes, str]:
    """Return (bytes, filename) for the original upload.

    Prefers the object-store copy (the true original bytes); falls back to
    the stored text extract if the object-store fetch fails for any reason.
    """
    name = record["name"]
    try:
        return get_object(record["r2_key"]), name
    except Exception:
        logger.warning(
            "Object store fetch failed for r2_key=%s, falling back to stored text",
            record.get("r2_key"),
            exc_info=True,
        )
        return (record.get("text") or "").encode("utf-8"), name


def _promote_doc(record: dict, client: httpx.Client) -> dict:
    file_bytes, filename = _load_file_bytes(record)
    meta = record.get("meta") or {}
    form = {
        "domain": meta.get("domain", ""),
        "category": meta.get("category", ""),
        "sha256": record["id"],
        "source": "workbench",
    }
    response = client.post(
        f"{settings.agentos_api_url}/knowledge/content",
        files={"file": (filename, file_bytes, record.get("mime") or "application/octet-stream")},
        data=form,
        headers=_auth_headers(),
    )
    if response.status_code == 404:
        return {"status": "failed", "error": "spine endpoint not deployed yet"}
    response.raise_for_status()
    body = response.json()
    content_id = body.get("content_id") or body.get("id")
    if not content_id:
        return {"status": "failed", "error": "no content_id in spine response", "response": body}

    deadline = time.monotonic() + _POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        status_resp = client.get(
            f"{settings.agentos_api_url}/knowledge/content/{content_id}/status",
            headers=_auth_headers(),
        )
        if status_resp.status_code == 404:
            return {
                "status": "failed",
                "content_id": content_id,
                "error": "spine status endpoint not deployed yet",
            }
        status_resp.raise_for_status()
        status_body = status_resp.json()
        state = status_body.get("status")
        if state == "completed":
            return {"status": "promoted", "content_id": content_id}
        if state == "failed":
            return {
                "status": "failed",
                "content_id": content_id,
                "error": status_body.get("error", "processing failed"),
            }
        time.sleep(_POLL_INTERVAL_S)

    return {"status": "failed", "content_id": content_id, "error": "promote timed out waiting for spine"}


def _promote_chat_export(record: dict, client: httpx.Client) -> dict:
    file_bytes, filename = _load_file_bytes(record)
    meta = record.get("meta") or {}
    form = {
        "workflow": "chat-transcript",
        "domain": meta.get("domain", ""),
        "source_meta": json.dumps({"source_platform": meta.get("source_platform", ""), "sha256": record["id"]}),
    }
    response = client.post(
        f"{settings.agentos_api_url}/v1/evidence/import",
        files={"file": (filename, file_bytes, record.get("mime") or "application/octet-stream")},
        data=form,
        headers=_auth_headers(),
    )
    if response.status_code == 404:
        return {"status": "failed", "error": "spine endpoint not deployed yet"}
    response.raise_for_status()
    body = response.json()
    records_stored = body.get("records_stored", 0)
    ok = body.get("status") in ("ok", "success") or records_stored > 0
    return {"status": "promoted" if ok else "failed", "response": body}


def promote(file_id: str) -> dict:
    """Promote a staged file. Returns the updated staged_files record."""
    record = staging.get(file_id)
    if record is None:
        raise PromoteError(f"Staged file '{file_id}' not found", 404)

    staging.update_status(file_id, "promoting")

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT_S) as client:
            if record["detected_type"] == "chat_export":
                result = _promote_chat_export(record, client)
            else:
                result = _promote_doc(record, client)
    except httpx.HTTPError as e:
        result = {"status": "failed", "error": f"spine request failed: {e}"}
        logger.warning("Promote failed for %s: %s", file_id, e)

    updated = staging.update_status(file_id, result["status"], promote_result=result)
    # Mirror the error at the top level too — the workbench/web frontend's
    # PromoteResult type reads `result.error` directly, not `result.promote_result.error`.
    updated["error"] = result.get("error")
    return updated


def promote_all() -> list[dict]:
    """Promote every currently-staged (not yet promoted) file."""
    pending = staging.list(status="staged", limit=1000)
    results = []
    for rec in pending:
        try:
            results.append(promote(rec["id"]))
        except PromoteError as e:
            results.append({"id": rec["id"], "status": "failed", "error": e.detail})
    return results
