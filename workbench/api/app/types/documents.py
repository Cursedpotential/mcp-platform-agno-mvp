# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Types describing a staged file — the workbench's only document shape.

Unlike the donor kit, the workbench never chunks or classifies documents
itself; it only stages whole files and hands them to the platform ingestion
API. `detected_type` distinguishes the two promote paths (doc vs chat_export).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class StagedStatus(StrEnum):
    """Lifecycle of a staged file record."""

    staged = "staged"
    promoting = "promoting"
    promoted = "promoted"
    failed = "failed"


class DetectedType(StrEnum):
    """What kind of promote path a staged file should take."""

    doc = "doc"
    chat_export = "chat_export"


class StagedFileMeta(BaseModel):
    """User-editable classification metadata for a staged file."""

    domain: str | None = None
    category: str | None = None
    source_platform: str | None = None


class StagedFile(BaseModel):
    """A row in the LanceDB `staged_files` table."""

    id: str  # sha256 of the file contents
    name: str
    size: int
    mime: str
    detected_type: DetectedType
    text: str = ""  # extracted text preview, capped; "" for binary formats
    meta: StagedFileMeta = StagedFileMeta()
    r2_key: str
    status: StagedStatus = StagedStatus.staged
    promote_result: dict | None = None
    created_at: datetime
    updated_at: datetime
