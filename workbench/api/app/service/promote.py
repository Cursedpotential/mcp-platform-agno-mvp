# Byline: Claude Code · Sonnet (agent) · 2026-07-19
# Byline: Claude Code · Sonnet 5 · 2026-08-26 (D-082 permanent AI-chat evidence fence, GAP-032/WP-C01)
"""Promote a staged file through the EXISTING platform ingestion API.

New in the workbench (no donor equivalent — the donor kit chunked/embedded
in-process instead of promoting through a separate spine). Two paths, keyed
off `detected_type`:

- "doc" -> POST {AGENTOS_API_URL}/knowledge/content, then poll
  GET /knowledge/content/{content_id}/status until completed/failed.
- "chat_export" -> DENIED, locally, before any network call. D-082
  (docs/DECISION_LOG.md, owner-ruled 2026-08-26) permanently forbids
  promoting AI-chat exports to evidence custody; GAP-032/WP-C01. This used to
  POST {AGENTOS_API_URL}/v1/evidence/import (workflow=chat-transcript) — that
  spine route now independently denies the same workflow too (defense in
  depth, server/api/evidence_routes.py), but there is no legitimate outcome
  left to wait on a round trip for.

The "doc" spine endpoint may not be deployed yet (P3 work) — a 404 is handled
as a clear "not deployed yet" failure, not a crash. This module never touches
Milvus/Postgres/LanceDB-chunks directly; it only calls the spine's own HTTP
API and records the spine's response verbatim in `promote_result`.
"""

from __future__ import annotations

import asyncio
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


async def _load_file_bytes(record: dict) -> tuple[bytes, str]:
    """Return (bytes, filename) for the original upload.

    Prefers the object-store copy (the true original bytes); falls back to
    the stored text extract if the object-store fetch fails for any reason.
    boto3 has no native async client, so the blocking call is offloaded to a
    worker thread instead of stalling the event loop.
    """
    name = record["name"]
    try:
        return await asyncio.to_thread(get_object, record["r2_key"]), name
    except Exception:
        logger.warning(
            "Object store fetch failed for r2_key=%s, falling back to stored text",
            record.get("r2_key"),
            exc_info=True,
        )
        return (record.get("text") or "").encode("utf-8"), name


async def _promote_doc(record: dict, client: httpx.AsyncClient) -> dict:
    file_bytes, filename = await _load_file_bytes(record)
    meta = record.get("meta") or {}
    form = {
        "domain": meta.get("domain", ""),
        "category": meta.get("category", ""),
        "sha256": record["id"],
        "source": "workbench",
    }
    response = await client.post(
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
        status_resp = await client.get(
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
        await asyncio.sleep(_POLL_INTERVAL_S)

    return {"status": "failed", "content_id": content_id, "error": "promote timed out waiting for spine"}


# D-082 permanent AI-chat evidence fence (GAP-032/WP-C01, owner-ruled
# 2026-08-26). "failed" (not a new status string) so no frontend/type change
# is needed — workbench/web's StagedStatus union stays "staged" | "promoting"
# | "promoted" | "failed" — but the message is unmistakably a permanent
# policy denial, not a transient "spine unreachable" failure, so an operator
# (or a test) can't confuse the two.
_CHAT_EXPORT_DENIAL = (
    "DENIED (permanent, D-082): AI-chat exports are context-only and can never be promoted to "
    "evidence. No promotion attempted; no network call made. See docs/DECISION_LOG.md#D-082, "
    "GAP-032/WP-C01."
)


async def _promote_chat_export(record: dict, client: httpx.AsyncClient) -> dict:
    # Denied locally, before any spine call — see _CHAT_EXPORT_DENIAL and the
    # module docstring. `record`/`client` args kept for call-site symmetry
    # with _promote_doc; unused here by construction.
    del record, client
    return {"status": "failed", "error": _CHAT_EXPORT_DENIAL, "denied": True}


async def promote(file_id: str) -> dict:
    """Promote a staged file. Returns the updated staged_files record."""
    record = staging.get(file_id)
    if record is None:
        raise PromoteError(f"Staged file '{file_id}' not found", 404)

    staging.update_status(file_id, "promoting")

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S) as client:
            if record["detected_type"] == "chat_export":
                result = await _promote_chat_export(record, client)
            else:
                result = await _promote_doc(record, client)
    except httpx.HTTPError as e:
        result = {"status": "failed", "error": f"spine request failed: {e}"}
        logger.warning("Promote failed for %s: %s", file_id, e)

    updated = staging.update_status(file_id, result["status"], promote_result=result)
    # Mirror the error at the top level too — the workbench/web frontend's
    # PromoteResult type reads `result.error` directly, not `result.promote_result.error`.
    updated["error"] = result.get("error")
    return updated


async def promote_all() -> list[dict]:
    """Promote every currently-staged (not yet promoted) file."""
    pending = staging.list(status="staged", limit=1000)
    results = []
    for rec in pending:
        try:
            results.append(await promote(rec["id"]))
        except PromoteError as e:
            results.append({"id": rec["id"], "status": "failed", "error": e.detail})
    return results
