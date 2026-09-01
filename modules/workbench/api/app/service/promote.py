# Byline: Claude Code · Sonnet (agent) · 2026-07-19
# Byline: Claude Code · Sonnet 5 · 2026-08-26 (D-082 permanent AI-chat evidence fence, GAP-032/WP-C01)
# Byline: Codex · GPT-5 · 2026-08-29 (runtime-read Platform API bearer file)
# Byline: Codex · GPT-5.6-Sol · 2026-08-29 (framework-neutral ingest cutover)
"""Promote a staged file through the EXISTING platform ingestion API.

New in the workbench (no donor equivalent — the donor kit chunked/embedded
in-process instead of promoting through a separate spine). Two paths, keyed
off `detected_type`:

- "doc" -> POST {PLATFORM_API_URL}/v1/ingest, then poll the durable
  PostgreSQL receipt at GET /v1/runs/{run_id} until completed/failed.
- "chat_export" -> DENIED, locally, before any network call. D-082
  (docs/DECISION_LOG.md, owner-ruled 2026-08-26) permanently forbids
  promoting AI-chat exports to evidence custody; GAP-032/WP-C01. This used to
  POST {PLATFORM_API_URL}/v1/evidence/import (workflow=chat-transcript) — that
  spine route now independently denies the same workflow too (defense in
  depth, server/api/evidence_routes.py), but there is no legitimate outcome
  left to wait on a round trip for.

This module never touches PostgreSQL, object-store projections, or chunks
directly; it calls the framework-neutral ingest boundary and records the
durable receipt identity in `promote_result`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from app.config import settings
from app.repo import get_object
from app.repo import staging
from app.repo.platform_api_auth import PlatformAPIAuthError, platform_api_bearer_headers

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
    try:
        return platform_api_bearer_headers()
    except PlatformAPIAuthError as error:
        raise PromoteError(str(error), 503) from None


async def _load_file_bytes(record: dict) -> tuple[bytes, str]:
    """Return the exact original upload bytes and filename.

    The staged text is a derivative and cannot stand in for the original while
    retaining the original source identity/hash. Object-store failure therefore
    fails closed before any ingest request. boto3 has no native async client,
    so the blocking call is offloaded to a worker thread.
    """
    name = record["name"]
    try:
        return await asyncio.to_thread(get_object, record["r2_key"]), name
    except Exception as error:
        logger.warning("Original object-store fetch failed for r2_key=%s", record.get("r2_key"), exc_info=True)
        raise PromoteError(f"original source bytes are unavailable: {error}", 503) from error


async def _promote_doc(record: dict, client: httpx.AsyncClient) -> dict:
    file_bytes, filename = await _load_file_bytes(record)
    meta = record.get("meta") or {}
    source_identity = dict(meta)
    # Staged-file identity is derived from the original bytes at upload time.
    # User-editable classification metadata must never override provenance.
    source_identity.update(
        original_name=filename,
        source="workbench",
        staged_id=record["id"],
        sha256=record["id"],
    )
    form = {
        # All generic documents enter canonical context. Classification and
        # evidentiary promotion remain separate governed decisions.
        "lane": "context",
        "matter_id": str(meta.get("matter_id") or meta.get("case_id") or "primary"),
        "engine": "auto",
        "allow_fallback": "true",
        "custody_tier": "light",
        "source_identity": json.dumps(source_identity),
    }
    response = await client.post(
        f"{settings.platform_api_url}/v1/ingest",
        files={"file": (filename, file_bytes, record.get("mime") or "application/octet-stream")},
        data=form,
        headers=_auth_headers(),
    )
    if response.status_code == 404:
        return {"status": "failed", "error": "framework-neutral ingest endpoint is unavailable"}
    response.raise_for_status()
    body = response.json()
    run_id = body.get("run_id")
    if not run_id:
        return {"status": "failed", "error": "no run_id in ingest response", "response": body}

    deadline = time.monotonic() + _POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            status_resp = await client.get(
                f"{settings.platform_api_url}/v1/runs/{run_id}",
                headers=_auth_headers(),
            )
            status_resp.raise_for_status()
            status_body = status_resp.json()
        except (httpx.HTTPError, ValueError):
            # Submission was durably accepted. A transient inability to read
            # its receipt cannot turn that accepted run into a terminal local
            # failure or discard the reconciliation identity.
            return {
                "status": "promoting",
                "run_id": run_id,
                "pending": True,
                "detail": "durable ingest was accepted; receipt polling is temporarily unavailable",
            }
        state = status_body.get("status")
        if state == "completed":
            artifact_id = status_body.get("artifact_id")
            if not artifact_id:
                return {
                    "status": "failed",
                    "run_id": run_id,
                    "error": "completed ingest receipt has no artifact_id",
                }
            return {
                "status": "promoted",
                "run_id": run_id,
                # Retain content_id as a temporary Workbench response alias;
                # its value is now the canonical artifact identity.
                "content_id": artifact_id,
                "artifact_id": artifact_id,
            }
        if state == "failed":
            return {
                "status": "failed",
                "run_id": run_id,
                "error": status_body.get("error") or "framework-neutral ingest failed",
            }
        await asyncio.sleep(_POLL_INTERVAL_S)

    return {
        "status": "promoting",
        "run_id": run_id,
        "pending": True,
        "detail": "durable ingest continues; polling window elapsed before a terminal receipt",
    }


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
    except PromoteError as e:
        result = {"status": "failed", "error": e.detail}
        logger.warning("Promote could not start for %s: %s", file_id, e.detail)

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
