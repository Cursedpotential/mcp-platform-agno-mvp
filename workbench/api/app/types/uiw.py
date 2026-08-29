"""Typed boundary models for the Universal Import Workflow starter.

Byline: Codex · GPT-5 · 2026-08-28.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import unquote, urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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

    workflow_id: NonBlank
    run_id: NonBlank


class UIWDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    reason: str = ""
    decider: NonBlank


class UIWDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: NonBlank


class UIWPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: NonBlank
    # Empty before parser selection is valid while a workflow is starting.
    select_ref: str = ""
    reason: str = ""
