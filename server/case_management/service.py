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
    ConversationContext,
    Matter,
    MatterCreate,
    MatterDetail,
    MatterList,
    ReviewState,
    OriginalSourceContent,
)

CaseManagementError = repository.CaseRepositoryError


def get_capabilities() -> dict[str, object]:
    return repository.get_case_management_capabilities()


def _require_advanced_evidence() -> None:
    capabilities = get_capabilities()
    if not capabilities["advanced_evidence_available"]:
        raise CaseManagementError(repository.ADVANCED_EVIDENCE_UNAVAILABLE_DETAIL, 503)


def list_matters(*, limit: int, offset: int) -> MatterList:
    return repository.list_matters(limit=limit, offset=offset)


def create_matter(body: MatterCreate) -> Matter:
    return repository.create_matter(body)


def get_matter(matter_id: UUID) -> MatterDetail:
    return repository.get_matter(matter_id)


def create_court_case(matter_id: UUID, body: CourtCaseCreate) -> CourtCase:
    return repository.create_court_case(matter_id, body)


def resolve_source(matter_id: UUID, body: KnowledgeSourceResolveRequest) -> KnowledgeSourceResolution:
    _require_advanced_evidence()
    return repository.resolve_source(matter_id, body)


def promote_evidence(matter_id: UUID, body: EvidenceItemCreate) -> EvidencePromotionResult:
    _require_advanced_evidence()
    return repository.promote_evidence(matter_id, body)


def get_evidence_detail(matter_id: UUID, evidence_item_id: UUID) -> EvidenceItemDetail:
    _require_advanced_evidence()
    return repository.get_evidence_detail(matter_id, evidence_item_id)


def get_court_readiness(matter_id: UUID, evidence_item_id: UUID) -> CourtReadiness:
    _require_advanced_evidence()
    return repository.get_court_readiness(matter_id, evidence_item_id)


def review_evidence(
    matter_id: UUID,
    evidence_item_id: UUID,
    body: EvidenceReviewCreate,
) -> EvidenceReviewResult:
    _require_advanced_evidence()
    return repository.review_evidence(matter_id, evidence_item_id, body)


def list_evidence_reviews(
    matter_id: UUID,
    evidence_item_id: UUID,
) -> EvidenceReviewList:
    _require_advanced_evidence()
    return repository.list_evidence_reviews(matter_id, evidence_item_id)


def list_evidence_items(
    matter_id: UUID,
    *,
    review_status: ReviewState | None,
    limit: int,
    offset: int,
) -> EvidenceItemList:
    _require_advanced_evidence()
    return repository.list_evidence_items(
        matter_id,
        review_status=review_status,
        limit=limit,
        offset=offset,
    )


def get_original_source_content(matter_id: UUID, evidence_item_id: UUID) -> OriginalSourceContent:
    _require_advanced_evidence()
    return repository.get_original_source_content(matter_id, evidence_item_id)


def get_conversation_context(
    matter_id: UUID,
    evidence_item_id: UUID,
    *,
    before: int,
    after: int,
) -> ConversationContext:
    _require_advanced_evidence()
    return repository.get_conversation_context(
        matter_id,
        evidence_item_id,
        before=before,
        after=after,
    )
