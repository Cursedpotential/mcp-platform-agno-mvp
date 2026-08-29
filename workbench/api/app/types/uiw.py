"""Typed boundary models for the Universal Import Workflow starter.

Byline: Codex · GPT-5 · 2026-08-28.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import unquote, urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OpaquePreviewHandle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{32,128}$"),
]
Sha256Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
BoundedReason = Annotated[str, StringConstraints(max_length=4000)]
OpaqueCursor = Annotated[str, StringConstraints(min_length=1, max_length=512)]


class UIWStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: NonBlank
    matter_id: UUID
    court_case_id: UUID
    source_ref: NonBlank
    declared_format: NonBlank
    parser_options_ref: NonBlank

    @field_validator("source_ref")
    @classmethod
    def source_must_be_authorized(cls, value: str) -> str:
        parsed = urlsplit(value)
        upload_digest = parsed.netloc.casefold()
        if (
            parsed.scheme == "upload"
            and len(upload_digest) == 64
            and all(character in "0123456789abcdef" for character in upload_digest)
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
        ):
            return value
        if parsed.scheme == "r2" and parsed.netloc == "casebible-sorted" and not parsed.query and not parsed.fragment:
            key = unquote(parsed.path.removeprefix("/"))
            if key and not key.startswith("/") and "\\" not in key and ".." not in key.split("/"):
                return value
        raise ValueError("source_ref must be an upload reference or a Case Bible Sorted object")


class UIWSourceObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["object"] = "object"
    key: NonBlank
    name: NonBlank
    byte_length: int
    last_modified: datetime | None = None
    etag: str | None = None


class UIWSourcePrefix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["prefix"] = "prefix"
    prefix: NonBlank
    name: NonBlank


class UIWSourceBrowserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["casebible-sorted"] = "casebible-sorted"
    prefix: str
    delimiter: Literal["/"] = "/"
    filter: str
    filter_applied: bool
    page_size: int
    is_truncated: bool
    continuation_token: str | None = None
    prefixes: list[UIWSourcePrefix]
    objects: list[UIWSourceObject]


class UIWStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_handle: OpaquePreviewHandle


class UIWDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    reason: BoundedReason = ""


class UIWDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_handle: OpaquePreviewHandle
    status: NonBlank


class UIWDecisionActor(BaseModel):
    """Immutable identity forwarded by the authenticated BFF, never the browser."""

    model_config = ConfigDict(extra="forbid")

    subject_uid: NonBlank
    username: NonBlank


class UIWParserIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parser_id: NonBlank
    parser_version: NonBlank
    config_digest: Sha256Digest


class UIWPreviewCorrelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: NonBlank
    source_version_id: UUID
    raw_generation_id: UUID
    normalized_generation_id: UUID


class UIWPreviewReceipt(BaseModel):
    """Reference-only receipt; raw or normalized payload bytes are forbidden here."""

    model_config = ConfigDict(extra="forbid")

    receipt_type: Literal[
        "custody",
        "parser_selection",
        "parser_execution",
        "normalization",
        "storage",
        "completeness",
    ]
    receipt_ref: NonBlank
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    digest: Sha256Digest | None = None
    recorded_at: datetime


class UIWPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_handle: OpaquePreviewHandle
    phase: NonBlank
    correlation: UIWPreviewCorrelation
    parser: UIWParserIdentity | None = None
    preview_digest: Sha256Digest
    receipts: Annotated[list[UIWPreviewReceipt], Field(max_length=64)]
    reason: BoundedReason = ""


class UIWPreviewParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_id: NonBlank
    display_name: NonBlank
    canonical_address: str | None = None


class UIWPreviewAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attachment_id: NonBlank
    filename: str | None = None
    media_type: str | None = None
    byte_length: Annotated[int, Field(ge=0)] | None = None
    sha256: Sha256Digest | None = None
    source_locator_ref: NonBlank


class UIWPreviewMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: NonBlank
    ordinal: Annotated[int, Field(ge=0)]
    sent_at: datetime | None = None
    sender_participant_id: str | None = None
    body: Annotated[str, StringConstraints(max_length=1_000_000)]
    participant_ids: Annotated[list[str], Field(max_length=64)]
    attachments: Annotated[list[UIWPreviewAttachment], Field(max_length=128)]
    source_locator_ref: NonBlank


class UIWPreviewMessagesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_handle: OpaquePreviewHandle
    participants: Annotated[list[UIWPreviewParticipant], Field(max_length=256)]
    messages: Annotated[list[UIWPreviewMessage], Field(max_length=250)]
    next_cursor: OpaqueCursor | None = None


class UIWPreviewEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: Annotated[int, Field(ge=0)]
    event_type: Literal[
        "phase_changed",
        "receipt_recorded",
        "messages_available",
        "decision_requested",
        "decision_recorded",
        "completed",
        "failed",
    ]
    occurred_at: datetime
    preview_handle: OpaquePreviewHandle
    phase: NonBlank
    receipt_ref: str | None = None
    message_count: Annotated[int, Field(ge=0)] | None = None
    detail: BoundedReason = ""
