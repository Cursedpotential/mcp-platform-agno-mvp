"""Static and optional rollback-safe behavior checks for migration 0048."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import sqlparse


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "0048_context_fingerprint_uiw_repair.sql"
SUPERSESSION = ROOT / "sql" / "0045_context_fingerprint_semantics.sql"
if not SUPERSESSION.exists():
    # 0045 was a 2026-08-29 merge-conflict casualty: only .broken-historical /
    # .incoming-conflict variants survived, quarantined out of the tree. Until
    # the conflict is resolved and a canonical 0045 restored, this module
    # cannot assert supersession semantics. Tracked in docs/pending-review.
    pytest.skip(
        "sql/0045_context_fingerprint_semantics.sql missing (unresolved "
        "2026-08-29 merge-conflict; variants quarantined)",
        allow_module_level=True,
    )
SQL = MIGRATION.read_text(encoding="utf-8")
SUPERSESSION_SQL = SUPERSESSION.read_text(encoding="utf-8")
NORMALIZED = " ".join(SQL.lower().split())


def test_0048_is_transactional_parseable_and_guarded() -> None:
    statements = [statement for statement in sqlparse.split(SQL) if statement.strip()]
    assert statements[0].strip().lower().endswith("begin;")
    assert statements[-1].strip().lower() == "commit;"
    assert "current_database() <> 'platform'" in NORMALIZED
    assert "to_regclass(v_relation) is null" in NORMALIZED
    assert "to_regprocedure(v_function) is null" in NORMALIZED
    assert "set local search_path = pg_catalog, context" in NORMALIZED
    assert NORMALIZED.count("set search_path = pg_catalog, context") >= 7
    for statement in statements:
        assert sqlparse.parse(statement), statement[:120]


def test_0048_repairs_real_0036_hash_tables() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    for relation in (
        "context.hash_batch",
        "context.hash_manifest",
        "context.hash_manifest_member",
        "context.hash_receipt",
        "context.reconciliation_receipt",
        "context.raw_generation",
    ):
        assert relation in sql


def test_0048_installs_context_fingerprint_vocabulary_and_canons() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    for value in (
        "context_source_fingerprint",
        "context_raw_record_fingerprint",
        "context_raw_generation_fingerprint",
        "context-source-fingerprint-v1",
        "context-rawrecord-fingerprint-v1",
        "context-rawspan-fingerprint-v1",
        "context-rawgen-fingerprint-chain-v1",
        "fingerprint_source_activity",
        "fingerprint_raw_records_activity",
        "fingerprint_raw_generation_activity",
        "context_raw_fingerprint_receipt_set",
    ):
        assert value in sql


def test_0048_replaces_trigger_functions_in_place() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    for function in (
        "guard_hash_batch_insert",
        "guard_hash_batch_member_insert",
        "assert_hash_manifest_complete",
        "guard_hash_manifest_member_insert",
        "guard_hash_receipt_insert",
        "seal_hash_manifest_from_receipt",
        "guard_raw_generation_transition",
    ):
        assert f"context.{function}" in sql


def test_0048_catalog_rewrite_refuses_unexpected_function_shape() -> None:
    """The only dynamic function rewrite must fail closed before EXECUTE."""
    assert "definition ~* 'SET[[:space:]]+search_path[[:space:]]*(=|TO)'" in SQL
    assert "regexp_count(definition, 'LANGUAGE[[:space:]]+plpgsql', 1, 'i') <> 1" in SQL
    search_path_guard = SQL.index(
        "migration 0048 refuses to rewrite context.guard_raw_generation_transition(): search_path is already configured"
    )
    language_guard = SQL.index(
        "migration 0048 refuses to rewrite context.guard_raw_generation_transition(): "
        "expected exactly one LANGUAGE plpgsql clause"
    )
    execute = SQL.index("EXECUTE definition;")
    assert search_path_guard < execute
    assert language_guard < execute


def test_0048_preserves_legacy_execution_identity_and_recomputes_bytes() -> None:
    assert "computed_by = case" not in NORMALIZED
    assert "new.computed_by not in ('fingerprint_source_activity', 'hash_source_activity')" in NORMALIZED
    assert "execution.activity_name = new.computed_by" in NORMALIZED
    assert "retained_bytes_recomputation" in NORMALIZED
    assert "independent_recomputation" not in NORMALIZED


def test_0048_preserves_applied_0045_and_append_only_guard() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "Migration 0045 is immutable" in sql
    assert "ALTER TABLE context.hash_receipt DISABLE TRIGGER" in sql
    assert "ALTER TABLE context.hash_receipt ENABLE TRIGGER" in sql


def test_0048_pg18_rollback_apply_when_service_is_available() -> None:
    """Apply the reachable 0045->0048 sequence inside one forced rollback."""
    service = os.getenv("PLATFORM_0048_TEST_SERVICE")
    if not service:
        pytest.skip("set PLATFORM_0048_TEST_SERVICE for rollback-only PostgreSQL 18 proof")
    psycopg = pytest.importorskip("psycopg")
    body = SQL.split("BEGIN;", 1)[1].rsplit("COMMIT;", 1)[0]
    supersession_body = SUPERSESSION_SQL.split("BEGIN;", 1)[1].rsplit("COMMIT;", 1)[0]
    connection = psycopg.connect(f"service={service}", autocommit=False)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            assert int(cursor.fetchone()[0]) >= 180000
            cursor.execute(supersession_body)
            cursor.execute(body)
            cursor.execute(
                """
                SELECT hash_kind, construction, computed_by
                FROM context.hash_receipt
                WHERE hash_kind LIKE 'context_%fingerprint'
                LIMIT 1
                """
            )
            cursor.execute(
                """
                SELECT proconfig
                FROM pg_proc
                WHERE oid = to_regprocedure('context.guard_hash_receipt_insert()')
                """
            )
            assert "search_path=pg_catalog, context" in (cursor.fetchone()[0] or [])
    finally:
        connection.rollback()
        connection.close()


def test_0048_pg18_refuses_preconfigured_function_when_service_is_available() -> None:
    """Prove the catalog rewrite aborts if another migration already pinned search_path."""
    service = os.getenv("PLATFORM_0048_TEST_SERVICE")
    if not service:
        pytest.skip("set PLATFORM_0048_TEST_SERVICE for rollback-only PostgreSQL 18 proof")
    psycopg = pytest.importorskip("psycopg")
    body = SQL.split("BEGIN;", 1)[1].rsplit("COMMIT;", 1)[0]
    supersession_body = SUPERSESSION_SQL.split("BEGIN;", 1)[1].rsplit("COMMIT;", 1)[0]
    connection = psycopg.connect(f"service={service}", autocommit=False)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            assert int(cursor.fetchone()[0]) >= 180000
            cursor.execute(supersession_body)
            cursor.execute(
                "ALTER FUNCTION context.guard_raw_generation_transition() SET search_path = pg_catalog, context"
            )
            with pytest.raises(
                psycopg.errors.RaiseException,
                match="search_path is already configured",
            ):
                cursor.execute(body)
    finally:
        connection.rollback()
        connection.close()
