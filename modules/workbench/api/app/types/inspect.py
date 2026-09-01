# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: inspectors)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (third-party conversation review request)
# Byline: Codex · GPT-5 · 2026-08-18 (governed entity picker contracts)
"""Request shapes for the C3 inspector routes — records curation + flags.

Response bodies (records/schemas/verify-verdict/flag rows) are NOT modeled
here — they're passthrough JSON from a parallel-built spine (console/c3-spine,
per the C3 build brief), same rationale as app/types/runs.py's module
docstring: a pydantic response_model would fight an open-ended, still-settling
shape rather than help.
"""

from __future__ import annotations

from uuid import UUID

from typing import Literal

from pydantic import BaseModel, ConfigDict, StringConstraints
from typing_extensions import Annotated


class RecordMetaPatchRequest(BaseModel):
    """PATCH /api/records/{id}/meta body — curation-only edits (title, label
    chips, attrs). Never touches evidence blobs/hashes — see
    docs/planning/operator-console-requirements.md addendum 3."""

    title: str | None = None
    labels: list[str] | None = None
    attrs_patch: dict | None = None


class ThirdPartyApprovalRequest(BaseModel):
    """Explicit human resolution for every derived sender and participant row."""

    model_config = ConfigDict(extra="forbid")
    sender_entity_ids: dict[UUID, UUID]
    participant_entity_ids: dict[UUID, UUID]
    reason: str


class EntityCreateRequest(BaseModel):
    """Create one reviewed identity; creator comes from authentication."""

    model_config = ConfigDict(extra="forbid")
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    entity_type: Literal[
        "person",
        "org",
        "project",
        "tech",
        "location",
        "concept",
        "phone",
        "email",
        "handle",
        "device",
        "account",
        "vehicle",
        "address",
        "court",
        "attorney",
        "school",
        "doctor",
        "institution",
        "platform",
        "ai_system",
    ] = "person"


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
