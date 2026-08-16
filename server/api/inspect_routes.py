"""server/api/inspect_routes.py — C3 operator-console inspectors + curation
(docs/planning/operator-console-requirements.md addenda 1, 2, 3, 6).

Registered on the base FastAPI app the same way run_routes.py/evidence_routes.py
are (base_app pattern, server/api/main.py's `_build_app`). Read paths hit
PostgreSQL/Weaviate directly and cheaply; write paths are analysis-lane ONLY —
evidence blobs/hashes (evidence.evidence_hash, evidence.source,
evidence.custody_event) are never mutated here, matching custody.py's
sole-writer guarantee (this module never imports anything that writes to the
`evidence` schema).

Routes:
  GET   /v1/records                        — paged working.normalized_record
                                              browser (addendum 1).
  GET   /v1/inspect/schemas                 — live PG table/column + Weaviate
                                              collection introspection.
  GET   /v1/inspect/tables/{schema}/{table} — bounded PG row/field previews.
  GET   /v1/inspect/weaviate/{collection}   — bounded vector/property previews.
  POST  /v1/verify/{sha256}                 — two-tier hash verification,
                                              full-tier H1/H2/H3 chain walk
                                              (addendum 2).
  POST  /v1/runs/{run_id}/parse-dryrun      — run the parser candidate chain
                                              WITHOUT storing anything.
  PATCH /v1/records/{record_id}/meta        — curate title/labels/attrs
                                              (addendum 3, attrs-only — see
                                              sql/0007_curation_and_flags.sql's
                                              header for the attrs-vs-columns
                                              decision).
  POST  /v1/flags                           — create a corroboration flag
                                              (addendum 6).
  GET   /v1/flags                           — paged/filtered flag list.
  PATCH /v1/flags/{flag_id}                 — status/notes/linked_artifacts
                                              (no DELETE — status covers
                                              lifecycle, per addendum 6).
"""
# Byline: Claude Code · Sonnet (agent) · 2026-07-22
# Byline: Codex · GPT-5 · 2026-08-16 (read-only Data Explorer contracts)

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile

from server.api.uploads import safe_upload_name
from pydantic import BaseModel
from sqlalchemy import create_engine, text

from server.core.knowledge_handle import resolve_knowledge
from server.evidence.custody import blob_root

_engine = None

# workflows.py's build_*_workflow parse_step capability strings — kept in
# lockstep by hand (same convention WORKFLOW_STAGE_NAMES in workflows.py
# already uses for stage names).
_CAPABILITY_FOR_WORKFLOW = {
    "chat-transcript": "parse.transcript",
    "sms-xml": "parse.sms-xml",
}

# GET /v1/inspect/schemas: below this live-row-count estimate
# (pg_class.reltuples), also run an exact COUNT(*) — cheap for small tables,
# and reltuples is only ever an ANALYZE-time estimate (0 for a never-
# vacuumed/analyzed table even when it has rows).
_EXACT_COUNT_THRESHOLD = 100_000
_INSPECT_SCHEMAS = ("evidence", "working", "analysis", "reference", "ops")
_TABLE_SAMPLE_MAX = 25
_CELL_PREVIEW_CHARS = 2_000
_BINARY_PREVIEW_BYTES = 256
_VECTOR_SAMPLE_MAX = 10
_VECTOR_PREVIEW_VALUES = 16

# GET /v1/records' `text` field (task spec's name; the actual DB column is
# `content` — see the docstring on `_row_to_record` for the rename decision).
_TEXT_TRUNCATE_CHARS = 2000
# POST /v1/runs/{run_id}/parse-dryrun's sample_records truncation — matches
# workflows.py's `_ledger_stage_output`'s existing convention exactly (same
# 500-char/json.dumps(default=str) shape) so a dry-run's "sample_records" and
# a real run's ledger "sample_records" look the same to a UI.
_SAMPLE_RECORD_CHARS = 500

# vendored/sbv/CUSTODY.md's H3 canonicalization (verified against
# vendored/sbv/internal/custody.go): chain_0 = "" (empty string),
# chain_i = sha256(chain_{i-1} + "\n" + H2_i_hex). This is the SBV chain
# and is what reconcile_sbv_import batches store, so it is what this module
# must recompute. NOTE (2026-08-02, owner-verified 2026-08-01): the Case
# Bible chain (genesis = H1, chain_i = sha256(prev_hex + h2_hex)) is a
# SECOND, equally valid construction used by the Case Bible vault — the
# earlier claim here that "genesis = H1 is INCORRECT" was itself wrong.
# Both currently share tag h3-chain-v1; match the construction to the
# writer that produced the batch being verified.
_H3_GENESIS = ""
_H3_SEPARATOR = "\n"


def _get_engine():
    global _engine
    if _engine is None:
        from server.core.url import db_url

        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def _sha256_file(path: Path) -> str:
    """Byte-identical to server/evidence/custody.py's private `_sha256_file`
    (streaming SHA-256) — duplicated rather than imported across the
    underscore-prefixed boundary so this module doesn't reach into custody.py
    internals; the two must stay in lockstep (both are literally `hashlib.
    sha256()` over 1MiB chunks — no room for drift)."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _jsonb(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def _preview_value(value: Any) -> Any:
    """Return a bounded JSON-safe representation for an operator row preview."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        return {
            "encoding": "hex",
            "byte_length": len(value),
            "preview": value[:_BINARY_PREVIEW_BYTES].hex(),
            "truncated": len(value) > _BINARY_PREVIEW_BYTES,
        }
    if isinstance(value, str):
        if len(value) <= _CELL_PREVIEW_CHARS:
            return value
        return {
            "preview": value[:_CELL_PREVIEW_CHARS],
            "character_length": len(value),
            "truncated": True,
        }
    if isinstance(value, (dict, list, tuple)):
        serialized = json.dumps(value, default=str, ensure_ascii=False)
        if len(serialized) <= _CELL_PREVIEW_CHARS:
            return json.loads(serialized)
        return {
            "preview": serialized[:_CELL_PREVIEW_CHARS],
            "character_length": len(serialized),
            "truncated": True,
        }
    return str(value)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


# =============================================================================
# GET /v1/records — paged working.normalized_record browser (addendum 1)
# =============================================================================


def _row_to_record(row: dict[str, Any]) -> dict[str, Any]:
    """Shape one working.normalized_record row for the API response.

    DEVIATION from the task spec's literal column list ("record id, idx/seq,
    record_type, role/participants, ts fields, text ... attrs") — read
    verbatim from sql/0003_normalized_records.sql and server/evidence/
    store.py before writing this: normalized_record has NO `idx`/`seq`
    column (never did) and its text column is named `content`, not `text`.
    This function:
      - renames `content` -> `text` in the response (matches the task's
        field name; the DB column stays `content`, unchanged — see
        sql/0007's header for why no new column was added);
      - truncates `text` to 2000 chars, adding `full_len` (the untruncated
        length) exactly as the spec asks;
      - synthesizes `seq` from a SQL window function
        (`row_number() OVER (PARTITION BY artifact_id ORDER BY occurred_at
        NULLS LAST, id)` — see the caller's SELECT), NOT a stored column —
        it's the record's 1-based position in this artifact's chronological
        order (occurred_at, NULLS LAST, then id as a stable tiebreak — same
        ordering convention server/evidence/store.py's
        `load_records_for_artifact` already uses for its retry path).
    """
    full_text = row.get("content") or ""
    return {
        "id": str(row["id"]),
        "seq": row["seq"],
        "artifact_id": str(row["artifact_id"]),
        "record_type": row["record_type"],
        "source": row["source"],
        "conversation_id": row["conversation_id"],
        "role": row["role"],
        "participants": _jsonb(row["participants"]) or [],
        "occurred_at": row["occurred_at"],
        "knowledge_time": row["knowledge_time"],
        "disclosure_tier": row["disclosure_tier"],
        "text": full_text[:_TEXT_TRUNCATE_CHARS],
        "full_len": len(full_text),
        "attrs": _jsonb(row["attrs"]) or {},
        "created_at": row["created_at"],
    }


def _resolve_artifact_id(artifact_id: str | None, run_id: str | None) -> str:
    """GET /v1/records' artifact_id resolution: explicit artifact_id wins;
    otherwise resolve via run_id -> ops.workflow_run.artifact_id (the
    run ledger's own `get_run`, so this stays consistent with run_routes.py's
    view of a run). 422 if neither is given; 404 if run_id doesn't resolve to
    an artifact yet (e.g. the run hasn't reached the custody stage)."""
    if artifact_id:
        return artifact_id
    if not run_id:
        raise HTTPException(422, "one of artifact_id or run_id is required")
    from server.evidence.run_ledger import get_run

    run = get_run(run_id)
    if run is None:
        raise HTTPException(404, f"run {run_id!r} not found")
    resolved = run.get("artifact_id")
    if not resolved:
        raise HTTPException(404, f"run {run_id!r} has no artifact_id yet (custody stage hasn't completed)")
    return resolved


def _register_records_routes(app: FastAPI) -> None:
    @app.get("/v1/records")
    async def list_records(
        artifact_id: str | None = Query(None),
        run_id: str | None = Query(None),
        q: str | None = Query(None),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        resolved_artifact_id = _resolve_artifact_id(artifact_id, run_id)

        where = ["artifact_id = :artifact_id"]
        params: dict[str, Any] = {"artifact_id": resolved_artifact_id}
        if q:
            where.append("content ILIKE :q")
            params["q"] = f"%{q}%"
        where_clause = " AND ".join(where)

        with _get_engine().connect() as conn:
            total = conn.execute(
                text(f"SELECT count(*) FROM working.normalized_record WHERE {where_clause}"), params
            ).scalar()
            rows = (
                conn.execute(
                    text(
                        "SELECT id, artifact_id, record_type, source, conversation_id, role, participants, "
                        "content, occurred_at, knowledge_time, disclosure_tier, attrs, created_at, "
                        "row_number() OVER (PARTITION BY artifact_id ORDER BY occurred_at NULLS LAST, id) AS seq "
                        f"FROM working.normalized_record WHERE {where_clause} "
                        "ORDER BY occurred_at NULLS LAST, id "
                        "LIMIT :limit OFFSET :offset"
                    ),
                    {**params, "limit": limit, "offset": offset},
                )
                .mappings()
                .all()
            )

        return {
            "artifact_id": resolved_artifact_id,
            "total": total or 0,
            "limit": limit,
            "offset": offset,
            "records": [_row_to_record(dict(r)) for r in rows],
        }


# =============================================================================
# GET /v1/inspect/schemas — live PG table/column + Weaviate collection
# introspection
# =============================================================================


def _inspect_pg_schemas() -> dict[str, Any]:
    with _get_engine().connect() as conn:
        table_rows = (
            conn.execute(
                text(
                    "SELECT n.nspname AS schema, c.relname AS table_name, c.reltuples::bigint AS est_rows "
                    "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = ANY(:schemas) AND c.relkind = 'r' "
                    "ORDER BY n.nspname, c.relname"
                ),
                {"schemas": list(_INSPECT_SCHEMAS)},
            )
            .mappings()
            .all()
        )
        column_rows = (
            conn.execute(
                text(
                    "SELECT table_schema, table_name, column_name, data_type, ordinal_position "
                    "FROM information_schema.columns "
                    "WHERE table_schema = ANY(:schemas) "
                    "ORDER BY table_schema, table_name, ordinal_position"
                ),
                {"schemas": list(_INSPECT_SCHEMAS)},
            )
            .mappings()
            .all()
        )

        columns_by_table: dict[tuple[str, str], list[dict[str, str]]] = {}
        for c in column_rows:
            key = (c["table_schema"], c["table_name"])
            columns_by_table.setdefault(key, []).append({"name": c["column_name"], "type": c["data_type"]})

        out: dict[str, list[dict[str, Any]]] = {s: [] for s in _INSPECT_SCHEMAS}
        for t in table_rows:
            schema, table_name = t["schema"], t["table_name"]
            est_rows = max(int(t["est_rows"] or 0), 0)
            row_count = est_rows
            is_estimate = True
            if est_rows < _EXACT_COUNT_THRESHOLD:
                # Exact count for small tables (task spec) — reltuples is
                # only an ANALYZE-time estimate (can read 0 on a table that
                # genuinely has rows but was never vacuumed/analyzed).
                qualified = f"{_quote_identifier(schema)}.{_quote_identifier(table_name)}"
                exact = conn.execute(text(f"SELECT count(*) FROM {qualified}")).scalar()
                row_count = exact or 0
                is_estimate = False
            out.setdefault(schema, []).append(
                {
                    "table": table_name,
                    "row_count": row_count,
                    "row_count_is_estimate": is_estimate,
                    "columns": columns_by_table.get((schema, table_name), []),
                }
            )
    return out


def _inspect_pg_table(schema: str, table_name: str, *, limit: int) -> dict[str, Any]:
    """Inspect one allowlisted table after resolving its exact catalog identity."""
    if schema not in _INSPECT_SCHEMAS:
        raise HTTPException(422, f"schema must be one of {list(_INSPECT_SCHEMAS)}")
    if not 1 <= limit <= _TABLE_SAMPLE_MAX:
        raise HTTPException(422, f"limit must be between 1 and {_TABLE_SAMPLE_MAX}")

    with _get_engine().connect() as conn:
        exists = conn.execute(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = :table_name AND table_type = 'BASE TABLE'"
                ")"
            ),
            {"schema": schema, "table_name": table_name},
        ).scalar()
        if not exists:
            raise HTTPException(404, f"table {schema}.{table_name} not found")

        columns = (
            conn.execute(
                text(
                    "SELECT column_name, data_type, udt_name, is_nullable, column_default, ordinal_position "
                    "FROM information_schema.columns "
                    "WHERE table_schema = :schema AND table_name = :table_name "
                    "ORDER BY ordinal_position"
                ),
                {"schema": schema, "table_name": table_name},
            )
            .mappings()
            .all()
        )
        indexes = (
            conn.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes "
                    "WHERE schemaname = :schema AND tablename = :table_name ORDER BY indexname"
                ),
                {"schema": schema, "table_name": table_name},
            )
            .mappings()
            .all()
        )
        qualified = f"{_quote_identifier(schema)}.{_quote_identifier(table_name)}"
        samples = conn.execute(text(f"SELECT * FROM {qualified} LIMIT :limit"), {"limit": limit}).mappings().all()

    return {
        "schema": schema,
        "table": table_name,
        "limit": limit,
        "columns": [
            {
                "name": row["column_name"],
                "type": row["data_type"],
                "database_type": row["udt_name"],
                "nullable": row["is_nullable"] == "YES",
                "default": row["column_default"],
                "position": row["ordinal_position"],
            }
            for row in columns
        ],
        "indexes": [{"name": row["indexname"], "definition": row["indexdef"]} for row in indexes],
        "rows": [{key: _preview_value(value) for key, value in row.items()} for row in samples],
    }


def _weaviate_client(knowledge: Any) -> Any:
    client = None
    vector_db = getattr(knowledge, "vector_db", None) if knowledge is not None else None
    if vector_db is not None and getattr(vector_db, "get_client", None) is not None:
        client = vector_db.get_client()
    if client is None:
        from server.core.session import get_weaviate_client

        client = get_weaviate_client()
    return client


def _collection_configs(client: Any, *, detailed: bool) -> dict[str, Any]:
    try:
        return client.collections.list_all(simple=not detailed)
    except TypeError:
        # Compatibility with older/fake clients whose list_all had no simple flag.
        return client.collections.list_all()


def _inspect_weaviate_collections(knowledge: Any) -> Any:
    """Guarded (task spec: "guard failures -> {"error"}") — returns a list of
    {name, fields, num_entities} on success, or {"error": str} on any failure
    (Weaviate down, collection introspection error, missing client).
    ADR-0040 cutover 2026-07-29: inspects Weaviate, not Milvus."""
    try:
        client = _weaviate_client(knowledge)

        collections = []
        for name, cfg in _collection_configs(client, detailed=True).items():
            fields = [
                {
                    "name": p.name,
                    "type": str(p.data_type),
                    "index_filterable": getattr(p, "index_filterable", None),
                    "index_searchable": getattr(p, "index_searchable", None),
                }
                for p in (cfg.properties or [])
            ]
            try:
                agg = client.collections.get(name).aggregate.over_all(total_count=True)
                num_entities = agg.total_count
            except Exception:
                num_entities = None
            raw = cfg.to_dict() if callable(getattr(cfg, "to_dict", None)) else {}
            collections.append(
                {
                    "name": name,
                    "description": getattr(cfg, "description", None),
                    "fields": fields,
                    "num_entities": num_entities,
                    "vectorizer": raw.get("vectorizer") or getattr(cfg, "vectorizer", None),
                    "vector_index_type": raw.get("vectorIndexType")
                    or str(getattr(cfg, "vector_index_type", "") or "")
                    or None,
                    "vector_index_config": raw.get("vectorIndexConfig"),
                    "named_vectors": raw.get("vectorConfig"),
                }
            )
        return collections
    except Exception as exc:
        return {"error": str(exc)[:300]}


def _vector_previews(vector: Any) -> list[dict[str, Any]]:
    values_by_name = vector if isinstance(vector, dict) else {"default": vector}
    previews = []
    for name, values in values_by_name.items():
        if not isinstance(values, (list, tuple)):
            continue
        previews.append(
            {
                "name": str(name),
                "dimensions": len(values),
                "preview": [float(value) for value in values[:_VECTOR_PREVIEW_VALUES]],
                "truncated": len(values) > _VECTOR_PREVIEW_VALUES,
            }
        )
    return previews


def _inspect_weaviate_objects(knowledge: Any, collection_name: str, *, limit: int) -> dict[str, Any]:
    """Return bounded object metadata and short vector previews for one collection."""
    if not 1 <= limit <= _VECTOR_SAMPLE_MAX:
        raise HTTPException(422, f"limit must be between 1 and {_VECTOR_SAMPLE_MAX}")
    try:
        client = _weaviate_client(knowledge)
        configs = _collection_configs(client, detailed=False)
        if collection_name not in configs:
            raise HTTPException(404, f"Weaviate collection {collection_name!r} not found")
        result = client.collections.get(collection_name).query.fetch_objects(limit=limit, include_vector=True)
        objects = []
        for item in result.objects:
            objects.append(
                {
                    "uuid": str(item.uuid),
                    "properties": _preview_value(dict(item.properties or {})),
                    "vectors": _vector_previews(item.vector),
                }
            )
        return {"collection": collection_name, "limit": limit, "objects": objects}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"Weaviate inspection failed: {str(exc)[:300]}") from None


def _register_schemas_route(app: FastAPI, knowledge: Any) -> None:
    @app.get("/v1/inspect/schemas")
    async def inspect_schemas() -> dict[str, Any]:
        vector = _inspect_weaviate_collections(resolve_knowledge(knowledge))
        return {
            "pg": _inspect_pg_schemas(),
            "weaviate": vector,
            "milvus": vector,  # deprecated compatibility alias (ADR-0040 cutover)
        }

    @app.get("/v1/inspect/tables/{schema}/{table_name}")
    async def inspect_table(schema: str, table_name: str, limit: int = Query(5, ge=1, le=_TABLE_SAMPLE_MAX)):
        return _inspect_pg_table(schema, table_name, limit=limit)

    @app.get("/v1/inspect/weaviate/{collection_name}")
    async def inspect_weaviate_collection(collection_name: str, limit: int = Query(5, ge=1, le=_VECTOR_SAMPLE_MAX)):
        return _inspect_weaviate_objects(resolve_knowledge(knowledge), collection_name, limit=limit)


# =============================================================================
# POST /v1/verify/{sha256} — two-tier hash verification (addendum 2)
# =============================================================================


def _lookup_h1(conn, sha256_hex: str) -> dict[str, Any] | None:
    row = (
        conn.execute(
            text(
                "SELECT id, source_id, blob_key, meta, hashed_at "
                "FROM evidence.evidence_hash "
                "WHERE algo = 'sha256' AND digest = :d AND level = 'H1' "
                "ORDER BY hashed_at ASC LIMIT 1"
            ),
            {"d": bytes.fromhex(sha256_hex)},
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def _walk_h3_chain(h2_hexes_in_order: list[str], stored_h3_hex: str | None) -> list[dict[str, Any]]:
    """Recompute the H3 chain over an ordered list of H2 hex digests using
    the SBV canonicalization (vendored/sbv/CUSTODY.md, cross-checked against
    vendored/sbv/internal/custody.go), which is what reconcile_sbv_import
    batches store: ``chain_0 = "" ; chain_i = sha256(chain_{i-1} + "\\n" +
    H2_i)``. (The Case Bible vault uses a different, equally valid H1-genesis
    construction — owner-verified 2026-08-01; do not "correct" one to the
    other. Match the construction to the batch's writer.) Folded
    left-to-right in raw source/parse order (record_locator->>'record_index'
    ASC) — H1 never enters the H3 computation at all.

    Only the FINAL link has anything stored to compare against
    (evidence.evidence_hash's single level='H3' row per import batch —
    reconcile_sbv_import() never persists intermediate chain values, only
    the batch's final `sbv_chain_hash`) — so `expected`/`ok` are only
    meaningful on the last element; every earlier element reports the
    computed running value with `ok=True` (nothing to falsify it against
    yet) so an operator can still see/audit the fold step by step. This is a
    deliberate, documented shape decision (not a bug) given what's actually
    persisted today.
    """
    chain = _H3_GENESIS
    links: list[dict[str, Any]] = []
    n = len(h2_hexes_in_order)
    for i, h2_hex in enumerate(h2_hexes_in_order, start=1):
        chain = hashlib.sha256((chain + _H3_SEPARATOR + h2_hex).encode("utf-8")).hexdigest()
        is_last = i == n
        expected = stored_h3_hex if is_last else None
        ok = (chain == stored_h3_hex) if (is_last and stored_h3_hex is not None) else True
        links.append({"seq": i, "ok": ok, "expected": expected, "actual": chain})
    return links


def _register_verify_route(app: FastAPI) -> None:
    @app.post("/v1/verify/{sha256}")
    async def verify_hash(sha256: str) -> dict[str, Any]:
        """Two-tier hash verification (addendum 2):
          1. Locate the artifact by sha256 (custody store, level='H1').
          2. Re-fetch the blob the SAME access path custody.py wrote it
             (blob_root() / blob_key) and recompute sha256.
          3. custody_tier == 'light': stop here (whole-file integrity only —
             addendum 2's "two-tier custody" decision: knowledge-lane pours
             get no H2/H3 chain, by design).
          4. custody_tier == 'full' AND H2/H3 rows exist (this artifact went
             through reconcile_sbv_import — most chat-transcript/plain
             custody-only runs never do): walk the H3 chain (see
             `_walk_h3_chain`'s docstring for the corrected canonicalization).
             'full' WITHOUT any H2/H3 rows (the common case for a full-tier
             artifact that was only ever linear-ingested, never SBV-
             reconciled) has nothing to walk — reported as 'hash-only-ok',
             not 'broken': there is no chain to be broken.

        Response: {sha256_match, computed, recorded, custody_tier,
        chain: [{seq, ok, expected, actual}] | None,
        verdict: 'intact' | 'broken' | 'hash-only-ok'}.
        """
        try:
            bytes.fromhex(sha256)
        except ValueError:
            raise HTTPException(422, f"sha256 {sha256!r} is not valid hex") from None

        with _get_engine().connect() as conn:
            h1 = _lookup_h1(conn, sha256)
            if h1 is None:
                raise HTTPException(404, f"no custody record for sha256={sha256!r}")

            meta = _jsonb(h1["meta"]) or {}
            custody_tier = meta.get("custody_tier", "full")
            recorded_hex = sha256.lower()

            blob_key = h1["blob_key"]
            blob_path = blob_root() / blob_key if blob_key else None
            computed: str | None = None
            if blob_path is not None and blob_path.is_file():
                computed = _sha256_file(blob_path)
            sha256_match = computed is not None and computed.lower() == recorded_hex

            chain: list[dict[str, Any]] | None = None
            if custody_tier == "full" and h1["source_id"] is not None:
                h2_rows = (
                    conn.execute(
                        text(
                            "SELECT digest, record_locator FROM evidence.evidence_hash "
                            "WHERE level = 'H2' AND source_id = :sid "
                            "ORDER BY (record_locator->>'record_index')::int ASC"
                        ),
                        {"sid": h1["source_id"]},
                    )
                    .mappings()
                    .all()
                )
                if h2_rows:
                    h3_row = (
                        conn.execute(
                            text(
                                "SELECT digest FROM evidence.evidence_hash "
                                "WHERE level = 'H3' AND source_id = :sid "
                                "ORDER BY hashed_at DESC LIMIT 1"
                            ),
                            {"sid": h1["source_id"]},
                        )
                        .mappings()
                        .first()
                    )
                    stored_h3_hex = h3_row["digest"].hex() if h3_row is not None else None
                    h2_hexes = [row["digest"].hex() for row in h2_rows]
                    chain = _walk_h3_chain(h2_hexes, stored_h3_hex)

        if not sha256_match:
            verdict = "broken"
        elif chain is not None:
            verdict = "intact" if all(link["ok"] for link in chain) else "broken"
        else:
            verdict = "hash-only-ok"

        return {
            "sha256_match": sha256_match,
            "computed": computed,
            "recorded": recorded_hex,
            "custody_tier": custody_tier,
            "chain": chain,
            "verdict": verdict,
        }


# =============================================================================
# POST /v1/runs/{run_id}/parse-dryrun — run the parser candidate chain
# WITHOUT storing anything
# =============================================================================


def _register_parse_dryrun_route(app: FastAPI) -> None:
    @app.post("/v1/runs/{run_id}/parse-dryrun")
    async def parse_dryrun(
        run_id: str,
        file: UploadFile | None = File(None),
        sha256: str | None = Form(None),
    ) -> dict[str, Any]:
        """`run_id` anchors WHICH capability to dry-run against (the run's
        own `workflow` — 'chat-transcript' -> 'parse.transcript', 'sms-xml'
        -> 'parse.sms-xml'; see `_CAPABILITY_FOR_WORKFLOW`), not which bytes
        to parse — that's `file` (a fresh multipart upload) XOR `sha256`
        (re-parse an ALREADY-in-custody artifact by digest, any prior
        artifact, not necessarily this run's own — read back via the SAME
        blob_root()/blob_key path custody.py wrote it). Exactly one of the
        two must be given.

        Runs `server.tools.registry.resolve(capability, ...)`'s candidate
        chain the SAME way server/evidence/workflows.py's `parse_step` does
        (this turned out to be directly reusable with zero detachment
        hacks — parse_step's only real dependency beyond the registry is
        `ctx["source_meta"]`, which this endpoint defaults to `{}`), but
        NEVER calls store_records()/ingest_into_knowledge() — nothing is
        persisted.

        Returns {attempts: [{tool, ok, confidence?, error?}], winning_parser_id,
        record_count, sample_records (<=3, trimmed), parse_stats}.
        """
        if file is not None and sha256:
            raise HTTPException(422, "provide either a multipart file or {sha256}, not both")
        if file is None and not sha256:
            raise HTTPException(422, "provide either a multipart file or {sha256}")

        if run_id == "new":
            # Sentinel used by the console for staged files with no run yet
            # (workbench service/runs.py::parse_dryrun): no ledger lookup —
            # default to the bootstrap vertical's parser capability.
            workflow = "chat-transcript"
        else:
            from server.evidence.run_ledger import get_run

            run = get_run(run_id)
            if run is None:
                raise HTTPException(404, f"run {run_id!r} not found")
            workflow = run["workflow"]
        capability = _CAPABILITY_FOR_WORKFLOW.get(workflow)
        if capability is None:
            raise HTTPException(422, f"unknown workflow {workflow!r}")

        tmpdir = Path(tempfile.mkdtemp(prefix="parse-dryrun-"))
        try:
            if file is not None:
                name = safe_upload_name(file.filename)
                p = tmpdir / name
                p.write_bytes(await file.read())
            else:
                with _get_engine().connect() as conn:
                    h1 = _lookup_h1(conn, sha256)  # type: ignore[arg-type]
                if h1 is None or not h1["blob_key"]:
                    raise HTTPException(404, f"no custody record for sha256={sha256!r}")
                src = blob_root() / h1["blob_key"]
                if not src.is_file():
                    raise HTTPException(404, f"custody blob for sha256={sha256!r} is missing on disk")
                name = src.name
                p = tmpdir / name
                shutil.copyfile(src, p)

            from server.tools.registry import load_builtin_tools, registry

            load_builtin_tools()
            candidates = registry.resolve(capability, media_hint=name.lower(), size_bytes=p.stat().st_size)

            attempts: list[dict[str, Any]] = []
            winning_parser_id: str | None = None
            records: list[dict[str, Any]] | None = None
            parse_stats: dict[str, Any] = {}
            for tool in candidates:
                try:
                    result = tool.run({"path": str(p), "source_meta": {}})
                    stats = result.get("stats", {})
                    attempts.append({"tool": tool.id, "ok": True, "confidence": stats.get("confidence")})
                    winning_parser_id = tool.id
                    records = result["records"]
                    parse_stats = stats
                    break
                except Exception as exc:
                    attempts.append({"tool": tool.id, "ok": False, "error": str(exc)})

            return {
                "attempts": attempts,
                "winning_parser_id": winning_parser_id,
                "record_count": len(records) if records is not None else 0,
                "sample_records": [json.dumps(r, default=str)[:_SAMPLE_RECORD_CHARS] for r in (records or [])[:3]],
                "parse_stats": parse_stats,
            }
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# =============================================================================
# PATCH /v1/records/{record_id}/meta — curation (addendum 3, attrs-only)
# =============================================================================


class RecordMetaPatch(BaseModel):
    title: str | None = None
    labels: list[str] | None = None
    attrs_patch: dict[str, Any] | None = None


def _register_record_meta_route(app: FastAPI) -> None:
    @app.patch("/v1/records/{record_id}/meta")
    async def patch_record_meta(record_id: str, body: RecordMetaPatch) -> dict[str, Any]:
        """Merges into `attrs` ONLY — never touches `content` or any
        evidence-provenance field (artifact_id, occurred_at, etc.). Uses
        Postgres jsonb `||` (shallow merge, right-hand side wins on
        top-level key collisions) so this is a single atomic UPDATE, not a
        read-modify-write race.
        """
        patch: dict[str, Any] = {}
        if body.title is not None:
            patch["title"] = body.title
        if body.labels is not None:
            patch["labels"] = body.labels
        if body.attrs_patch:
            patch.update(body.attrs_patch)
        if not patch:
            raise HTTPException(422, "at least one of title/labels/attrs_patch must be given")

        with _get_engine().begin() as conn:
            row = (
                conn.execute(
                    text(
                        "UPDATE working.normalized_record "
                        "SET attrs = attrs || CAST(:patch AS jsonb) "
                        "WHERE id = :id "
                        "RETURNING id, artifact_id, record_type, source, conversation_id, role, "
                        "         participants, content, occurred_at, knowledge_time, disclosure_tier, "
                        "         attrs, created_at"
                    ),
                    {"id": record_id, "patch": json.dumps(patch)},
                )
                .mappings()
                .first()
            )
        if row is None:
            raise HTTPException(404, f"record {record_id!r} not found")
        out = _row_to_record({**dict(row), "seq": None})
        return out


# =============================================================================
# Corroboration flags — POST/GET/PATCH /v1/flags (addendum 6)
# =============================================================================

_ALLOWED_TARGET_KINDS = {"record", "knowledge", "run"}
_ALLOWED_FLAG_STATUSES = {"open", "partial", "corroborated", "unobtainable"}


class FlagCreate(BaseModel):
    target_kind: str
    target_id: str
    claim: str
    claim_date_start: str | None = None
    claim_date_end: str | None = None
    evidence_wanted: list[str] | None = None
    status: str = "open"
    linked_artifacts: list[dict[str, Any]] | None = None
    notes: str | None = None


class FlagPatch(BaseModel):
    status: str | None = None
    notes: str | None = None
    linked_artifacts_append: list[dict[str, Any]] | None = None


def _row_to_flag(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "flag_id": str(row["flag_id"]),
        "target_kind": row["target_kind"],
        "target_id": row["target_id"],
        "claim": row["claim"],
        "claim_date_start": row["claim_date_start"],
        "claim_date_end": row["claim_date_end"],
        "evidence_wanted": row["evidence_wanted"] or [],
        "status": row["status"],
        "linked_artifacts": _jsonb(row["linked_artifacts"]) or [],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _register_flags_routes(app: FastAPI) -> None:
    @app.post("/v1/flags", status_code=201)
    async def create_flag(body: FlagCreate) -> dict[str, Any]:
        if body.target_kind not in _ALLOWED_TARGET_KINDS:
            raise HTTPException(
                422, f"unknown target_kind {body.target_kind!r}; allowed: {sorted(_ALLOWED_TARGET_KINDS)}"
            )
        if body.status not in _ALLOWED_FLAG_STATUSES:
            raise HTTPException(422, f"unknown status {body.status!r}; allowed: {sorted(_ALLOWED_FLAG_STATUSES)}")

        with _get_engine().begin() as conn:
            row = (
                conn.execute(
                    text(
                        "INSERT INTO analysis.corroboration_flag "
                        "(target_kind, target_id, claim, claim_date_start, claim_date_end, "
                        " evidence_wanted, status, linked_artifacts, notes) "
                        "VALUES (:target_kind, :target_id, :claim, :claim_date_start, :claim_date_end, "
                        " :evidence_wanted, :status, CAST(:linked_artifacts AS jsonb), :notes) "
                        "RETURNING *"
                    ),
                    {
                        "target_kind": body.target_kind,
                        "target_id": body.target_id,
                        "claim": body.claim,
                        "claim_date_start": body.claim_date_start,
                        "claim_date_end": body.claim_date_end,
                        "evidence_wanted": body.evidence_wanted,
                        "status": body.status,
                        "linked_artifacts": json.dumps(body.linked_artifacts or []),
                        "notes": body.notes,
                    },
                )
                .mappings()
                .first()
            )
        return _row_to_flag(dict(row))

    @app.get("/v1/flags")
    async def list_flags(
        status: str | None = Query(None),
        target_kind: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        where = []
        params: dict[str, Any] = {}
        if status is not None:
            where.append("status = :status")
            params["status"] = status
        if target_kind is not None:
            where.append("target_kind = :target_kind")
            params["target_kind"] = target_kind
        where_clause = f"WHERE {' AND '.join(where)}" if where else ""

        with _get_engine().connect() as conn:
            total = conn.execute(
                text(f"SELECT count(*) FROM analysis.corroboration_flag {where_clause}"), params
            ).scalar()
            rows = (
                conn.execute(
                    text(
                        f"SELECT * FROM analysis.corroboration_flag {where_clause} "
                        "ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
                    ),
                    {**params, "limit": limit, "offset": offset},
                )
                .mappings()
                .all()
            )
        return {
            "total": total or 0,
            "limit": limit,
            "offset": offset,
            "flags": [_row_to_flag(dict(r)) for r in rows],
        }

    @app.patch("/v1/flags/{flag_id}")
    async def patch_flag(flag_id: str, body: FlagPatch) -> dict[str, Any]:
        if body.status is not None and body.status not in _ALLOWED_FLAG_STATUSES:
            raise HTTPException(422, f"unknown status {body.status!r}; allowed: {sorted(_ALLOWED_FLAG_STATUSES)}")
        if body.status is None and body.notes is None and body.linked_artifacts_append is None:
            raise HTTPException(422, "at least one of status/notes/linked_artifacts_append must be given")

        sets = ["updated_at = now()"]
        params: dict[str, Any] = {"id": flag_id}
        if body.status is not None:
            sets.append("status = :status")
            params["status"] = body.status
        if body.notes is not None:
            sets.append("notes = :notes")
            params["notes"] = body.notes
        if body.linked_artifacts_append is not None:
            sets.append("linked_artifacts = linked_artifacts || CAST(:append AS jsonb)")
            params["append"] = json.dumps(body.linked_artifacts_append)

        with _get_engine().begin() as conn:
            row = (
                conn.execute(
                    text(f"UPDATE analysis.corroboration_flag SET {', '.join(sets)} WHERE flag_id = :id RETURNING *"),
                    params,
                )
                .mappings()
                .first()
            )
        if row is None:
            raise HTTPException(404, f"flag {flag_id!r} not found")
        return _row_to_flag(dict(row))


# =============================================================================
# Registration
# =============================================================================


def register_inspect_routes(app: FastAPI, knowledge: Any) -> None:
    """Register every C3 inspector/curation route on the FastAPI app.

    Parameters
    ----------
    app:
        The FastAPI application instance (base app, pre-AgentOS wrap).
    knowledge:
        Agno Knowledge instance (or a `server.core.knowledge_handle.
        KnowledgeHandle`, C3 addendum 9) — used only by the Weaviate
        collection/vector inspection routes and resolved fresh per request
        via `resolve_knowledge()`.
    """
    _register_records_routes(app)
    _register_schemas_route(app, knowledge)
    _register_verify_route(app)
    _register_parse_dryrun_route(app)
    _register_record_meta_route(app)
    _register_flags_routes(app)
