# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: parse-dryrun endpoint)
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
    get_run,
    list_runs,
    parse_dryrun,
    retry_run,
    start_run,
)
from app.types.runs import RunCreateRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["runs"])


async def _start_from_multipart(request: Request) -> dict:
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="file is required for a multipart /api/runs request")

    source_meta_raw = form.get("source_meta")
    try:
        source_meta = json.loads(source_meta_raw) if source_meta_raw else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="source_meta must be valid JSON") from None

    file_bytes = await upload.read()
    return start_run(
        workflow=str(form.get("workflow", "")),
        domain=form.get("domain") or None,
        mode=str(form.get("mode", "auto")),
        custody_tier=form.get("custody_tier") or None,
        source_meta=source_meta,
        file_bytes=file_bytes,
        filename=upload.filename,
    )


async def _start_from_json(request: Request) -> dict:
    try:
        body = await request.json()
        payload = RunCreateRequest.model_validate(body)
    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    return start_run(
        staged_id=payload.staged_id,
        workflow=payload.workflow,
        domain=payload.domain,
        mode=payload.mode,
        custody_tier=payload.custody_tier,
        source_meta=payload.source_meta,
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
        return list_runs(status=status, limit=limit)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/runs/{run_id}")
async def get_run_endpoint(run_id: str):
    try:
        return get_run(run_id)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/runs/{run_id}/continue")
async def continue_run_endpoint(run_id: str):
    """Release a gated run past its current stage boundary. 409 if not paused."""
    try:
        return continue_run(run_id)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/runs/{run_id}/abort")
async def abort_run_endpoint(run_id: str):
    """Abort a running or gated run. 409 if the run is already terminal."""
    try:
        return abort_run(run_id)
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
        return retry_run(run_id, from_stage=from_stage)
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
            return parse_dryrun(file_bytes=file_bytes, filename=upload.filename)

        body_bytes = await request.body()
        try:
            body = json.loads(body_bytes) if body_bytes else {}
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="dry-run body is not valid JSON") from None
        sha256 = body.get("sha256") if isinstance(body, dict) else None
        if not sha256:
            raise HTTPException(status_code=400, detail="sha256 is required in the JSON body")
        return parse_dryrun(sha256=sha256)
    except RunsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
