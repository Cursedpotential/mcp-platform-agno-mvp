"""Use-case boundary for Matter workspaces and evidence promotion.

The service keeps FastAPI out of the domain and delegates persistence to the
transactional repository.  It is intentionally thin today, but is the stable
seam for future authorization grants and alternative runtimes.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

from uuid import UUID

from server.case_management import repository
from server.contracts.case_management import (
    CourtCase,
    CourtCaseCreate,
    CourtReadiness,
    EvidenceItemCreate,
    EvidenceItemDetail,
    EvidenceItemList,
    EvidencePromotionResult,
    EvidenceReviewCreate,
    EvidenceReviewList,
    EvidenceReviewResult,
    KnowledgeSourceResolution,
    KnowledgeSourceResolveRequest,
    Matter,
    MatterCreate,
    MatterDetail,
    MatterList,
    ReviewState,
)

CaseManagementError = repository.CaseRepositoryError


def list_matters(*, limit: int, offset: int) -> MatterList:
    return repository.list_matters(limit=limit, offset=offset)


def create_matter(body: MatterCreate) -> Matter:
    return repository.create_matter(body)


def get_matter(matter_id: UUID) -> MatterDetail:
    return repository.get_matter(matter_id)


def create_court_case(matter_id: UUID, body: CourtCaseCreate) -> CourtCase:
    return repository.create_court_case(matter_id, body)


def resolve_source(matter_id: UUID, body: KnowledgeSourceResolveRequest) -> KnowledgeSourceResolution:
    return repository.resolve_source(matter_id, body)


def promote_evidence(matter_id: UUID, body: EvidenceItemCreate) -> EvidencePromotionResult:
    return repository.promote_evidence(matter_id, body)


def get_evidence_detail(matter_id: UUID, evidence_item_id: UUID) -> EvidenceItemDetail:
    return repository.get_evidence_detail(matter_id, evidence_item_id)


def get_court_readiness(matter_id: UUID, evidence_item_id: UUID) -> CourtReadiness:
    return repository.get_court_readiness(matter_id, evidence_item_id)


def review_evidence(
    matter_id: UUID,
    evidence_item_id: UUID,
    body: EvidenceReviewCreate,
) -> EvidenceReviewResult:
    return repository.review_evidence(matter_id, evidence_item_id, body)


def list_evidence_reviews(
    matter_id: UUID,
    evidence_item_id: UUID,
) -> EvidenceReviewList:
    return repository.list_evidence_reviews(matter_id, evidence_item_id)


def list_evidence_items(
    matter_id: UUID,
    *,
    review_status: ReviewState | None,
    limit: int,
    offset: int,
) -> EvidenceItemList:
    return repository.list_evidence_items(
        matter_id,
        review_status=review_status,
        limit=limit,
        offset=offset,
    )
