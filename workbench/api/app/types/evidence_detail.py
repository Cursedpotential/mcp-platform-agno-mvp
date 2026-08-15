"""Sanitized Workbench contracts for Matter evidence inspection.

Byline: Codex · GPT-5 · 2026-08-15 (custody and court-readiness projections)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.types.case_management import EvidenceItem, KnowledgeLane, ReviewState


class EvidenceSourcePointerDetail(BaseModel):
    """Redacted promotion pointer; unknown/private keys are dropped."""

    matter_id: UUID
    court_case_id: UUID
    partition_key: str
    lane: KnowledgeLane
    normalized_record_id: UUID
    evidence_hash_id: UUID
    source_id: UUID
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    conversation_id: str | None = None
    retrieval_ref: str
    content_ref: str | None = None
    chunk_ref: str | None = None

    @field_validator("sha256")
    @classmethod
    def normalize_pointer_sha256(cls, value: str) -> str:
        return value.lower()


class EvidencePromotionDetail(BaseModel):
    id: UUID
    partition_key: str
    knowledge_lane: KnowledgeLane
    retrieval_item_ref: str
    content_ref: str | None = None
    chunk_ref: str | None = None
    source_pointer: EvidenceSourcePointerDetail
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
    digest_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    level: str
    canon_version: str
    hashed_at: datetime
    computed_by: str | None = None

    @field_validator("digest_sha256")
    @classmethod
    def normalize_digest(cls, value: str) -> str:
        return value.lower()


class EvidenceSourceDetail(BaseModel):
    id: UUID
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    byte_size: int = Field(ge=0)
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

    @field_validator("sha256")
    @classmethod
    def normalize_sha256(cls, value: str) -> str:
        return value.lower()


class EvidenceFileNodeDetail(BaseModel):
    id: UUID
    node_kind: str
    node_path: str | None = None
    ordinal: int | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    byte_span_start: int | None = None
    byte_span_end: int | None = None
    locator: dict[str, object] = Field(default_factory=dict)
    mime_type: str | None = None

    @field_validator("sha256")
    @classmethod
    def normalize_optional_sha256(cls, value: str | None) -> str | None:
        return value.lower() if value else None


CourtReadinessBlocker = Literal[
    "CONTENT_REVIEW_REQUIRED",
    "PROVENANCE_INVALID",
    "CUSTODY_NOT_VERIFIED",
    "CUSTODY_CHAIN_INVALID",
    "AUTHENTICATION_REQUIRED",
    "CONFIDENCE_NOT_EXPORTABLE",
    "HYPOTHESIS_NOT_EXPORTABLE",
    "REDACTION_REQUIRED",
    "SENSITIVITY_SEALED",
    "NOT_RELEASED",
]


class ContentReviewReadinessGate(BaseModel):
    approved: bool
    decision_id: UUID | None = None


class ProvenanceReadinessGate(BaseModel):
    exact: bool


class CustodyReadinessGate(BaseModel):
    h1_valid: bool
    event_chain_valid: bool
    verified_event_present: bool
    source_status: str = Field(min_length=1, max_length=100)
    source_reviewed: bool
    verified_by: str | None = Field(default=None, max_length=500)
    verified_at: datetime | None = None


class AuthenticationReadinessGate(BaseModel):
    authenticated: bool
    method: str | None = Field(default=None, max_length=200)


class ConfidenceReadinessGate(BaseModel):
    value: float | None = Field(default=None, ge=0, le=1)
    tier: str = Field(min_length=1, max_length=100)
    export_band: bool


class AssertionReadinessGate(BaseModel):
    not_hypothesis: bool


class RedactionReadinessGate(BaseModel):
    privacy_sensitivity: str = Field(min_length=1, max_length=100)
    source_privacy_sensitivity: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=100)
    clear_for_export: bool


class SensitivityReadinessGate(BaseModel):
    evidence_tier: str = Field(min_length=1, max_length=100)
    source_tier: str = Field(min_length=1, max_length=100)
    sealed: bool


class CourtExportReadinessGate(BaseModel):
    view_member: bool


class CourtReadinessGates(BaseModel):
    content_review: ContentReviewReadinessGate
    provenance: ProvenanceReadinessGate
    custody: CustodyReadinessGate
    authentication: AuthenticationReadinessGate
    confidence: ConfidenceReadinessGate
    assertion: AssertionReadinessGate
    redaction: RedactionReadinessGate
    sensitivity: SensitivityReadinessGate
    court_export: CourtExportReadinessGate


class CourtReadiness(BaseModel):
    """Matter-scoped database gate projection, not a legal conclusion."""

    evidence_item_id: UUID
    matter_id: UUID
    readiness_passed: bool
    blockers: list[CourtReadinessBlocker]
    gates: CourtReadinessGates

    @model_validator(mode="after")
    def require_honest_readiness(self) -> CourtReadiness:
        expected: set[CourtReadinessBlocker] = set()
        if not self.gates.content_review.approved or self.gates.content_review.decision_id is None:
            expected.add("CONTENT_REVIEW_REQUIRED")
        if not self.gates.provenance.exact:
            expected.add("PROVENANCE_INVALID")
        custody = self.gates.custody
        if not (
            custody.verified_event_present
            and custody.source_status.lower() == "verified"
            and custody.source_reviewed
            and custody.verified_by is not None
            and custody.verified_at is not None
        ):
            expected.add("CUSTODY_NOT_VERIFIED")
        if not custody.h1_valid or not custody.event_chain_valid:
            expected.add("CUSTODY_CHAIN_INVALID")
        if not self.gates.authentication.authenticated or self.gates.authentication.method is None:
            expected.add("AUTHENTICATION_REQUIRED")
        if not self.gates.confidence.export_band:
            expected.add("CONFIDENCE_NOT_EXPORTABLE")
        if not self.gates.assertion.not_hypothesis:
            expected.add("HYPOTHESIS_NOT_EXPORTABLE")
        if not self.gates.redaction.clear_for_export:
            expected.add("REDACTION_REQUIRED")
        if self.gates.sensitivity.sealed:
            expected.add("SENSITIVITY_SEALED")
        if not self.gates.court_export.view_member:
            expected.add("NOT_RELEASED")
        if len(self.blockers) != len(set(self.blockers)) or set(self.blockers) != expected:
            raise ValueError("court-export blockers do not match their database gates")
        if self.readiness_passed != (not expected):
            raise ValueError("supplemental readiness result does not match its database gates")
        return self


class EvidenceDetail(BaseModel):
    """Matter-scoped detail; private spine fields are dropped by default."""

    item: EvidenceItem
    promotion: EvidencePromotionDetail
    record: CanonicalRecordDetail
    custody_hash: CustodyHashDetail
    source: EvidenceSourceDetail
    file_node: EvidenceFileNodeDetail | None = None

    @model_validator(mode="after")
    def require_exact_h1_provenance(self) -> EvidenceDetail:
        if self.record.id != self.item.normalized_record_id:
            raise ValueError("canonical record does not match evidence item")
        if self.custody_hash.id != self.item.evidence_hash_id:
            raise ValueError("custody hash does not match evidence item")
        if self.source.id != self.item.source_id:
            raise ValueError("source does not match evidence item")
        if self.item.file_node_id is not None and (
            self.file_node is None or self.file_node.id != self.item.file_node_id
        ):
            raise ValueError("file node does not match evidence item")
        if self.custody_hash.level != "H1" or self.custody_hash.algo.lower() != "sha256":
            raise ValueError("evidence inspection requires an H1 SHA-256 custody hash")
        if self.custody_hash.canon_version != "h1-rawbytes-v1":
            raise ValueError("evidence inspection requires h1-rawbytes-v1")
        pointer = self.promotion.source_pointer
        if (
            pointer.matter_id != self.item.matter_id
            or pointer.court_case_id != self.item.court_case_id
            or pointer.normalized_record_id != self.record.id
            or pointer.evidence_hash_id != self.custody_hash.id
            or pointer.source_id != self.source.id
        ):
            raise ValueError("redacted promotion pointer does not match evidence provenance")
        return self
