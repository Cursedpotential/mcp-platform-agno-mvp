# Byline: Claude Code · Sonnet 5 · 2026-08-26
"""Append-only receipt writer + the two manifest reads R09/WP-H01 reconcile against.

Every function here does exactly one INSERT or one read against `sql/0035_timeline_projection.sql`'s
`timeline_projection_receipt` table / its two derived views — no other table is touched.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

ReceiptStatus = str  # 'pending'|'attempted'|'succeeded'|'failed_retryable'|'failed_terminal'|'quarantined'|'superseded'


@dataclass(frozen=True)
class ExpectedManifestRow:
    generation_id: str
    sequence: int
    status: str
    membership_hash: str
    content_hash: str
    stable_member_id: str
    opensearch_doc_id: str
    member_content_hash: str
    authority_state: str
    change_class: str


def record_receipt(
    conn: Connection,
    *,
    generation_id: str,
    idempotency_key: str,
    status: ReceiptStatus,
    member_id: Optional[str] = None,
    sink: str = "timesketch_opensearch",
    attempt: int = 1,
    expected_content_hash: Optional[str] = None,
    observed_content_hash: Optional[str] = None,
    opensearch_doc_id: Optional[str] = None,
    opensearch_index: Optional[str] = None,
    error_code: Optional[str] = None,
    error_digest: Optional[str] = None,
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None,
    observed_at: Optional[datetime] = None,
    previous_receipt_id: Optional[str] = None,
) -> str:
    """Append one receipt row. Never updates a prior receipt — a retry or a later observation is
    always a NEW row, optionally linked via `previous_receipt_id` (mirrors the append-only
    `timeline_projection_receipt` table's own contract, enforced independently by its DB trigger).
    """
    row = conn.execute(
        text(
            """
            INSERT INTO timeline.timeline_projection_receipt (
                generation_id, member_id, sink, idempotency_key, status, attempt,
                expected_content_hash, observed_content_hash, opensearch_doc_id, opensearch_index,
                error_code, error_digest, started_at, finished_at, observed_at, previous_receipt_id
            ) VALUES (
                :generation_id, :member_id, :sink, :idempotency_key, :status, :attempt,
                :expected_content_hash, :observed_content_hash, :opensearch_doc_id, :opensearch_index,
                :error_code, :error_digest, :started_at, :finished_at, :observed_at, :previous_receipt_id
            )
            RETURNING id
            """
        ),
        {
            "generation_id": generation_id,
            "member_id": member_id,
            "sink": sink,
            "idempotency_key": idempotency_key,
            "status": status,
            "attempt": attempt,
            "expected_content_hash": expected_content_hash,
            "observed_content_hash": observed_content_hash,
            "opensearch_doc_id": opensearch_doc_id,
            "opensearch_index": opensearch_index,
            "error_code": error_code,
            "error_digest": error_digest,
            "started_at": started_at,
            "finished_at": finished_at,
            "observed_at": observed_at,
            "previous_receipt_id": previous_receipt_id,
        },
    ).first()
    assert row is not None, "RETURNING id must always yield exactly one row on INSERT"
    return str(row[0])


def record_activation(conn: Connection, *, generation_id: str, activated_by: str, note: Optional[str] = None) -> str:
    """Append an activation attestation (R09 Phase 7). Does not flip any mutable "active" flag —
    "currently active" is defined as the latest row here, by `activated_at`."""
    row = conn.execute(
        text(
            "INSERT INTO timeline.timeline_projection_activation (generation_id, activated_by, note) "
            "VALUES (:generation_id, :activated_by, :note) RETURNING id"
        ),
        {"generation_id": generation_id, "activated_by": activated_by, "note": note},
    ).first()
    assert row is not None, "RETURNING id must always yield exactly one row on INSERT"
    return str(row[0])


def current_active_generation(conn: Connection, *, collection_slug: str = "primary") -> Optional[str]:
    row = conn.execute(
        text(
            """
            SELECT a.generation_id
            FROM timeline.timeline_projection_activation a
            JOIN timeline.timeline_projection_generation g ON g.id = a.generation_id
            JOIN timeline.timeline_collection c ON c.id = g.collection_id
            WHERE c.slug = :slug
            ORDER BY a.activated_at DESC, a.id DESC
            LIMIT 1
            """
        ),
        {"slug": collection_slug},
    ).first()
    return str(row[0]) if row else None


def expected_manifest(conn: Connection, *, generation_id: str) -> list[ExpectedManifestRow]:
    """The exact shape R09/WP-H01 diffs against an OpenSearch read-back observation."""
    rows = conn.execute(
        text(
            """
            SELECT generation_id, sequence, status, membership_hash, content_hash,
                   stable_member_id, opensearch_doc_id, member_content_hash, authority_state, change_class
            FROM timeline.vw_projection_expected_manifest
            WHERE generation_id = :generation_id
            """
        ),
        {"generation_id": generation_id},
    ).all()
    return [
        ExpectedManifestRow(
            generation_id=str(r[0]),
            sequence=int(r[1]),
            status=r[2],
            membership_hash=r[3],
            content_hash=r[4],
            stable_member_id=r[5],
            opensearch_doc_id=r[6],
            member_content_hash=r[7],
            authority_state=r[8],
            change_class=r[9],
        )
        for r in rows
    ]
