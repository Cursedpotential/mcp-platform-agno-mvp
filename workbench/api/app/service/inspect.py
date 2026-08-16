# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: record browser, schema views, hash verify)
# Byline: Codex · GPT-5 · 2026-08-16 (neutral Data Explorer detail proxies)
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
    "patch_record_meta",
    "verify_sha256",
]


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
    return result if isinstance(result, dict) else {"records": result}


def patch_record_meta(record_id: str, patch: dict) -> dict:
    """PATCH /v1/records/{id}/meta passthrough -> the updated row.

    `patch` should only carry keys the caller explicitly set (the runtime
    layer passes `RecordMetaPatchRequest.model_dump(exclude_unset=True)`) so
    "field omitted" and "field explicitly cleared" stay distinguishable —
    same convention as app/service/files.py::update_metadata.
    """
    return spine_json("PATCH", f"/v1/records/{record_id}/meta", json=patch)


def get_schemas() -> dict:
    """GET /v1/inspect/schemas passthrough -> `{pg: {...}, weaviate: ...}`.

    Each top-level section (PostgreSQL schemas and Weaviate collections) can
    independently carry its own `{"error": ...}` per the contract — this
    module doesn't unwrap or validate that, it's the Schemas page's job to
    render whichever sections came back healthy.
    """
    return spine_json("GET", "/v1/inspect/schemas")


def get_table_detail(schema: str, table_name: str, *, limit: int = 5) -> dict:
    """Return bounded rows, columns, and indexes for one allowlisted PG table."""
    return spine_json("GET", f"/v1/inspect/tables/{schema}/{table_name}", params={"limit": limit})


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
