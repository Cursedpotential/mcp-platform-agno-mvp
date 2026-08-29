"""Framework-neutral HTTP ingest and canonical knowledge-read routes.

Byline: Codex · GPT-5 · 2026-08-16
Byline amendment: Codex · GPT-5 · 2026-08-18 (third-party acquisition input)
"""

from __future__ import annotations

import asyncio
import json
import secrets
from os import getenv
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from pydantic import ValidationError

from server.api.uploads import safe_upload_name
from server.contracts.ingest import IngestLane, IngestRequest
from server.ingest.service import IngestError, PostgresReceiptJournal, ingest_file

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
_INGEST_TASKS: set[asyncio.Task[None]] = set()


def _authorize(request: Request) -> None:
    expected = getenv("OS_SECURITY_KEY", "")
    if not expected:
        raise HTTPException(503, "ingest authorization is not configured")
    scheme, separator, credential = request.headers.get("authorization", "").partition(" ")
    valid = bool(
        separator
        and scheme.lower() == "bearer"
        and credential
        and secrets.compare_digest(credential.encode("utf-8"), expected.encode("utf-8"))
    )
    if not valid:
        raise HTTPException(401, "authentication required", headers={"WWW-Authenticate": "Bearer"})


def _staging_root() -> Path:
    root = Path(getenv("INGEST_STAGING_ROOT", "/tmp/horizon-ingest-staging")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


async def _stage_upload(upload: Any) -> Path:
    root = _staging_root()
    destination = root / f"{uuid4()}-{safe_upload_name(getattr(upload, 'filename', None))}"
    written = 0
    with destination.open("xb") as stream:
        while chunk := await upload.read(1024 * 1024):
            written += len(chunk)
            stream.write(chunk)
            if written > _MAX_UPLOAD_BYTES:
                rejected = destination.with_suffix(destination.suffix + ".rejected-too-large")
                destination.replace(rejected)
                raise HTTPException(413, f"upload exceeds {_MAX_UPLOAD_BYTES} bytes; staged copy retained as rejected")
    return destination


def _json_object(raw: Any, field: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError):
        raise HTTPException(422, f"{field} must be valid JSON") from None
    if not isinstance(value, dict):
        raise HTTPException(422, f"{field} must be a JSON object")
    return value


def _receipt_response(receipt) -> dict[str, Any]:
    return {
        "run_id": receipt.receipt_id,
        "workflow": "framework-neutral-ingest",
        "mode": "auto",
        "receipt": receipt.model_dump(mode="json"),
    }


async def _run_reserved_ingest(
    payload: IngestRequest,
    journal: PostgresReceiptJournal,
    receipt_id: str,
    projector: Any | None = None,
) -> None:
    try:
        await asyncio.to_thread(ingest_file, payload, journal=journal, receipt_id=receipt_id, projector=projector)
    except IngestError:
        # ingest_file already persisted the failed receipt.
        return


async def _submit_ingest(payload: IngestRequest, projector: Any | None = None) -> str:
    journal = PostgresReceiptJournal()
    path = Path(payload.staged_path).resolve(strict=True)
    receipt_id = await asyncio.to_thread(journal.start, payload, path)
    worker = (
        _run_reserved_ingest(payload, journal, receipt_id)
        if projector is None
        else _run_reserved_ingest(payload, journal, receipt_id, projector)
    )
    task = asyncio.create_task(worker)
    _INGEST_TASKS.add(task)
    task.add_done_callback(_INGEST_TASKS.discard)
    return receipt_id


def register_ingest_routes(app: FastAPI, native_projector: Any | None = None) -> None:
    @app.post("/v1/ingest", status_code=202)
    async def ingest_upload(request: Request) -> dict[str, Any]:
        _authorize(request)
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(400, "file is required")
        staged_path = await _stage_upload(upload)
        source_identity = _json_object(form.get("source_identity"), "source_identity")
        source_identity.setdefault("original_name", safe_upload_name(getattr(upload, "filename", None)))
        acquisition = _json_object(form.get("acquisition"), "acquisition") if form.get("acquisition") else None
        if acquisition is not None:
            acquisition["asserted_by"] = "owner"
            acquisition["asserted_by_category"] = "human"
        try:
            payload = IngestRequest(
                staged_path=str(staged_path),
                source_identity=source_identity,
                message_corpus=form.get("message_corpus") or None,
                source_principal=form.get("source_principal") or None,
                caller_owns_conversation=str(form.get("caller_owns_conversation") or "false").lower()
                in {"1", "true", "yes"},
                acquisition=acquisition,
                coverage_hint=form.get("coverage_hint") or None,
                lane=str(form.get("lane") or "context"),
                matter_id=str(form.get("matter_id") or "primary"),
                engine=str(form.get("engine") or "auto"),
                allow_fallback=str(form.get("allow_fallback") or "false").lower() in {"1", "true", "yes"},
                custody_tier=str(form.get("custody_tier") or "light"),
            )
        except ValidationError as error:
            raise HTTPException(422, json.loads(error.json())) from None
        try:
            receipt_id = (
                await _submit_ingest(payload)
                if native_projector is None
                else await _submit_ingest(payload, native_projector)
            )
        except Exception as error:
            raise HTTPException(503, f"cannot reserve ingest receipt: {error}") from None
        return {
            "run_id": receipt_id,
            "workflow": "framework-neutral-ingest",
            "mode": "auto",
            "status": "running",
        }

    @app.post("/v1/ingest/path", status_code=201)
    async def ingest_staged_path(payload: IngestRequest, request: Request) -> dict[str, Any]:
        _authorize(request)
        if payload.acquisition is not None:
            payload = payload.model_copy(
                update={
                    "acquisition": payload.acquisition.model_copy(
                        update={"asserted_by": "owner", "asserted_by_category": "human"}
                    )
                }
            )
        try:
            receipt = await asyncio.to_thread(ingest_file, payload, projector=native_projector)
        except (FileNotFoundError, IngestError) as error:
            detail = (
                {"message": str(error), "receipt": error.receipt.model_dump(mode="json")}
                if isinstance(error, IngestError)
                else str(error)
            )
            raise HTTPException(422, detail) from None
        return _receipt_response(receipt)

    @app.get("/v1/knowledge/items")
    async def knowledge_items(
        request: Request, matter_id: str = "primary", lane: IngestLane | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        _authorize(request)
        if not 1 <= limit <= 500:
            raise HTTPException(422, "limit must be between 1 and 500")
        from server.ingest.query import list_items

        return await asyncio.to_thread(list_items, matter_id=matter_id, lane=lane, limit=limit)

    @app.get("/v1/knowledge/items/{artifact_id}")
    async def knowledge_item(artifact_id: str, request: Request, matter_id: str = "primary") -> dict[str, Any]:
        _authorize(request)
        from server.ingest.query import get_item

        item = await asyncio.to_thread(get_item, artifact_id, matter_id=matter_id)
        if item is None:
            raise HTTPException(404, "knowledge item not found")
        return item
