"""Framework-neutral contracts for canonical file ingestion.

These models deliberately import no workflow, agent, vector, graph, or database
framework. HTTP and in-process callers share the same request and receipt shape.

Byline: Codex · GPT-5 · 2026-08-16
"""

# Byline amendment: Codex · GPT-5 · 2026-08-18 (typed acquisition/source class)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (human authority category + named asserter)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (pending native projection receipt state)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (authenticated first-party ownership assertion)

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class IngestLane(str, Enum):
    platform = "platform"
    legal = "legal"
    personal_history = "personal_history"
    context = "context"
    evidence = "evidence"


class AcquisitionAssertion(BaseModel):
    """Human-asserted acquisition event; distinct from file ingest time."""

    acquired_at: datetime
    method: Literal[
        "own_device",
        "household_device",
        "voluntary_third_party",
        "legal_process",
        "public_source",
        "unknown",
    ] = "unknown"
    authority: Literal[
        "device_owner",
        "parent_guardian",
        "account_holder",
        "consent_given",
        "court_order",
        "unclear",
    ] = "unclear"
    source_device: str | None = None
    device_custodian: str | None = None
    notes: str | None = None
    asserted_by_category: Literal["human"] = "human"
    asserted_by: str = "owner"

    @field_validator("asserted_by")
    @classmethod
    def _asserter_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("asserted_by identity must not be blank")
        return value


class IngestRequest(BaseModel):
    """One staged file and the routing context required to ingest it."""

    staged_path: str
    source_identity: dict[str, Any] = Field(default_factory=dict)
    message_corpus: Literal["first_party", "acquired_third_party"] | None = None
    source_principal: str | None = None
    caller_owns_conversation: bool = False
    acquisition: AcquisitionAssertion | None = None
    coverage_hint: str | None = None
    lane: IngestLane = IngestLane.platform
    matter_id: str = "primary"
    engine: Literal["auto", "go", "python"] = "auto"
    allow_fallback: bool = False
    custody_tier: Literal["full", "light"] = "light"

    @field_validator("staged_path", "matter_id")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("source_principal")
    @classmethod
    def _optional_nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("source_principal must not be blank")
        return value

    def model_post_init(self, __context: Any) -> None:
        if self.message_corpus == "first_party" and not self.caller_owns_conversation:
            raise ValueError(
                "first_party ingestion requires an explicit authenticated caller_owns_conversation assertion"
            )
        if self.message_corpus == "first_party" and self.source_principal is None:
            raise ValueError("first_party ingestion requires the caller's source_principal identity")
        if self.message_corpus == "acquired_third_party":
            if self.acquisition is None:
                raise ValueError("acquired_third_party ingestion requires an acquisition assertion")
            if self.source_principal is None:
                raise ValueError("acquired_third_party ingestion requires the source account/device principal")


class IngestRejection(BaseModel):
    code: str
    detail: str


class ProjectionResult(BaseModel):
    sink: str
    status: Literal["completed", "pending", "skipped", "failed"]
    detail: str | None = None


class IngestReceipt(BaseModel):
    """Durable result returned by both HTTP and in-process ingestion."""

    receipt_id: str
    status: Literal["completed", "failed"]
    lane: IngestLane
    matter_id: str
    source_name: str
    source_path: str
    source_sha256: str | None = None
    artifact_id: str | None = None
    duplicate: bool = False
    parser_id: str | None = None
    parser_engine: Literal["go", "python", "none"] = "none"
    chunker_id: str
    record_count: int = 0
    chunk_count: int = 0
    rejections: list[IngestRejection] = Field(default_factory=list)
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    projections: list[ProjectionResult] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime
