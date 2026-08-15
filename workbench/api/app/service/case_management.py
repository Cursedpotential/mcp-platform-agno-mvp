"""HTTP-only adapter to the spine's framework-neutral Matter API.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

from uuid import UUID

from app.repo.spine_client import SpineError, spine_json
from app.types.case_management import (
    CourtCaseCreate,
    EvidenceItemCreate,
    EvidenceReviewCreate,
    KnowledgeSourceRef,
    MatterCreate,
)

__all__ = [
    "SpineError",
    "create_court_case",
    "create_evidence_item",
    "create_matter",
    "get_evidence_detail",
    "get_matter",
    "list_evidence_items",
    "list_evidence_reviews",
    "list_matters",
    "review_evidence_item",
    "resolve_knowledge_source",
]


def list_matters(*, limit: int = 50, offset: int = 0) -> dict:
    return spine_json("GET", "/v1/matters", params={"limit": limit, "offset": offset})


def create_matter(payload: MatterCreate) -> dict:
    return spine_json(
        "POST",
        "/v1/matters",
        json=payload.model_dump(mode="json", exclude_none=True),
    )


def get_matter(matter_id: UUID) -> dict:
    return spine_json("GET", f"/v1/matters/{matter_id}")


def create_court_case(matter_id: UUID, payload: CourtCaseCreate) -> dict:
    return spine_json(
        "POST",
        f"/v1/matters/{matter_id}/court-cases",
        json=payload.model_dump(mode="json", exclude_none=True),
    )


def resolve_knowledge_source(matter_id: UUID, payload: KnowledgeSourceRef) -> dict:
    return spine_json(
        "POST",
        f"/v1/matters/{matter_id}/knowledge/resolve",
        json=payload.model_dump(mode="json", exclude_none=True),
    )


def create_evidence_item(matter_id: UUID, payload: EvidenceItemCreate) -> dict:
    return spine_json(
        "POST",
        f"/v1/matters/{matter_id}/evidence-items",
        json=payload.model_dump(mode="json", exclude_none=True),
    )


def review_evidence_item(
    matter_id: UUID,
    evidence_item_id: UUID,
    payload: EvidenceReviewCreate,
) -> dict:
    return spine_json(
        "POST",
        f"/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/reviews",
        json=payload.model_dump(mode="json", exclude_none=True),
    )


def list_evidence_reviews(matter_id: UUID, evidence_item_id: UUID) -> dict:
    return spine_json(
        "GET",
        f"/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/reviews",
    )


def get_evidence_detail(matter_id: UUID, evidence_item_id: UUID) -> dict:
    return spine_json(
        "GET",
        f"/v1/matters/{matter_id}/evidence-items/{evidence_item_id}",
    )


def list_evidence_items(
    matter_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    return spine_json(
        "GET",
        f"/v1/matters/{matter_id}/evidence-items",
        params={"limit": limit, "offset": offset},
    )
