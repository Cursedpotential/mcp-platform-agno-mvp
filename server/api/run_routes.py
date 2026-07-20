"""server/api/run_routes.py — REST surface for the C0 operator-console run ledger.

Modeled on server/api/evidence_routes.py's multipart pattern (same base_app
registration convention as register_knowledge_routes / register_evidence_routes
— see server/api/main.py), but "fire-and-watch" instead of request/response:

  POST /v1/runs          — save the upload, seed the run + its stage rows,
                            kick the workflow off in the background, return
                            202 {run_id, workflow, mode} immediately.
  GET  /v1/runs          — list recent runs (+ per-stage name/status pairs).
  GET  /v1/runs/{run_id} — full run detail (run row + ordered stages).

The caller polls GET /v1/runs/{run_id} to watch analysis.workflow_run_stage
rows fill in as server/evidence/workflows.py executes (server/evidence/
run_ledger.py is the write side; this module never touches the DB directly).

`mode="supervised"` is accepted but behaves identically to "auto" for now —
the actual HITL gating lands in C2; see docs/planning/operator-console (or
the C0 task report) for the phase breakdown.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-07-20

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile

from server.evidence.run_ledger import create_run, get_run, list_runs, seed_stages

_ALLOWED_DOMAINS = {
    "timeline_relationship",
    "personal_history",
    "platform_design",
    "legal_strategy",
}
_ALLOWED_WORKFLOWS = {"chat-transcript", "sms-xml"}
_ALLOWED_MODES = {"auto", "supervised"}

_DEFAULT_DOMAIN: dict[str, str] = {
    "chat-transcript": "platform_design",
    "sms-xml": "timeline_relationship",
}


def register_run_routes(app: FastAPI, knowledge: Any) -> None:
    """Register the C0 run-ledger REST surface on the FastAPI app.

    Parameters
    ----------
    app:
        The FastAPI application instance (base app, pre-AgentOS wrap).
    knowledge:
        Agno Knowledge instance handed through to the workflow's knowledge step
        (same handle register_evidence_routes uses).
    """

    async def _execute_run(
        run_id: str,
        workflow: str,
        tmp_path: Path,
        tmpdir: Path,
        meta: dict[str, Any],
        domain: str,
    ) -> None:
        """Background task body: run the workflow with the ledger wired in,
        then clean up the private temp dir regardless of outcome. The runner's
        own finally-block (workflows.py) calls finish_run — this task doesn't
        need to (and must not swallow/re-report status; the ledger IS the
        result surface for a fire-and-watch run)."""
        from server.evidence.workflows import run_chat_transcript, run_sms_xml

        runner = run_chat_transcript if workflow == "chat-transcript" else run_sms_xml
        try:
            await runner(str(tmp_path), source_meta=meta, domain=domain, knowledge=knowledge, run_id=run_id)
        except Exception:
            # workflows.py's own finally-block already recorded this failure
            # into the ledger (finish_run(status='failed', error=...)); this
            # background task has no caller left to raise to, so just stop
            # the exception from becoming an unhandled-task-exception log spam.
            pass
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @app.post("/v1/runs", status_code=202)
    async def start_run(
        file: UploadFile = File(...),
        workflow: str = Form("chat-transcript"),
        domain: str | None = Form(None),
        mode: str = Form("auto"),
        source_meta: str = Form("{}"),
    ) -> dict[str, Any]:
        """Start a workflow run in the background; return its run_id immediately.

        Returns
        -------
        dict
            ``{"run_id": ..., "workflow": ..., "mode": ...}`` — poll
            GET /v1/runs/{run_id} for progress.
        """
        if workflow not in _ALLOWED_WORKFLOWS:
            raise HTTPException(422, f"unknown workflow {workflow!r}; allowed: {sorted(_ALLOWED_WORKFLOWS)}")
        if mode not in _ALLOWED_MODES:
            raise HTTPException(422, f"unknown mode {mode!r}; allowed: {sorted(_ALLOWED_MODES)}")
        resolved_domain = domain or _DEFAULT_DOMAIN[workflow]
        if resolved_domain not in _ALLOWED_DOMAINS:
            raise HTTPException(422, f"unknown domain {resolved_domain!r}; allowed: {sorted(_ALLOWED_DOMAINS)}")
        try:
            meta = json.loads(source_meta) if source_meta else {}
        except json.JSONDecodeError as exc:
            raise HTTPException(422, f"source_meta is not valid JSON: {exc}") from exc

        from server.evidence.workflows import WORKFLOW_STAGE_NAMES

        # Persist the upload to a private temp dir that OUTLIVES this request
        # (deliberately not `with TemporaryDirectory()` — the background task
        # reads it after we return 202, and removes it itself when done).
        tmpdir = Path(tempfile.mkdtemp(prefix="run-ledger-"))
        suffix_name = Path(file.filename or "upload.bin").name
        tmp_path = tmpdir / suffix_name
        tmp_path.write_bytes(await file.read())

        run_id = create_run(
            workflow=workflow,
            mode=mode,  # supervised behaves as auto for now — gates land in C2
            source_name=file.filename,
            source_path=str(tmp_path),
            domain=resolved_domain,
        )
        seed_stages(run_id, WORKFLOW_STAGE_NAMES[workflow])

        asyncio.create_task(_execute_run(run_id, workflow, tmp_path, tmpdir, meta, resolved_domain))

        return {"run_id": run_id, "workflow": workflow, "mode": mode}

    @app.get("/v1/runs")
    async def get_runs(
        status: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        """List recent runs (most recent first), each with its per-stage
        name/status pairs."""
        return list_runs(limit=limit, status=status)

    @app.get("/v1/runs/{run_id}")
    async def get_run_detail(run_id: str) -> dict[str, Any]:
        """Full run detail: the run row + its ordered stages (typed output
        included), or 404 if run_id is unknown."""
        run = get_run(run_id)
        if run is None:
            raise HTTPException(404, f"run {run_id!r} not found")
        return run
