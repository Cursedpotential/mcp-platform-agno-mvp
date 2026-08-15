"""Exercise the real Matter repository against PostgreSQL, then roll back.

The target must be a clean, explicitly labeled non-production database. The
minimal prerequisite fixture, migration 0030, source data, repository writes,
and audit entry all live inside one outer transaction and are rolled back.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

import argparse
import hashlib
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, text

from server.case_management import repository
from server.contracts.case_management import (
    EvidenceItemCreate,
    EvidenceReviewCreate,
    KnowledgeSourceResolveRequest,
)

if __package__:
    from scripts._matter_validate_0030 import strip_transaction_control, validate_target
else:
    from _matter_validate_0030 import strip_transaction_control, validate_target

ROOT = Path(__file__).resolve().parent.parent
PREREQUISITES = ROOT / "tests" / "fixtures" / "matter_0030_prerequisites.sql"
MIGRATION = ROOT / "sql" / "0030_matter_case_foundation.sql"


class TransactionBoundEngine:
    """Expose Engine-shaped contexts without owning the outer transaction."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    @contextmanager
    def connect(self) -> Iterator[Any]:
        yield self.connection

    @contextmanager
    def begin(self) -> Iterator[Any]:
        yield self.connection


def run_repository_validation(*, dsn: str, target: str) -> None:
    """Run actual repository reads/writes/audit under one rollback boundary."""
    validate_target(target)
    sqlalchemy_dsn = dsn.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(sqlalchemy_dsn, pool_pre_ping=True)
    marker = f"repository-validator-{uuid.uuid4()}"
    sibling_marker = f"{marker}:sibling"
    source_digest = hashlib.sha256(f"{marker}:source".encode()).digest()
    member_digest = hashlib.sha256(f"{marker}:member".encode()).digest()

    with engine.connect() as connection:
        before = connection.execute(
            text("SELECT to_regclass('analysis.matter'), to_regclass('ops.audit_ledger')")
        ).one()
        assert before == (None, None), "target must be a clean disposable database"
        connection.rollback()
        outer = connection.begin()
        previous_engine = repository._engine
        try:
            connection.exec_driver_sql(PREREQUISITES.read_text(encoding="utf-8").replace("%", "%%"))
            connection.exec_driver_sql(
                strip_transaction_control(MIGRATION.read_text(encoding="utf-8")).replace("%", "%%")
            )
            ids = (
                connection.execute(
                    text(
                        "WITH source AS ("
                        " INSERT INTO evidence.source "
                        " (sha256, byte_size, source_type, acquisition_source, original_filename, "
                        "  custody_status, review_status, verified_by, verified_at) "
                        " VALUES (:source_digest, 1, 'other', 'repository-validator', :marker, "
                        "  'verified', 'reviewed', 'owner', now()) RETURNING id"
                        "), node AS ("
                        " INSERT INTO evidence.file_node (source_id, node_kind, sha256) "
                        " SELECT id, 'message_unit', :member_digest FROM source RETURNING id, source_id"
                        "), hash AS ("
                        " INSERT INTO evidence.evidence_hash "
                        " (source_ref, digest, level, source_id, file_node_id, computed_by) "
                        " SELECT :marker, :member_digest, 'H1', node.source_id, node.id, 'repository-validator' "
                        " FROM node RETURNING id, source_id, file_node_id"
                        "), sibling_node AS ("
                        " INSERT INTO evidence.file_node (source_id, node_kind, sha256) "
                        " SELECT id, 'message_unit', digest(:sibling_marker, 'sha256') FROM source "
                        " RETURNING id, source_id"
                        "), sibling_hash AS ("
                        " INSERT INTO evidence.evidence_hash "
                        " (source_ref, digest, level, source_id, file_node_id, computed_by) "
                        " SELECT :sibling_marker, digest(:sibling_marker, 'sha256'), 'H1', "
                        " sibling_node.source_id, sibling_node.id, 'repository-validator' "
                        " FROM sibling_node RETURNING id, file_node_id"
                        "), run AS ("
                        " INSERT INTO ops.processing_run (run_type, actor, status) "
                        " VALUES ('ingestion', 'repository-validator', 'ok') RETURNING run_id"
                        "), record AS ("
                        " INSERT INTO working.normalized_record "
                        " (artifact_id, record_type, source, conversation_id, role, content, "
                        "  occurred_at, provenance_id, case_id, domain) "
                        " SELECT hash.id, 'message', 'repository-validator', :marker, 'owner', "
                        " :content, now(), run.run_id, 'primary', 'evidence' FROM hash, run "
                        " RETURNING id, artifact_id, provenance_id"
                        ") SELECT record.id AS record_id, record.artifact_id AS hash_id, "
                        "record.provenance_id AS run_id, hash.source_id, hash.file_node_id, "
                        "sibling_hash.id AS sibling_hash_id, sibling_hash.file_node_id AS sibling_file_node_id "
                        "FROM record JOIN hash ON hash.id = record.artifact_id CROSS JOIN sibling_hash"
                    ),
                    {
                        "source_digest": source_digest,
                        "member_digest": member_digest,
                        "marker": marker,
                        "sibling_marker": sibling_marker,
                        "content": "Exact repository validation sentence.",
                    },
                )
                .mappings()
                .one()
            )

            connection.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
            connection.execute(
                text(
                    "INSERT INTO evidence.custody_event "
                    "(source_id, event_type, actor, detail) "
                    "VALUES (:source_id, 'collected', 'repository-validator', '{\"scope\":\"source\"}')"
                ),
                {"source_id": ids["source_id"]},
            )
            connection.execute(
                text(
                    "INSERT INTO evidence.custody_event "
                    "(source_id, file_node_id, evidence_hash_id, event_type, actor, detail) "
                    "VALUES (:source_id, :file_node_id, :hash_id, 'verified', "
                    "'repository-validator', '{\"scope\":\"sibling\"}')"
                ),
                {
                    "source_id": ids["source_id"],
                    "file_node_id": ids["sibling_file_node_id"],
                    "hash_id": ids["sibling_hash_id"],
                },
            )

            connection.execute(text("SET LOCAL statement_timeout = '10s'"))
            repository._engine = TransactionBoundEngine(connection)
            matter = repository.list_matters(limit=10, offset=0).data[0]
            detail = repository.get_matter(matter.id)
            court_case = next(item for item in detail.court_cases if item.is_primary)
            sha256 = member_digest.hex()
            source_payload = {
                "lane": "evidence",
                "partition_key": "primary",
                "artifact_id": str(ids["hash_id"]),
                "sha256": sha256,
                "conversation_id": marker,
                "quote": "Exact repository validation sentence.",
                "retrieval_ref": marker,
            }
            resolution = repository.resolve_source(
                matter.id, KnowledgeSourceResolveRequest.model_validate(source_payload)
            )
            assert len(resolution.candidates) == 1
            candidate = resolution.candidates[0]
            assert candidate.normalized_record_id == ids["record_id"]
            body = EvidenceItemCreate.model_validate(
                {
                    "court_case_id": str(court_case.id),
                    "source": {
                        **source_payload,
                        "normalized_record_id": str(candidate.normalized_record_id),
                    },
                    "title": "Repository validation evidence",
                    "quote": "Exact repository validation sentence.",
                    "created_by": "owner",
                }
            )
            first = repository.promote_evidence(matter.id, body)
            second = repository.promote_evidence(matter.id, body)
            assert first.created is True
            assert second.created is False
            assert second.item.id == first.item.id
            assert first.item.review_status.value == "unreviewed"
            assert first.item.hitl_required is True
            assert first.item.safe_for_legal_use is False
            assert first.item.is_authenticated is False
            listed = repository.list_evidence_items(matter.id, review_status=None, limit=10, offset=0)
            assert listed.total == 1 and listed.data[0].id == first.item.id
            custody_detail = repository.get_evidence_detail(matter.id, first.item.id)
            assert custody_detail.item.id == first.item.id
            assert custody_detail.record.content == "Exact repository validation sentence."
            assert custody_detail.custody_hash.digest_sha256 == member_digest.hex()
            assert custody_detail.source.sha256 == source_digest.hex()
            assert custody_detail.custody_hash.digest_sha256 != custody_detail.source.sha256
            assert custody_detail.file_node is not None
            assert custody_detail.file_node.sha256 == member_digest.hex()
            try:
                repository.get_evidence_detail(uuid.uuid4(), first.item.id)
            except repository.CaseRepositoryError as error:
                assert error.status_code == 404
            else:
                raise AssertionError("cross-Matter evidence detail must fail closed")
            reviewed = repository.review_evidence(
                matter.id,
                first.item.id,
                EvidenceReviewCreate(
                    decision="approved",
                    rationale="Scratch reviewer confirmed the record-level promotion only.",
                    reviewer="owner",
                ),
            )
            assert reviewed.item.review_status.value == "approved"
            assert reviewed.item.hitl_required is False
            assert reviewed.item.safe_for_legal_use is False
            assert reviewed.item.is_authenticated is False
            assert reviewed.court_readiness == "review_passed"
            connection.execute(text("SET LOCAL TIME ZONE 'UTC'"))
            sibling_only = repository.get_court_readiness(matter.id, first.item.id)
            assert sibling_only.gates.custody.event_chain_valid is True
            assert sibling_only.gates.custody.verified_event_present is False
            assert sibling_only.gates.court_export.view_member is False
            assert sibling_only.readiness_passed is False
            connection.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
            connection.execute(
                text(
                    "INSERT INTO evidence.custody_event "
                    "(source_id, file_node_id, evidence_hash_id, event_type, actor, detail) "
                    "VALUES (:source_id, :file_node_id, :hash_id, 'verified', "
                    "'repository-validator', '{\"scope\":\"selected\"}')"
                ),
                {
                    "source_id": ids["source_id"],
                    "file_node_id": ids["file_node_id"],
                    "hash_id": ids["hash_id"],
                },
            )
            connection.execute(
                text(
                    "UPDATE analysis.evidence_item SET confidence = 0.8, confidence_tier = 'high', "
                    "is_authenticated = true, authentication_method = 'hash_chain_of_custody', "
                    "safe_for_legal_use = true WHERE id = :item_id"
                ),
                {"item_id": first.item.id},
            )
            assert connection.execute(
                text("SELECT EXISTS (SELECT 1 FROM analysis.vw_court_export WHERE id = :item_id)"),
                {"item_id": first.item.id},
            ).scalar_one()
            readiness_by_zone = []
            for timezone_name in ("UTC", "America/New_York"):
                connection.execute(text(f"SET LOCAL TIME ZONE '{timezone_name}'"))
                readiness_by_zone.append(repository.get_court_readiness(matter.id, first.item.id))
            assert all(result.readiness_passed for result in readiness_by_zone)
            assert all(result.gates.custody.event_chain_valid for result in readiness_by_zone)
            assert all(result.gates.custody.verified_event_present for result in readiness_by_zone)
            assert all(result.gates.court_export.view_member for result in readiness_by_zone)
            history = repository.list_evidence_reviews(matter.id, first.item.id)
            assert history.total == 1
            assert history.data[0].decision_id == reviewed.decision_id
            assert history.data[0].rationale.startswith("Scratch reviewer")
            audit_count = connection.execute(
                text(
                    "SELECT count(*) FROM ops.audit_ledger "
                    "WHERE (object_schema = 'analysis.evidence_item' AND object_ref = :item_id) "
                    "   OR (object_schema = 'analysis.review_decision' "
                    "       AND object_ref = :decision_id)"
                ),
                {
                    "item_id": str(first.item.id),
                    "decision_id": str(reviewed.decision_id),
                },
            ).scalar_one()
            assert audit_count == 2
        finally:
            repository._engine = previous_engine
            outer.rollback()

        after = connection.execute(text("SELECT to_regclass('analysis.matter'), to_regclass('ops.audit_ledger')")).one()
        assert after == before
    engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True, help="Explicit clean non-production PostgreSQL DSN")
    parser.add_argument("--target", required=True, choices=("development", "scratch", "staging"))
    args = parser.parse_args()
    run_repository_validation(dsn=args.dsn, target=args.target)
    print(f"PASS: real repository + audit validation ({args.target}); zero net write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
