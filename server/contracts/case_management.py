"""Framework-neutral contracts for Matter workspaces and draft evidence.

These models intentionally expose platform-owned identifiers and provenance
only.  AgentOS/Agno knowledge-base identifiers are adapter details and must
not become part of the case-management API.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

KnowledgeLane = Literal["platform", "legal", "personal_history", "context", "evidence"]


class ReviewState(StrEnum):
    """Review states shared with ``ai.review_state``."""

    unreviewed = "unreviewed"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"
    needs_more_evidence = "needs_more_evidence"


class MatterStatus(StrEnum):
    active = "active"
    closed = "closed"
    archived = "archived"


class CourtCaseStatus(StrEnum):
    pre_filing = "pre_filing"
    active = "active"
    stayed = "stayed"
    closed = "closed"
    appealed = "appealed"
    archived = "archived"


class EvidenceReviewDecision(StrEnum):
    approved = "approved"
    rejected = "rejected"
    needs_changes = "needs_changes"
    needs_context = "needs_context"
    escalated = "escalated"
    hold = "hold"


class MatterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=10_000)
    partition_key: str | None = Field(default=None, min_length=1, max_length=200)
    created_by: Literal["owner"] = "owner"

    @field_validator("title", "partition_key")
    @classmethod
    def _strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class Matter(BaseModel):
    id: UUID
    title: str
    description: str | None = None
    status: MatterStatus
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
    status: CourtCaseStatus = CourtCaseStatus.pre_filing
    filed_on: date | None = None
    closed_on: date | None = None
    is_primary: bool = False
    created_by: Literal["owner"] = "owner"

    @field_validator("caption")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class CourtCase(BaseModel):
    id: UUID
    matter_id: UUID
    caption: str
    court_name: str | None = None
    docket_number: str | None = None
    jurisdiction: str | None = None
    case_type: str | None = None
    status: CourtCaseStatus
    filed_on: date | None = None
    closed_on: date | None = None
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class MatterDetail(Matter):
    court_cases: list[CourtCase] = Field(default_factory=list)


class KnowledgeSourceRef(BaseModel):
    """Custody-backed source coordinates carried by a retrieval result.

    Every field is treated as an assertion to verify against Postgres.  The
    client never authorizes or establishes provenance by supplying it.
    """

    lane: KnowledgeLane
    partition_key: str = Field(min_length=1, max_length=200)
    artifact_id: UUID
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    conversation_id: str | None = Field(default=None, max_length=500)
    quote: str | None = Field(default=None, max_length=50_000)
    retrieval_ref: str = Field(min_length=1, max_length=500)
    content_ref: str | None = Field(default=None, max_length=500)
    chunk_ref: str | None = Field(default=None, max_length=500)

    @field_validator("partition_key")
    @classmethod
    def _strip_partition(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("sha256")
    @classmethod
    def _lower_sha256(cls, value: str) -> str:
        return value.lower()


class KnowledgeSourceResolveRequest(KnowledgeSourceRef):
    pass


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
    def _strip_item_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


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


class PromotionSourcePointer(BaseModel):
    """Public allowlist for the immutable promotion pointer."""

    model_config = ConfigDict(extra="ignore")

    matter_id: UUID
    court_case_id: UUID
    partition_key: str
    lane: KnowledgeLane
    normalized_record_id: UUID
    evidence_hash_id: UUID
    source_id: UUID
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conversation_id: str | None = None
    retrieval_ref: str
    content_ref: str | None = None
    chunk_ref: str | None = None
    quote: str | None = None


class EvidencePromotionDetail(BaseModel):
    id: UUID
    partition_key: str
    knowledge_lane: KnowledgeLane
    retrieval_item_ref: str
    content_ref: str | None = None
    chunk_ref: str | None = None
    source_pointer: PromotionSourcePointer
    promoted_by: str
    promoted_at: datetime


class CanonicalRecordDetail(BaseModel):
    id: UUID
    record_type: str
    source: str
    conversation_id: str | None = None
    role: str | None = None
    content: str
    occurred_at: datetime | None = None
    acquired_at: datetime | None = None
    ingested_at: datetime
    realized_at: datetime | None = None
    disclosure_tier: str
    review_status: ReviewState
    case_id: str


class CustodyHashDetail(BaseModel):
    id: UUID
    source_ref: str
    algo: str
    digest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    level: Literal["H1"]
    canon_version: str
    hashed_at: datetime
    computed_by: str | None = None


class SourceCustodyDetail(BaseModel):
    id: UUID
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int
    mime_type: str | None = None
    original_filename: str | None = None
    source_type: str
    source_platform: str | None = None
    acquisition_source: str
    acquisition_method: str | None = None
    acquired_at_utc: datetime | None = None
    acquired_certainty: str
    provenance_tier: str
    hash_canon_version: str
    custody_status: str
    review_status: str
    verified_by: str | None = None
    verified_at: datetime | None = None


class FileNodeDetail(BaseModel):
    id: UUID
    node_kind: str
    node_path: str | None = None
    ordinal: int | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    byte_span_start: int | None = None
    byte_span_end: int | None = None
    locator: dict[str, Any]
    mime_type: str | None = None


class EvidenceItemDetail(BaseModel):
    item: EvidenceItem
    promotion: EvidencePromotionDetail
    record: CanonicalRecordDetail
    custody_hash: CustodyHashDetail
    source: SourceCustodyDetail
    file_node: FileNodeDetail | None = None


class EvidencePromotionResult(BaseModel):
    item: EvidenceItem
    promotion_id: UUID
    created: bool


class EvidenceReviewCreate(BaseModel):
    decision: EvidenceReviewDecision
    rationale: str = Field(min_length=1, max_length=20_000)
    reviewer: Literal["owner"] = "owner"

    @field_validator("rationale")
    @classmethod
    def _strip_review_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class EvidenceReviewResult(BaseModel):
    item: EvidenceItem
    task_id: UUID
    decision_id: UUID
    decision: EvidenceReviewDecision
    court_readiness: Literal["review_passed", "excluded", "draft"]


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


class EvidenceItemList(BaseModel):
    data: list[EvidenceItem]
    total: int
    limit: int
    offset: int
