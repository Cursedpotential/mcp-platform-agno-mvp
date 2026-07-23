# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: inspectors)
"""Request shapes for the C3 inspector routes — records curation + flags.

Response bodies (records/schemas/verify-verdict/flag rows) are NOT modeled
here — they're passthrough JSON from a parallel-built spine (console/c3-spine,
per the C3 build brief), same rationale as app/types/runs.py's module
docstring: a pydantic response_model would fight an open-ended, still-settling
shape rather than help.
"""

from __future__ import annotations

from pydantic import BaseModel


class RecordMetaPatchRequest(BaseModel):
    """PATCH /api/records/{id}/meta body — curation-only edits (title, label
    chips, attrs). Never touches evidence blobs/hashes — see
    docs/planning/operator-console-requirements.md addendum 3."""

    title: str | None = None
    labels: list[str] | None = None
    attrs_patch: dict | None = None


class FlagLinkArtifact(BaseModel):
    """A corroborating artifact linked to a flag once found."""

    id: str
    sha256: str


class FlagCreateRequest(BaseModel):
    """POST /api/flags body — "needs corroborating evidence" annotation.

    Field shapes per docs/planning/operator-console-requirements.md
    addendum 6.
    """

    target_kind: str
    target_id: str
    claim: str
    claim_date_start: str | None = None
    claim_date_end: str | None = None
    evidence_wanted: list[str] | None = None
    notes: str | None = None


class FlagUpdateRequest(BaseModel):
    """PATCH /api/flags/{id} body — status transitions + corroboration linking."""

    status: str | None = None
    notes: str | None = None
    link_artifact: FlagLinkArtifact | None = None
