# Byline: Claude Code · Sonnet (agent) · 2026-07-20 (custody_tier added — C2 gate controls)
# Byline: Codex · GPT-5 · 2026-08-13 (review action request)
"""Request shape for the JSON branch of POST /api/runs.

The multipart branch (a fresh file drop) is parsed by hand in
runtime/runs.py from the raw `Request.form()` — FastAPI can't cleanly bind
one endpoint to either a pydantic JSON body OR multipart Form/File params
based on the runtime content-type, so only the JSON shape gets a model here.

Response bodies (run/stage records from the spine) are NOT modeled — they're
passthrough JSON from a parallel-built service (see workbench/api/app/
service/runs.py module docstring for the assumed contract); pydantic
response_model would fight that open-ended, still-settling shape rather than
help.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class RunCreateRequest(BaseModel):
    """POST /api/runs JSON body — starts a run from an already-staged file."""

    staged_id: str
    workflow: str
    domain: str | None = None
    mode: str = "auto"
    source_meta: dict | None = None
    # C2 spine contract (console/c2-spine, parallel branch): the spine
    # defaults this per-workflow (chat-transcript -> light, sms-xml -> full)
    # when omitted, so it stays optional here too.
    custody_tier: str | None = None


class RunReviewActionRequest(BaseModel):
    """Append a human decision without replacing the recorded outcome."""

    model_config = ConfigDict(extra="forbid")

    action_type: Literal["acknowledge", "approve", "override"]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    stage_seq: int | None = Field(default=None, ge=1)
    replacement: dict | None = None
