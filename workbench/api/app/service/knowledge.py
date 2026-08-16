# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (C4: Knowledge browser + Graphiti pane)
# Byline: Codex · GPT-5 · 2026-08-15 (case/lane-safe multi-base adapter)
# Byline: Codex · GPT-5 · 2026-08-16 (neutral canonical catalog + chunk detail)
"""Knowledge projection search plus canonical PostgreSQL source inspection.

Two deliberately different read surfaces live here:

- Search is a labeled Weaviate projection reached through Agno's generated
  `/knowledge/search` route. Mandatory dict filters remain pre-ranking because
  Agno's Weaviate adapter drops FilterExpr lists.
- Browse/detail is the framework-neutral `/v1/knowledge/items` contract backed
  by canonical `working.normalized_record` plus `evidence.evidence_hash` rows.
  It never imports Agno and exposes parser, chunker, source hash, records, and
  provenance needed by the Workbench operator loop.

This Workbench service never touches PostgreSQL or Weaviate directly; all reads
remain spine-mediated.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from app.repo.spine_client import SpineError, spine_json

__all__ = ["SpineError", "get_content", "list_contents", "search"]

_DEFAULT_CONTENT_LIMIT = 20
_MAX_SEARCH_RESULTS = 100
_MAX_CONTENT_ITEMS = 500
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
    """Return a case/lane-scoped catalog from the neutral canonical read API."""
    normalized_case = _require_text(case_id, "case_id")
    if lane not in _KNOWLEDGE_TABLES:
        raise ValueError(f"unsupported knowledge lane: {lane}")
    effective_limit = _positive_limit(limit, default=_DEFAULT_CONTENT_LIMIT, maximum=100)
    effective_offset = 0 if offset is None else offset
    if effective_offset < 0:
        raise ValueError("offset must be greater than or equal to 0")

    items = spine_json(
        "GET",
        "/v1/knowledge/items",
        params={"matter_id": normalized_case, "lane": lane, "limit": _MAX_CONTENT_ITEMS},
    )
    if not isinstance(items, list):
        raise SpineError("spine returned an invalid canonical knowledge catalog")

    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        artifact_id = str(item.get("artifact_id") or "")
        source_path = item.get("source_path")
        rows.append(
            {
                "id": artifact_id,
                "name": item.get("source_name") or source_path or artifact_id,
                "description": source_path,
                "type": item.get("lane") or lane,
                "status": "completed",
                "created_at": item.get("created_at"),
                "metadata": {
                    "matter_id": item.get("matter_id") or normalized_case,
                    "case_id": item.get("matter_id") or normalized_case,
                    "knowledge_lane": item.get("lane") or lane,
                    "source_path": source_path,
                    "parser_id": item.get("parser_id"),
                    "chunker_id": item.get("chunker_id"),
                    "source_sha256": item.get("source_sha256"),
                    "record_count": item.get("record_count"),
                },
            }
        )

    page_rows = rows[effective_offset : effective_offset + effective_limit]
    return {
        "data": page_rows,
        "meta": {
            "page": (effective_offset // effective_limit) + 1,
            "limit": effective_limit,
            "total_pages": (len(rows) + effective_limit - 1) // effective_limit,
            "total_count": len(rows),
            "knowledge_lane": lane,
            "case_id": normalized_case,
            "truncated": len(items) == _MAX_CONTENT_ITEMS,
        },
    }


def get_content(artifact_id: str, *, case_id: str) -> dict[str, Any]:
    """Return canonical records/chunks and custody provenance for one source."""
    normalized_artifact = _require_text(artifact_id, "artifact_id")
    normalized_case = _require_text(case_id, "case_id")
    item = spine_json(
        "GET",
        f"/v1/knowledge/items/{normalized_artifact}",
        params={"matter_id": normalized_case},
    )
    if not isinstance(item, dict):
        raise SpineError("spine returned an invalid canonical knowledge item")

    records = item.get("records")
    first = records[0] if isinstance(records, list) and records and isinstance(records[0], dict) else {}
    attrs = first.get("attrs") if isinstance(first.get("attrs"), dict) else {}
    return {
        **item,
        "source_name": attrs.get("source_name") or item.get("source_ref"),
        "source_path": attrs.get("source_path") or item.get("source_ref"),
        "parser_id": attrs.get("parser_id"),
        "chunker_id": attrs.get("chunker_id"),
        "lane": attrs.get("lane") or first.get("domain"),
    }
