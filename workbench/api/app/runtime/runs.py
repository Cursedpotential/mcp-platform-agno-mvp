# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: parse-dryrun endpoint)
# Byline: Codex · GPT-5 · 2026-08-13 (report and review-action endpoints)
# Byline: Codex · GPT-5 · 2026-08-18 (authenticated conversation intake)
"""POST /api/runs, GET /api/runs, GET /api/runs/{id} — proxy to the spine's run pipeline.

POST /api/runs accepts EITHER a JSON body ({staged_id, workflow, domain,
mode, source_meta, custody_tier}) OR a multipart body (file, workflow,
domain, mode, source_meta as a json string, custody_tier) — the New-run
dialog uses JSON when the operator picked an already-staged file, multipart
when they dropped a fresh one. FastAPI can't bind one endpoint signature to
both shapes based on runtime content-type, so this handler reads the raw
`Request` and branches on `Content-Type` itself, then hands a
validated/normalized call down to service/runs.py either way.

C2 (supervised-gate controls) adds three action endpoints against an
existing run — continue/abort/retry — each a bare POST with no body. They
share the same RunsError -> HTTPException translation as the rest of this
module, which is what lets the spine's own 409 (continue on a non-paused
run, abort on a terminal run, retry on a non-failed run) reach the frontend
with its real `detail` message intact instead of a generic 502.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from app.service.runs import (
    RunsError,
    abort_run,
    continue_run,
    create_review_action,
    get_run,
    get_run_report,
    list_runs,
    parse_dryrun,
    retry_run,
    start_run,
)
from app.types.runs import RunCreateRequest, RunReviewActionRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["runs"])


def _authenticated_owner(request: Request) -> str:
    principal = getattr(request.state, "principal", None)
    if principal != "owner":
        raise HTTPException(status_code=401, detail="authenticated owner required")
    return principal


def _acquisition_with_principal(value: dict | None, request: Request) -> dict | None:
    if value is None:
        return None
    return {**value, "asserted_by_category": "human", "asserted_by": _authenticated_owner(request)}


async def _start_from_multipart(request: Request) -> dict:
    _authenticated_owner(request)
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="file is required for a multipart /api/runs request")

    source_meta_raw = form.get("source_meta")
    try:
        source_meta = json.loads(source_meta_raw) if source_meta_raw else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="source_meta must be valid JSON") from None

    acquisition_raw = form.get("acquisition")
    try:
        acquisition = json.loads(acquisition_raw) if acquisition_raw else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="acquisition must be valid JSON") from None
    if acquisition is not None and not isinstance(acquisition, dict):
        raise HTTPException(status_code=400, detail="acquisition must be a JSON object")

    file_bytes = await upload.read()
    return await start_run(
        workflow=str(form.get("workflow", "")),
        domain=form.get("domain") or None,
        mode=str(form.get("mode", "auto")),
        custody_tier=form.get("custody_tier") or None,
        source_meta=source_meta,
        message_corpus=str(form.get("message_corpus") or ""),
        source_principal=str(form.get("source_principal") or ""),
        caller_owns_conversation=str(form.get("caller_owns_conversation") or "false").lower() in {"1", "true", "yes"},
        acquisition=_acquisition_with_principal(acquisition, request),
        file_bytes=file_bytes,
        filename=upload.filename,
    )


async def _start_from_json(request: Request) -> dict:
    _authenticated_owner(request)
    try:
        body = await request.json()
        payload = RunCreateRequest.model_validate(body)
    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    return await start_run(
        staged_id=payload.staged_id,
        workflow=payload.workflow,
        domain=payload.domain,
        mode=payload.mode,
        custody_tier=payload.custody_tier,
        source_meta=payload.source_meta,
        message_corpus=payload.message_corpus,
        source_principal=payload.source_principal,
        caller_owns_conversation=payload.caller_owns_conversation,
        acquisition=_acquisition_with_principal(
            payload.acquisition.model_dump(mode="json") if payload.acquisition else None,
            request,
        ),
    )


@router.post("/runs")
async def create_run_endpoint(request: Request):
    content_type = request.headers.get("content-type", "")
    try:
        if content_type.startswith("multipart/form-data"):
            return await _start_from_multipart(request)
        return await _start_from_json(request)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/runs")
async def list_runs_endpoint(status: str | None = None, limit: int | None = None):
    try:
        return await list_runs(status=status, limit=limit)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/runs/{run_id}")
async def get_run_endpoint(run_id: str):
    try:
        return await get_run(run_id)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/runs/{run_id}/report")
async def get_run_report_endpoint(run_id: str):
    try:
        return await get_run_report(run_id)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/runs/{run_id}/review-actions", status_code=201)
async def create_review_action_endpoint(run_id: str, body: RunReviewActionRequest):
    try:
        return await create_review_action(run_id, body.model_dump())
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/runs/{run_id}/continue")
async def continue_run_endpoint(run_id: str):
    """Release a gated run past its current stage boundary. 409 if not paused."""
    try:
        return await continue_run(run_id)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/runs/{run_id}/abort")
async def abort_run_endpoint(run_id: str):
    """Abort a running or gated run. 409 if the run is already terminal."""
    try:
        return await abort_run(run_id)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/runs/{run_id}/retry")
async def retry_run_endpoint(run_id: str, request: Request):
    """Start a fresh run from a terminal-failed one. 409 if not failed.

    Optional JSON body ``{"from_stage": "knowledge"}`` (C2.6) — forwarded
    verbatim to the spine's retry endpoint; see app/service/runs.py's
    `retry_run` docstring. No body (or a body without `from_stage`) keeps
    the pre-C2.6 full-rerun behavior."""
    from_stage: str | None = None
    body_bytes = await request.body()
    if body_bytes:
        try:
            payload = json.loads(body_bytes)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="retry body is not valid JSON") from None
        if payload is not None:
            if not isinstance(payload, dict):
                raise HTTPException(status_code=422, detail="retry body must be a JSON object")
            from_stage = payload.get("from_stage")
    try:
        return await retry_run(run_id, from_stage=from_stage)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/runs/parse-dryrun")
async def parse_dryrun_endpoint(request: Request):
    """Dry-run parse a staged file (by sha256) or a fresh upload — no run
    is created (C3, requirements addendum 1). Accepts JSON `{"sha256": "..."}`
    or multipart (`file`). See service/runs.py::parse_dryrun's docstring for
    the {id}="new" sentinel this forwards to the spine with."""
    content_type = request.headers.get("content-type", "")
    try:
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            upload = form.get("file")
            if upload is None or not hasattr(upload, "read"):
                raise HTTPException(status_code=400, detail="file is required for a multipart dry-run request")
            file_bytes = await upload.read()
            return await parse_dryrun(file_bytes=file_bytes, filename=upload.filename)

        body_bytes = await request.body()
        try:
            body = json.loads(body_bytes) if body_bytes else {}
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="dry-run body is not valid JSON") from None
        sha256 = body.get("sha256") if isinstance(body, dict) else None
        if not sha256:
            raise HTTPException(status_code=400, detail="sha256 is required in the JSON body")
        return await parse_dryrun(sha256=sha256)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
