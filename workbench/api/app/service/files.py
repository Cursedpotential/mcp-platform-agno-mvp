# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Staged-file service — list/detail/edit-metadata over the LanceDB staging table.

Rewired from the donor kit's files.py, which listed raw B2 objects. Here the
`staged_files` table (repo/staging.py) is the single source of truth for
what's queued for promotion; this module never talks to the object store
directly.
"""

from __future__ import annotations

from app.repo import staging
from app.service.metadata import build_display_metadata
from app.types.files import ALLOWED_DOMAINS

TEXT_PREVIEW_CHARS = 2000


class StagedFileNotFoundError(Exception):
    """Raised when a staged file id does not exist."""

    def __init__(self, detail: str = "Staged file not found"):
        self.detail = detail
        super().__init__(detail)


class StagedFileValidationError(Exception):
    """Raised when a metadata edit fails validation."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def list_staged(
    status: str | None = None,
    detected_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """List staged files, stripping the full text body (list view is a summary)."""
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    records = staging.list(status=status, detected_type=detected_type, limit=limit, offset=offset)
    for r in records:
        r.pop("text", None)
    return records


def get_staged_detail(file_id: str) -> dict:
    """Return a staged file record with a truncated text preview + display metadata."""
    record = staging.get(file_id)
    if record is None:
        raise StagedFileNotFoundError()
    text = record.get("text") or ""
    record["text"] = text[:TEXT_PREVIEW_CHARS]
    record["text_truncated"] = len(text) > TEXT_PREVIEW_CHARS
    record["display"] = build_display_metadata(record["name"], record["size"], record["mime"])
    return record


def update_metadata(file_id: str, updates: dict) -> dict:
    """Patch a staged file's classification metadata.

    `updates` must only contain keys the caller explicitly set — pass
    `FilePatchRequest.model_dump(exclude_unset=True)` from the runtime layer
    — so that "field omitted" (leave alone) and "field set to null"
    (explicitly clear) are distinguishable. Recognized keys: domain,
    category, source_platform (-> record.meta), detected_type
    (-> record.detected_type).
    """
    record = staging.get(file_id)
    if record is None:
        raise StagedFileNotFoundError()

    meta = dict(record.get("meta") or {})
    if "domain" in updates:
        domain = updates["domain"]
        if domain is not None and domain not in ALLOWED_DOMAINS:
            raise StagedFileValidationError(f"domain must be one of {sorted(ALLOWED_DOMAINS)}")
        meta["domain"] = domain
    if "category" in updates:
        meta["category"] = updates["category"]
    if "source_platform" in updates:
        meta["source_platform"] = updates["source_platform"]
    record["meta"] = meta

    if "detected_type" in updates:
        detected_type = updates["detected_type"]
        if detected_type not in ("doc", "chat_export"):
            raise StagedFileValidationError("detected_type must be 'doc' or 'chat_export'")
        record["detected_type"] = detected_type

    return staging.upsert_staged(record)
