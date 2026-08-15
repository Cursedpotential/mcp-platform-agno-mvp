# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (C4: Knowledge browser + Graphiti pane)
# Byline: Codex · GPT-5 · 2026-08-15 (case/group-scoped browser contract)
"""GET /api/knowledge/search, GET /api/knowledge/contents, GET
/api/graphiti/search, GET /api/graphiti/episodes — the C4 Knowledge page's
backend routes.

Thin FastAPI wrappers over app/service/knowledge.py + app/service/graphiti.py;
every SpineError/GraphitiError becomes an HTTPException with the upstream's
own error message preserved verbatim — mirrors app/runtime/inspect.py's
error-translation pattern.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from app.repo.spine_client import SpineError
from app.service import graphiti as graphiti_service
from app.service import knowledge as knowledge_service
from app.service.graphiti import GraphitiError

router = APIRouter(prefix="/api", tags=["knowledge"])


# ---------------------------------------------------------------------------
# Knowledge (Weaviate-backed, via the spine's agno AgentOS knowledge routes)
# ---------------------------------------------------------------------------


@router.get("/knowledge/search")
async def search_knowledge_endpoint(
    q: Annotated[str, Query(min_length=1, max_length=2000)],
    case_id: Annotated[str, Query(min_length=1, max_length=200)] = "primary",
    lane: Literal["platform", "legal", "personal_history", "context", "evidence"] | None = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
):
    try:
        return knowledge_service.search(q, case_id=case_id, lane=lane, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/knowledge/contents")
async def list_knowledge_contents_endpoint(
    case_id: Annotated[str, Query(min_length=1, max_length=200)],
    lane: Literal["platform", "legal", "personal_history", "context", "evidence"],
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int | None, Query(ge=0)] = None,
):
    try:
        return knowledge_service.list_contents(case_id=case_id, lane=lane, limit=limit, offset=offset)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


# ---------------------------------------------------------------------------
# Graphiti (Neo4j-backed knowledge-graph memory, read-only)
# ---------------------------------------------------------------------------


@router.get("/graphiti/search")
async def search_graphiti_endpoint(
    q: Annotated[str, Query(min_length=1, max_length=2000)],
    kind: Literal["facts", "nodes"] = "facts",
    group_id: Annotated[str, Query(min_length=1, max_length=200)] = "platform",
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
):
    try:
        if kind == "nodes":
            return graphiti_service.search_nodes(q, group_ids=[group_id], max_nodes=limit)
        return graphiti_service.search_facts(q, group_ids=[group_id], max_facts=limit)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from None
    except GraphitiError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/graphiti/episodes")
async def list_graphiti_episodes_endpoint(
    group_id: Annotated[str, Query(min_length=1, max_length=200)] = "platform",
    last: Annotated[int | None, Query(ge=1, le=100)] = None,
):
    try:
        return graphiti_service.get_episodes(group_ids=[group_id], last=last)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from None
    except GraphitiError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
