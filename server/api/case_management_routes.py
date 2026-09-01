"""FastAPI transport for Matter workspaces and Knowledge-to-Evidence.

All authorization, provenance resolution, idempotency, and writes live below
this transport in ``server.case_management``.  These routes only validate the
HTTP contract and translate domain errors.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel

from server.case_management import service
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
    ConversationContext,
    KnowledgeSourceResolution,
    KnowledgeSourceResolveRequest,
    Matter,
    MatterCreate,
    MatterDetail,
    MatterList,
    ReviewState,
    OriginalSourceContent,
)


_T = TypeVar("_T")


class CaseManagementCapabilities(BaseModel):
    """Availability of platform-native case-management slices."""

    registry_available: bool
    advanced_evidence_available: bool
    advanced_evidence_reason: str


def _translate(call: Callable[[], _T]) -> _T:
    try:
        return call()
    except service.CaseManagementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


def register_case_management_routes(app: FastAPI) -> None:
    """Register the platform-owned, framework-neutral case-management API."""

    @app.get("/v1/matters", response_model=MatterList, tags=["case-management"])
    def list_matters(
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> MatterList:
        return _translate(lambda: service.list_matters(limit=limit, offset=offset))

    @app.post(
        "/v1/matters",
        response_model=Matter,
        status_code=status.HTTP_201_CREATED,
        tags=["case-management"],
    )
    def create_matter(body: MatterCreate) -> Matter:
        return _translate(lambda: service.create_matter(body))

    @app.get("/v1/matters/{matter_id}", response_model=MatterDetail, tags=["case-management"])
    def get_matter(matter_id: UUID) -> MatterDetail:
        return _translate(lambda: service.get_matter(matter_id))

    @app.post(
        "/v1/matters/{matter_id}/court-cases",
        response_model=CourtCase,
        status_code=status.HTTP_201_CREATED,
        tags=["case-management"],
    )
    def create_court_case(matter_id: UUID, body: CourtCaseCreate) -> CourtCase:
        return _translate(lambda: service.create_court_case(matter_id, body))

    @app.post(
        "/v1/matters/{matter_id}/knowledge/resolve",
        response_model=KnowledgeSourceResolution,
        tags=["case-management"],
    )
    def resolve_knowledge_source(
        matter_id: UUID,
        body: KnowledgeSourceResolveRequest,
    ) -> KnowledgeSourceResolution:
        return _translate(lambda: service.resolve_source(matter_id, body))

    @app.post(
        "/v1/matters/{matter_id}/evidence-items",
        response_model=EvidencePromotionResult,
        tags=["case-management"],
    )
    def promote_evidence_item(
        matter_id: UUID,
        body: EvidenceItemCreate,
    ) -> EvidencePromotionResult:
        return _translate(lambda: service.promote_evidence(matter_id, body))

    @app.get(
        "/v1/matters/{matter_id}/evidence-items/{evidence_item_id}",
        response_model=EvidenceItemDetail,
        tags=["case-management"],
    )
    def get_evidence_item_detail(
        matter_id: UUID,
        evidence_item_id: UUID,
    ) -> EvidenceItemDetail:
        return _translate(lambda: service.get_evidence_detail(matter_id, evidence_item_id))

    @app.get(
        "/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/court-readiness",
        response_model=CourtReadiness,
        tags=["case-management"],
    )
    def get_evidence_item_court_readiness(
        matter_id: UUID,
        evidence_item_id: UUID,
    ) -> CourtReadiness:
        return _translate(lambda: service.get_court_readiness(matter_id, evidence_item_id))

    @app.post(
        "/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/reviews",
        response_model=EvidenceReviewResult,
        tags=["case-management"],
    )
    def review_evidence_item(
        matter_id: UUID,
        evidence_item_id: UUID,
        body: EvidenceReviewCreate,
    ) -> EvidenceReviewResult:
        return _translate(lambda: service.review_evidence(matter_id, evidence_item_id, body))

    @app.get(
        "/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/reviews",
        response_model=EvidenceReviewList,
        tags=["case-management"],
    )
    def list_evidence_reviews(
        matter_id: UUID,
        evidence_item_id: UUID,
    ) -> EvidenceReviewList:
        return _translate(lambda: service.list_evidence_reviews(matter_id, evidence_item_id))

    @app.get(
        "/v1/matters/{matter_id}/evidence-items",
        response_model=EvidenceItemList,
        tags=["case-management"],
    )
    def list_evidence_items(
        matter_id: UUID,
        review_status: ReviewState | None = Query(default=None),
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> EvidenceItemList:
        return _translate(
            lambda: service.list_evidence_items(
                matter_id,
                review_status=review_status,
                limit=limit,
                offset=offset,
            )
        )

    @app.get(
        "/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/source-content",
        response_model=OriginalSourceContent,
        tags=["case-management"],
    )
    def get_original_source_content(
        matter_id: UUID,
        evidence_item_id: UUID,
    ) -> OriginalSourceContent:
        return _translate(lambda: service.get_original_source_content(matter_id, evidence_item_id))

    @app.get(
        "/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/conversation-context",
        response_model=ConversationContext,
        tags=["case-management"],
    )
    def get_conversation_context(
        matter_id: UUID,
        evidence_item_id: UUID,
        before: Annotated[int, Query(ge=0, le=100)] = 25,
        after: Annotated[int, Query(ge=0, le=100)] = 25,
    ) -> ConversationContext:
        return _translate(
            lambda: service.get_conversation_context(
                matter_id,
                evidence_item_id,
                before=before,
                after=after,
            )
        )

    @app.get(
        "/v1/case-management/capabilities",
        response_model=CaseManagementCapabilities,
        tags=["case-management"],
    )
    def get_case_management_capabilities() -> CaseManagementCapabilities:
        return CaseManagementCapabilities.model_validate(_translate(service.get_capabilities))
