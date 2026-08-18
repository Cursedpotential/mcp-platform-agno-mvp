"""Governed relational projections for source-grain message records.

The normalized record remains the only authored spine.  These rows are
rebuildable projections written in the same transaction as that spine; acquired
third-party rows remain proposed until a human resolves and approves identities.

Byline: Codex · GPT-5 · 2026-08-18
Byline amendment: Codex · GPT-5 · 2026-08-18 (audited review and duplicate acquisition linking)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from server.contracts.records import MessageCorpus, NormalizedRecord, RecordType

if TYPE_CHECKING:
    from server.contracts.ingest import IngestRequest
    from server.evidence.custody import ArtifactRef


DERIVER_VERSION = "message-projection@2026-08-18"
_SOURCE_MARKERS = {"self", "me", "owner", "ownerrole"}


@dataclass(frozen=True)
class ProjectionPlan:
    record_id: str
    kind: MessageCorpus
    conversation_key: str
    platform: str
    sender: str | None
    recipients: tuple[tuple[str, str], ...]
    external_id: str | None
    direction: str
    review_required: bool


@dataclass(frozen=True)
class VectorReprojectionHandoff:
    """Post-approval coordinates consumed by the vector replay workflow."""

    conversation_id: str
    artifact_id: str
    normalized_record_ids: tuple[str, ...]
    source_available_from: dict[str, datetime]


@dataclass(frozen=True)
class ThirdPartyApprovalResult:
    conversation_id: str
    approved_record_count: int
    audit_ledger_id: int
    vector_reprojection: VectorReprojectionHandoff


def _clean(value: object) -> str | None:
    rendered = str(value).strip() if value is not None else ""
    return rendered or None


def _same_identity(left: str | None, right: str | None) -> bool:
    return left is not None and right is not None and left.casefold() == right.casefold()


def _actual_identity(value: object, principal: str | None) -> str | None:
    identity = _clean(value)
    if identity is not None and identity.casefold().replace("_", "") in _SOURCE_MARKERS:
        return principal
    return identity


def build_projection_plan(
    record: NormalizedRecord,
    record_id: str,
    artifact_id: str,
    request: IngestRequest,
) -> ProjectionPlan | None:
    """Build a neutral projection plan; never substitute the case owner."""

    if record.record_type is not RecordType.message or record.message_corpus is None:
        return None
    principal = _clean(request.source_principal)
    sender = _actual_identity(record.sender, principal)
    recipients = tuple(
        (identity, recipient.role)
        for recipient in record.recipients
        if (identity := _actual_identity(recipient.identity, principal)) is not None
    )
    if _same_identity(sender, principal):
        direction = "outbound"
    elif any(_same_identity(identity, principal) for identity, _role in recipients):
        direction = "inbound"
    else:
        direction = "unknown"
    attrs = record.attrs
    external_id = _clean(
        attrs.get("message_id")
        or attrs.get("source_record_id")
        or attrs.get("external_id")
        or attrs.get("source_position")
    )
    conversation_key = _clean(record.conversation_id) or f"artifact:{artifact_id}"
    review_required = "source_party_review_required" in attrs or sender is None or not recipients
    return ProjectionPlan(
        record_id=record_id,
        kind=record.message_corpus,
        conversation_key=conversation_key,
        platform=_clean(attrs.get("platform")) or record.source,
        sender=sender,
        recipients=recipients,
        external_id=external_id,
        direction=direction,
        review_required=review_required,
    )


def _insert_route(conn: Any, plan: ProjectionPlan, *, approved: bool) -> None:
    state = "approved" if approved else "proposed"
    actor = "ingest-source-parties" if approved else None
    conn.execute(
        text(
            "INSERT INTO working.message_projection_route "
            "(normalized_record_id, projection_kind, decision_state, basis, proposed_by, "
            " approved_by, approved_at, deriver_version) "
            "VALUES (CAST(:record_id AS uuid), :kind, :state, CAST(:basis AS jsonb), "
            " :proposed_by, :approved_by, CASE WHEN :approved_by IS NULL THEN NULL ELSE now() END, :version)"
        ),
        {
            "record_id": plan.record_id,
            "kind": plan.kind.value,
            "state": state,
            "basis": json.dumps(
                {
                    "source_parties_present": not plan.review_required,
                    "source_party_review_required": plan.review_required,
                }
            ),
            "proposed_by": DERIVER_VERSION,
            "approved_by": actor,
            "version": DERIVER_VERSION,
        },
    )


def _write_first_party(conn: Any, plan: ProjectionPlan, record: NormalizedRecord, artifact_id: str) -> None:
    conversation_id = str(
        conn.execute(
            text(
                "INSERT INTO working.conversation "
                "(source_artifact_id, platform, external_thread_key, title, participants, participant_count, "
                " started_at, ended_at, message_count, platform_attrs) "
                "VALUES (CAST(:artifact_id AS uuid), :platform, :thread_key, :title, CAST(:participants AS jsonb), "
                " :participant_count, :occurred_at, :occurred_at, 1, CAST(:attrs AS jsonb)) "
                "ON CONFLICT (platform, external_thread_key) DO UPDATE SET "
                " started_at=LEAST(working.conversation.started_at, EXCLUDED.started_at), "
                " ended_at=GREATEST(working.conversation.ended_at, EXCLUDED.ended_at), "
                " message_count=working.conversation.message_count+1 RETURNING id"
            ),
            {
                "artifact_id": artifact_id,
                "platform": plan.platform,
                "thread_key": plan.conversation_key,
                "title": record.attrs.get("conversation_title"),
                "participants": json.dumps(
                    [value for value in [plan.sender, *(p[0] for p in plan.recipients)] if value]
                ),
                "participant_count": len(
                    {value.casefold() for value in [plan.sender, *(p[0] for p in plan.recipients)] if value}
                ),
                "occurred_at": record.occurred_at,
                "attrs": json.dumps({"projection_deriver": DERIVER_VERSION}),
            },
        ).scalar_one()
    )
    message_id = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO working.message "
            "(id, conversation_id, ts_utc, platform, external_id, sender_raw, recipient_raw, direction, "
            " message_type, content_sha256, platform_attrs, raw_data, derived_from_record_id, "
            " deriver_version, derived_at, projection_kind) "
            "VALUES (CAST(:id AS uuid), CAST(:conversation_id AS uuid), :occurred_at, :platform, :external_id, "
            " :sender, :recipient_raw, :direction, :message_type, :content_sha256, CAST(:attrs AS jsonb), "
            " CAST(:raw_data AS jsonb), CAST(:record_id AS uuid), :version, now(), 'first_party')"
        ),
        {
            "id": message_id,
            "conversation_id": conversation_id,
            "occurred_at": record.occurred_at,
            "platform": plan.platform,
            "external_id": plan.external_id,
            "sender": plan.sender,
            "recipient_raw": ", ".join(identity for identity, _role in plan.recipients) or None,
            "direction": plan.direction,
            "message_type": record.attrs.get("message_type") or "text",
            "content_sha256": hashlib.sha256(record.content.encode("utf-8")).digest(),
            "attrs": json.dumps(record.attrs),
            "raw_data": json.dumps({"content": record.content}),
            "record_id": plan.record_id,
            "version": DERIVER_VERSION,
        },
    )
    parties = [(plan.sender, "from"), *plan.recipients]
    for identity, role in parties:
        if identity is not None:
            conn.execute(
                text(
                    "INSERT INTO working.message_participant "
                    "(message_id, participant_raw, role, deriver_version) "
                    "VALUES (CAST(:message_id AS uuid), :identity, :role, :version)"
                ),
                {"message_id": message_id, "identity": identity, "role": role, "version": DERIVER_VERSION},
            )


def _write_third_party(
    conn: Any,
    plan: ProjectionPlan,
    record: NormalizedRecord,
    artifact: ArtifactRef,
    request: IngestRequest,
) -> None:
    if artifact.acquisition_id is None:
        raise ValueError("acquired-third-party projection requires an authoritative acquisition row")
    conversation_id = str(
        conn.execute(
            text(
                "INSERT INTO working.third_party_conversation "
                "(case_id, source_artifact_id, platform, external_thread_key, title, started_at, ended_at, "
                " message_count, review_status, platform_attrs, deriver_version) "
                "VALUES (:case_id, CAST(:artifact_id AS uuid), :platform, :thread_key, :title, :occurred_at, "
                " :occurred_at, 1, 'pending', CAST(:attrs AS jsonb), :version) "
                "ON CONFLICT (source_artifact_id, platform, external_thread_key) DO UPDATE SET "
                " started_at=LEAST(working.third_party_conversation.started_at, EXCLUDED.started_at), "
                " ended_at=GREATEST(working.third_party_conversation.ended_at, EXCLUDED.ended_at), "
                " message_count=working.third_party_conversation.message_count+1 RETURNING id"
            ),
            {
                "case_id": request.matter_id,
                "artifact_id": artifact.artifact_id,
                "platform": plan.platform,
                "thread_key": plan.conversation_key,
                "title": record.attrs.get("conversation_title"),
                "occurred_at": record.occurred_at,
                "attrs": json.dumps({"projection_deriver": DERIVER_VERSION}),
                "version": DERIVER_VERSION,
            },
        ).scalar_one()
    )
    message_id = str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO working.third_party_message "
            "(id, conversation_id, normalized_record_id, occurred_at, platform, external_id, sender_raw, "
            " content_sha256, platform_attrs, raw_data, deriver_version) "
            "VALUES (CAST(:id AS uuid), CAST(:conversation_id AS uuid), CAST(:record_id AS uuid), :occurred_at, "
            " :platform, :external_id, :sender, :content_sha256, CAST(:attrs AS jsonb), "
            " CAST(:raw_data AS jsonb), :version)"
        ),
        {
            "id": message_id,
            "conversation_id": conversation_id,
            "record_id": plan.record_id,
            "occurred_at": record.occurred_at,
            "platform": plan.platform,
            "external_id": plan.external_id,
            "sender": plan.sender,
            "content_sha256": hashlib.sha256(record.content.encode("utf-8")).digest(),
            "attrs": json.dumps(record.attrs),
            "raw_data": json.dumps({"content": record.content}),
            "version": DERIVER_VERSION,
        },
    )
    for identity, role in [(plan.sender, "from"), *plan.recipients]:
        if identity is not None:
            conn.execute(
                text(
                    "INSERT INTO working.third_party_message_participant "
                    "(message_id, participant_raw, role, deriver_version) "
                    "VALUES (CAST(:message_id AS uuid), :identity, :role, :version)"
                ),
                {"message_id": message_id, "identity": identity, "role": role, "version": DERIVER_VERSION},
            )
    asserted_by = request.acquisition.asserted_by if request.acquisition is not None else "owner"
    conn.execute(
        text(
            "INSERT INTO working.third_party_conversation_acquisition "
            "(conversation_id, acquisition_id, approval_state, proposed_by, approved_by, approved_at, notes) "
            "VALUES (CAST(:conversation_id AS uuid), CAST(:acquisition_id AS uuid), 'approved', "
            " :asserted_by, :asserted_by, now(), 'Direct link created from the human acquisition assertion') "
            "ON CONFLICT (conversation_id, acquisition_id) DO NOTHING"
        ),
        {
            "conversation_id": conversation_id,
            "acquisition_id": artifact.acquisition_id,
            "asserted_by": asserted_by,
        },
    )


def write_message_projections(
    conn: Any,
    records: list[NormalizedRecord],
    record_ids: list[str],
    artifact: ArtifactRef,
    request: IngestRequest,
) -> int:
    """Write governed projections using the caller's open PG transaction."""

    written = 0
    for record, record_id in zip(records, record_ids, strict=True):
        plan = build_projection_plan(record, record_id, artifact.artifact_id, request)
        if plan is None:
            continue
        # First-party source identities can be accepted as stated by the source.
        # Third-party projection approval additionally requires entity resolution,
        # owner exclusion and human conversation review, so it always starts proposed.
        _insert_route(conn, plan, approved=plan.kind is MessageCorpus.first_party and not plan.review_required)
        if plan.kind is MessageCorpus.first_party:
            _write_first_party(conn, plan, record, artifact.artifact_id)
        else:
            _write_third_party(conn, plan, record, artifact, request)
        written += 1
    return written


def link_duplicate_acquisition(
    conn: Any,
    *,
    artifact_id: str,
    acquisition_id: str,
    asserted_by: str,
) -> int:
    """Attach a new human acquisition to existing third-party conversations.

    This is the duplicate-artifact path: no normalized or projection row is
    rewritten.  The acquisition is already authoritative because custody wrote
    it from the current human assertion.
    """

    rows = conn.execute(
        text(
            "INSERT INTO working.third_party_conversation_acquisition "
            "(conversation_id, acquisition_id, approval_state, proposed_by, approved_by, approved_at, notes) "
            "SELECT tc.id, CAST(:acquisition_id AS uuid), 'approved', :asserted_by, :asserted_by, now(), "
            " 'Additional direct human acquisition assertion for duplicate artifact' "
            "FROM working.third_party_conversation tc "
            "WHERE tc.source_artifact_id=CAST(:artifact_id AS uuid) "
            "ON CONFLICT (conversation_id, acquisition_id) DO NOTHING RETURNING id"
        ),
        {
            "artifact_id": artifact_id,
            "acquisition_id": acquisition_id,
            "asserted_by": asserted_by,
        },
    ).all()
    return len(rows)


def _validate_entity_resolutions(
    party_rows: list[dict[str, Any]],
    sender_entity_ids: dict[str, str],
    participant_entity_ids: dict[str, str],
    owner_entity_id: str,
) -> tuple[set[str], set[str]]:
    """Validate exact, complete supplied resolutions without guessing."""

    message_ids = {str(row["message_id"]) for row in party_rows}
    participant_ids = {str(row["participant_id"]) for row in party_rows if row.get("participant_id") is not None}
    if set(sender_entity_ids) != message_ids:
        raise ValueError("sender_entity_ids must resolve every and only every message in the conversation")
    if set(participant_entity_ids) != participant_ids:
        raise ValueError("participant_entity_ids must resolve every and only every participant row")
    if any(not str(row.get("sender_raw") or "").strip() for row in party_rows):
        raise ValueError("every message requires a nonblank raw sender before approval")
    recipient_message_ids = {
        str(row["message_id"])
        for row in party_rows
        if row.get("participant_id") is not None and row.get("role") in {"to", "cc", "bcc", "group"}
    }
    if recipient_message_ids != message_ids:
        raise ValueError("every message requires at least one raw recipient before approval")
    resolved_entities = {str(value) for value in sender_entity_ids.values()} | {
        str(value) for value in participant_entity_ids.values()
    }
    if owner_entity_id in resolved_entities:
        raise ValueError("the configured case owner cannot participate in an acquired-third-party conversation")
    for row in party_rows:
        if row.get("role") == "from":
            message_id = str(row["message_id"])
            participant_id = str(row["participant_id"])
            if participant_entity_ids[participant_id] != sender_entity_ids[message_id]:
                raise ValueError("each from-participant entity must equal its message sender entity")
    return message_ids, resolved_entities


def approve_third_party_conversation(
    conversation_id: str,
    *,
    sender_entity_ids: dict[str, str],
    participant_entity_ids: dict[str, str],
    actor: str,
    reason: str,
    engine: Any = None,
) -> ThirdPartyApprovalResult:
    """Resolve and approve one third-party conversation in one audited txn.

    The supplied maps are keyed by projection row IDs, making the contract
    directly usable by an API without relying on ambiguous raw-name matching.
    """

    if not actor.strip() or not reason.strip():
        raise ValueError("actor and reason are required for third-party approval")
    if not sender_entity_ids or not participant_entity_ids:
        raise ValueError("sender and recipient entity resolutions are required")
    if engine is None:
        from server.evidence.store import _get_engine

        engine = _get_engine()
    with engine.begin() as conn:
        conversation = (
            conn.execute(
                text(
                    "SELECT id, source_artifact_id, case_id, review_status "
                    "FROM working.third_party_conversation "
                    "WHERE id=CAST(:conversation_id AS uuid) FOR UPDATE"
                ),
                {"conversation_id": conversation_id},
            )
            .mappings()
            .first()
        )
        if conversation is None:
            raise ValueError("third-party conversation does not exist")
        owners = conn.execute(text("SELECT id FROM working.person WHERE role_in_case='user' FOR SHARE")).scalars().all()
        if len(owners) != 1:
            raise ValueError("exactly one configured case owner is required before approval")
        party_rows = [
            dict(row)
            for row in conn.execute(
                text(
                    "SELECT tm.id AS message_id, tm.normalized_record_id, tm.sender_raw, "
                    "p.id AS participant_id, p.participant_raw, p.role "
                    "FROM working.third_party_message tm "
                    "JOIN working.third_party_message_participant p ON p.message_id=tm.id "
                    "WHERE tm.conversation_id=CAST(:conversation_id AS uuid) "
                    "ORDER BY tm.id, p.id FOR UPDATE OF tm, p"
                ),
                {"conversation_id": conversation_id},
            ).mappings()
        ]
        if not party_rows:
            raise ValueError("third-party conversation has no message projections")
        message_ids, resolved_entities = _validate_entity_resolutions(
            party_rows,
            sender_entity_ids,
            participant_entity_ids,
            str(owners[0]),
        )
        existing_entities = {
            str(value)
            for value in conn.execute(
                text("SELECT id FROM working.entity WHERE id=ANY(CAST(:entity_ids AS uuid[])) FOR SHARE"),
                {"entity_ids": sorted(resolved_entities)},
            ).scalars()
        }
        if existing_entities != resolved_entities:
            raise ValueError("every supplied sender/recipient entity ID must exist")
        for message_id, entity_id in sender_entity_ids.items():
            conn.execute(
                text(
                    "UPDATE working.third_party_message SET sender_entity_id=CAST(:entity_id AS uuid) "
                    "WHERE id=CAST(:message_id AS uuid)"
                ),
                {"message_id": message_id, "entity_id": entity_id},
            )
        for participant_id, entity_id in participant_entity_ids.items():
            conn.execute(
                text(
                    "UPDATE working.third_party_message_participant SET entity_id=CAST(:entity_id AS uuid) "
                    "WHERE id=CAST(:participant_id AS uuid)"
                ),
                {"participant_id": participant_id, "entity_id": entity_id},
            )
        conn.execute(
            text(
                "UPDATE working.third_party_conversation SET review_status='approved', "
                "platform_attrs=platform_attrs || CAST(:review AS jsonb) WHERE id=CAST(:conversation_id AS uuid)"
            ),
            {
                "conversation_id": conversation_id,
                "review": json.dumps({"approved_by": actor, "approval_reason": reason.strip()}),
            },
        )
        conn.execute(
            text(
                "UPDATE working.third_party_conversation_acquisition "
                "SET approval_state='approved', approved_by=:actor, approved_at=now() "
                "WHERE conversation_id=CAST(:conversation_id AS uuid) AND approval_state='proposed'"
            ),
            {"conversation_id": conversation_id, "actor": actor},
        )
        valid_acquisitions = conn.execute(
            text(
                "SELECT count(*) FROM working.third_party_conversation_acquisition ca "
                "JOIN evidence.acquisition a ON a.id=ca.acquisition_id "
                "WHERE ca.conversation_id=CAST(:conversation_id AS uuid) "
                "AND ca.approval_state='approved' AND a.asserted_by='human' AND a.acquired_at IS NOT NULL"
            ),
            {"conversation_id": conversation_id},
        ).scalar_one()
        if int(valid_acquisitions) < 1:
            raise ValueError("approval requires an approved human acquisition with acquired_at")
        record_ids = sorted({str(row["normalized_record_id"]) for row in party_rows})
        conn.execute(
            text(
                "UPDATE working.message_projection_route SET decision_state='approved', approved_by=:actor, "
                "approved_at=now(), basis=basis || CAST(:basis AS jsonb) "
                "WHERE normalized_record_id=ANY(CAST(:record_ids AS uuid[])) "
                "AND projection_kind='acquired_third_party'"
            ),
            {
                "actor": actor,
                "record_ids": record_ids,
                "basis": json.dumps({"source_party_review_resolved": True, "review_reason": reason.strip()}),
            },
        )
        availability_rows = list(
            conn.execute(
                text(
                    "SELECT id, working.source_available_from(id) AS source_available_from "
                    "FROM working.normalized_record WHERE id=ANY(CAST(:record_ids AS uuid[]))"
                ),
                {"record_ids": record_ids},
            ).mappings()
        )
        availability = {
            str(row["id"]): row["source_available_from"]
            for row in availability_rows
            if row["source_available_from"] is not None
        }
        if set(availability) != set(record_ids):
            raise RuntimeError("approved projection did not produce source_available_from for every record")
        canonical = json.dumps(
            {
                "conversation_id": conversation_id,
                "actor": actor,
                "reason": reason.strip(),
                "sender_entity_ids": sender_entity_ids,
                "participant_entity_ids": participant_entity_ids,
                "record_ids": record_ids,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        from server.core.audit import record as audit_record

        audit_id = audit_record(
            "approval",
            conversation_id,
            actor=actor,
            ctx={"case_id": str(conversation["case_id"]), "reason": reason.strip()},
            object_schema="working.third_party_conversation",
            payload_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            connection=conn,
        )
        handoff = VectorReprojectionHandoff(
            conversation_id=conversation_id,
            artifact_id=str(conversation["source_artifact_id"]),
            normalized_record_ids=tuple(record_ids),
            source_available_from=availability,
        )
        return ThirdPartyApprovalResult(
            conversation_id=conversation_id,
            approved_record_count=len(message_ids),
            audit_ledger_id=audit_id,
            vector_reprojection=handoff,
        )
