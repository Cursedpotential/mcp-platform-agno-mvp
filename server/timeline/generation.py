# Byline: Claude Code · Sonnet 5 · 2026-08-26
"""D02 physical realization: build one immutable `timeline.timeline_projection_generation` from
the current `timeline.timeline_member` set.

Scope note (WP-C02/B01 are themselves "Blocked by physical design" as of this packet — see
`SEMANTIC-AGENT-WORK-PACKAGES.md`): only the `candidate_context` branch is auto-resolvable today,
via a plain join to `timeline.event_candidate`. The `evidence_approved` branch is a polymorphic
pointer (`governed_source_schema`/`table`/`pk`) with no populated producer yet — resolving it
generically would mean building dynamic SQL against a table name, which this module refuses to
do. Instead it accepts an explicit, code-reviewed resolver registry (`GOVERNED_SOURCE_RESOLVERS`)
that a future packet populates once R00/C02 names the real governed table(s); until then,
`evidence_approved` members are reported back in `GenerationResult.skipped_unresolved_governed_members`
rather than silently dropped or guessed at.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from server.timeline.hashing import domain_hash, idempotency_key_for_generation, opensearch_doc_id, stable_member_id
from server.timeline.models import ChangeClass, GenerationResult, ProjectedMember, SourceMemberRow

logger = logging.getLogger(__name__)

# STUB: governed_source resolvers — populate once WP-C02/R00 names the real evidence-approved
# source table(s). Each resolver takes the open connection + the exact (schema, table) pointer
# values already stored in timeline.timeline_member and returns SourceMemberRow objects for the
# governed_source_pk values it recognizes. See docs/reviews/2026-08-25-schema-audit/
# TIMESKETCH-WP-E02-IMPLEMENTATION-STATUS.md for the tracked follow-up (a docs/DEBT.md row is a
# recommended addition by whichever agent owns that shared file next).
GovernedSourceResolver = Callable[[Connection, str, str], list[SourceMemberRow]]
GOVERNED_SOURCE_RESOLVERS: dict[tuple[str, str], GovernedSourceResolver] = {}


def _collection_id(conn: Connection, slug: str) -> str:
    row = conn.execute(
        text("SELECT id FROM timeline.timeline_collection WHERE slug = :slug"),
        {"slug": slug},
    ).first()
    if row is None:
        raise ValueError(f"no timeline.timeline_collection with slug={slug!r}")
    return str(row[0])


def _fetch_candidate_context_members(conn: Connection, collection_id: str) -> list[SourceMemberRow]:
    rows = conn.execute(
        text(
            """
            SELECT
                tm.id AS source_member_id,
                tm.collection_id,
                ec.source_system, ec.source_record_id, ec.source_record_version,
                ec.temporal_precision, ec.occurred_at, ec.valid_from, ec.valid_to, ec.temporal_confidence,
                ec.display_summary, ec.event_type, ec.entity_refs,
                ec.created_at AS source_available_from
            FROM timeline.timeline_member tm
            JOIN timeline.event_candidate ec ON ec.id = tm.candidate_id
            WHERE tm.collection_id = :collection_id
              AND tm.included = true
              AND tm.member_authority = 'candidate_context'
            """
        ),
        {"collection_id": collection_id},
    ).mappings()
    return [
        SourceMemberRow(
            source_member_id=str(r["source_member_id"]),
            collection_id=str(r["collection_id"]),
            authority_state="candidate_context",
            source_system=r["source_system"],
            source_record_id=r["source_record_id"],
            source_record_version=r["source_record_version"],
            temporal_precision=r["temporal_precision"],
            occurred_at=r["occurred_at"],
            valid_from=r["valid_from"],
            valid_to=r["valid_to"],
            temporal_confidence=r["temporal_confidence"],
            display_summary=r["display_summary"],
            event_type=r["event_type"],
            entity_refs=tuple(r["entity_refs"] or ()),
            # STUB: candidate availability defaults to proposal time (event_candidate.created_at)
            # until WP-B01's typed extraction-run contract supplies a real acquisition timestamp.
            source_available_from=r["source_available_from"],
        )
        for r in rows
    ]


def _fetch_governed_members(conn: Connection, collection_id: str) -> tuple[list[SourceMemberRow], list[str]]:
    pointer_rows = conn.execute(
        text(
            """
            SELECT id, governed_source_schema, governed_source_table, governed_source_pk
            FROM timeline.timeline_member
            WHERE collection_id = :collection_id AND included = true AND member_authority = 'evidence_approved'
            """
        ),
        {"collection_id": collection_id},
    ).mappings()

    by_source: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for r in pointer_rows:
        key = (r["governed_source_schema"], r["governed_source_table"])
        by_source.setdefault(key, []).append((str(r["id"]), r["governed_source_pk"]))

    resolved: list[SourceMemberRow] = []
    skipped: list[str] = []
    for key, member_pk_pairs in by_source.items():
        resolver = GOVERNED_SOURCE_RESOLVERS.get(key)
        if resolver is None:
            logger.warning(
                "timeline.generation: no governed-source resolver registered for %s — "
                "%d member(s) skipped from this generation",
                key,
                len(member_pk_pairs),
            )
            skipped.extend(member_id for member_id, _pk in member_pk_pairs)
            continue
        for member_id, pk in member_pk_pairs:
            rows = resolver(conn, member_id, pk)
            resolved.extend(rows)
    return resolved, skipped


def _fetch_prior_hashes(conn: Connection, collection_id: str) -> dict[str, tuple[str, str]]:
    """Latest known (core_content_hash, annotation_content_hash) per stable_member_id, across ALL
    prior generations for this collection (not just the immediately-prior one) — so a member that
    was momentarily unresolved/skipped and later reappears still diffs against its real last-known
    state, not against nothing."""
    rows = conn.execute(
        text(
            """
            SELECT DISTINCT ON (m.stable_member_id)
                m.stable_member_id, m.core_content_hash, m.annotation_content_hash
            FROM timeline.timeline_projection_member m
            JOIN timeline.timeline_projection_generation g ON g.id = m.generation_id
            WHERE g.collection_id = :collection_id
            ORDER BY m.stable_member_id, g.sequence DESC
            """
        ),
        {"collection_id": collection_id},
    ).all()
    return {r[0]: (r[1], r[2]) for r in rows}


def _display_at_utc(row: SourceMemberRow) -> datetime:
    """Never coerce imprecision into false precision (ADR-0060) — but a Timesketch `datetime` is
    mandatory, so pick the best available anchor in a fixed, documented order."""
    for candidate in (row.occurred_at, row.valid_from, row.valid_to, row.source_available_from):
        if candidate is not None:
            return candidate
    raise ValueError(
        f"source_member_id={row.source_member_id}: no occurred_at/valid_from/valid_to/"
        "source_available_from to derive a display anchor from"
    )


def _project_member(row: SourceMemberRow, prior_hashes: dict[str, tuple[str, str]]) -> ProjectedMember:
    stable_id = stable_member_id(row.source_member_id)
    display_at_utc = _display_at_utc(row)

    core_payload = {
        "source_system": row.source_system,
        "source_record_id": row.source_record_id,
        "source_record_version": row.source_record_version,
        "temporal_precision": row.temporal_precision,
        "occurred_at": row.occurred_at,
        "valid_from": row.valid_from,
        "valid_to": row.valid_to,
        "temporal_confidence": row.temporal_confidence,
        "display_at_utc": display_at_utc,
        "display_summary": row.display_summary,
        "event_type": row.event_type,
    }
    annotation_payload = {
        "entity_refs": sorted(row.entity_refs),
        "verification_state": row.verification_state,
        "privacy_level": row.privacy_level,
        "privileged": row.privileged,
    }
    core_hash = domain_hash("timeline-member-core-v1", core_payload)
    annotation_hash = domain_hash("timeline-member-annotation-v1", annotation_payload)
    member_hash = domain_hash("timeline-member-content-v1", {"core": core_hash, "annotation": annotation_hash})

    prior = prior_hashes.get(stable_id)
    change_class: ChangeClass
    if prior is None:
        change_class = "core"
    elif prior == (core_hash, annotation_hash):
        change_class = "unchanged"
    elif prior[0] != core_hash:
        change_class = "core"
    else:
        change_class = "annotation"

    if row.source_available_from is None:
        raise ValueError(f"source_member_id={row.source_member_id}: source_available_from is required")

    return ProjectedMember(
        source_member_id=row.source_member_id,
        stable_member_id=stable_id,
        opensearch_doc_id=opensearch_doc_id(stable_id),
        authority_state=row.authority_state,
        amends_stable_member_id=row.amends_stable_member_id,
        display_at_utc=display_at_utc,
        display_summary=row.display_summary,
        event_type=row.event_type,
        temporal_precision=row.temporal_precision,
        occurred_at=row.occurred_at,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        temporal_confidence=row.temporal_confidence,
        source_available_from=row.source_available_from,
        entity_refs=row.entity_refs,
        verification_state=row.verification_state,
        privacy_level=row.privacy_level,
        privileged=row.privileged,
        source_system=row.source_system,
        source_record_id=row.source_record_id,
        source_record_version=row.source_record_version,
        core_content_hash=core_hash,
        annotation_content_hash=annotation_hash,
        member_content_hash=member_hash,
        change_class=change_class,
    )


def build_generation(
    conn: Connection,
    *,
    collection_slug: str = "primary",
    created_by: str = "timeline_projector",
) -> GenerationResult:
    """Build (or idempotently return) one sealed generation for `collection_slug`.

    Caller owns the transaction — pass a connection already inside `conn.begin()` (or let the
    caller's own transaction wrap this call) so a mid-build failure leaves nothing partially
    written. Idempotent: an unchanged member set returns the existing generation with
    `created=False` rather than inserting a duplicate (`idempotency_key` is deterministic from
    `content_hash`, enforced by the table's UNIQUE constraint).
    """
    collection_id = _collection_id(conn, collection_slug)
    candidate_rows = _fetch_candidate_context_members(conn, collection_id)
    governed_rows, skipped = _fetch_governed_members(conn, collection_id)
    prior_hashes = _fetch_prior_hashes(conn, collection_id)

    projected = sorted(
        (_project_member(row, prior_hashes) for row in (*candidate_rows, *governed_rows)),
        key=lambda pm: pm.stable_member_id,
    )

    membership_hash = domain_hash(
        "timeline-generation-membership-v1", {"members": [pm.stable_member_id for pm in projected]}
    )
    content_hash = domain_hash(
        "timeline-generation-content-v1",
        {"members": [{"id": pm.stable_member_id, "hash": pm.member_content_hash} for pm in projected]},
    )
    idempotency_key = idempotency_key_for_generation(content_hash)

    existing = conn.execute(
        text("SELECT id, sequence FROM timeline.timeline_projection_generation WHERE idempotency_key = :k"),
        {"k": idempotency_key},
    ).first()
    if existing is not None:
        return GenerationResult(
            generation_id=str(existing[0]),
            sequence=int(existing[1]),
            created=False,
            member_count=len(projected),
            skipped_unresolved_governed_members=tuple(skipped),
        )

    prior_generation = conn.execute(
        text(
            """
            SELECT id FROM timeline.timeline_projection_generation
            WHERE collection_id = :collection_id AND status = 'sealed'
            ORDER BY sequence DESC LIMIT 1
            """
        ),
        {"collection_id": collection_id},
    ).first()

    inserted = conn.execute(
        text(
            """
            INSERT INTO timeline.timeline_projection_generation
                (collection_id, member_count, membership_hash, content_hash, idempotency_key,
                 since_generation_id, created_by)
            VALUES (:collection_id, :member_count, :membership_hash, :content_hash, :idempotency_key,
                    :since_generation_id, :created_by)
            RETURNING id, sequence
            """
        ),
        {
            "collection_id": collection_id,
            "member_count": len(projected),
            "membership_hash": membership_hash,
            "content_hash": content_hash,
            "idempotency_key": idempotency_key,
            "since_generation_id": str(prior_generation[0]) if prior_generation else None,
            "created_by": created_by,
        },
    ).first()
    assert inserted is not None, "RETURNING id, sequence must always yield exactly one row on INSERT"
    generation_id, sequence = str(inserted[0]), int(inserted[1])

    for pm in projected:
        conn.execute(
            text(
                """
                INSERT INTO timeline.timeline_projection_member (
                    generation_id, source_member_id, stable_member_id, opensearch_doc_id,
                    authority_state, amends_stable_member_id,
                    display_at_utc, display_summary, event_type,
                    temporal_precision, occurred_at, valid_from, valid_to, temporal_confidence,
                    source_available_from, entity_refs, verification_state, privacy_level, privileged,
                    source_system, source_record_id, source_record_version,
                    core_content_hash, annotation_content_hash, member_content_hash, change_class
                ) VALUES (
                    :generation_id, :source_member_id, :stable_member_id, :opensearch_doc_id,
                    :authority_state, :amends_stable_member_id,
                    :display_at_utc, :display_summary, :event_type,
                    :temporal_precision, :occurred_at, :valid_from, :valid_to, :temporal_confidence,
                    :source_available_from, :entity_refs, :verification_state, :privacy_level, :privileged,
                    :source_system, :source_record_id, :source_record_version,
                    :core_content_hash, :annotation_content_hash, :member_content_hash, :change_class
                )
                """
            ),
            {
                "generation_id": generation_id,
                "source_member_id": pm.source_member_id,
                "stable_member_id": pm.stable_member_id,
                "opensearch_doc_id": pm.opensearch_doc_id,
                "authority_state": pm.authority_state,
                "amends_stable_member_id": pm.amends_stable_member_id,
                "display_at_utc": pm.display_at_utc,
                "display_summary": pm.display_summary,
                "event_type": pm.event_type,
                "temporal_precision": pm.temporal_precision,
                "occurred_at": pm.occurred_at,
                "valid_from": pm.valid_from,
                "valid_to": pm.valid_to,
                "temporal_confidence": pm.temporal_confidence,
                "source_available_from": pm.source_available_from,
                "entity_refs": list(pm.entity_refs),
                "verification_state": pm.verification_state,
                "privacy_level": pm.privacy_level,
                "privileged": pm.privileged,
                "source_system": pm.source_system,
                "source_record_id": pm.source_record_id,
                "source_record_version": pm.source_record_version,
                "core_content_hash": pm.core_content_hash,
                "annotation_content_hash": pm.annotation_content_hash,
                "member_content_hash": pm.member_content_hash,
                "change_class": pm.change_class,
            },
        )

    if prior_generation is not None:
        conn.execute(
            text(
                "UPDATE timeline.timeline_projection_generation "
                "SET status = 'superseded', superseded_by = :new_id WHERE id = :old_id"
            ),
            {"new_id": generation_id, "old_id": str(prior_generation[0])},
        )

    return GenerationResult(
        generation_id=generation_id,
        sequence=sequence,
        created=True,
        member_count=len(projected),
        skipped_unresolved_governed_members=tuple(skipped),
    )
