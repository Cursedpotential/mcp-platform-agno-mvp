"""server/api/evidence_routes.py — REST exposure for the evidence workflows.

The chat-transcript vertical (custody → parse → normalize → store → knowledge)
previously had CLI-only access (``server/evidence/cli.py``). This registers a
thin multipart endpoint on the base app so GUI surfaces (Knowledge Workbench)
can drive the spine without shelling into the container.

Registered on the base FastAPI app BEFORE AgentOS wraps it (base_app pattern,
same as ``register_knowledge_routes`` — see ``server/api/main.py``).
"""
# Byline: Claude Code · Fable 5 · 2026-07-19

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

_ALLOWED_DOMAINS = {
    "timeline_relationship",
    "personal_history",
    "platform_design",
    "legal_strategy",
}

_ALLOWED_WORKFLOWS = {"chat-transcript"}


def register_evidence_routes(app: FastAPI, knowledge: Any) -> None:
    """Register evidence-workflow routes on the FastAPI app.

    Parameters
    ----------
    app:
        The FastAPI application instance (base app, pre-AgentOS wrap).
    knowledge:
        Agno Knowledge instance handed to the workflow's knowledge step.
    """

    @app.post("/v1/evidence/import")
    async def import_evidence(
        file: UploadFile = File(...),
        workflow: str = Form("chat-transcript"),
        domain: str = Form("platform_design"),
        source_meta: str = Form("{}"),
    ) -> dict[str, Any]:
        """Run an evidence workflow on an uploaded artifact; return its summary.

        Returns
        -------
        dict
            The workflow's verifiable summary — for chat-transcript:
            ``{workflow, status, artifact_id, sha256, duplicate, parser,
            parse_attempts, records_stored, step_log}``.
        """
        if workflow not in _ALLOWED_WORKFLOWS:
            raise HTTPException(422, f"unknown workflow {workflow!r}; allowed: {sorted(_ALLOWED_WORKFLOWS)}")
        if domain not in _ALLOWED_DOMAINS:
            raise HTTPException(422, f"unknown domain {domain!r}; allowed: {sorted(_ALLOWED_DOMAINS)}")
        try:
            meta = json.loads(source_meta) if source_meta else {}
        except json.JSONDecodeError as exc:
            raise HTTPException(422, f"source_meta is not valid JSON: {exc}") from exc

        from server.evidence.workflows import run_chat_transcript

        # Preserve the original filename (parsers sniff extensions) inside a
        # private temp dir; custody re-persists the blob durably to R2.
        suffix_name = Path(file.filename or "upload.bin").name
        with tempfile.TemporaryDirectory(prefix="evidence-import-") as tmpdir:
            tmp_path = Path(tmpdir) / suffix_name
            tmp_path.write_bytes(await file.read())
            return await run_chat_transcript(
                str(tmp_path), source_meta=meta, domain=domain, knowledge=knowledge
            )
