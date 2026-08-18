"""PostgreSQL read model for Workbench knowledge visibility.

This module exposes canonical rows and their custody provenance without
depending on Agno or a vector-store projection.

Byline: Codex · GPT-5 · 2026-08-16
Byline amendment: Codex · GPT-5 · 2026-08-18 (source records and derived chunks split)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text

from server.contracts.ingest import IngestLane

_engine = None
_DB_DOMAIN = {
    IngestLane.platform: "platform_design",
    IngestLane.legal: "legal",
    IngestLane.personal_history: "behavioral",
    IngestLane.context: "context",
    IngestLane.evidence: "evidence",
}


def _get_engine():
    global _engine
    if _engine is None:
        from server.core.url import db_url

        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def list_items(*, matter_id: str = "primary", lane: IngestLane | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List canonical artifacts that have normalized PostgreSQL rows."""
    params: dict[str, Any] = {"case_id": matter_id, "limit": limit}
    domain_clause = ""
    if lane is not None:
        domain_clause = "AND r.domain = :domain"
        params["domain"] = _DB_DOMAIN[lane]
    with _get_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT r.artifact_id::text AS artifact_id, encode(e.digest, 'hex') AS source_sha256, "
                "       min(coalesce(r.attrs->>'source_name', e.source_ref)) AS source_name, "
                "       min(coalesce(r.attrs->>'source_path', e.source_ref)) AS source_path, "
                "       min(r.attrs->>'parser_id') AS parser_id, min(c.chunker_id) AS chunker_id, "
                "       min(coalesce(r.attrs->>'lane', r.domain)) AS lane, r.case_id AS matter_id, "
                "       count(DISTINCT r.id)::int AS record_count, count(c.id)::int AS chunk_count, "
                "       min(r.created_at) AS created_at "
                "FROM working.normalized_record r "
                "JOIN evidence.evidence_hash e ON e.id = r.artifact_id "
                "LEFT JOIN working.normalized_record_chunk c ON c.normalized_record_id = r.id "
                "WHERE r.case_id = :case_id "
                f"{domain_clause} "
                "GROUP BY r.artifact_id, e.digest, r.case_id "
                "ORDER BY min(r.created_at) DESC LIMIT :limit"
            ),
            params,
        ).mappings()
    return [dict(row) for row in rows]


def get_item(artifact_id: str, *, matter_id: str = "primary") -> dict[str, Any] | None:
    """Return authored source rows and rebuildable chunks as separate collections."""
    with _get_engine().connect() as conn:
        rows = list(
            conn.execute(
                text(
                    "SELECT r.id::text AS record_id, r.artifact_id::text AS artifact_id, "
                    "       encode(e.digest, 'hex') AS source_sha256, e.source_ref, e.blob_key, "
                    "       r.record_type, r.source, r.conversation_id, r.role, r.participants, "
                    "       r.content, r.occurred_at, r.knowledge_time, r.disclosure_tier, "
                    "       r.attrs, r.case_id AS matter_id, r.domain, r.created_at "
                    "FROM working.normalized_record r "
                    "JOIN evidence.evidence_hash e ON e.id = r.artifact_id "
                    "WHERE r.artifact_id = CAST(:artifact_id AS uuid) AND r.case_id = :case_id "
                    "ORDER BY r.occurred_at NULLS LAST, r.created_at, r.id"
                ),
                {"artifact_id": artifact_id, "case_id": matter_id},
            ).mappings()
        )
        chunks = list(
            conn.execute(
                text(
                    "SELECT c.id::text AS chunk_id, c.normalized_record_id::text AS normalized_record_id, "
                    "       c.chunker_id, c.chunk_index, c.content, encode(c.content_sha256, 'hex') AS content_sha256, "
                    "       encode(c.source_content_sha256, 'hex') AS source_content_sha256, "
                    "       c.char_start, c.char_end, c.token_count, c.attrs, c.derived_at "
                    "FROM working.normalized_record_chunk c "
                    "JOIN working.normalized_record r ON r.id = c.normalized_record_id "
                    "WHERE r.artifact_id = CAST(:artifact_id AS uuid) AND r.case_id = :case_id "
                    "ORDER BY r.created_at, r.id, c.chunk_index, c.id"
                ),
                {"artifact_id": artifact_id, "case_id": matter_id},
            ).mappings()
        )
    if not rows:
        return None
    first = rows[0]
    return {
        "artifact_id": first["artifact_id"],
        "source_sha256": first["source_sha256"],
        "source_ref": first["source_ref"],
        "blob_key": first["blob_key"],
        "matter_id": first["matter_id"],
        "record_count": len(rows),
        "chunk_count": len(chunks),
        "records": [dict(row) for row in rows],
        "chunks": [dict(row) for row in chunks],
    }
