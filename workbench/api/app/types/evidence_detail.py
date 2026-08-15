"""Sanitized Workbench contracts for Matter evidence inspection.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

from datetime import datetime
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
