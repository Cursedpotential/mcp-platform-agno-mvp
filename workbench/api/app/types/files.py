# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Request shape for the /api/files PATCH endpoint.

Staged file records themselves are plain dicts coming out of repo/staging.py
(see app.types.documents.StagedFile for the canonical shape); this module
only holds the PATCH request body and the fixed domain taxonomy it validates
against, replacing the donor kit's raw-object FileMetadata/FileMetadataDetail
models (which no longer apply — the workbench doesn't extract image/PDF
metadata itself).
"""

from __future__ import annotations

from pydantic import BaseModel

ALLOWED_DOMAINS = (
    "timeline_relationship",
    "personal_history",
    "platform_design",
    "legal_strategy",
)


class FilePatchRequest(BaseModel):
    """PATCH /api/files/{id} body — all fields optional (partial update).

    A field set to `null` explicitly clears it; a field omitted entirely is
    left untouched. The runtime layer must pass `.model_dump(exclude_unset=True)`
    to the service layer to preserve that distinction (see runtime/files.py).
    """

    domain: str | None = None
    category: str | None = None
    source_platform: str | None = None
    detected_type: str | None = None
