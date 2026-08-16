"""Framework-neutral contracts for governed Semantica extraction.

The worker receives immutable normalized-record snapshots and emits candidates.
It has no persistence, projection, agent, or provider contract.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtractionRecord(BaseModel):
    """One custody-approved normalized row copied into an immutable batch."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_raw_table: Literal["working.normalized_record"] = "working.normalized_record"
    source_raw_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance_ref: str = Field(min_length=1)
    occurred_at: datetime | None = None

    @model_validator(mode="after")
    def content_hash_matches(self) -> ExtractionRecord:
        from hashlib import sha256

        observed = sha256(self.content.encode("utf-8")).hexdigest()
        if observed != self.content_sha256:
            raise ValueError("content_sha256 does not match immutable content")
        return self


class ExtractionBatch(BaseModel):
    """Horizon-blind extraction input; deliberately has no HorizonContext."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_id: str = Field(min_length=1)
    matter_id: str = Field(min_length=1)
    records: tuple[ExtractionRecord, ...] = Field(min_length=1)


class CandidateProvenance(BaseModel):
    """Lineage required on every emitted candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_raw_table: str
    source_raw_id: str
    source_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_provenance_ref: str
    extractor: Literal["semantica"] = "semantica"
    extractor_version: str
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    method: str
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=0)
    evidence_quote: str | None = None

    @model_validator(mode="after")
    def valid_span(self) -> CandidateProvenance:
        if (self.span_start is None) != (self.span_end is None):
            raise ValueError("candidate span must provide both start and end")
        if self.span_start is not None and self.span_end is not None and self.span_end < self.span_start:
            raise ValueError("candidate span end precedes start")
        return self


EntityType = Literal["person", "organization", "location", "device", "account", "other"]


class EntityCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    entity_type: EntityType
    name: str
    normalized_name: str
    confidence: float = Field(ge=0, le=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: CandidateProvenance


class FactCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    subject_key: str
    object_key: str
    predicate: str
    statement: str
    confidence: float = Field(ge=0, le=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: CandidateProvenance


class EventCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    event_type: str
    summary: str
    occurred_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    temporal_confidence: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance: CandidateProvenance

    @model_validator(mode="after")
    def has_defensible_time(self) -> EventCandidate:
        if self.occurred_at is None and (self.valid_from is None or self.valid_to is None):
            raise ValueError("event candidate requires a point or bounded validity interval")
        if self.valid_from is not None and self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("event validity interval must be increasing")
        return self


class ExtractionRejection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_raw_id: str
    stage: Literal["entity", "relation", "event"]
    reason: str
    detail: str


class ExtractionFailure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_raw_id: str
    stage: str
    error: str


class CandidateBatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    batch_id: str
    matter_id: str
    extractor: Literal["semantica"] = "semantica"
    extractor_version: str
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_count: int = Field(ge=1)
    entities: tuple[EntityCandidate, ...] = ()
    facts: tuple[FactCandidate, ...] = ()
    events: tuple[EventCandidate, ...] = ()
    rejections: tuple[ExtractionRejection, ...] = ()
    failures: tuple[ExtractionFailure, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.failures


class SubmissionReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    batch_id: str
    status: Literal["completed", "failed"]
    entity_count: int = 0
    fact_count: int = 0
    event_count: int = 0


class CandidateRepository(Protocol):
    """The only outward door from extraction results into platform state."""

    def submit(self, batch: CandidateBatch) -> SubmissionReceipt: ...
