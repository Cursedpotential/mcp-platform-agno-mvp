"""Framework-neutral Workbench context preamble construction.

The neutral chat gateway and the legacy Copilot adapter share this module so
neither needs to duplicate run/file context rules.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

import json
import logging

from app.repo import staging
from app.service.runs import RunsError, get_run

logger = logging.getLogger(__name__)

_FILE_TEXT_PREVIEW_CHARS = 2048


def _run_digest(run_id: str) -> str:
    """Return a compact run digest without large stage content."""
    try:
        run = get_run(run_id)
    except RunsError as error:
        logger.warning("chat context: run %s unavailable: %s", run_id, error.detail)
        return f"(run {run_id} context unavailable: {error.detail})"
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
                "seq": stage.get("seq"),
                "name": stage.get("name"),
                "status": stage.get("status"),
                "output": stage.get("output"),
            }
            for stage in run.get("stages", [])
        ],
    }
    return json.dumps(digest, default=str)[:4000]


def _file_digest(file_id: str) -> str:
    """Return bounded metadata and text preview for a staged file."""
    record = staging.get(file_id)
    if record is None:
        logger.warning("chat context: file %s not found", file_id)
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
    """Compose the optional operator-console context for a chat request."""
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
            "Attached staged-file context (compact JSON digest, text truncated to "
            f"{_FILE_TEXT_PREVIEW_CHARS} chars):\n{_file_digest(file_id)}"
        )
    if len(lines) == 1:
        return ""
    return "\n\n".join(lines) + "\n\n---\n\n"
