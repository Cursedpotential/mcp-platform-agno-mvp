"""server/api/evidence_routes.py — REST exposure for the evidence workflows.

The chat-transcript vertical (custody → parse → normalize → store → knowledge)
previously had CLI-only access (``server/evidence/cli.py``). This registers a
thin multipart endpoint on the base app so GUI surfaces (Knowledge Workbench)
can drive the spine without shelling into the container.

Registered on the base FastAPI app BEFORE AgentOS wraps it (base_app pattern,
same as ``register_knowledge_routes`` — see ``server/api/main.py``).

NOTE (2026-07-20): ported verbatim from `main` (commit 0a5b917) onto
`workbench/sprint`, which branched before that commit landed — this branch
had no REST evidence-import route at all until now. Content unchanged from
main; only its presence on this branch is new. See the C0 run-ledger task
report for the full explanation.

D-082 (2026-08-26): the chat-transcript workflow IS the AI-chat vertical by
definition, and it is currently the ONLY workflow this route accepts — so
POST /v1/evidence/import now permanently denies every request (see
_DENIED_WORKFLOWS below) rather than reaching custody. AI-chat exports are
context-only forever; GAP-032/WP-C01.
"""
# Byline: Claude Code · Fable 5 · 2026-07-19 (C3 KnowledgeHandle live-resolve 2026-07-22 — Claude Code · Sonnet (agent))
# Byline: Codex · GPT-5 · 2026-08-13 (ADR-0053 five-lane alignment)
# Byline: Claude Code · Sonnet 5 · 2026-08-26 (D-082 permanent AI-chat evidence fence, GAP-032/WP-C01)

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from server.core.knowledge_handle import resolve_knowledge
from server.api.uploads import safe_upload_name

# ADR-0053 five-lane knowledge domains. MUST stay aligned with
# server.evidence.store.KNOWLEDLEDGE_DOMAINS — the store is the authority and
# raises ValueError on any domain it doesn't recognize (store.py:448). This set
# was stale (timeline_relationship/platform_design/legal_strategy — a different
# vocabulary than the store's canonical lane names) AND omitted
# `context`, so the route's own `context` default 422'd and every accepted
# domain the store then rejected with a 500 on a real ingest (2026-08-12).
# Relationship history is now part of personal_history. AI chat never routes
# directly to evidence; this route keeps evidence for custody-approved imports.
_ALLOWED_DOMAINS = {
    "platform",
    "legal",
    "personal_history",
    "context",
    "evidence",
}

_ALLOWED_WORKFLOWS = {"chat-transcript"}

# D-082 permanent AI-chat evidence fence (GAP-032/WP-C01, owner-ruled
# 2026-08-26 — docs/DECISION_LOG.md). AI-chat exports are permanently
# context-only and can never be promoted to evidence custody. "chat-transcript"
# IS the AI-chat workflow by definition (server/evidence/workflows.py's
# chat-transcript vertical); today it is also the ONLY workflow this route
# accepts, so this route currently has no allowed outcome other than denial.
# If a future non-AI-chat workflow is ever added to _ALLOWED_WORKFLOWS, it
# must NOT be added here. server/evidence/custody.py::ingest_artifact()
# independently denies the same marker (defense in depth) if this check is
# ever bypassed or this route is ever reordered.
_DENIED_WORKFLOWS = {
    "chat-transcript": (
        "AI-chat exports are permanently context-only under D-082 and can never be promoted to "
        "evidence custody (GAP-032/WP-C01). Extraction of candidate events/claims/leads happens "
        "through the context-ingest lane, not this endpoint."
    ),
}


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
        domain: str = Form("context"),  # ADR-0050: AI chats = context lane (was platform_design)
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
        if workflow in _DENIED_WORKFLOWS:
            # Fail closed before touching the upload body, domain, source_meta,
            # or run_chat_transcript/custody at all — zero I/O for a denied call.
            raise HTTPException(
                403,
                {"denied": True, "workflow": workflow, "reason": _DENIED_WORKFLOWS[workflow]},
            )
        if domain not in _ALLOWED_DOMAINS:
            raise HTTPException(422, f"unknown domain {domain!r}; allowed: {sorted(_ALLOWED_DOMAINS)}")
        try:
            meta = json.loads(source_meta) if source_meta else {}
        except json.JSONDecodeError as exc:
            raise HTTPException(422, f"source_meta is not valid JSON: {exc}") from exc

        from server.evidence.workflows import run_chat_transcript

        # Preserve the original filename (parsers sniff extensions) inside a
        # private temp dir; custody re-persists the blob durably to R2.
        suffix_name = safe_upload_name(file.filename)
        with tempfile.TemporaryDirectory(prefix="evidence-import-") as tmpdir:
            tmp_path = Path(tmpdir) / suffix_name
            tmp_path.write_bytes(await file.read())
            return await run_chat_transcript(
                str(tmp_path), source_meta=meta, domain=domain, knowledge=resolve_knowledge(knowledge)
            )
