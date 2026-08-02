# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (C4: Knowledge browser + Graphiti pane)
"""GET /api/knowledge/search, GET /api/knowledge/contents, GET
/api/graphiti/search, GET /api/graphiti/episodes — the C4 Knowledge page's
backend routes.

Thin FastAPI wrappers over app/service/knowledge.py + app/service/graphiti.py;
every SpineError/GraphitiError becomes an HTTPException with the upstream's
own error message preserved verbatim — mirrors app/runtime/inspect.py's
error-translation pattern.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.repo.spine_client import SpineError
from app.service import graphiti as graphiti_service
from app.service import knowledge as knowledge_service
from app.service.graphiti import GraphitiError

router = APIRouter(prefix="/api", tags=["knowledge"])


# ---------------------------------------------------------------------------
# Knowledge (Milvus-backed, via the spine's agno AgentOS knowledge routes)
# ---------------------------------------------------------------------------


@router.get("/knowledge/search")
async def search_knowledge_endpoint(q: str, domain: str | None = None, limit: int | None = None):
    try:
        return knowledge_service.search(q, domain=domain, limit=limit)
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/knowledge/contents")
async def list_knowledge_contents_endpoint(limit: int | None = None, offset: int | None = None):
    try:
        return knowledge_service.list_contents(limit=limit, offset=offset)
    except SpineError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


# ---------------------------------------------------------------------------
# Graphiti (Neo4j-backed knowledge-graph memory, read-only)
# ---------------------------------------------------------------------------


@router.get("/graphiti/search")
async def search_graphiti_endpoint(q: str, kind: str = "facts", limit: int | None = None):
    try:
        if kind == "nodes":
            return graphiti_service.search_nodes(q, max_nodes=limit)
        return graphiti_service.search_facts(q, max_facts=limit)
    except GraphitiError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/graphiti/episodes")
async def list_graphiti_episodes_endpoint(last: int | None = None):
    try:
        return graphiti_service.get_episodes(last=last)
    except GraphitiError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
