# Byline: Claude Code · Sonnet (agent) · 2026-07-21
"""Ops Copilot (C2.5) — ask()/continue_ask() over the OpenCode server, with
console-context injection.

New in the workbench. Builds a short preamble from console context (which
page the operator is on, an attached run, an attached staged file) and
forwards prompt+preamble to the headless OpenCode server via
app.repo.opencode_client. Run context reuses the EXISTING app.service.runs
module (never re-implements the spine call); file context reuses
app.repo.staging (the same staged_files store service/runs.py itself reads
for promote). Also backs GET /api/copilot/models (redact-by-construction —
see list_models()) and GET /api/copilot/health.
"""

from __future__ import annotations

import json
import logging

from app.config import settings
from app.repo import opencode_client, staging
from app.service.runs import RunsError, get_run

logger = logging.getLogger(__name__)

# Staged-file text preview cap for context injection — matches the build
# brief's "first 2KB text" instruction.
_FILE_TEXT_PREVIEW_CHARS = 2048


class CopilotError(Exception):
    """Raised when the copilot can't be reached, misconfigured, or a session can't be created."""

    def __init__(self, detail: str, status_code: int = 502):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _split_model(model: str | None) -> tuple[str, str]:
    raw = model or settings.opencode_model
    if "/" not in raw:
        raise CopilotError(f"model must be 'provider/model', got {raw!r}", 400)
    provider_id, model_id = raw.split("/", 1)
    return provider_id, model_id


def _run_digest(run_id: str) -> str:
    """Compact JSON digest of a run for context injection — id/workflow/
    status/domain/gate + per-stage seq/name/status/output, NOT full stage
    `content` (that can be large; the model gets the summary, the operator
    still sees the full run in the console)."""
    try:
        run = get_run(run_id)
    except RunsError as e:
        logger.warning("copilot: run context %s unavailable: %s", run_id, e.detail)
        return f"(run {run_id} context unavailable: {e.detail})"
    digest = {
        "run_id": run.get("run_id"),
        "workflow": run.get("workflow"),
        "mode": run.get("mode"),
        "status": run.get("status"),
        "domain": run.get("domain"),
        "gate_state": run.get("gate_state"),
        "error": run.get("error"),
        "stages": [
            {
                "seq": s.get("seq"),
                "name": s.get("name"),
                "status": s.get("status"),
                "output": s.get("output"),
            }
            for s in run.get("stages", [])
        ],
    }
    return json.dumps(digest, default=str)[:4000]


def _file_digest(file_id: str) -> str:
    record = staging.get(file_id)
    if record is None:
        logger.warning("copilot: file context %s not found", file_id)
        return f"(staged file {file_id} not found)"
    digest = {
        "id": record.get("id"),
        "name": record.get("name"),
        "mime": record.get("mime"),
        "detected_type": record.get("detected_type"),
        "meta": record.get("meta"),
        "text_preview": (record.get("text") or "")[:_FILE_TEXT_PREVIEW_CHARS],
    }
    return json.dumps(digest, default=str)[: _FILE_TEXT_PREVIEW_CHARS + 1000]


def build_preamble(context: dict | None) -> str:
    """Compose the context preamble prepended to the operator's prompt.

    `context` (all keys optional): {"page": "runs"|"intake"|"tools"|None,
    "run_id": str, "file_id": str}. Missing/unreachable context degrades to
    an inline note rather than failing the whole ask() call — same tolerant
    style as service/tools.py's per-server error entries.
    """
    if not context:
        return ""
    lines = ["You are the Ops Copilot embedded in the Knowledge Workbench operator console."]
    page = context.get("page")
    if page:
        lines.append(f"The operator is currently on the '{page}' page.")
    run_id = context.get("run_id")
    if run_id:
        lines.append(f"Attached run context (compact JSON digest):\n{_run_digest(run_id)}")
    file_id = context.get("file_id")
    if file_id:
        lines.append(
            f"Attached staged-file context (compact JSON digest, text truncated to "
            f"{_FILE_TEXT_PREVIEW_CHARS} chars):\n{_file_digest(file_id)}"
        )
    if len(lines) == 1:
        return ""
    return "\n\n".join(lines) + "\n\n---\n\n"


def _send(session_id: str, provider_id: str, model_id: str, prompt: str) -> dict:
    try:
        text, error = opencode_client.send_message(
            session_id, provider_id, model_id, prompt, directory=settings.opencode_workspace_dir
        )
    except opencode_client.OpenCodeError as e:
        raise CopilotError(e.detail, e.status_code) from e
    if error:
        text = f"[model error] {error}" if not text else text
    return {
        "reply": text or "(no text content in response)",
        "session_id": session_id,
        "model": f"{provider_id}/{model_id}",
    }


def ask(prompt: str, context: dict | None = None, model: str | None = None) -> dict:
    """Start a NEW copilot session, ask one question, return the reply.

    Returns {"reply", "session_id", "model"}. Raises CopilotError on
    transport failure or a bad model string; a model that runs but errors
    server-side surfaces that error IN the reply text instead (see
    app.repo.opencode_client.send_message).
    """
    provider_id, model_id = _split_model(model)
    try:
        session_id = opencode_client.create_session(directory=settings.opencode_workspace_dir)
    except opencode_client.OpenCodeError as e:
        raise CopilotError(e.detail, e.status_code) from e

    full_prompt = build_preamble(context) + prompt
    return _send(session_id, provider_id, model_id, full_prompt)


def continue_ask(session_id: str, prompt: str, model: str | None = None) -> dict:
    """Continue an existing copilot session — no context is re-injected
    (the session already carries it from the first turn)."""
    provider_id, model_id = _split_model(model)
    return _send(session_id, provider_id, model_id, prompt)


def list_models() -> list[dict]:
    """Connected providers -> model id lists, via GET /provider.

    Redacted BY CONSTRUCTION: only `id`/`name`/`models` keys are ever read
    off each provider dict below — the source `key` field (see
    app.repo.opencode_client module docstring) is never touched, so there is
    nothing to strip before returning this to the frontend.
    """
    try:
        doc = opencode_client.list_providers()
    except opencode_client.OpenCodeError as e:
        raise CopilotError(e.detail, e.status_code) from e
    connected = set(doc.get("connected", []))
    out = []
    for provider in doc.get("all", []):
        pid = provider.get("id")
        if pid not in connected:
            continue
        out.append(
            {
                "provider": pid,
                "label": provider.get("name", pid),
                "models": sorted(provider.get("models", {}).keys()),
            }
        )
    return out


def health() -> dict:
    """Probe the OpenCode server (auth'd) + report connected provider count.
    Never raises — degrades to reachable=False for a dead/misconfigured server."""
    reachable = opencode_client.check_liveness()
    connected = 0
    detail = None
    try:
        doc = opencode_client.list_providers()
        connected = len(doc.get("connected", []))
    except opencode_client.OpenCodeError as e:
        detail = e.detail
    return {"reachable": reachable, "connected_providers": connected, "detail": detail}
