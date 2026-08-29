"""Static and optional rollback-only PostgreSQL 18 checks for migration 0051."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import sqlparse

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "0051_uiw_repair_activity_store.sql"
SQL = MIGRATION.read_text(encoding="utf-8")
NORMALIZED = " ".join(SQL.lower().split())


def test_0051_is_forward_only_transactional_and_platform_guarded() -> None:
    statements = [statement for statement in sqlparse.split(SQL) if statement.strip()]
    assert statements[0].strip().lower().endswith("begin;")
    assert statements[-1].strip().lower() == "commit;"
    assert "current_database() <> 'platform'" in NORMALIZED
    assert "context.repair_assessment" in NORMALIZED
    assert "context.repair_decision" in NORMALIZED
    assert "context.repair_resolution" in NORMALIZED
    assert "repair.write-derived" in NORMALIZED
    assert "repair.pdf-derived" in NORMALIZED
    assert "before update or delete" in NORMALIZED
    assert "before truncate" in NORMALIZED
    assert "grant select, insert" in NORMALIZED
    assert "grant update" not in NORMALIZED
    assert "grant delete" not in NORMALIZED
    for statement in statements:
        assert sqlparse.parse(statement), statement[:120]


def test_0051_actor_approval_and_reference_only_constraints_are_explicit() -> None:
    for required in (
        "actor_ref text not null",
        "approved boolean not null",
        "activity_receipt_id uuid not null unique",
        "active_object_id uuid not null references context.retained_object",
        "octet_length(tool_payload::text) <= 65536",
        "octet_length(tool_result::text) <= 2097152",
    ):
        assert required in NORMALIZED
    assert "bytea" not in NORMALIZED.split("create table context.repair_assessment", 1)[1].split(")", 1)[0]


def test_0051_pg18_apply_and_append_only_rollback_when_service_is_available() -> None:
    service = os.getenv("PLATFORM_0051_TEST_SERVICE")
    if not service:
        pytest.skip("set PLATFORM_0051_TEST_SERVICE for rollback-only PostgreSQL 18 proof")
    psycopg = pytest.importorskip("psycopg")
    body = SQL.split("BEGIN;", 1)[1].rsplit("COMMIT;", 1)[0]
    connection = psycopg.connect(f"service={service}", autocommit=False)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            assert int(cursor.fetchone()[0]) >= 180000
            cursor.execute(body)
            cursor.execute(
                "SELECT to_regclass('context.repair_assessment'), "
                "to_regclass('context.repair_decision'), to_regclass('context.repair_resolution')"
            )
            assert all(cursor.fetchone())
            cursor.execute(
                "SELECT has_table_privilege('platform_runtime','context.repair_decision','INSERT'), "
                "has_table_privilege('platform_runtime','context.repair_decision','UPDATE')"
            )
            assert cursor.fetchone() == (True, False)
    finally:
        connection.rollback()
        connection.close()
