# Byline: Claude Code · Sonnet 5 · 2026-08-26
"""The "authenticated projector interface" (WP-E02 brief): reads a sealed
`timeline.timeline_projection_generation` + its members back out in the shape the Timesketch-fork
importer (`timesketch-fork/personal_case_authority/importer.py`) consumes.

"Authenticated" here means the DB-role boundary from `sql/0035_timeline_projection.sql`
(`timeline_projector`, SELECT-only on candidate/membership tables, INSERT-only-and-append-only
everywhere else) — not an HTTP bearer. This mirrors R09's own authority model, where the
projector is a service identity invoked by Temporal/CLI, not a caller-facing REST route (and
`server/api/main.py` is out of this packet's file boundary regardless — see
`docs/reviews/2026-08-25-schema-audit/TIMESKETCH-WP-E02-IMPLEMENTATION-STATUS.md` for the
explicit follow-up this leaves for whichever packet next touches routing).

`fetch_generation()`'s signature/return shape is written to match
`personal_case_authority.authority.TimelineProjectionSource.fetch_generation` field-for-field
(same method name, same `(since_generation) -> (new_generation_id, members)` shape) WITHOUT
importing that module — see `models.py`'s docstring for why the two stay decoupled.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from server.timeline.models import ProjectedMember


def _row_to_member(r) -> ProjectedMember:
    return ProjectedMember(
        source_member_id=str(r["source_member_id"]),
        stable_member_id=r["stable_member_id"],
        opensearch_doc_id=r["opensearch_doc_id"],
        authority_state=r["authority_state"],
        amends_stable_member_id=r["amends_stable_member_id"],
        display_at_utc=r["display_at_utc"],
        display_summary=r["display_summary"],
        event_type=r["event_type"],
        temporal_precision=r["temporal_precision"],
        occurred_at=r["occurred_at"],
        valid_from=r["valid_from"],
        valid_to=r["valid_to"],
        temporal_confidence=r["temporal_confidence"],
        source_available_from=r["source_available_from"],
        entity_refs=tuple(r["entity_refs"] or ()),
        verification_state=r["verification_state"],
        privacy_level=r["privacy_level"],
        privileged=r["privileged"],
        source_system=r["source_system"],
        source_record_id=r["source_record_id"],
        source_record_version=r["source_record_version"],
        core_content_hash=r["core_content_hash"],
        annotation_content_hash=r["annotation_content_hash"],
        member_content_hash=r["member_content_hash"],
        change_class=r["change_class"],
    )


_MEMBER_COLUMNS = """
    source_member_id, stable_member_id, opensearch_doc_id, authority_state, amends_stable_member_id,
    display_at_utc, display_summary, event_type,
    temporal_precision, occurred_at, valid_from, valid_to, temporal_confidence,
    source_available_from, entity_refs, verification_state, privacy_level, privileged,
    source_system, source_record_id, source_record_version,
    core_content_hash, annotation_content_hash, member_content_hash, change_class
"""


def _members_for_generation(conn: Connection, generation_id: str) -> list[ProjectedMember]:
    rows = conn.execute(
        text(f"SELECT {_MEMBER_COLUMNS} FROM timeline.timeline_projection_member WHERE generation_id = :g"),
        {"g": generation_id},
    ).mappings()
    return [_row_to_member(r) for r in rows]


class PostgresTimelineProjectionSource:
    """TS-03/WP-E02's real, PostgreSQL-backed timeline projection source.

    Reads only — never writes `timeline_projection_generation`/`member` (that is
    `generation.build_generation()`'s job, kept separate so the read path used by an external
    Timesketch-side caller can never accidentally mutate canonical state).
    """

    def __init__(self, conn: Connection, *, collection_slug: str = "primary") -> None:
        self._conn = conn
        self._collection_slug = collection_slug

    def fetch_generation(self, since_generation: Optional[str] = None) -> tuple[str, list[ProjectedMember]]:
        """Return `(generation_id, members)` for outbox-driven reprojection.

        - `since_generation=None`: the latest SEALED generation for the collection (full import).
        - `since_generation=<id>`: the DIRECT successor generation (the one whose
          `since_generation_id` equals the given id), so a caller can walk the chain one hop at a
          time. If `since_generation` is already the latest sealed generation, returns
          `(since_generation, [])` — nothing new yet, not an error.

        Raises `ValueError` if `since_generation` does not name a real generation for this
        collection (a caller replaying an unknown/foreign id is a programming error, not a
        "no new data" condition — those must stay distinguishable).
        """
        conn = self._conn
        collection_row = conn.execute(
            text("SELECT id FROM timeline.timeline_collection WHERE slug = :slug"),
            {"slug": self._collection_slug},
        ).first()
        if collection_row is None:
            raise ValueError(f"no timeline.timeline_collection with slug={self._collection_slug!r}")
        collection_id = str(collection_row[0])

        if since_generation is None:
            latest = conn.execute(
                text(
                    "SELECT id FROM timeline.timeline_projection_generation "
                    "WHERE collection_id = :c AND status = 'sealed' ORDER BY sequence DESC LIMIT 1"
                ),
                {"c": collection_id},
            ).first()
            if latest is None:
                raise ValueError(f"no sealed generation exists yet for collection={self._collection_slug!r}")
            generation_id = str(latest[0])
            return generation_id, _members_for_generation(conn, generation_id)

        anchor = conn.execute(
            text("SELECT id FROM timeline.timeline_projection_generation WHERE id = :id AND collection_id = :c"),
            {"id": since_generation, "c": collection_id},
        ).first()
        if anchor is None:
            raise ValueError(f"since_generation={since_generation!r} is not a known generation for this collection")

        successor = conn.execute(
            text(
                "SELECT id FROM timeline.timeline_projection_generation "
                "WHERE since_generation_id = :since AND collection_id = :c"
            ),
            {"since": since_generation, "c": collection_id},
        ).first()
        if successor is None:
            return since_generation, []
        generation_id = str(successor[0])
        return generation_id, _members_for_generation(conn, generation_id)
