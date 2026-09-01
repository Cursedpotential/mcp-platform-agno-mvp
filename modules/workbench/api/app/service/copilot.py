# Byline: Claude Code · Sonnet (agent) · 2026-07-21
# Byline: Codex · GPT-5 · 2026-08-16 (share neutral context builder)
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

import logging

from app.config import settings
from app.repo import opencode_client
from app.service import chat_context

logger = logging.getLogger(__name__)

_FILE_TEXT_PREVIEW_CHARS = chat_context._FILE_TEXT_PREVIEW_CHARS
_run_digest = chat_context._run_digest
_file_digest = chat_context._file_digest
build_preamble = chat_context.build_preamble


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
