"""Transactional Postgres repository for Matter and evidence promotion.

The repository is the only case-management layer that knows table names.
Knowledge retrieval metadata is never trusted: every promotion re-resolves
the selected normalized record through the custody tables in one transaction.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from server.contracts.case_management import (
    AssertionReadinessGate,
    AuthenticationReadinessGate,
    CanonicalRecordDetail,
    ConfidenceReadinessGate,
    ContentReviewGate,
    CourtCase,
    CourtCaseCreate,
    CourtExportReadinessGate,
    CourtReadiness,
    CourtReadinessBlocker,
    CourtReadinessGates,
    CustodyHashDetail,
    CustodyReadinessGate,
    EvidenceItemDetail,
    EvidenceItem,
    EvidenceItemCreate,
    EvidenceItemList,
    EvidencePromotionDetail,
    EvidencePromotionResult,
    EvidenceReviewCreate,
    EvidenceReviewDecision,
    EvidenceReviewList,
    EvidenceReviewRecord,
    EvidenceReviewResult,
    KnowledgeSourceResolution,
    KnowledgeSourceResolveRequest,
    Matter,
    MatterCreate,
    MatterDetail,
    MatterList,
    ProvenanceReadinessGate,
    RedactionReadinessGate,
    ReviewState,
    SensitivityReadinessGate,
    FileNodeDetail,
    SourceCustodyDetail,
    SourceCandidate,
)

_engine: Any = None


class CaseRepositoryError(Exception):
    """Repository failure carrying the intended HTTP-compatible status."""

    def __init__(self, detail: str, status_code: int) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _get_engine() -> Any:
    global _engine
    if _engine is None:
        from server.core.url import db_url

        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def _matter_from_row(row: dict[str, Any]) -> Matter:
    return Matter(
        id=row["id"],
        title=row["title"],
        description=row.get("description"),
        status=row["status"],
        partition_keys=list(row.get("partition_keys") or []),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _court_case_from_row(row: dict[str, Any]) -> CourtCase:
    return CourtCase(
        id=row["id"],
        matter_id=row["matter_id"],
        caption=row["caption"],
        court_name=row.get("court_name"),
        docket_number=row.get("docket_number"),
        jurisdiction=row.get("jurisdiction"),
        case_type=row.get("case_type"),
        status=row["status"],
        filed_on=row.get("filed_on"),
        closed_on=row.get("closed_on"),
        is_primary=bool(row["is_primary"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _candidate_from_row(row: dict[str, Any]) -> SourceCandidate:
    return SourceCandidate(
        normalized_record_id=row["normalized_record_id"],
        artifact_id=row["artifact_id"],
        evidence_hash_id=row["evidence_hash_id"],
        source_id=row["source_id"],
        file_node_id=row.get("file_node_id"),
        source_run_id=row.get("source_run_id"),
        sha256=row["sha256"],
        conversation_id=row.get("conversation_id"),
        record_type=row["record_type"],
        role=row.get("role"),
        content=row["content"],
        occurred_at=row.get("occurred_at"),
        disclosure_tier=row["disclosure_tier"],
        review_status=row["review_status"],
    )


def _evidence_item_from_row(row: dict[str, Any]) -> EvidenceItem:
    return EvidenceItem(
        id=row["id"],
        matter_id=row["matter_id"],
        court_case_id=row["court_case_id"],
        title=row["title"],
        description=row.get("description"),
        quote=row.get("quote"),
        evidence_type=row["evidence_type"],
        evidence_date=row.get("evidence_date"),
        normalized_record_id=row["normalized_record_id"],
        evidence_hash_id=row["evidence_hash_id"],
        source_id=row["source_id"],
        file_node_id=row.get("file_node_id"),
        source_run_id=row.get("source_run_id"),
        review_status=row["review_status"],
        hitl_required=bool(row["hitl_required"]),
        safe_for_legal_use=bool(row["safe_for_legal_use"]),
        is_authenticated=bool(row["is_authenticated"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _evidence_detail_from_row(row: dict[str, Any]) -> EvidenceItemDetail:
    file_node = None
    if row.get("detail_file_node_id") is not None:
        file_node = FileNodeDetail(
            id=row["detail_file_node_id"],
            node_kind=row["file_node_kind"],
            node_path=row.get("file_node_path"),
            ordinal=row.get("file_node_ordinal"),
            sha256=row.get("file_node_sha256"),
            byte_span_start=row.get("file_node_byte_span_start"),
            byte_span_end=row.get("file_node_byte_span_end"),
            locator=row["file_node_locator"],
            mime_type=row.get("file_node_mime_type"),
        )
    return EvidenceItemDetail(
        item=_evidence_item_from_row(row),
        promotion=EvidencePromotionDetail(
            id=row["promotion_id"],
            partition_key=row["promotion_partition_key"],
            knowledge_lane=row["promotion_knowledge_lane"],
            retrieval_item_ref=row["promotion_retrieval_item_ref"],
            content_ref=row.get("promotion_content_ref"),
            chunk_ref=row.get("promotion_chunk_ref"),
            source_pointer=row["promotion_source_pointer"],
            promoted_by=row["promotion_promoted_by"],
            promoted_at=row["promotion_promoted_at"],
        ),
        record=CanonicalRecordDetail(
            id=row["record_id"],
            record_type=row["record_type"],
            source=row["record_source"],
            conversation_id=row.get("record_conversation_id"),
            role=row.get("record_role"),
            content=row["record_content"],
            occurred_at=row.get("record_occurred_at"),
            acquired_at=row.get("record_acquired_at"),
            ingested_at=row["record_ingested_at"],
            realized_at=row.get("record_realized_at"),
            disclosure_tier=row["record_disclosure_tier"],
            review_status=row["record_review_status"],
            case_id=row["record_case_id"],
        ),
        custody_hash=CustodyHashDetail(
            id=row["custody_hash_id"],
            source_ref=row["custody_hash_source_ref"],
            algo=row["custody_hash_algo"],
            digest_sha256=row["custody_hash_digest_sha256"],
            level=row["custody_hash_level"],
            canon_version=row["custody_hash_canon_version"],
            hashed_at=row["custody_hash_hashed_at"],
            computed_by=row.get("custody_hash_computed_by"),
        ),
        source=SourceCustodyDetail(
            id=row["custody_source_id"],
            sha256=row["custody_source_sha256"],
            byte_size=row["custody_source_byte_size"],
            mime_type=row.get("custody_source_mime_type"),
            original_filename=row.get("custody_source_original_filename"),
            source_type=row["custody_source_type"],
            source_platform=row.get("custody_source_platform"),
            acquisition_source=row["custody_source_acquisition_source"],
            acquisition_method=row.get("custody_source_acquisition_method"),
            acquired_at_utc=row.get("custody_source_acquired_at_utc"),
            acquired_certainty=row["custody_source_acquired_certainty"],
            provenance_tier=row["custody_source_provenance_tier"],
            hash_canon_version=row["custody_source_hash_canon_version"],
            custody_status=row["custody_source_custody_status"],
            review_status=row["custody_source_review_status"],
            verified_by=row.get("custody_source_verified_by"),
            verified_at=row.get("custody_source_verified_at"),
        ),
        file_node=file_node,
    )


def _court_readiness_from_row(row: dict[str, Any]) -> CourtReadiness:
    content_approved = bool(row["content_review_approved"])
    h1_valid = bool(row["h1_valid"])
    event_chain_valid = bool(row["event_chain_valid"])
    verified_event_present = bool(row["verified_event_present"])
    source_reviewed = row["source_review_status"] == "reviewed"
    source_verified = (
        row["source_custody_status"] == "verified"
        and source_reviewed
        and row.get("source_verified_by") is not None
        and row.get("source_verified_at") is not None
        and verified_event_present
    )
    authenticated = bool(row["is_authenticated"]) and row.get("authentication_method") is not None
    export_band = row["confidence_tier"] in {"high", "medium"}
    not_hypothesis = not bool(row["is_hypothesis"])
    redaction_clear = row["redaction_status"] != "required" and (
        row["redaction_status"] == "applied"
        or (row["privacy_sensitivity"] == "none" and row["source_privacy_sensitivity"] == "none")
    )
    sealed = row["sensitivity_tier"] == "sealed" or row["source_sensitivity_tier"] == "sealed"
    view_member = bool(row["court_export_view_member"])

    blockers: list[CourtReadinessBlocker] = []
    if not content_approved:
        blockers.append(CourtReadinessBlocker.content_review_required)
    if not source_verified:
        blockers.append(CourtReadinessBlocker.custody_not_verified)
    if not h1_valid or not event_chain_valid:
        blockers.append(CourtReadinessBlocker.custody_chain_invalid)
    if not authenticated:
        blockers.append(CourtReadinessBlocker.authentication_required)
    if not export_band:
        blockers.append(CourtReadinessBlocker.confidence_not_exportable)
    if not not_hypothesis:
        blockers.append(CourtReadinessBlocker.hypothesis_not_exportable)
    if not redaction_clear:
        blockers.append(CourtReadinessBlocker.redaction_required)
    if sealed:
        blockers.append(CourtReadinessBlocker.sensitivity_sealed)
    if not bool(row["safe_for_legal_use"]) or not view_member:
        blockers.append(CourtReadinessBlocker.not_released)

    gates = CourtReadinessGates(
        content_review=ContentReviewGate(
            approved=content_approved,
            decision_id=row.get("content_review_decision_id"),
        ),
        provenance=ProvenanceReadinessGate(exact=True),
        custody=CustodyReadinessGate(
            h1_valid=h1_valid,
            event_chain_valid=event_chain_valid,
            verified_event_present=verified_event_present,
            source_status=row["source_custody_status"],
            source_reviewed=source_reviewed,
            verified_by=row.get("source_verified_by"),
            verified_at=row.get("source_verified_at"),
        ),
        authentication=AuthenticationReadinessGate(
            authenticated=authenticated,
            method=row.get("authentication_method"),
        ),
        confidence=ConfidenceReadinessGate(
            value=float(row["confidence"]) if row.get("confidence") is not None else None,
            tier=row["confidence_tier"],
            export_band=export_band,
        ),
        assertion=AssertionReadinessGate(not_hypothesis=not_hypothesis),
        redaction=RedactionReadinessGate(
            privacy_sensitivity=row["privacy_sensitivity"],
            source_privacy_sensitivity=row["source_privacy_sensitivity"],
            status=row["redaction_status"],
            clear_for_export=redaction_clear,
        ),
        sensitivity=SensitivityReadinessGate(
            evidence_tier=row["sensitivity_tier"],
            source_tier=row["source_sensitivity_tier"],
            sealed=sealed,
        ),
        court_export=CourtExportReadinessGate(view_member=view_member),
    )
    return CourtReadiness(
        evidence_item_id=row["id"],
        matter_id=row["matter_id"],
        readiness_passed=(
            view_member
            and content_approved
            and h1_valid
            and event_chain_valid
            and source_verified
            and authenticated
            and export_band
            and not_hypothesis
            and redaction_clear
            and not sealed
            and bool(row["safe_for_legal_use"])
        ),
        blockers=blockers,
        gates=gates,
    )


_MATTER_SELECT = """
SELECT m.id, m.title, m.description, m.status, m.created_at, m.updated_at,
       COALESCE(array_agg(mp.partition_key ORDER BY mp.partition_key)
         FILTER (WHERE mp.partition_key IS NOT NULL), ARRAY[]::text[]) AS partition_keys
FROM analysis.matter m
LEFT JOIN analysis.matter_knowledge_partition mp ON mp.matter_id = m.id
"""


def list_matters(*, limit: int, offset: int) -> MatterList:
    with _get_engine().connect() as conn:
        total = int(conn.execute(text("SELECT count(*) FROM analysis.matter")).scalar() or 0)
        rows = (
            conn.execute(
                text(_MATTER_SELECT + " GROUP BY m.id ORDER BY m.updated_at DESC, m.id LIMIT :limit OFFSET :offset"),
                {"limit": limit, "offset": offset},
            )
            .mappings()
            .all()
        )
    return MatterList(data=[_matter_from_row(dict(row)) for row in rows], total=total, limit=limit, offset=offset)


def create_matter(body: MatterCreate) -> Matter:
    try:
        with _get_engine().begin() as conn:
            row = (
                conn.execute(
                    text(
                        "INSERT INTO analysis.matter (title, description, created_by) "
                        "VALUES (:title, :description, :created_by) "
                        "RETURNING id, title, description, status, created_at, updated_at"
                    ),
                    body.model_dump(include={"title", "description", "created_by"}),
                )
                .mappings()
                .one()
            )
            matter_id = row["id"]
            partition_key = body.partition_key or str(matter_id)
            default_case_id = conn.execute(
                text(
                    "INSERT INTO analysis.court_case "
                    "(matter_id, caption, status, is_primary, created_by) "
                    "VALUES (:matter_id, :caption, 'pre_filing', true, :created_by) "
                    "RETURNING id"
                ),
                {"matter_id": matter_id, "caption": body.title, "created_by": body.created_by},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO analysis.matter_knowledge_partition "
                    "(partition_key, matter_id, default_court_case_id, created_by) "
                    "VALUES (:partition_key, :matter_id, :default_case_id, :created_by)"
                ),
                {
                    "partition_key": partition_key,
                    "matter_id": matter_id,
                    "default_case_id": default_case_id,
                    "created_by": body.created_by,
                },
            )
            return _matter_from_row({**dict(row), "partition_keys": [partition_key]})
    except IntegrityError as exc:
        raise CaseRepositoryError("matter title or partition key already exists", 409) from exc


def get_matter(matter_id: UUID) -> MatterDetail:
    with _get_engine().connect() as conn:
        row = (
            conn.execute(text(_MATTER_SELECT + " WHERE m.id = :matter_id GROUP BY m.id"), {"matter_id": matter_id})
            .mappings()
            .first()
        )
        if row is None:
            raise CaseRepositoryError("matter not found", 404)
        cases = (
            conn.execute(
                text(
                    "SELECT id, matter_id, caption, docket_number, court_name, jurisdiction, case_type, "
                    "status, filed_on, closed_on, is_primary, created_at, updated_at "
                    "FROM analysis.court_case WHERE matter_id = :matter_id "
                    "ORDER BY is_primary DESC, created_at, id"
                ),
                {"matter_id": matter_id},
            )
            .mappings()
            .all()
        )
    matter = _matter_from_row(dict(row))
    return MatterDetail(**matter.model_dump(), court_cases=[_court_case_from_row(dict(case)) for case in cases])


def create_court_case(matter_id: UUID, body: CourtCaseCreate) -> CourtCase:
    try:
        with _get_engine().begin() as conn:
            if not conn.execute(text("SELECT 1 FROM analysis.matter WHERE id = :id"), {"id": matter_id}).first():
                raise CaseRepositoryError("matter not found", 404)

            has_case = bool(
                conn.execute(
                    text("SELECT 1 FROM analysis.court_case WHERE matter_id = :matter_id LIMIT 1"),
                    {"matter_id": matter_id},
                ).first()
            )
            is_primary = body.is_primary or not has_case
            if is_primary:
                conn.execute(
                    text("UPDATE analysis.court_case SET is_primary = false WHERE matter_id = :matter_id"),
                    {"matter_id": matter_id},
                )
            values = body.model_dump(exclude={"is_primary"})
            row = (
                conn.execute(
                    text(
                        "INSERT INTO analysis.court_case "
                        "(matter_id, caption, docket_number, court_name, jurisdiction, case_type, status, "
                        " filed_on, closed_on, is_primary, created_by) "
                        "VALUES (:matter_id, :caption, :docket_number, :court_name, :jurisdiction, :case_type, "
                        " :status, :filed_on, :closed_on, :is_primary, :created_by) "
                        "RETURNING id, matter_id, caption, docket_number, court_name, jurisdiction, case_type, "
                        "status, filed_on, closed_on, is_primary, created_at, updated_at"
                    ),
                    {**values, "matter_id": matter_id, "is_primary": is_primary},
                )
                .mappings()
                .one()
            )
            if is_primary:
                conn.execute(
                    text(
                        "UPDATE analysis.matter_knowledge_partition SET default_court_case_id = :case_id "
                        "WHERE matter_id = :matter_id"
                    ),
                    {"case_id": row["id"], "matter_id": matter_id},
                )
            return _court_case_from_row(dict(row))
    except IntegrityError as exc:
        raise CaseRepositoryError("court case conflicts with an existing proceeding", 409) from exc


def _require_partition(conn: Any, matter_id: UUID, partition_key: str) -> None:
    if not conn.execute(text("SELECT 1 FROM analysis.matter WHERE id = :id"), {"id": matter_id}).first():
        raise CaseRepositoryError("matter not found", 404)
    matched = conn.execute(
        text(
            "SELECT 1 FROM analysis.matter_knowledge_partition "
            "WHERE matter_id = :matter_id AND partition_key = :partition_key"
        ),
        {"matter_id": matter_id, "partition_key": partition_key},
    ).first()
    if not matched:
        raise CaseRepositoryError("knowledge partition is not authorized for this matter", 403)


_SOURCE_SELECT = """
SELECT nr.id AS normalized_record_id, nr.artifact_id, nr.conversation_id,
       nr.record_type, nr.role, nr.content, nr.occurred_at, nr.disclosure_tier,
       nr.review_status, nr.provenance_id AS source_run_id,
       eh.id AS evidence_hash_id, eh.source_id, eh.file_node_id,
       encode(eh.digest, 'hex') AS sha256
FROM working.normalized_record nr
JOIN evidence.evidence_hash eh ON eh.id = nr.artifact_id
WHERE nr.case_id = :partition_key
  AND nr.artifact_id = :artifact_id
  AND eh.level = 'H1'
  AND eh.algo = 'sha256'
  AND eh.canon_version = 'h1-rawbytes-v1'
  AND octet_length(eh.digest) = 32
  AND eh.source_id IS NOT NULL
  AND encode(eh.digest, 'hex') = :sha256
"""


def resolve_source(matter_id: UUID, body: KnowledgeSourceResolveRequest) -> KnowledgeSourceResolution:
    if body.lane != "evidence":
        raise CaseRepositoryError("only custody-backed evidence-lane knowledge can be promoted", 422)
    params: dict[str, Any] = {
        "partition_key": body.partition_key,
        "artifact_id": body.artifact_id,
        "sha256": body.sha256,
    }
    query = _SOURCE_SELECT
    if body.conversation_id is not None:
        query += " AND nr.conversation_id = :conversation_id"
        params["conversation_id"] = body.conversation_id
    if body.quote:
        query += " AND position(:quote in nr.content) > 0"
        params["quote"] = body.quote
    query += " ORDER BY nr.occurred_at NULLS LAST, nr.id LIMIT 500"

    with _get_engine().connect() as conn:
        _require_partition(conn, matter_id, body.partition_key)
        rows = conn.execute(text(query), params).mappings().all()

    return KnowledgeSourceResolution(
        matter_id=matter_id,
        candidates=[_candidate_from_row(dict(row)) for row in rows],
    )


def _resolve_selected_source(conn: Any, matter_id: UUID, body: EvidenceItemCreate) -> dict[str, Any]:
    source = body.source
    _require_partition(conn, matter_id, source.partition_key)
    if source.lane != "evidence":
        raise CaseRepositoryError("only custody-backed evidence-lane knowledge can be promoted", 422)
    case_owner = conn.execute(
        text("SELECT 1 FROM analysis.court_case WHERE id = :case_id AND matter_id = :matter_id"),
        {"case_id": body.court_case_id, "matter_id": matter_id},
    ).first()
    if not case_owner:
        raise CaseRepositoryError("court case is not part of this matter", 403)

    params: dict[str, Any] = {
        "partition_key": source.partition_key,
        "artifact_id": source.artifact_id,
        "sha256": source.sha256,
        "record_id": source.normalized_record_id,
    }
    query = _SOURCE_SELECT + " AND nr.id = :record_id"
    if source.conversation_id is not None:
        query += " AND nr.conversation_id = :conversation_id"
        params["conversation_id"] = source.conversation_id
    row = conn.execute(text(query), params).mappings().first()
    if row is None:
        raise CaseRepositoryError("selected record has no matching custody-backed provenance", 422)
    return dict(row)


def _promotion_identity(
    matter_id: UUID, body: EvidenceItemCreate, source_row: dict[str, Any]
) -> tuple[str, str, dict[str, Any]]:
    quote = body.quote if body.quote is not None else body.source.quote
    pointer = {
        "matter_id": str(matter_id),
        "court_case_id": str(body.court_case_id),
        "partition_key": body.source.partition_key,
        "lane": body.source.lane,
        "normalized_record_id": str(source_row["normalized_record_id"]),
        "evidence_hash_id": str(source_row["evidence_hash_id"]),
        "source_id": str(source_row["source_id"]),
        "sha256": source_row["sha256"],
        "conversation_id": source_row.get("conversation_id"),
        "retrieval_ref": body.source.retrieval_ref,
        "content_ref": body.source.content_ref,
        "chunk_ref": body.source.chunk_ref,
        "quote": quote,
    }
    # Retrieval/content/chunk refs are useful trace metadata but are adapter-
    # generated and can change when the same canonical record is reindexed.
    # Dedupe on authoritative provenance + selected quote, not those refs.
    stable_pointer = {
        key: value for key, value in pointer.items() if key not in {"retrieval_ref", "content_ref", "chunk_ref"}
    }
    canonical = json.dumps(stable_pointer, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    pointer_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    dedupe_material = f"{matter_id}|{body.court_case_id}|{pointer_hash}"
    return hashlib.sha256(dedupe_material.encode()).hexdigest(), pointer_hash, pointer


def _database_pointer_hash(conn: Any, pointer: dict[str, Any]) -> str:
    """Use the migration-owned canonicalizer so app and DB cannot drift."""
    return str(
        conn.execute(
            text("SELECT encode(analysis.knowledge_evidence_pointer_hash(CAST(:source_pointer AS jsonb)), 'hex')"),
            {"source_pointer": json.dumps(pointer)},
        ).scalar_one()
    )


_EVIDENCE_RETURNING = """
id, matter_id, court_case_id, title, description, quote, evidence_type,
evidence_date, normalized_record_id, evidence_hash_id, source_id,
file_node_id, source_run_id,
review_status, hitl_required, safe_for_legal_use, is_authenticated,
created_by, created_at
"""


def _existing_promotion(conn: Any, matter_id: UUID, pointer_hash: str) -> EvidencePromotionResult | None:
    row = (
        conn.execute(
            text(
                "SELECT ei.id, ei.matter_id, ei.court_case_id, ei.title, ei.description, ei.quote, "
                "ei.evidence_type, ei.evidence_date, ei.normalized_record_id, ei.evidence_hash_id, "
                "ei.source_id, ei.file_node_id, ei.source_run_id, ei.review_status, ei.hitl_required, "
                "ei.safe_for_legal_use, ei.is_authenticated, ei.created_by, ei.created_at, "
                "p.id AS promotion_id "
                "FROM analysis.knowledge_evidence_promotion p "
                "JOIN analysis.evidence_item ei ON ei.id = p.evidence_item_id "
                "WHERE p.matter_id = :matter_id AND p.source_pointer_hash = :pointer_hash "
                "LIMIT 1"
            ),
            {"matter_id": matter_id, "pointer_hash": bytes.fromhex(pointer_hash)},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return EvidencePromotionResult(
        item=_evidence_item_from_row(dict(row)), promotion_id=row["promotion_id"], created=False
    )


def promote_evidence(matter_id: UUID, body: EvidenceItemCreate) -> EvidencePromotionResult:
    with _get_engine().begin() as conn:
        source_row = _resolve_selected_source(conn, matter_id, body)
        quote = body.quote if body.quote is not None else body.source.quote
        if quote is not None and quote not in source_row["content"]:
            raise CaseRepositoryError("quote is not contained in the selected normalized record", 422)

        _, _, pointer = _promotion_identity(matter_id, body, source_row)
        pointer_hash = _database_pointer_hash(conn, pointer)
        dedupe_material = f"{matter_id}|{body.court_case_id}|{pointer_hash}"
        dedupe_key = hashlib.sha256(dedupe_material.encode()).hexdigest()
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": dedupe_key})
        existing = _existing_promotion(conn, matter_id, pointer_hash)
        if existing is not None:
            return existing

        item_row = (
            conn.execute(
                text(
                    "INSERT INTO analysis.evidence_item "
                    "(case_id, matter_id, court_case_id, source_id, file_node_id, normalized_record_id, "
                    " evidence_hash_id, source_run_id, "
                    " title, description, quote, evidence_type, evidence_date, created_by, metadata) "
                    "VALUES (:court_case_id, :matter_id, :court_case_id, :source_id, :file_node_id, "
                    " :record_id, :hash_id, :source_run_id, "
                    " :title, :description, :quote, :evidence_type, :evidence_date, :created_by, "
                    " CAST(:metadata AS jsonb)) RETURNING " + _EVIDENCE_RETURNING
                ),
                {
                    "matter_id": matter_id,
                    "court_case_id": body.court_case_id,
                    "source_id": source_row["source_id"],
                    "file_node_id": source_row.get("file_node_id"),
                    "source_run_id": source_row.get("source_run_id"),
                    "record_id": source_row["normalized_record_id"],
                    "hash_id": source_row["evidence_hash_id"],
                    "title": body.title,
                    "description": body.description,
                    "quote": quote,
                    "evidence_type": body.evidence_type,
                    "evidence_date": source_row.get("occurred_at"),
                    "created_by": body.created_by,
                    "metadata": json.dumps({"promotion_source_pointer_hash": pointer_hash}),
                },
            )
            .mappings()
            .one()
        )
        promotion_id = conn.execute(
            text(
                "INSERT INTO analysis.knowledge_evidence_promotion "
                "(idempotency_key, partition_key, matter_id, court_case_id, evidence_item_id, "
                " normalized_record_id, evidence_hash_id, source_id, file_node_id, source_run_id, "
                " knowledge_lane, retrieval_item_ref, content_ref, chunk_ref, source_pointer, "
                " source_pointer_hash, promoted_by) "
                "VALUES (:dedupe_key, :partition_key, :matter_id, :court_case_id, :item_id, "
                " :record_id, :hash_id, :source_id, :file_node_id, :source_run_id, :lane, "
                " :retrieval_ref, :content_ref, :chunk_ref, CAST(:pointer AS jsonb), :pointer_hash, "
                " :promoted_by) RETURNING id"
            ),
            {
                "dedupe_key": dedupe_key,
                "partition_key": body.source.partition_key,
                "matter_id": matter_id,
                "court_case_id": body.court_case_id,
                "item_id": item_row["id"],
                "record_id": source_row["normalized_record_id"],
                "hash_id": source_row["evidence_hash_id"],
                "source_id": source_row["source_id"],
                "file_node_id": source_row.get("file_node_id"),
                "source_run_id": source_row.get("source_run_id"),
                "lane": body.source.lane,
                "retrieval_ref": body.source.retrieval_ref,
                "content_ref": body.source.content_ref,
                "chunk_ref": body.source.chunk_ref,
                "pointer": json.dumps(pointer, sort_keys=True),
                "pointer_hash": bytes.fromhex(pointer_hash),
                "promoted_by": body.created_by,
            },
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO analysis.review_task "
                "(trigger_code, target_kind, target_id, blocks, reviewer_role, state, created_by) "
                "VALUES ('knowledge_evidence_promotion', 'evidence_item', :item_id, "
                "'legal_use', 'owner', 'pending', :created_by)"
            ),
            {"item_id": item_row["id"], "created_by": body.created_by},
        )

        from server.core.audit import record as audit_record

        audit_record(
            "write",
            str(item_row["id"]),
            actor=body.created_by,
            ctx={"case_id": str(body.court_case_id), "matter_id": str(matter_id), "actor": body.created_by},
            object_schema="analysis.evidence_item",
            payload_hash=pointer_hash,
            connection=conn,
        )
        item = _evidence_item_from_row(dict(item_row))
        return EvidencePromotionResult(item=item, promotion_id=promotion_id, created=True)


def review_evidence(
    matter_id: UUID,
    evidence_item_id: UUID,
    body: EvidenceReviewCreate,
) -> EvidenceReviewResult:
    """Record one reviewer-of-record decision without granting legal safety."""
    with _get_engine().begin() as conn:
        item_row = (
            conn.execute(
                text(
                    "SELECT ei.id, ei.matter_id, ei.court_case_id, ei.title, ei.description, "
                    "ei.quote, ei.evidence_type, ei.evidence_date, ei.normalized_record_id, "
                    "ei.evidence_hash_id, ei.source_id, ei.file_node_id, ei.source_run_id, "
                    "ei.review_status, ei.hitl_required, ei.safe_for_legal_use, "
                    "ei.is_authenticated, ei.created_by, ei.created_at "
                    "FROM analysis.evidence_item ei "
                    "JOIN analysis.knowledge_evidence_promotion promotion "
                    "  ON promotion.evidence_item_id = ei.id "
                    "WHERE ei.id = :item_id AND ei.matter_id = :matter_id FOR UPDATE"
                ),
                {"item_id": evidence_item_id, "matter_id": matter_id},
            )
            .mappings()
            .first()
        )
        if item_row is None:
            raise CaseRepositoryError("promoted evidence item not found in this matter", 404)

        task_id = conn.execute(
            text(
                "SELECT task_id FROM analysis.review_task "
                "WHERE target_kind = 'evidence_item' AND target_id = :item_id "
                "  AND trigger_code = 'knowledge_evidence_promotion' "
                "  AND state IN ('pending', 'in_review') "
                "ORDER BY created_at, task_id LIMIT 1 FOR UPDATE"
            ),
            {"item_id": evidence_item_id},
        ).scalar()
        if task_id is None:
            raise CaseRepositoryError("evidence review is already resolved", 409)

        terminal = body.decision in {
            EvidenceReviewDecision.approved,
            EvidenceReviewDecision.rejected,
        }
        review_status = (
            ReviewState.approved
            if body.decision == EvidenceReviewDecision.approved
            else ReviewState.rejected
            if body.decision == EvidenceReviewDecision.rejected
            else ReviewState.in_review
        )
        court_readiness = (
            "review_passed"
            if body.decision == EvidenceReviewDecision.approved
            else "excluded"
            if body.decision == EvidenceReviewDecision.rejected
            else "draft"
        )
        decision_id = conn.execute(
            text(
                "INSERT INTO analysis.review_decision "
                "(task_id, target_kind, target_id, reviewer, decision, court_readiness, rationale) "
                "VALUES (:task_id, 'evidence_item', :item_id, :reviewer, :decision, "
                ":court_readiness, :rationale) RETURNING decision_id"
            ),
            {
                "task_id": task_id,
                "item_id": evidence_item_id,
                "reviewer": body.reviewer,
                "decision": body.decision.value,
                "court_readiness": court_readiness,
                "rationale": body.rationale,
            },
        ).scalar_one()
        updated = (
            conn.execute(
                text(
                    "UPDATE analysis.evidence_item SET "
                    "review_status = :review_status, hitl_required = :hitl_required, "
                    "safe_for_legal_use = false "
                    "WHERE id = :item_id RETURNING " + _EVIDENCE_RETURNING
                ),
                {
                    "review_status": review_status.value,
                    "hitl_required": not terminal,
                    "item_id": evidence_item_id,
                },
            )
            .mappings()
            .one()
        )
        conn.execute(
            text("UPDATE analysis.review_task SET state = :state WHERE task_id = :task_id"),
            {"state": "resolved" if terminal else "in_review", "task_id": task_id},
        )

        from server.core.audit import record as audit_record

        decision_hash = hashlib.sha256(
            json.dumps(
                {
                    "decision": body.decision.value,
                    "rationale": body.rationale,
                    "reviewer": body.reviewer,
                    "task_id": str(task_id),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        audit_record(
            "approval",
            str(decision_id),
            actor=body.reviewer,
            ctx={"case_id": str(updated["court_case_id"]), "matter_id": str(matter_id)},
            object_schema="analysis.review_decision",
            payload_hash=decision_hash,
            connection=conn,
        )
        return EvidenceReviewResult(
            item=_evidence_item_from_row(dict(updated)),
            task_id=task_id,
            decision_id=decision_id,
            decision=body.decision,
            court_readiness=court_readiness,
        )


def list_evidence_reviews(
    matter_id: UUID,
    evidence_item_id: UUID,
) -> EvidenceReviewList:
    """Return append-only reviewer-of-record history for one promoted item."""
    with _get_engine().connect() as conn:
        owned = conn.execute(
            text(
                "SELECT 1 FROM analysis.evidence_item item "
                "JOIN analysis.knowledge_evidence_promotion promotion "
                "  ON promotion.evidence_item_id = item.id "
                "WHERE item.id = :item_id AND item.matter_id = :matter_id"
            ),
            {"item_id": evidence_item_id, "matter_id": matter_id},
        ).first()
        if not owned:
            raise CaseRepositoryError("promoted evidence item not found in this matter", 404)
        rows = (
            conn.execute(
                text(
                    "SELECT decision_id, task_id, target_id AS evidence_item_id, reviewer, "
                    "decision, court_readiness, rationale, decided_at "
                    "FROM analysis.review_decision "
                    "WHERE target_kind = 'evidence_item' AND target_id = :item_id "
                    "ORDER BY decided_at, decision_id"
                ),
                {"item_id": evidence_item_id},
            )
            .mappings()
            .all()
        )
    records = [EvidenceReviewRecord.model_validate(dict(row)) for row in rows]
    return EvidenceReviewList(data=records, total=len(records))


def list_evidence_items(
    matter_id: UUID,
    *,
    review_status: ReviewState | None,
    limit: int,
    offset: int,
) -> EvidenceItemList:
    with _get_engine().connect() as conn:
        if not conn.execute(text("SELECT 1 FROM analysis.matter WHERE id = :id"), {"id": matter_id}).first():
            raise CaseRepositoryError("matter not found", 404)
        where = "ei.matter_id = :matter_id"
        params: dict[str, Any] = {"matter_id": matter_id, "limit": limit, "offset": offset}
        if review_status is not None:
            where += " AND ei.review_status = :review_status"
            params["review_status"] = review_status.value
        total = int(
            conn.execute(text(f"SELECT count(*) FROM analysis.evidence_item ei WHERE {where}"), params).scalar() or 0
        )
        rows = (
            conn.execute(
                text(
                    "SELECT ei.id, ei.matter_id, ei.court_case_id, ei.title, ei.description, ei.quote, "
                    "ei.evidence_type, ei.evidence_date, ei.normalized_record_id, ei.evidence_hash_id, "
                    "ei.source_id, ei.file_node_id, ei.source_run_id, ei.review_status, ei.hitl_required, "
                    "ei.safe_for_legal_use, ei.is_authenticated, ei.created_by, ei.created_at "
                    "FROM analysis.evidence_item ei "
                    f"WHERE {where} ORDER BY ei.created_at DESC, ei.id LIMIT :limit OFFSET :offset"
                ),
                params,
            )
            .mappings()
            .all()
        )
    return EvidenceItemList(
        data=[_evidence_item_from_row(dict(row)) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_evidence_detail(matter_id: UUID, evidence_item_id: UUID) -> EvidenceItemDetail:
    """Return one exact promoted item with its public custody chain."""
    query = text(
        """
        SELECT
            ei.id, ei.matter_id, ei.court_case_id, ei.title, ei.description, ei.quote,
            ei.evidence_type, ei.evidence_date, ei.normalized_record_id,
            ei.evidence_hash_id, ei.source_id, ei.file_node_id, ei.source_run_id,
            ei.review_status, ei.hitl_required, ei.safe_for_legal_use,
            ei.is_authenticated, ei.created_by, ei.created_at,
            promotion.id AS promotion_id,
            promotion.partition_key AS promotion_partition_key,
            promotion.knowledge_lane AS promotion_knowledge_lane,
            promotion.retrieval_item_ref AS promotion_retrieval_item_ref,
            promotion.content_ref AS promotion_content_ref,
            promotion.chunk_ref AS promotion_chunk_ref,
            promotion.source_pointer AS promotion_source_pointer,
            promotion.promoted_by AS promotion_promoted_by,
            promotion.promoted_at AS promotion_promoted_at,
            record.id AS record_id,
            record.record_type AS record_type,
            record.source AS record_source,
            record.conversation_id AS record_conversation_id,
            record.role AS record_role,
            record.content AS record_content,
            record.occurred_at AS record_occurred_at,
            record.acquired_at AS record_acquired_at,
            record.ingested_at AS record_ingested_at,
            record.realized_at AS record_realized_at,
            record.disclosure_tier AS record_disclosure_tier,
            record.review_status AS record_review_status,
            record.case_id AS record_case_id,
            custody_hash.id AS custody_hash_id,
            custody_hash.source_ref AS custody_hash_source_ref,
            custody_hash.algo AS custody_hash_algo,
            encode(custody_hash.digest, 'hex') AS custody_hash_digest_sha256,
            custody_hash.level AS custody_hash_level,
            custody_hash.canon_version AS custody_hash_canon_version,
            custody_hash.hashed_at AS custody_hash_hashed_at,
            custody_hash.computed_by AS custody_hash_computed_by,
            custody_source.id AS custody_source_id,
            encode(custody_source.sha256, 'hex') AS custody_source_sha256,
            custody_source.byte_size AS custody_source_byte_size,
            custody_source.mime_type AS custody_source_mime_type,
            custody_source.original_filename AS custody_source_original_filename,
            custody_source.source_type AS custody_source_type,
            custody_source.source_platform AS custody_source_platform,
            custody_source.acquisition_source AS custody_source_acquisition_source,
            custody_source.acquisition_method AS custody_source_acquisition_method,
            custody_source.acquired_at_utc AS custody_source_acquired_at_utc,
            custody_source.acquired_certainty AS custody_source_acquired_certainty,
            custody_source.provenance_tier AS custody_source_provenance_tier,
            custody_source.hash_canon_version AS custody_source_hash_canon_version,
            custody_source.custody_status AS custody_source_custody_status,
            custody_source.review_status AS custody_source_review_status,
            custody_source.verified_by AS custody_source_verified_by,
            custody_source.verified_at AS custody_source_verified_at,
            file_node.id AS detail_file_node_id,
            file_node.node_kind AS file_node_kind,
            file_node.node_path::text AS file_node_path,
            file_node.ordinal AS file_node_ordinal,
            encode(file_node.sha256, 'hex') AS file_node_sha256,
            file_node.byte_span_start AS file_node_byte_span_start,
            file_node.byte_span_end AS file_node_byte_span_end,
            file_node.locator AS file_node_locator,
            file_node.mime_type AS file_node_mime_type
        FROM analysis.evidence_item ei
        JOIN analysis.knowledge_evidence_promotion promotion
          ON promotion.evidence_item_id = ei.id
         AND promotion.matter_id = ei.matter_id
         AND promotion.court_case_id = ei.court_case_id
         AND promotion.normalized_record_id = ei.normalized_record_id
         AND promotion.evidence_hash_id = ei.evidence_hash_id
         AND promotion.source_id = ei.source_id
         AND promotion.file_node_id IS NOT DISTINCT FROM ei.file_node_id
         AND promotion.source_run_id IS NOT DISTINCT FROM ei.source_run_id
        JOIN working.normalized_record record
          ON record.id = promotion.normalized_record_id
         AND record.artifact_id = promotion.evidence_hash_id
         AND record.case_id = promotion.partition_key
         AND record.provenance_id IS NOT DISTINCT FROM promotion.source_run_id
        JOIN evidence.evidence_hash custody_hash
          ON custody_hash.id = promotion.evidence_hash_id
         AND custody_hash.source_id = promotion.source_id
         AND custody_hash.file_node_id IS NOT DISTINCT FROM promotion.file_node_id
        JOIN evidence.source custody_source
          ON custody_source.id = promotion.source_id
        LEFT JOIN evidence.file_node file_node
          ON file_node.id = promotion.file_node_id
         AND file_node.source_id = promotion.source_id
        WHERE ei.id = :evidence_item_id
          AND ei.matter_id = :matter_id
          AND promotion.knowledge_lane = 'evidence'
          AND custody_hash.algo = 'sha256'
          AND octet_length(custody_hash.digest) = 32
          AND custody_hash.level = 'H1'
          AND custody_hash.canon_version = 'h1-rawbytes-v1'
          AND (promotion.file_node_id IS NULL OR file_node.id IS NOT NULL)
          AND promotion.source_pointer->>'matter_id' = promotion.matter_id::text
          AND promotion.source_pointer->>'court_case_id' = promotion.court_case_id::text
          AND promotion.source_pointer->>'partition_key' = promotion.partition_key
          AND promotion.source_pointer->>'lane' = promotion.knowledge_lane
          AND promotion.source_pointer->>'normalized_record_id' = promotion.normalized_record_id::text
          AND promotion.source_pointer->>'evidence_hash_id' = promotion.evidence_hash_id::text
          AND promotion.source_pointer->>'source_id' = promotion.source_id::text
          AND promotion.source_pointer->>'sha256' = encode(custody_hash.digest, 'hex')
          AND analysis.knowledge_evidence_pointer_hash(promotion.source_pointer)
              = promotion.source_pointer_hash
        """
    )
    with _get_engine().connect() as conn:
        row = (
            conn.execute(
                query,
                {"matter_id": matter_id, "evidence_item_id": evidence_item_id},
            )
            .mappings()
            .first()
        )
    if row is None:
        raise CaseRepositoryError("promoted evidence item not found in this matter", 404)
    return _evidence_detail_from_row(dict(row))


def get_court_readiness(matter_id: UUID, evidence_item_id: UUID) -> CourtReadiness:
    """Evaluate exact custody and export gates without trusting session timezone.

    The legacy, unversioned custody trigger hashed a session-rendered timestamp.
    Verification therefore tries the complete modern civil-offset grid
    (-12:00 through +14:00 in 15-minute increments) while retaining the
    trigger's exact timestamp/string construction. Platform custody events
    postdate historical sub-15-minute IANA offsets.
    """
    query = text(
        """
        WITH exact_item AS (
            SELECT
                ei.id, ei.matter_id, ei.evidence_hash_id, ei.file_node_id,
                ei.review_status, ei.hitl_required,
                ei.safe_for_legal_use, ei.is_hypothesis, ei.is_authenticated,
                ei.authentication_method, ei.confidence, ei.confidence_tier,
                ei.privacy_sensitivity, ei.redaction_status, ei.sensitivity_tier,
                custody_hash.algo AS hash_algo,
                octet_length(custody_hash.digest) AS hash_length,
                custody_hash.level AS hash_level,
                custody_hash.canon_version AS hash_canon_version,
                custody_source.id AS source_id,
                custody_source.custody_status AS source_custody_status,
                custody_source.review_status AS source_review_status,
                custody_source.verified_by AS source_verified_by,
                custody_source.verified_at AS source_verified_at,
                custody_source.privacy_sensitivity AS source_privacy_sensitivity,
                custody_source.sensitivity_tier AS source_sensitivity_tier
            FROM analysis.evidence_item ei
            JOIN analysis.knowledge_evidence_promotion promotion
              ON promotion.evidence_item_id = ei.id
             AND promotion.matter_id = ei.matter_id
             AND promotion.court_case_id = ei.court_case_id
             AND promotion.normalized_record_id = ei.normalized_record_id
             AND promotion.evidence_hash_id = ei.evidence_hash_id
             AND promotion.source_id = ei.source_id
             AND promotion.file_node_id IS NOT DISTINCT FROM ei.file_node_id
             AND promotion.source_run_id IS NOT DISTINCT FROM ei.source_run_id
            JOIN working.normalized_record record
              ON record.id = promotion.normalized_record_id
             AND record.artifact_id = promotion.evidence_hash_id
             AND record.case_id = promotion.partition_key
             AND record.provenance_id IS NOT DISTINCT FROM promotion.source_run_id
            JOIN evidence.evidence_hash custody_hash
              ON custody_hash.id = promotion.evidence_hash_id
             AND custody_hash.source_id = promotion.source_id
             AND custody_hash.file_node_id IS NOT DISTINCT FROM promotion.file_node_id
            JOIN evidence.source custody_source
              ON custody_source.id = promotion.source_id
            LEFT JOIN evidence.file_node file_node
              ON file_node.id = promotion.file_node_id
             AND file_node.source_id = promotion.source_id
            WHERE ei.id = :evidence_item_id
              AND ei.matter_id = :matter_id
              AND promotion.knowledge_lane = 'evidence'
              AND (promotion.file_node_id IS NULL OR file_node.id IS NOT NULL)
              AND promotion.source_pointer->>'matter_id' = promotion.matter_id::text
              AND promotion.source_pointer->>'court_case_id' = promotion.court_case_id::text
              AND promotion.source_pointer->>'partition_key' = promotion.partition_key
              AND promotion.source_pointer->>'lane' = promotion.knowledge_lane
              AND promotion.source_pointer->>'normalized_record_id' = promotion.normalized_record_id::text
              AND promotion.source_pointer->>'evidence_hash_id' = promotion.evidence_hash_id::text
              AND promotion.source_pointer->>'source_id' = promotion.source_id::text
              AND promotion.source_pointer->>'sha256' = encode(custody_hash.digest, 'hex')
              AND analysis.knowledge_evidence_pointer_hash(promotion.source_pointer)
                  = promotion.source_pointer_hash
        )
        SELECT
            exact_item.*,
            latest_review.decision_id AS content_review_decision_id,
            (
                exact_item.review_status = 'approved'::ai.review_state
                AND exact_item.hitl_required = false
                AND latest_review.decision = 'approved'
                AND latest_review.court_readiness = 'review_passed'
                AND latest_review.task_state = 'resolved'
            ) AS content_review_approved,
            (
                exact_item.hash_algo = 'sha256'
                AND exact_item.hash_length = 32
                AND exact_item.hash_level = 'H1'
                AND exact_item.hash_canon_version = 'h1-rawbytes-v1'
            ) AS h1_valid,
            COALESCE(custody.event_chain_valid, false) AS event_chain_valid,
            COALESCE(custody.verified_event_present, false) AS verified_event_present,
            EXISTS (
                SELECT 1 FROM analysis.vw_court_export court_export
                 WHERE court_export.id = exact_item.id
            ) AS court_export_view_member
        FROM exact_item
        LEFT JOIN LATERAL (
            SELECT decision.decision_id, decision.decision, decision.court_readiness,
                   task.state AS task_state
              FROM analysis.review_decision decision
              JOIN analysis.review_task task ON task.task_id = decision.task_id
             WHERE decision.target_kind = 'evidence_item'
               AND decision.target_id = exact_item.id
               AND task.target_kind = 'evidence_item'
               AND task.target_id = exact_item.id
               AND task.trigger_code = 'knowledge_evidence_promotion'
             ORDER BY decision.decided_at DESC, decision.decision_id DESC
             LIMIT 1
        ) latest_review ON true
        LEFT JOIN LATERAL (
            SELECT
                COALESCE(
                    bool_and(
                        chained.prev_event_digest IS NOT DISTINCT FROM chained.expected_prev_digest
                        AND chained.event_digest_matches_legacy_trigger
                    ),
                    false
                ) AS event_chain_valid,
                COALESCE(
                    bool_or(
                        chained.event_type = 'verified'
                        AND (
                            (chained.evidence_hash_id IS NULL AND chained.file_node_id IS NULL)
                            OR (
                                chained.evidence_hash_id = exact_item.evidence_hash_id
                                AND chained.file_node_id IS NOT DISTINCT FROM exact_item.file_node_id
                            )
                        )
                    ),
                    false
                ) AS verified_event_present
            FROM (
                SELECT
                    event.event_type,
                    event.evidence_hash_id,
                    event.file_node_id,
                    event.prev_event_digest,
                    event.event_digest,
                    lag(event.event_digest) OVER (ORDER BY event.seq) AS expected_prev_digest,
                    EXISTS (
                        SELECT 1
                        FROM generate_series(-720, 840, 15) AS candidate(offset_minutes)
                        WHERE event.event_digest = digest(
                            convert_to(
                                coalesce(event.source_id::text, '') || '|' ||
                                coalesce(event.file_node_id::text, '') || '|' ||
                                coalesce(event.evidence_hash_id::text, '') || '|' ||
                                event.event_type || '|' || event.actor || '|' ||
                                to_char(
                                    timezone(
                                        make_interval(mins => candidate.offset_minutes),
                                        event.occurred_at
                                    ),
                                    'YYYY-MM-DD"T"HH24:MI:SS.US'
                                ) || ' ' ||
                                CASE WHEN candidate.offset_minutes < 0 THEN '-' ELSE '+' END ||
                                lpad((abs(candidate.offset_minutes) / 60)::text, 2, '0') || ':' ||
                                lpad((abs(candidate.offset_minutes) % 60)::text, 2, '0') || '|' ||
                                coalesce(event.detail::text, '{}') || '|' ||
                                coalesce(encode(event.prev_event_digest, 'hex'), ''),
                                'UTF8'
                            ),
                            'sha256'
                        )
                    ) AS event_digest_matches_legacy_trigger
                FROM evidence.custody_event event
                WHERE event.source_id = exact_item.source_id
                ORDER BY event.seq
            ) chained
        ) custody ON true
        """
    )
    with _get_engine().connect() as conn:
        row = (
            conn.execute(
                query,
                {"matter_id": matter_id, "evidence_item_id": evidence_item_id},
            )
            .mappings()
            .first()
        )
    if row is None:
        raise CaseRepositoryError("promoted evidence item not found in this matter", 404)
    return _court_readiness_from_row(dict(row))
