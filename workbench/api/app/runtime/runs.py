# Byline: Claude Code · Sonnet (agent) · 2026-07-20
"""POST /api/runs, GET /api/runs, GET /api/runs/{id} — proxy to the spine's run pipeline.

POST /api/runs accepts EITHER a JSON body ({staged_id, workflow, domain,
mode, source_meta}) OR a multipart body (file, workflow, domain, mode,
source_meta as a json string) — the New-run dialog uses JSON when the
operator picked an already-staged file, multipart when they dropped a fresh
one. FastAPI can't bind one endpoint signature to both shapes based on
runtime content-type, so this handler reads the raw `Request` and branches
on `Content-Type` itself, then hands a validated/normalized call down to
service/runs.py either way.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from app.service.runs import RunsError, get_run, list_runs, start_run
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
