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

from server.case_management import service
from server.contracts.case_management import (
    CourtCase,
    CourtCaseCreate,
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


_T = TypeVar("_T")


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
