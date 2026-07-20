"""server/api/run_routes.py — REST surface for the C0/C2 operator-console run ledger.

Modeled on server/api/evidence_routes.py's multipart pattern (same base_app
registration convention as register_knowledge_routes / register_evidence_routes
— see server/api/main.py), but "fire-and-watch" instead of request/response:

  POST /v1/runs                   — save the upload, seed the run + its stage
                                     rows, kick the workflow off in the
                                     background, return 202 {run_id, workflow,
                                     mode} immediately.
  GET  /v1/runs                   — list recent runs (+ per-stage pairs).
  GET  /v1/runs/{run_id}          — full run detail (run row + ordered stages).
  POST /v1/runs/{run_id}/continue — release a supervised-mode gate (C2).
  POST /v1/runs/{run_id}/abort    — abort a paused or running run (C2).
  POST /v1/runs/{run_id}/retry    — re-run a terminal-failed run from its
                                     original custody blob, linked via
                                     parent_run_id (C2).

The caller polls GET /v1/runs/{run_id} to watch analysis.workflow_run_stage
rows fill in as server/evidence/workflows.py executes (server/evidence/
run_ledger.py is the write side; this module never touches the DB directly).

C2 supervised gates (server/evidence/workflows.py's
`_wrap_step_for_run_control`): when mode="supervised", the run pauses after
every non-final stage and waits on POST .../continue or .../abort. The
run's own background asyncio task (`_execute_run` below, still alive for as
long as the process is) is the ONLY thing that ever calls finish_run() —
these control endpoints only flip analysis.workflow_run.gate_state (and, for
/continue and a /abort-while-paused, also flip status directly so the HTTP
response is truthful immediately); single-writer discipline for run
termination is preserved exactly the way custody.py is the sole writer of
the evidence schema.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-07-20 (C2: gates + retry + custody_tier added)

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile

from server.evidence.custody import blob_root
from server.evidence.run_ledger import create_run, get_run, list_runs, seed_stages, set_gate

_ALLOWED_DOMAINS = {
    "timeline_relationship",
    "personal_history",
    "platform_design",
    "legal_strategy",
}
_ALLOWED_WORKFLOWS = {"chat-transcript", "sms-xml"}
_ALLOWED_MODES = {"auto", "supervised"}
_ALLOWED_CUSTODY_TIERS = {"full", "light"}

_DEFAULT_DOMAIN: dict[str, str] = {
    "chat-transcript": "platform_design",
    "sms-xml": "timeline_relationship",
}

# Two-tier custody (operator-console-requirements.md addendum 2): the
# knowledge-lane AI-chat vertical defaults to 'light' (whole-file sha256 +
# blob + dedupe only — this is the owner's STORY, not evidence); the
# evidence vertical (sms-xml) keeps the historical 'full' default.
_DEFAULT_CUSTODY_TIER: dict[str, str] = {
    "chat-transcript": "light",
    "sms-xml": "full",
}

_TERMINAL_STATUSES = {"completed", "failed"}


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
        mode: str = "auto",
        custody_tier: str = "full",
    ) -> None:
        """Background task body: run the workflow with the ledger wired in,
        then clean up the private temp dir regardless of outcome. The runner's
        own finally-block (workflows.py) calls finish_run — this task doesn't
        need to (and must not swallow/re-report status; the ledger IS the
        result surface for a fire-and-watch run).

        This same task is what stays alive to service a supervised-mode run's
        gate poll loop (server/evidence/workflows.py's
        `_wrap_step_for_run_control`) — POST .../continue and .../abort below
        only flip analysis.workflow_run.gate_state; THIS coroutine is what
        actually observes it and resumes/halts the workflow."""
        from server.evidence.workflows import run_chat_transcript, run_sms_xml

        runner = run_chat_transcript if workflow == "chat-transcript" else run_sms_xml
        try:
            await runner(
                str(tmp_path),
                source_meta=meta,
                domain=domain,
                knowledge=knowledge,
                run_id=run_id,
                mode=mode,
                custody_tier=custody_tier,
            )
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
        custody_tier: str | None = Form(None),
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
        # Two-tier custody (addendum 2): 'light' for chat-transcript, 'full'
        # for sms-xml, unless the caller explicitly overrides.
        resolved_tier = custody_tier or _DEFAULT_CUSTODY_TIER[workflow]
        if resolved_tier not in _ALLOWED_CUSTODY_TIERS:
            raise HTTPException(422, f"unknown custody_tier {resolved_tier!r}; allowed: {sorted(_ALLOWED_CUSTODY_TIERS)}")
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
            mode=mode,
            source_name=file.filename,
            source_path=str(tmp_path),
            domain=resolved_domain,
            custody_tier=resolved_tier,
        )
        seed_stages(run_id, WORKFLOW_STAGE_NAMES[workflow])

        asyncio.create_task(
            _execute_run(run_id, workflow, tmp_path, tmpdir, meta, resolved_domain, mode=mode, custody_tier=resolved_tier)
        )

        return {"run_id": run_id, "workflow": workflow, "mode": mode}

    @app.get("/v1/runs")
    async def get_runs(
        status: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        """List recent runs (most recent first), each with its per-stage
        name/status pairs. Each run dict now also carries gate_state,
        parent_run_id, and custody_tier (C2)."""
        return list_runs(limit=limit, status=status)

    @app.get("/v1/runs/{run_id}")
    async def get_run_detail(run_id: str) -> dict[str, Any]:
        """Full run detail: the run row + its ordered stages (typed output
        included), or 404 if run_id is unknown. Now also carries gate_state,
        parent_run_id, and custody_tier (C2)."""
        run = get_run(run_id)
        if run is None:
            raise HTTPException(404, f"run {run_id!r} not found")
        return run

    @app.post("/v1/runs/{run_id}/continue")
    async def continue_run(run_id: str) -> dict[str, Any]:
        """Release a supervised-mode gate: 200 {run_id, status:'running'}.

        409 if the run is not currently paused (nothing to release) — includes
        runs that were never gated (mode='auto') and terminal runs."""
        run = get_run(run_id)
        if run is None:
            raise HTTPException(404, f"run {run_id!r} not found")
        if run["status"] != "paused":
            raise HTTPException(409, f"run {run_id!r} is {run['status']!r}, not paused — nothing to continue")
        # Write BOTH columns now so the response is truthful the instant it
        # returns; the run's own background poll loop (workflows.py's
        # `_wrap_step_for_run_control`) will independently notice
        # gate_state='released' within ~2s and clear it back to None as it
        # resumes — a harmless, idempotent second write.
        set_gate(run_id, "released", status="running")
        return {"run_id": run_id, "status": "running"}

    @app.post("/v1/runs/{run_id}/abort")
    async def abort_run(run_id: str) -> dict[str, Any]:
        """Abort a paused or running run: 200 {run_id, status:'failed'}.

        409 on a terminal run (completed/failed already — nothing to abort).

        LIMITATION (by design, matches the C2 task spec): this endpoint only
        ever sets gate_state='abort' — it never calls finish_run itself. For
        a PAUSED run, the run's own background gate-poll loop is already
        awake roughly every 2s and will observe the flag almost immediately.
        For a RUNNING run, the abort is honored at "the next gate/stage
        boundary" (server/evidence/workflows.py's
        `_wrap_step_for_run_control`) — i.e. once the in-flight stage's
        executor returns, NOT preemptively mid-stage. If that run is in
        'auto' mode and its currently-executing stage happens to be the
        workflow's LAST stage, the abort can still race a run that finishes
        on its own in the meantime (the abort flag would then sit unused on
        an already-terminal row). The 200 response below reports the
        *intended* outcome of this call, not a synchronously-verified one —
        poll GET /v1/runs/{run_id} to observe the actual terminal state."""
        run = get_run(run_id)
        if run is None:
            raise HTTPException(404, f"run {run_id!r} not found")
        status = run["status"]
        if status in _TERMINAL_STATUSES:
            raise HTTPException(409, f"run {run_id!r} is {status!r} (terminal) — cannot abort")
        set_gate(run_id, "abort")
        return {"run_id": run_id, "status": "failed"}

    @app.post("/v1/runs/{run_id}/retry", status_code=202)
    async def retry_run(run_id: str) -> dict[str, Any]:
        """Re-run a terminal-failed run from its ORIGINAL custody blob.

        409 if the parent run is not status='failed'. 410 Gone if neither the
        custody blob (preferred) nor the original source_path (fallback) is
        still readable — see the docstring below for which path this ships.

        Returns 202 {"run_id": <NEW run_id>, "parent_run_id": <this run_id>}
        — poll the new run_id like any other fire-and-watch run.
        """
        run = get_run(run_id)
        if run is None:
            raise HTTPException(404, f"run {run_id!r} not found")
        if run["status"] != "failed":
            raise HTTPException(
                409, f"run {run_id!r} is {run['status']!r}, not failed — retry only allowed on a terminal-failed run"
            )

        workflow = run["workflow"]
        domain = run["domain"]
        mode = run["mode"]
        custody_tier = run.get("custody_tier") or _DEFAULT_CUSTODY_TIER.get(workflow, "full")

        # PREFERRED path: read the pristine write-once blob back the same way
        # custody.py's ingest_artifact() wrote it (blob_root() / blob_key) —
        # the custody stage's typed output (analysis.workflow_run_stage.output,
        # server/evidence/workflows.py's `_ledger_stage_output`) carries
        # blob_key for exactly this reason. FALLBACK (only if the blob isn't
        # there): the original upload's source_path, if that private temp
        # file still happens to exist (it's normally deleted by
        # `_execute_run`'s finally-block right after the parent run finishes,
        # so this fallback will rarely succeed in practice — it exists per
        # the task spec as a documented, less-preferred second attempt before
        # giving up with 410).
        custody_stage = next((s for s in run["stages"] if s["name"] == "custody"), None)
        blob_key = (custody_stage or {}).get("output", {}).get("blob_key") if custody_stage else None
        original_name = Path(run.get("source_name") or "retry-upload.bin").name

        tmpdir = Path(tempfile.mkdtemp(prefix="run-retry-"))
        tmp_path = tmpdir / original_name
        source_used: str | None = None

        if blob_key:
            blob_path = blob_root() / blob_key
            if blob_path.is_file():
                shutil.copyfile(blob_path, tmp_path)
                source_used = "blob"

        if source_used is None and run.get("source_path"):
            legacy_path = Path(run["source_path"])
            if legacy_path.is_file():
                shutil.copyfile(legacy_path, tmp_path)
                source_used = "source_path"

        if source_used is None:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise HTTPException(
                410,
                f"run {run_id!r}: neither the custody blob ({blob_key!r}) nor the original "
                f"source_path ({run.get('source_path')!r}) is still readable — cannot retry",
            )

        from server.evidence.workflows import WORKFLOW_STAGE_NAMES

        new_run_id = create_run(
            workflow=workflow,
            mode=mode,
            source_name=run.get("source_name"),
            source_path=str(tmp_path),
            domain=domain,
            parent_run_id=run_id,
            custody_tier=custody_tier,
        )
        seed_stages(new_run_id, WORKFLOW_STAGE_NAMES[workflow])

        # source_meta isn't persisted anywhere in the ledger schema (only the
        # derived custody/parse outputs are) — a retried run's source_meta is
        # always {} (documented deviation; workflow/domain/mode/custody_tier
        # and the original bytes are all faithfully re-used).
        asyncio.create_task(
            _execute_run(new_run_id, workflow, tmp_path, tmpdir, {}, domain, mode=mode, custody_tier=custody_tier)
        )

        return {"run_id": new_run_id, "parent_run_id": run_id}
