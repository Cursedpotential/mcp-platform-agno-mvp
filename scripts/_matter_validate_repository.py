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
    digest = hashlib.sha256(marker.encode()).digest()

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
                        " (sha256, byte_size, source_type, acquisition_source, original_filename) "
                        " VALUES (:digest, 1, 'other', 'repository-validator', :marker) RETURNING id"
                        "), node AS ("
                        " INSERT INTO evidence.file_node (source_id, node_kind, sha256) "
                        " SELECT id, 'message_unit', :digest FROM source RETURNING id, source_id"
                        "), hash AS ("
                        " INSERT INTO evidence.evidence_hash "
                        " (source_ref, digest, level, source_id, file_node_id, computed_by) "
                        " SELECT :marker, :digest, 'H1', node.source_id, node.id, 'repository-validator' "
                        " FROM node RETURNING id, source_id, file_node_id"
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
                        "record.provenance_id AS run_id, hash.source_id, hash.file_node_id "
                        "FROM record JOIN hash ON hash.id = record.artifact_id"
                    ),
                    {"digest": digest, "marker": marker, "content": "Exact repository validation sentence."},
                )
                .mappings()
                .one()
            )

            connection.execute(text("SET LOCAL statement_timeout = '10s'"))
            repository._engine = TransactionBoundEngine(connection)
            matter = repository.list_matters(limit=10, offset=0).data[0]
            detail = repository.get_matter(matter.id)
            court_case = next(item for item in detail.court_cases if item.is_primary)
            sha256 = digest.hex()
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
