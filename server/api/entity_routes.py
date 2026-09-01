"""Governed canonical-entity lookup and owner-authenticated creation.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import create_engine, text
from typing_extensions import Annotated

_engine = None
EntityType = Literal[
    "person",
    "org",
    "project",
    "tech",
    "location",
    "concept",
    "phone",
    "email",
    "handle",
    "device",
    "account",
    "vehicle",
    "address",
    "court",
    "attorney",
    "school",
    "doctor",
    "institution",
    "platform",
    "ai_system",
]


class EntityCreateRequest(BaseModel):
    """A deliberate operator-created identity; never implies participation."""

    model_config = ConfigDict(extra="forbid")
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    entity_type: EntityType = "person"


def _get_engine():
    global _engine
    if _engine is None:
        from server.core.url import db_url

        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def _entity_dict(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "display_name": str(row["display_name"] or row["canonical_name"] or row["id"]),
        "entity_type": str(row["entity_type"]),
        "review_status": str(row["review_status"]),
        "safe_for_legal_use": bool(row["safe_for_legal_use"]),
    }


def list_entities(*, query: str | None, limit: int) -> list[dict[str, Any]]:
    normalized_query = (query or "").strip()
    pattern = f"%{normalized_query}%"
    with _get_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT e.id,e.display_name,e.canonical_name,e.entity_type,e.review_status,e.safe_for_legal_use, "
                "COALESCE(e.display_name,e.canonical_name,'') AS sort_name "
                "FROM registry.entity e LEFT JOIN registry.entity_alias a ON a.entity_id=e.id "
                "WHERE e.merged_into_id IS NULL AND "
                "(:query='' OR COALESCE(e.display_name,e.canonical_name,'') ILIKE :pattern OR a.alias_text ILIKE :pattern) "
                "ORDER BY sort_name,e.id LIMIT :limit"
            ),
            {"query": normalized_query, "pattern": pattern, "limit": limit},
        ).mappings()
        return [_entity_dict(row) for row in rows]


def create_entity(body: EntityCreateRequest) -> dict[str, Any]:
    normalized_name = " ".join(body.display_name.casefold().split())
    try:
        with _get_engine().begin() as conn:
            row = (
                conn.execute(
                    text(
                        "INSERT INTO registry.entity "
                        "(entity_type,display_name,canonical_name,normalized_name,data_tier,requires_human_review,review_status,safe_for_legal_use) "
                        "VALUES (CAST(:entity_type AS ai.entity_type),:display_name,:display_name,:normalized_name,'inferred',false,'approved',false) "
                        "RETURNING id,display_name,canonical_name,entity_type,review_status,safe_for_legal_use"
                    ),
                    {
                        "entity_type": body.entity_type,
                        "display_name": body.display_name,
                        "normalized_name": normalized_name,
                    },
                )
                .mappings()
                .one()
            )
    except Exception as exc:
        if "uq_entity_norm" in str(exc) or "duplicate key" in str(exc).lower():
            raise HTTPException(409, "an active entity with this type and normalized name already exists") from None
        raise
    return _entity_dict(row)


def register_entity_routes(app: FastAPI) -> None:
    @app.get("/v1/entities")
    async def entities(q: str | None = None, limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
        return {"entities": list_entities(query=q, limit=limit)}

    @app.post("/v1/entities", status_code=201)
    async def add_entity(body: EntityCreateRequest) -> dict[str, Any]:
        # The AgentOS security boundary authenticates the sole owner before
        # base-app routes run. No caller-supplied creator/reviewer is accepted.
        return create_entity(body)
