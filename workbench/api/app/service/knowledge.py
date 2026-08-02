# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (C4: Knowledge browser + Graphiti pane)
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
  DEVIATION from the build brief's "if filters aren't supported, filter
  client-side": filters ARE supported server-side (confirmed by reading
  `agno.knowledge.knowledge.Knowledge.asearch`), so `search()` below passes
  `{"domain": domain}` straight into `filters` — no client-side
  post-filtering needed. Ingested conversation docs already carry a
  `"domain"` key in their metadata (server/evidence/workflows.py sets it on
  every knowledge doc), so this filter has something real to match against.
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

from app.repo.spine_client import SpineError, spine_json

__all__ = ["SpineError", "search", "list_contents"]

_DEFAULT_CONTENT_LIMIT = 20


def search(query: str, *, domain: str | None = None, limit: int | None = None) -> dict:
    """POST /knowledge/search passthrough -> PaginatedResponse[VectorSearchResult]."""
    body: dict = {"query": query}
    if limit is not None:
        body["max_results"] = limit
    if domain:
        body["filters"] = {"domain": domain}
    return spine_json("POST", "/knowledge/search", json=body)


def list_contents(*, limit: int | None = None, offset: int | None = None) -> dict:
    """GET /knowledge/content passthrough -> PaginatedResponse[ContentResponseSchema].

    Converts the caller's 0-based `offset` into agno's 1-based `page` (the
    real query param the route accepts) — `offset=0` -> page 1, `offset=limit`
    -> page 2, etc. A non-multiple-of-limit offset rounds down to the
    containing page (agno has no arbitrary-offset pagination).
    """
    effective_limit = limit or _DEFAULT_CONTENT_LIMIT
    page = (offset // effective_limit) + 1 if offset else 1
    params: dict[str, int] = {"limit": effective_limit, "page": page}
    return spine_json("GET", "/knowledge/content", params=params)
