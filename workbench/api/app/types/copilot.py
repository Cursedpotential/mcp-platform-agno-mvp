# Byline: Claude Code · Sonnet (agent) · 2026-07-21
"""Request shapes for the Ops Copilot endpoints (POST /api/copilot/ask, /continue).

Response bodies (reply/session_id/model, provider->model listings, presets,
health) are plain passthrough dicts from app.service.copilot[_presets] — not
modeled here, matching this app's existing convention for open-ended/
passthrough JSON (see app/types/tools.py).
"""

from __future__ import annotations

from pydantic import BaseModel


class CopilotContext(BaseModel):
    """Optional console context attached to a copilot question. All fields
    optional; a run/file id that doesn't resolve degrades to an inline note
    in the preamble rather than a request error (see app/service/copilot.py)."""

    page: str | None = None
    run_id: str | None = None
    file_id: str | None = None


class CopilotAskRequest(BaseModel):
    """POST /api/copilot/ask body — starts a NEW copilot session."""

    prompt: str
    model: str | None = None
    context: CopilotContext | None = None


class CopilotContinueRequest(BaseModel):
    """POST /api/copilot/continue body — continues an existing session."""

    session_id: str
    prompt: str
    model: str | None = None
