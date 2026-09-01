# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (C4: Knowledge browser + Graphiti pane)
# Byline: Codex · GPT-5 · 2026-08-15 (case/lane-safe multi-base adapter)
# Byline: Codex · GPT-5 · 2026-08-16 (neutral canonical catalog + chunk detail)
# Byline: Codex · GPT-5 · 2026-08-18 (projection context overlay; records/chunks remain split)
# Byline: Codex · GPT-5 · 2026-08-18 (native horizon-prefiltered evidence search cutover)
# Byline: Codex · GPT-5 · 2026-08-18 (owner-only operator/agent-pass boundary)
# Byline: Codex · GPT-5.6-Sol · 2026-08-29 (retired AgentOS search fails closed)
"""Spine-mediated knowledge search plus canonical source inspection.

Evidence search uses the owner-only native, horizon-prefiltered route.
Semantic search for other lanes remains unavailable until a framework-neutral
projection contract exists; this adapter fails closed instead of calling the
retired AgentOS ``/knowledge/search`` endpoint.
"""

from __future__ import annotations

from typing import Any

from app.repo.platform_api_auth import PlatformAPIAuthError, evidence_operator_bearer_headers
from app.repo.spine_client import SpineError, spine_json

__all__ = ["SpineError", "get_content", "list_contents", "search"]

_DEFAULT_CONTENT_LIMIT = 20
_MAX_SEARCH_RESULTS = 100
_MAX_CONTENT_ITEMS = 500
_KNOWLEDGE_LANES = frozenset({"platform", "legal", "evidence", "personal_history", "context"})
_NATIVE_SEARCH_LANES = frozenset({"evidence"})


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


def _search_lane(
    query: str,
    *,
    case_id: str,
    lane: str,
    limit: int,
    horizon: str | None,
) -> dict:
    if lane not in _NATIVE_SEARCH_LANES:
        raise SpineError(
            f"semantic search for lane '{lane}' is disabled until its framework-neutral projection is available",
            503,
        )
    try:
        headers = evidence_operator_bearer_headers()
    except PlatformAPIAuthError as error:
        raise SpineError(str(error), 503) from None
    body: dict[str, Any] = {
        "query": query,
        "case_id": case_id,
        "limit": limit,
        "mode": "hybrid",
    }
    if horizon is not None:
        body["horizon"] = horizon
    response = spine_json(
        "POST",
        "/v1/operator/evidence/search",
        headers=headers,
        json=body,
    )
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
    horizon: str | None = None,
) -> dict:
    """Search one or all lanes with mandatory case and evidence-horizon gates."""
    normalized_query = _require_text(query, "query")
    normalized_case = _require_text(case_id, "case_id")
    effective_limit = _positive_limit(limit, default=20, maximum=_MAX_SEARCH_RESULTS)
    if lane and lane not in _KNOWLEDGE_LANES:
        raise ValueError(f"unsupported knowledge lane: {lane}")

    if lane is None:
        raise SpineError(
            "cross-lane semantic search is disabled until every requested lane has a framework-neutral projection; "
            "select the evidence lane to use native horizon-safe search",
            503,
        )
    lanes = [lane]

    responses = [
        _search_lane(
            normalized_query,
            case_id=normalized_case,
            lane=selected,
            limit=effective_limit,
            horizon=horizon,
        )
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
    if lane not in _KNOWLEDGE_LANES:
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
                    "chunk_count": item.get("chunk_count"),
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
    projection_rows: list[Any] = []
    projection_offset = 0
    projection_limit = 1000
    while True:
        projection_page = spine_json(
            "GET",
            "/v1/records",
            params={
                "artifact_id": normalized_artifact,
                "limit": projection_limit,
                "offset": projection_offset,
            },
        )
        page_rows = projection_page.get("records") if isinstance(projection_page, dict) else None
        if not isinstance(page_rows, list):
            raise SpineError("spine returned an invalid normalized-record projection page")
        projection_rows.extend(page_rows)
        projection_offset += len(page_rows)
        total = projection_page.get("total") if isinstance(projection_page, dict) else None
        if (isinstance(total, int) and projection_offset >= total) or len(page_rows) < projection_limit:
            break
        if not page_rows:
            raise SpineError("spine projection pagination made no progress")
    projection_by_id = {str(row.get("id")): row for row in projection_rows if isinstance(row, dict) and row.get("id")}
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            projection = projection_by_id.get(str(record.get("record_id")))
            if projection:
                for key in (
                    "source_kind",
                    "projection_kind",
                    "source_available_from",
                    "normalized_lineage",
                    "third_party_conversation",
                    "realization_events",
                ):
                    record[key] = projection.get(key)
            else:
                record.update(
                    {
                        "source_kind": "unclassified",
                        "projection_kind": "authored_normalized",
                        "source_available_from": None,
                        "normalized_lineage": {
                            "normalized_record_id": str(record.get("record_id") or ""),
                            "artifact_id": str(record.get("artifact_id") or normalized_artifact),
                        },
                        "third_party_conversation": None,
                        "realization_events": [],
                    }
                )
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
