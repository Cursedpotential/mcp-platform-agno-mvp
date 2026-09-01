# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: record browser, schema views, hash verify)
# Byline: Codex · GPT-5 · 2026-08-16 (neutral Data Explorer detail proxies)
# Byline: Codex · GPT-5 · 2026-08-18 (projection compatibility and table authority)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (governed third-party review proxy)
# Byline: Codex · GPT-5 · 2026-08-18 (governed entity proxy)
"""Records / Schemas / Verify — C3 read+curate proxies to the spine.

Thin bearer-authed passthroughs to the console/c3-spine's own HTTP API (a
parallel branch this module codes against, per the C3 build brief — contract
assumed, not independently verified, same posture as app/service/runs.py's
module docstring):

- `GET /v1/records?artifact_id=&run_id=&q=&limit=&offset=` -> the per-run
  record browser (parse-quality review — requirements addendum 1).
- `PATCH /v1/records/{id}/meta` -> curation edits (title/labels/attrs_patch;
  analysis-lane metadata ONLY, never evidence blobs — addendum 3).
- `GET /v1/inspect/schemas` -> raw PG schema/table/row counts and Weaviate
  collection/index metadata.
- `GET /v1/inspect/tables/{schema}/{table}` -> bounded row/field/index preview.
- `GET /v1/inspect/weaviate/{collection}` -> bounded vector/property preview.
- `POST /v1/verify/{sha256}` -> active hash verification, walking the
  H1/H2/H3 custody chain for full-tier runs (addendum 2).

Never touches PostgreSQL/Weaviate directly — every read goes through the spine,
same single-writer/single-reader discipline as app/service/runs.py.
"""

from __future__ import annotations

from app.repo.spine_client import SpineError, spine_json

__all__ = [
    "SpineError",
    "get_schemas",
    "get_table_detail",
    "get_vector_detail",
    "list_records",
    "list_entities",
    "create_entity",
    "patch_record_meta",
    "approve_third_party_conversation",
    "verify_sha256",
]

_WORKING_AUTHORED = {
    "normalized_record",
    "context_record",
    "context_archive",
    "context_asset",
    "chat_conversation",
    "chat_message",
}
_AUDIT_CONTROL_MARKERS = (
    "acquisition",
    "audit",
    "approval",
    "decision",
    "event",
    "grant",
    "ledger",
    "outbox",
    "promotion",
    "review",
    "route",
    "run",
    "task",
)


def table_authority(schema: str, table_name: str) -> str:
    """Classify authority without claiming every PostgreSQL table is canonical."""

    if schema == "evidence":
        return "authored"
    if schema in {"ops", "reference"}:
        return "audit-control"
    if schema == "working" and table_name in _WORKING_AUTHORED:
        return "authored"
    if schema == "working" and any(marker in table_name for marker in _AUDIT_CONTROL_MARKERS):
        return "audit-control"
    if schema == "analysis" and any(marker in table_name for marker in _AUDIT_CONTROL_MARKERS):
        return "audit-control"
    return "derived"


def list_records(
    *,
    artifact_id: str | None = None,
    run_id: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict:
    """GET /v1/records passthrough -> `{records: [...], total?}`.

    At least one of `artifact_id`/`run_id` is expected by the spine (the
    record browser is always scoped to one run or artifact) but that's
    enforced spine-side, not here — this stays a dumb passthrough.
    """
    params: dict[str, str | int] = {}
    if artifact_id:
        params["artifact_id"] = artifact_id
    if run_id:
        params["run_id"] = run_id
    if q:
        params["q"] = q
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    result = spine_json("GET", "/v1/records", params=params)
    # Defensive: normalize a bare list response into the documented
    # `{records: [...]}` shape so the frontend never has to branch on it.
    shaped = result if isinstance(result, dict) else {"records": result}
    records = shaped.get("records")
    if isinstance(records, list):
        for record in records:
            if isinstance(record, dict):
                record.setdefault("idx", record.get("seq"))
                record.setdefault("ts", record.get("occurred_at"))
                record.setdefault("source_kind", "unclassified")
                record.setdefault("projection_kind", "authored_normalized")
                record.setdefault("source_available_from", None)
                record.setdefault(
                    "normalized_lineage",
                    {
                        "normalized_record_id": str(record.get("id") or ""),
                        "artifact_id": str(record.get("artifact_id") or ""),
                    },
                )
                record.setdefault("third_party_conversation", None)
                record.setdefault("third_party_review", None)
                record.setdefault("realization_events", [])
    return shaped


def patch_record_meta(record_id: str, patch: dict) -> dict:
    """PATCH /v1/records/{id}/meta passthrough -> the updated row.

    `patch` should only carry keys the caller explicitly set (the runtime
    layer passes `RecordMetaPatchRequest.model_dump(exclude_unset=True)`) so
    "field omitted" and "field explicitly cleared" stay distinguishable —
    same convention as app/service/files.py::update_metadata.
    """
    return spine_json("PATCH", f"/v1/records/{record_id}/meta", json=patch)


def approve_third_party_conversation(conversation_id: str, review: dict) -> dict:
    """Forward an explicit human review; derived projection rows remain API-read-only."""

    return spine_json(
        "POST",
        f"/v1/third-party-conversations/{conversation_id}/approve",
        json=review,
    )


def list_entities(*, query: str | None = None, limit: int = 20) -> dict:
    params: dict[str, str | int] = {"limit": limit}
    if query:
        params["q"] = query
    return spine_json("GET", "/v1/entities", params=params)


def create_entity(payload: dict) -> dict:
    """Create a reviewed canonical entity; upstream derives the owner boundary."""

    return spine_json("POST", "/v1/entities", json=payload)


def get_schemas() -> dict:
    """GET /v1/inspect/schemas passthrough -> `{pg: {...}, weaviate: ...}`.

    Each top-level section (PostgreSQL schemas and Weaviate collections) can
    independently carry its own `{"error": ...}` per the contract — this
    module doesn't unwrap or validate that, it's the Schemas page's job to
    render whichever sections came back healthy.
    """
    result = spine_json("GET", "/v1/inspect/schemas")
    if not isinstance(result, dict):
        return result
    pg = result.get("pg")
    if isinstance(pg, dict):
        for schema, tables in pg.items():
            if not isinstance(tables, list):
                continue
            for table in tables:
                if isinstance(table, dict) and isinstance(table.get("table"), str):
                    table["authority"] = table_authority(schema, table["table"])
    return result


def get_table_detail(schema: str, table_name: str, *, limit: int = 5) -> dict:
    """Return bounded rows, columns, and indexes for one allowlisted PG table."""
    result = spine_json("GET", f"/v1/inspect/tables/{schema}/{table_name}", params={"limit": limit})
    if isinstance(result, dict):
        result["authority"] = table_authority(schema, table_name)
    return result


def get_vector_detail(collection_name: str, *, limit: int = 5) -> dict:
    """Return bounded properties and vector previews for one Weaviate collection."""
    return spine_json("GET", f"/v1/inspect/weaviate/{collection_name}", params={"limit": limit})


def verify_sha256(sha256: str) -> dict:
    """POST /v1/verify/{sha256} passthrough -> the verdict panel payload.

    `{sha256_match, computed, recorded, custody_tier, chain, verdict}` per
    the C3 contract — verdict is one of 'intact' | 'broken' | 'hash-only-ok'.
    Verification logic (re-fetch blob, recompute, walk the H1/H2/H3 chain)
    lives entirely spine-side; this is a bare passthrough.
    """
    return spine_json("POST", f"/v1/verify/{sha256}")
