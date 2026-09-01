# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""LanceDB `staged_files` table — CRUD for the whole-file staging store.

New in the workbench (no donor equivalent). This is the single source of
truth for what's queued for promotion; it holds whole files (id = sha256),
never chunks or embeddings.

LanceDB requires a vector column for ANN indexing even though this table is
never vector-searched (whole-file staging only, not RAG) — `vector` is a
fixed-dimension all-zero dummy column purely to satisfy the schema
requirement. Do not read anything into its values.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pyarrow as pa

from app.repo.lancedb_client import get_db

logger = logging.getLogger(__name__)

STAGED_TABLE = "staged_files"

# Dummy vector column dimension — see module docstring. Never searched.
DUMMY_VECTOR_DIM = 2

STAGED_FILES_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string()),  # sha256, primary key
        pa.field("name", pa.string()),
        pa.field("size", pa.int64()),
        pa.field("mime", pa.string()),
        pa.field("detected_type", pa.string()),  # "doc" | "chat_export"
        pa.field("text", pa.string()),  # extracted text preview, capped, or ""
        pa.field("meta", pa.string()),  # JSON: {domain, category, source_platform}
        pa.field("r2_key", pa.string()),
        pa.field("status", pa.string()),  # staged | promoting | promoted | failed
        pa.field("promote_result", pa.string()),  # JSON, nullable
        pa.field("created_at", pa.string()),  # ISO 8601
        pa.field("updated_at", pa.string()),  # ISO 8601
        pa.field("vector", pa.list_(pa.float32(), DUMMY_VECTOR_DIM)),
    ]
)

_FIELD_NAMES = [f.name for f in STAGED_FILES_SCHEMA]

_SAFE_VALUE_RE_CHARS = ("'",)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _escape(value: str) -> str:
    """Escape single quotes for a LanceDB SQL-style WHERE clause literal."""
    return value.replace("'", "''")


def _get_or_create_table():
    db = get_db()
    if STAGED_TABLE in db.table_names():
        return db.open_table(STAGED_TABLE)
    logger.info("Creating LanceDB table '%s'", STAGED_TABLE)
    return db.create_table(STAGED_TABLE, schema=STAGED_FILES_SCHEMA)


def _row_to_record(row: dict) -> dict:
    """Deserialize JSON-string columns back into dicts and drop the dummy vector."""
    record = dict(row)
    record.pop("vector", None)
    meta_raw = record.get("meta")
    try:
        record["meta"] = json.loads(meta_raw) if meta_raw else {}
    except (TypeError, ValueError):
        record["meta"] = {}
    result_raw = record.get("promote_result")
    try:
        record["promote_result"] = json.loads(result_raw) if result_raw else None
    except (TypeError, ValueError):
        record["promote_result"] = None
    return record


def get(id: str) -> dict | None:
    """Return the staged_files record for `id` (sha256), or None."""
    table = _get_or_create_table()
    safe_id = _escape(id)
    rows = table.search().where(f"id = '{safe_id}'").limit(1).to_list()
    if not rows:
        return None
    return _row_to_record(rows[0])


def exists(sha256: str) -> bool:
    """Whether a staged_files row already exists for this content hash."""
    return get(sha256) is not None


def upsert_staged(record: dict) -> dict:
    """Insert or update a staged_files row.

    `record` uses API-shape fields (`meta`/`promote_result` as dicts or None).
    `created_at` is preserved if already set on `record`; `updated_at` is
    always refreshed to now.
    """
    table = _get_or_create_table()
    now = _now_iso()
    row = dict(record)
    row.setdefault("created_at", now)
    row["updated_at"] = now
    row["meta"] = json.dumps(row.get("meta") or {})
    promote_result = row.get("promote_result")
    row["promote_result"] = json.dumps(promote_result) if promote_result is not None else None
    row["vector"] = [0.0] * DUMMY_VECTOR_DIM

    data = pa.table({name: [row.get(name)] for name in _FIELD_NAMES}, schema=STAGED_FILES_SCHEMA)
    (table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(data))
    return get(row["id"])


def update_status(id: str, status: str, promote_result: dict | None = None) -> dict | None:
    """Patch just the status (+ optional promote_result) of an existing row."""
    existing = get(id)
    if existing is None:
        return None
    existing["status"] = status
    if promote_result is not None:
        existing["promote_result"] = promote_result
    return upsert_staged(existing)


def list(
    status: str | None = None,
    detected_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """List staged_files rows, newest first, with optional status/type filters."""
    table = _get_or_create_table()
    clauses = []
    if status:
        clauses.append(f"status = '{_escape(status)}'")
    if detected_type:
        clauses.append(f"detected_type = '{_escape(detected_type)}'")

    query = table.search()
    if clauses:
        query = query.where(" AND ".join(clauses))

    # LanceDB has no native OFFSET/ORDER BY on a plain (non-vector) scan, and
    # a partial .limit() would return rows in undefined internal order rather
    # than newest-first — so pull the full (filtered) table and sort/paginate
    # in Python. Staging tables are a personal-scale corpus, not millions of
    # rows; a generous cap still bounds worst-case memory.
    rows = query.limit(100_000).to_list()
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    window = rows[offset : offset + limit]
    return [_row_to_record(r) for r in window]
