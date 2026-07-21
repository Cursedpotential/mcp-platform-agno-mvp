# Byline: Claude Code · Sonnet (agent) · 2026-07-21 (C2.7: get_staged_text + analyze_file added)
"""Staged-file service — list/detail/edit-metadata over the LanceDB staging table.

Rewired from the donor kit's files.py, which listed raw B2 objects. Here the
`staged_files` table (repo/staging.py) is the single source of truth for
what's queued for promotion; this module never talks to the object store
directly.
"""

from __future__ import annotations

import json

from app.repo import staging
from app.service import detect
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


def get_staged_text(file_id: str) -> dict:
    """Full, untruncated extracted text for the Preview modal (C2.7 owner
    scope addition). Unlike get_staged_detail() (capped at
    TEXT_PREVIEW_CHARS for the summary/detail views), this always returns
    the complete text field already sitting in the staging row — no re-fetch
    from the object store, no re-parse."""
    record = staging.get(file_id)
    if record is None:
        raise StagedFileNotFoundError()
    text = record.get("text") or ""
    return {"id": file_id, "text": text, "length": len(text)}


def analyze_file(file_id: str) -> dict:
    """Re-run detect.py's sniffing over a staged file and report basic shape
    stats (C2.7 owner scope addition) — lightweight and in-process only:
    no R2/object-store re-fetch, and deliberately does NOT invoke any spine
    parser (a true dry-run parse is a future spine-side feature; see the
    C2.7 build report for that recommendation).
    """
    record = staging.get(file_id)
    if record is None:
        raise StagedFileNotFoundError()
    text = record.get("text") or ""
    detected_type, evidence = detect.detect_type_with_evidence(record["name"], text)

    is_json_parseable = False
    if text:
        try:
            json.loads(text)
            is_json_parseable = True
        except (json.JSONDecodeError, ValueError):
            is_json_parseable = False

    return {
        "id": file_id,
        "detected_type": detected_type,
        "current_detected_type": record.get("detected_type"),
        "evidence": evidence,
        "shape": {
            "size": record.get("size"),
            "mime": record.get("mime"),
            "text_length": len(text),
            "line_count": (text.count("\n") + 1) if text else 0,
            "is_json_parseable": is_json_parseable,
            "has_text": bool(text.strip()),
        },
    }


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
