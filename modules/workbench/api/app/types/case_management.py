"""Workbench contracts for the framework-neutral Matter spine API.

Byline: Codex · GPT-5 · 2026-08-15
Byline amendment: Codex · GPT-5 · 2026-08-18 (source/projection classification contracts)
Byline amendment: Codex · GPT-5.6-Sol · 2026-08-30 (split conversation context contracts)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

KnowledgeLane = Literal["platform", "legal", "personal_history", "context", "evidence"]
ReviewState = Literal["unreviewed", "in_review", "approved", "rejected", "needs_more_evidence"]
EvidenceReviewDecision = Literal["approved", "rejected", "needs_changes", "needs_context", "escalated", "hold"]
RecordSourceKind = Literal["first_party", "third_party_acquired", "unclassified"]
RecordProjectionKind = Literal["authored_normalized", "derived_third_party"]


class CaseManagementCapabilities(BaseModel):
    registry_available: bool
    advanced_evidence_available: bool
    advanced_evidence_reason: str


class MatterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10_000)
    partition_key: str | None = Field(default=None, min_length=1, max_length=200)
    created_by: Literal["owner"] = "owner"

    @field_validator("title", "partition_key")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class Matter(BaseModel):
    id: UUID
    title: str
    description: str | None = None
    status: Literal["active", "closed", "archived"]
    partition_keys: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MatterList(BaseModel):
    data: list[Matter]
    total: int
    limit: int
    offset: int


class CourtCaseCreate(BaseModel):
    caption: str = Field(min_length=1, max_length=300)
    court_name: str | None = Field(default=None, max_length=500)
    docket_number: str | None = Field(default=None, max_length=200)
    jurisdiction: str | None = Field(default=None, max_length=300)
    case_type: str | None = Field(default=None, max_length=200)
    status: Literal["pre_filing", "active", "stayed", "closed", "appealed", "archived"] = "pre_filing"
    filed_on: date | None = None
    closed_on: date | None = None
    is_primary: bool = False
    created_by: Literal["owner"] = "owner"

    @field_validator("caption")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class CourtCase(BaseModel):
    id: UUID
    matter_id: UUID
    caption: str
    court_name: str | None = None
    docket_number: str | None = None
    jurisdiction: str | None = None
    case_type: str | None = None
    status: Literal["pre_filing", "active", "stayed", "closed", "appealed", "archived"]
    filed_on: date | None = None
    closed_on: date | None = None
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class MatterDetail(Matter):
    court_cases: list[CourtCase] = Field(default_factory=list)


class KnowledgeSourceRef(BaseModel):
    lane: KnowledgeLane
    partition_key: str = Field(min_length=1, max_length=200)
    artifact_id: UUID
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    conversation_id: str | None = Field(default=None, max_length=500)
    quote: str | None = Field(default=None, max_length=50_000)
    retrieval_ref: str = Field(min_length=1, max_length=500)
    content_ref: str | None = Field(default=None, max_length=500)
    chunk_ref: str | None = Field(default=None, max_length=500)

    @field_validator("partition_key", "retrieval_ref")
    @classmethod
    def strip_partition(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return value.lower()


class SourceCandidate(BaseModel):
    normalized_record_id: UUID
    artifact_id: UUID
    evidence_hash_id: UUID
    source_id: UUID
    file_node_id: UUID | None = None
    source_run_id: UUID | None = None
    sha256: str
    conversation_id: str | None = None
    record_type: str
    role: str | None = None
    content: str
    occurred_at: datetime | None = None
    source_kind: RecordSourceKind = "unclassified"
    projection_kind: RecordProjectionKind = "authored_normalized"
    source_available_from: datetime | None = None
    disclosure_tier: str
    review_status: ReviewState


class KnowledgeSourceResolution(BaseModel):
    matter_id: UUID
    candidates: list[SourceCandidate]


class EvidenceSourcePointer(KnowledgeSourceRef):
    normalized_record_id: UUID


class EvidenceItemCreate(BaseModel):
    court_case_id: UUID
    source: EvidenceSourcePointer
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=20_000)
    quote: str | None = Field(default=None, max_length=50_000)
    evidence_type: Literal[
        "communication",
        "document",
        "photo",
        "record",
        "media",
        "screenshot",
        "transcript",
        "metadata",
        "other",
    ] = "communication"
    created_by: Literal["owner"] = "owner"

    @field_validator("title")
    @classmethod
    def strip_item_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class EvidenceItem(BaseModel):
    id: UUID
    matter_id: UUID
    court_case_id: UUID
    title: str
    description: str | None = None
    quote: str | None = None
    evidence_type: str
    evidence_date: datetime | None = None
    normalized_record_id: UUID
    evidence_hash_id: UUID
    source_id: UUID
    file_node_id: UUID | None = None
    source_run_id: UUID | None = None
    review_status: ReviewState
    hitl_required: bool
    safe_for_legal_use: bool
    is_authenticated: bool
    created_by: str
    created_at: datetime


class EvidencePromotionResult(BaseModel):
    item: EvidenceItem
    promotion_id: UUID
    created: bool

    @model_validator(mode="after")
    def require_unsafe_review_draft(self) -> EvidencePromotionResult:
        if self.created and (
            self.item.review_status != "unreviewed"
            or not self.item.hitl_required
            or self.item.safe_for_legal_use
            or self.item.is_authenticated
        ):
            raise ValueError("new evidence promotion must return an unreviewed unsafe HITL draft")
        return self


class EvidenceReviewCreate(BaseModel):
    decision: EvidenceReviewDecision
    rationale: str = Field(min_length=1, max_length=20_000)
    reviewer: Literal["owner"] = "owner"

    @field_validator("rationale")
    @classmethod
    def strip_review_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class EvidenceReviewResult(BaseModel):
    item: EvidenceItem
    task_id: UUID
    decision_id: UUID
    decision: EvidenceReviewDecision
    court_readiness: Literal["review_passed", "excluded", "draft"]

    @model_validator(mode="after")
    def never_infer_legal_safety(self) -> EvidenceReviewResult:
        if self.item.safe_for_legal_use or self.item.is_authenticated:
            raise ValueError("review alone cannot authenticate evidence or grant legal safety")
        return self


class EvidenceReviewRecord(BaseModel):
    decision_id: UUID
    task_id: UUID | None = None
    evidence_item_id: UUID
    reviewer: str
    decision: EvidenceReviewDecision
    court_readiness: str
    rationale: str
    decided_at: datetime


class EvidenceReviewList(BaseModel):
    data: list[EvidenceReviewRecord]
    total: int


class OriginalSourceContent(BaseModel):
    """Sanitized read-only text fetched from the custody H1 blob."""

    matter_id: UUID
    evidence_item_id: UUID
    normalized_record_id: UUID
    source_id: UUID
    file_node_id: UUID | None = None
    evidence_hash_id: UUID
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=0)
    content_byte_size: int = Field(ge=0)
    mime_type: str | None = None
    original_filename: str | None = None
    content: str
    encoding: str
    source_pointer: dict[str, object] = Field(default_factory=dict)
    provenance: dict[str, object] = Field(default_factory=dict)
    h1: str
    h2: str | None = None
    h3: str | None = None


class EvidenceItemList(BaseModel):
    data: list[EvidenceItem]
    total: int
    limit: int
    offset: int
