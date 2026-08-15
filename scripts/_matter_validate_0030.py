"""Validate the held Matter/CourtCase foundation migration.

Static validation is the default and performs no database connection. An
optional rollback-only database validation is available for an explicitly
identified scratch, development, or staging database; production is rejected.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

import psycopg

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "sql" / "0030_matter_case_foundation.sql"
ALLOWED_DATABASE_TARGETS = frozenset({"scratch", "development", "staging"})


def strip_transaction_control(sql: str) -> str:
    """Remove only outer, line-leading transaction statements."""
    sql = re.sub(r"^\s*BEGIN\s*;\s*$", "", sql, flags=re.MULTILINE)
    return re.sub(r"^\s*COMMIT\s*;\s*$", "", sql, flags=re.MULTILINE)


def validate_static(sql: str | None = None) -> list[str]:
    """Return invariant failures without executing SQL."""
    text = MIGRATION.read_text(encoding="utf-8") if sql is None else sql
    normalized = re.sub(r"\s+", " ", text.lower())
    failures: list[str] = []

    required = {
        "held/unapplied banner": "held for owner" in normalized and "not applied" in normalized,
        "matter table": "create table analysis.matter (" in normalized,
        "court case table": "create table analysis.court_case (" in normalized,
        "partition bridge": "create table analysis.matter_knowledge_partition (" in normalized,
        "primary seed": "select 'primary', matter_id, id, 'migration-0030'" in normalized,
        "evidence matter column": "add column matter_id uuid" in normalized,
        "evidence court case column": "add column court_case_id uuid" in normalized,
        "promotion ledger": "create table analysis.knowledge_evidence_promotion (" in normalized,
        "request idempotency": "unique (matter_id, idempotency_key)" in normalized,
        "pointer idempotency": "unique (court_case_id, source_pointer_hash)" in normalized,
        "append-only trigger": "knowledge_evidence_promotion_append_only" in normalized
        and "working.forbid_mutation()" in normalized,
        "unsafe provenance guard": "knowledge_evidence_promotion_guard" in normalized
        and "promoted evidence must start unreviewed" in normalized
        and "record_row.case_id is distinct from new.partition_key" in normalized,
        "transaction wrapper": bool(re.search(r"^\s*begin\s*;", text, re.IGNORECASE | re.MULTILINE))
        and bool(re.search(r"^\s*commit\s*;", text, re.IGNORECASE | re.MULTILINE)),
    }
    failures.extend(label for label, passed in required.items() if not passed)

    destructive_legacy_patterns = (
        r"drop\s+column\s+case_id",
        r"alter\s+column\s+case_id\s+type",
        r"rename\s+column\s+case_id",
        r"update\s+analysis\.evidence_item\s+set\s+case_id",
    )
    for pattern in destructive_legacy_patterns:
        if re.search(pattern, normalized):
            failures.append(f"legacy case_id mutation: {pattern}")

    if "sql/bootstrap/schema_baseline.sql" in normalized:
        failures.append("baseline mutation reference")
    return failures


def validate_target(target: str) -> None:
    """Fail closed for production or an ambiguous database target."""
    if target not in ALLOWED_DATABASE_TARGETS:
        allowed = ", ".join(sorted(ALLOWED_DATABASE_TARGETS))
        raise ValueError(f"database target must be one of: {allowed}; production is forbidden")


def expect_database_error(
    cursor: psycopg.Cursor[Any],
    statement: str,
    parameters: tuple[object, ...],
    *,
    contains: str,
) -> None:
    """Assert one statement fails without poisoning the outer validation transaction."""
    cursor.execute("SAVEPOINT matter_expected_error")
    try:
        cursor.execute(statement, parameters)
    except psycopg.Error as exc:
        cursor.execute("ROLLBACK TO SAVEPOINT matter_expected_error")
        assert contains.lower() in str(exc).lower(), str(exc)
    else:
        cursor.execute("ROLLBACK TO SAVEPOINT matter_expected_error")
        raise AssertionError(f"database accepted an invalid operation: {contains}")
    finally:
        cursor.execute("RELEASE SAVEPOINT matter_expected_error")


def validate_promotion_contract(cursor: psycopg.Cursor[Any], marker: str) -> None:
    """Exercise custody-bound promotion, safety gates, dedupe, and immutability."""
    digest = hashlib.sha256(marker.encode()).digest()

    cursor.execute(
        "INSERT INTO evidence.source "
        "(sha256, byte_size, source_type, acquisition_source, original_filename) "
        "VALUES (%s, 1, 'other', 'matter-validator', %s) RETURNING id",
        (digest, marker),
    )
    source_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO evidence.file_node (source_id, node_kind, sha256) VALUES (%s, 'message_unit', %s) RETURNING id",
        (source_id, digest),
    )
    file_node_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO evidence.evidence_hash "
        "(source_ref, digest, level, source_id, file_node_id, computed_by) "
        "VALUES (%s, %s, 'H1', %s, %s, 'matter-validator') RETURNING id",
        (marker, digest, source_id, file_node_id),
    )
    evidence_hash_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO ops.processing_run (run_type, actor, status) "
        "VALUES ('ingestion', 'matter-validator', 'ok') RETURNING run_id"
    )
    source_run_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO working.normalized_record "
        "(artifact_id, record_type, source, content, provenance_id, case_id, domain) "
        "VALUES (%s, 'message', 'matter-validator', %s, %s, 'primary', 'evidence') "
        "RETURNING id",
        (evidence_hash_id, marker, source_run_id),
    )
    normalized_record_id = cursor.fetchone()[0]
    cursor.execute(
        "SELECT matter_id, default_court_case_id "
        "FROM analysis.matter_knowledge_partition WHERE partition_key = 'primary'"
    )
    matter_id, court_case_id = cursor.fetchone()
    cursor.execute(
        "INSERT INTO analysis.evidence_item "
        "(case_id, matter_id, court_case_id, source_id, file_node_id, "
        "normalized_record_id, evidence_hash_id, source_run_id, title, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'matter-validator') "
        "RETURNING id",
        (
            court_case_id,
            matter_id,
            court_case_id,
            source_id,
            file_node_id,
            normalized_record_id,
            evidence_hash_id,
            source_run_id,
            marker,
        ),
    )
    evidence_item_id = cursor.fetchone()[0]

    source_pointer = json.dumps(
        {
            "matter_id": str(matter_id),
            "court_case_id": str(court_case_id),
            "partition_key": "primary",
            "lane": "evidence",
            "normalized_record_id": str(normalized_record_id),
            "evidence_hash_id": str(evidence_hash_id),
            "source_id": str(source_id),
            "sha256": digest.hex(),
            "conversation_id": None,
            "quote": None,
            "retrieval_ref": marker,
        }
    )

    promotion_sql = (
        "INSERT INTO analysis.knowledge_evidence_promotion "
        "(idempotency_key, partition_key, matter_id, court_case_id, evidence_item_id, "
        "normalized_record_id, evidence_hash_id, source_id, file_node_id, source_run_id, "
        "knowledge_lane, retrieval_item_ref, source_pointer, source_pointer_hash, promoted_by) "
        "VALUES (%s, 'primary', %s, %s, %s, %s, %s, %s, %s, %s, 'evidence', %s, "
        "CAST(%s AS jsonb), analysis.knowledge_evidence_pointer_hash(CAST(%s AS jsonb)), "
        "'matter-validator') "
        "RETURNING id"
    )
    promotion_parameters = (
        marker,
        matter_id,
        court_case_id,
        evidence_item_id,
        normalized_record_id,
        evidence_hash_id,
        source_id,
        file_node_id,
        source_run_id,
        marker,
        source_pointer,
        source_pointer,
    )
    cursor.execute(promotion_sql, promotion_parameters)
    promotion_id = cursor.fetchone()[0]
    cursor.execute(
        "SELECT item.review_status::text, item.hitl_required, item.safe_for_legal_use, "
        "item.is_authenticated, promotion.normalized_record_id = item.normalized_record_id "
        "FROM analysis.knowledge_evidence_promotion promotion "
        "JOIN analysis.evidence_item item ON item.id = promotion.evidence_item_id "
        "WHERE promotion.id = %s",
        (promotion_id,),
    )
    assert cursor.fetchone() == ("unreviewed", True, False, False, True)

    expect_database_error(
        cursor,
        promotion_sql.replace("'evidence', %s", "'legal', %s"),
        promotion_parameters,
        contains="only the evidence Knowledge lane may be promoted",
    )

    mismatched_pointer = json.dumps({**json.loads(source_pointer), "matter_id": str(uuid.uuid4())})
    mismatched_parameters = (*promotion_parameters[:-2], mismatched_pointer, promotion_parameters[-1])
    expect_database_error(
        cursor,
        promotion_sql,
        mismatched_parameters,
        contains="source pointer hash does not match canonical source pointer",
    )

    expect_database_error(
        cursor,
        promotion_sql,
        promotion_parameters,
        contains="knowledge_evidence_promotion_request_key",
    )

    cursor.execute(
        "INSERT INTO analysis.evidence_item "
        "(case_id, matter_id, court_case_id, source_id, file_node_id, "
        "normalized_record_id, evidence_hash_id, source_run_id, title, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, "
        "'pointer dedupe probe', 'matter-validator') RETURNING id",
        (
            court_case_id,
            matter_id,
            court_case_id,
            source_id,
            file_node_id,
            normalized_record_id,
            evidence_hash_id,
            source_run_id,
        ),
    )
    pointer_probe_item_id = cursor.fetchone()[0]
    pointer_probe_parameters = list(promotion_parameters)
    pointer_probe_parameters[0] = f"pointer-probe:{marker}"
    pointer_probe_parameters[3] = pointer_probe_item_id
    expect_database_error(
        cursor,
        promotion_sql,
        tuple(pointer_probe_parameters),
        contains="knowledge_evidence_promotion_pointer_key",
    )
    expect_database_error(
        cursor,
        "UPDATE analysis.knowledge_evidence_promotion SET content_ref = 'changed' WHERE id = %s",
        (promotion_id,),
        contains="append-only",
    )

    cursor.execute(
        "INSERT INTO analysis.evidence_item "
        "(case_id, matter_id, court_case_id, file_node_id, normalized_record_id, "
        "evidence_hash_id, source_run_id, title, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'mismatched provenance', 'matter-validator') "
        "RETURNING id",
        (
            court_case_id,
            matter_id,
            court_case_id,
            file_node_id,
            normalized_record_id,
            evidence_hash_id,
            source_run_id,
        ),
    )
    mismatched_item_id = cursor.fetchone()[0]
    mismatch_parameters = list(promotion_parameters)
    mismatch_parameters[0] = f"mismatch:{marker}"
    mismatch_parameters[3] = mismatched_item_id
    mismatch_parameters[6] = None
    mismatch_parameters[9] = f"mismatch:{marker}"
    mismatch_parameters[10] = f"mismatch:{marker}"
    mismatch_parameters[11] = hashlib.sha256(f"mismatch:{marker}".encode()).digest()
    expect_database_error(
        cursor,
        promotion_sql,
        tuple(mismatch_parameters),
        contains="custody hash source/file provenance does not match promotion",
    )

    cursor.execute(
        "INSERT INTO analysis.matter (title, created_by) VALUES ('Isolation probe', 'matter-validator') RETURNING id"
    )
    foreign_matter_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO analysis.court_case "
        "(matter_id, caption, is_primary, created_by) "
        "VALUES (%s, 'Isolation proceeding', true, 'matter-validator') RETURNING id",
        (foreign_matter_id,),
    )
    foreign_case_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO analysis.evidence_item "
        "(case_id, matter_id, court_case_id, source_id, file_node_id, "
        "normalized_record_id, evidence_hash_id, source_run_id, title, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, "
        "'cross-matter probe', 'matter-validator') RETURNING id",
        (
            foreign_case_id,
            foreign_matter_id,
            foreign_case_id,
            source_id,
            file_node_id,
            normalized_record_id,
            evidence_hash_id,
            source_run_id,
        ),
    )
    foreign_item_id = cursor.fetchone()[0]
    foreign_parameters = list(promotion_parameters)
    foreign_parameters[0] = f"foreign:{marker}"
    foreign_parameters[1] = foreign_matter_id
    foreign_parameters[2] = foreign_case_id
    foreign_parameters[3] = foreign_item_id
    foreign_parameters[9] = f"foreign:{marker}"
    foreign_parameters[10] = f"foreign:{marker}"
    foreign_parameters[11] = hashlib.sha256(f"foreign:{marker}".encode()).digest()
    expect_database_error(
        cursor,
        promotion_sql,
        tuple(foreign_parameters),
        contains="knowledge_evidence_promotion_partition_fkey",
    )


def validate_database(*, dsn: str, target: str) -> None:
    """Apply inside one transaction, assert the contract, and always roll back."""
    validate_target(target)
    sql = strip_transaction_control(MIGRATION.read_text(encoding="utf-8"))
    marker = f"matter-validator-{uuid.uuid4()}"
    with psycopg.connect(dsn, autocommit=False) as connection:
        assert connection.autocommit is False
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass('analysis.matter'), "
                "to_regclass('analysis.court_case'), "
                "to_regclass('analysis.matter_knowledge_partition'), "
                "to_regclass('analysis.knowledge_evidence_promotion')"
            )
            before_relations = cursor.fetchone()
            assert before_relations == (None, None, None, None), (
                "scratch target already contains migration 0030 objects; use a clean disposable database"
            )
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                cursor.execute(
                    "SELECT to_regclass('analysis.matter'), "
                    "to_regclass('analysis.court_case'), "
                    "to_regclass('analysis.matter_knowledge_partition'), "
                    "to_regclass('analysis.knowledge_evidence_promotion')"
                )
                assert cursor.fetchone() == (
                    "analysis.matter",
                    "analysis.court_case",
                    "analysis.matter_knowledge_partition",
                    "analysis.knowledge_evidence_promotion",
                )
                cursor.execute(
                    "SELECT count(*) FROM analysis.matter_knowledge_partition WHERE partition_key = 'primary'"
                )
                assert cursor.fetchone() == (1,)
                cursor.execute(
                    "SELECT column_name, is_nullable FROM information_schema.columns "
                    "WHERE table_schema='analysis' AND table_name='evidence_item' "
                    "AND column_name IN ('case_id','matter_id','court_case_id') "
                    "ORDER BY column_name"
                )
                assert cursor.fetchall() == [
                    ("case_id", "NO"),
                    ("court_case_id", "YES"),
                    ("matter_id", "YES"),
                ]
                validate_promotion_contract(cursor, marker)
        finally:
            connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass('analysis.matter'), "
                "to_regclass('analysis.court_case'), "
                "to_regclass('analysis.matter_knowledge_partition'), "
                "to_regclass('analysis.knowledge_evidence_promotion')"
            )
            assert cursor.fetchone() == before_relations
            cursor.execute("SELECT count(*) FROM evidence.source WHERE original_filename = %s", (marker,))
            assert cursor.fetchone() == (0,)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="Explicit non-production PostgreSQL DSN")
    parser.add_argument("--target", choices=sorted(ALLOWED_DATABASE_TARGETS))
    args = parser.parse_args()

    failures = validate_static()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: static migration contract")

    if args.dsn or args.target:
        if not (args.dsn and args.target):
            parser.error("--dsn and --target must be supplied together")
        validate_database(dsn=args.dsn, target=args.target)
        print(f"PASS: rollback-only database validation ({args.target}); zero net write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
