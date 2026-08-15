# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (C4: Knowledge browser + Graphiti pane)
# Byline: Codex · GPT-5 · 2026-08-15 (case/lane-safe multi-base adapter)
"""Knowledge search + browse — C4 read proxies to the spine's own agno
AgentOS knowledge routes.

These are NOT custom routes registered by server/api/main.py — they're
agno's built-in AgentOS knowledge router (agno/os/routers/knowledge/
knowledge.py), auto-mounted because `AgentOS(..., knowledge=[knowledge])`
is handed a live instance. Read that file directly (this platform's own
venv: .venv/Lib/site-packages/agno/os/routers/knowledge/knowledge.py)
rather than assuming shapes — verified against it 2026-07-23:

- `POST /knowledge/search` body is `VectorSearchRequestSchema`: `query`
  (required), `db_id`?, `knowledge_id`?, `vector_db_ids`?, `search_type`?,
  `max_results`?, `filters`? (an arbitrary `dict` — `Knowledge.asearch()`
  passes it straight through to `vector_db.search(filters=...)`, i.e. a
  genuine server-side metadata filter, NOT decorative), `meta`?:
  `{limit, page}`. Response: `PaginatedResponse[VectorSearchResult]` ->
  `{data: [{id, content, name, meta_data, usage, reranking_score,
  content_id, content_origin, size}], meta: {page, limit, total_pages,
  total_count, search_time_ms}}`.
  Filters ARE supported server-side (confirmed by reading
  `agno.knowledge.knowledge.Knowledge.asearch`). Case isolation therefore
  stays a pre-ranking dict filter. Lane selection is structural: it resolves
  one registered Knowledge base by deterministic `knowledge_id`; an all-lane
  search queries every allowed base independently and merges only the
  already-case-filtered results.
- `GET /knowledge/content` is the paged content-browse list ->
  `PaginatedResponse[ContentResponseSchema]` -> `{data: [{id, name,
  description, type, size, metadata, status, status_message, created_at,
  updated_at, ...}], meta: {page, limit, total_pages, total_count}}`. Query
  params are `page` (1-based) + `limit`, NOT `offset` — `list_contents()`
  below converts an offset into a page for its caller so the runtime layer
  can expose the `offset` shape the build brief asked for.

Never touches Milvus/Postgres directly — same single-reader discipline as
app/service/inspect.py (spine-mediated reads only).
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from app.repo.spine_client import SpineError, spine_json

__all__ = ["SpineError", "search", "list_contents"]

_DEFAULT_CONTENT_LIMIT = 20
_MAX_SEARCH_RESULTS = 100
_CONTENT_SCAN_PAGE_SIZE = 200
_MAX_CONTENT_SCAN_PAGES = 50
_DB_ID = "agentos-db"

# Mirrors the registered names/tables in server/api/main.py. This is an
# anti-corruption adapter for Agno's generated knowledge IDs, not a public
# platform contract. Contract tests below pin it so registry drift fails
# visibly instead of producing ambiguous multi-base 400s in production.
_KNOWLEDGE_TABLES: dict[str, str] = {
    "platform": "platform_knowledge_contents",
    "legal": "legal_knowledge_contents",
    "evidence": "evidence_knowledge_contents",
    "personal_history": "personal_history_knowledge_contents",
    "context": "platform_context_contents",
}


def _knowledge_id(lane: str) -> str:
    try:
        table = _KNOWLEDGE_TABLES[lane]
    except KeyError as exc:
        raise ValueError(f"unsupported knowledge lane: {lane}") from exc
    digest = sha256(f"{_DB_ID}:{table}:{lane}".encode()).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


def _positive_limit(limit: int | None, *, default: int, maximum: int) -> int:
    effective = default if limit is None else limit
    if effective < 1 or effective > maximum:
        raise ValueError(f"limit must be between 1 and {maximum}")
    return effective


def _require_text(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must be a non-empty string")
    return normalized


def _search_lane(query: str, *, case_id: str, lane: str, limit: int) -> dict:
    body = {
        "query": query,
        "knowledge_id": _knowledge_id(lane),
        "max_results": limit,
        # Dict filters are applied by Agno's Weaviate adapter before ranking.
        # Never use FilterExpr here: that adapter silently drops FilterExpr lists.
        "filters": {"case_id": case_id},
    }
    response = spine_json("POST", "/knowledge/search", json=body)
    for hit in response.get("data") or []:
        metadata = dict(hit.get("meta_data") or {})
        metadata.setdefault("knowledge_lane", lane)
        hit["meta_data"] = metadata
    return response


def search(
    query: str,
    *,
    case_id: str = "primary",
    lane: str | None = None,
    limit: int | None = None,
) -> dict:
    """Search one or all allowed Knowledge bases with a mandatory case prefilter."""
    normalized_query = _require_text(query, "query")
    normalized_case = _require_text(case_id, "case_id")
    effective_limit = _positive_limit(limit, default=20, maximum=_MAX_SEARCH_RESULTS)
    lanes = [lane] if lane else list(_KNOWLEDGE_TABLES)
    if lane and lane not in _KNOWLEDGE_TABLES:
        raise ValueError(f"unsupported knowledge lane: {lane}")

    responses = [
        _search_lane(normalized_query, case_id=normalized_case, lane=selected, limit=effective_limit)
        for selected in lanes
    ]
    hits: list[dict[str, Any]] = [hit for response in responses for hit in (response.get("data") or [])]
    hits.sort(
        key=lambda hit: hit.get("reranking_score") if isinstance(hit.get("reranking_score"), (int, float)) else -1,
        reverse=True,
    )
    total_count = sum(int((response.get("meta") or {}).get("total_count") or 0) for response in responses)
    return {
        "data": hits[:effective_limit],
        "meta": {
            "page": 1,
            "limit": effective_limit,
            "total_pages": 1 if total_count else 0,
            "total_count": total_count,
            "knowledge_lanes": lanes,
        },
    }


def list_contents(
    *,
    case_id: str,
    lane: str,
    limit: int | None = None,
    offset: int | None = None,
) -> dict:
    """Return a case-scoped catalog from one structural Knowledge lane.

    AgentOS cannot metadata-filter its content catalog. The trusted Workbench
    service therefore scans the selected base, filters before returning any
    row to the browser, and fails closed for rows lacking a matching case ID.
    The bounded scan reports `truncated=true` rather than claiming a complete
    catalog if the safety cap is reached.
    """
    normalized_case = _require_text(case_id, "case_id")
    if lane not in _KNOWLEDGE_TABLES:
        raise ValueError(f"unsupported knowledge lane: {lane}")
    effective_limit = _positive_limit(limit, default=_DEFAULT_CONTENT_LIMIT, maximum=100)
    effective_offset = 0 if offset is None else offset
    if effective_offset < 0:
        raise ValueError("offset must be greater than or equal to 0")

    visible: list[dict[str, Any]] = []
    total_pages = 1
    scanned_pages = 0
    for page in range(1, _MAX_CONTENT_SCAN_PAGES + 1):
        response = spine_json(
            "GET",
            "/knowledge/content",
            params={
                "limit": _CONTENT_SCAN_PAGE_SIZE,
                "page": page,
                "knowledge_id": _knowledge_id(lane),
            },
        )
        scanned_pages = page
        meta = response.get("meta") or {}
        total_pages = max(1, int(meta.get("total_pages") or 1))
        for row in response.get("data") or []:
            metadata = row.get("metadata") or {}
            if metadata.get("case_id") == normalized_case:
                row = dict(row)
                row["metadata"] = {**metadata, "knowledge_lane": lane}
                visible.append(row)
        if page >= total_pages:
            break

    truncated = scanned_pages < total_pages
    page_rows = visible[effective_offset : effective_offset + effective_limit]
    return {
        "data": page_rows,
        "meta": {
            "page": (effective_offset // effective_limit) + 1,
            "limit": effective_limit,
            "total_pages": (len(visible) + effective_limit - 1) // effective_limit,
            "total_count": len(visible),
            "knowledge_lane": lane,
            "case_id": normalized_case,
            "truncated": truncated,
        },
    }
