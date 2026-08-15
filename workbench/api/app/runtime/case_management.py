"""Workbench Matter routes: validated, same-origin proxies to the spine.

Byline: Codex · GPT-5 · 2026-08-15 (Matter routes and read-only readiness)
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.service import case_management as service
from app.types.case_management import (
    CourtCase,
    CourtCaseCreate,
    EvidenceItemCreate,
    EvidenceItemList,
    EvidencePromotionResult,
    EvidenceReviewCreate,
    EvidenceReviewList,
    EvidenceReviewResult,
    KnowledgeSourceRef,
    KnowledgeSourceResolution,
    Matter,
    MatterCreate,
    MatterDetail,
    MatterList,
)
from app.types.evidence_detail import CourtReadiness, EvidenceDetail

router = APIRouter(prefix="/api", tags=["matters"])


def _raise_spine(error: service.SpineError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from None


@router.get("/matters", response_model=MatterList)
def list_matters_endpoint(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    try:
        return service.list_matters(limit=limit, offset=offset)
    except service.SpineError as error:
        _raise_spine(error)


@router.post("/matters", response_model=Matter, status_code=201)
def create_matter_endpoint(payload: MatterCreate):
    try:
        return service.create_matter(payload)
    except service.SpineError as error:
        _raise_spine(error)


@router.get("/matters/{matter_id}", response_model=MatterDetail)
def get_matter_endpoint(matter_id: UUID):
    try:
        return service.get_matter(matter_id)
    except service.SpineError as error:
        _raise_spine(error)


@router.post("/matters/{matter_id}/court-cases", response_model=CourtCase, status_code=201)
def create_court_case_endpoint(matter_id: UUID, payload: CourtCaseCreate):
    try:
        return service.create_court_case(matter_id, payload)
    except service.SpineError as error:
        _raise_spine(error)


@router.post(
    "/matters/{matter_id}/knowledge/resolve",
    response_model=KnowledgeSourceResolution,
)
def resolve_knowledge_source_endpoint(matter_id: UUID, payload: KnowledgeSourceRef):
    try:
        return service.resolve_knowledge_source(matter_id, payload)
    except service.SpineError as error:
        _raise_spine(error)


@router.post(
    "/matters/{matter_id}/evidence-items",
    response_model=EvidencePromotionResult,
    status_code=201,
)
def create_evidence_item_endpoint(matter_id: UUID, payload: EvidenceItemCreate):
    try:
        return service.create_evidence_item(matter_id, payload)
    except service.SpineError as error:
        _raise_spine(error)


@router.get("/matters/{matter_id}/evidence-items", response_model=EvidenceItemList)
def list_evidence_items_endpoint(
    matter_id: UUID,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    try:
        return service.list_evidence_items(matter_id, limit=limit, offset=offset)
    except service.SpineError as error:
        _raise_spine(error)


@router.get(
    "/matters/{matter_id}/evidence-items/{evidence_item_id}",
    response_model=EvidenceDetail,
)
def get_evidence_detail_endpoint(matter_id: UUID, evidence_item_id: UUID):
    try:
        return service.get_evidence_detail(matter_id, evidence_item_id)
    except service.SpineError as error:
        _raise_spine(error)


@router.get(
    "/matters/{matter_id}/evidence-items/{evidence_item_id}/court-readiness",
    response_model=CourtReadiness,
)
def get_court_readiness_endpoint(matter_id: UUID, evidence_item_id: UUID):
    try:
        readiness = CourtReadiness.model_validate(service.get_court_readiness(matter_id, evidence_item_id))
    except service.SpineError as error:
        _raise_spine(error)
    if readiness.matter_id != matter_id or readiness.evidence_item_id != evidence_item_id:
        raise HTTPException(status_code=502, detail="Spine returned court readiness for a different evidence item")
    return readiness


@router.post(
    "/matters/{matter_id}/evidence-items/{evidence_item_id}/reviews",
    response_model=EvidenceReviewResult,
)
def review_evidence_item_endpoint(
    matter_id: UUID,
    evidence_item_id: UUID,
    payload: EvidenceReviewCreate,
):
    try:
        return service.review_evidence_item(matter_id, evidence_item_id, payload)
    except service.SpineError as error:
        _raise_spine(error)


@router.get(
    "/matters/{matter_id}/evidence-items/{evidence_item_id}/reviews",
    response_model=EvidenceReviewList,
)
def list_evidence_reviews_endpoint(matter_id: UUID, evidence_item_id: UUID):
    try:
        return service.list_evidence_reviews(matter_id, evidence_item_id)
    except service.SpineError as error:
        _raise_spine(error)
