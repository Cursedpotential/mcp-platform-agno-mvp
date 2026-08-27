"""Offline invariants for the platform runtime's narrow ledger-probe grant."""

from __future__ import annotations

import re
from pathlib import Path

import sqlparse


ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "sql" / "0038_platform_runtime_schema_version_probe.sql"
APPLY_SCRIPT = ROOT / "scripts" / "apply_0038_live.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate_0038_live.py"


def test_migration_is_platform_only_transactional_and_column_level() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    statements = [statement for statement in sqlparse.split(sql) if statement.strip()]
    assert statements[0].strip().lower().endswith("begin;")
    assert statements[-1].strip().lower() == "commit;"
    normalized = re.sub(r"\s+", " ", sql.lower())
    assert "current_database() <> 'platform'" in normalized
    assert "set local role platform_admin" in normalized
    assert "grant select (migration_id, status) on table public.schema_version to platform_runtime" in normalized
    assert "grant select on table public.schema_version" not in normalized
    for forbidden in ("drop ", "delete ", "truncate ", "alter role ", "create role "):
        assert forbidden not in normalized


def test_apply_and_validator_use_platform_lock_rich_ledger_and_runtime_probe() -> None:
    validator = VALIDATE_SCRIPT.read_text(encoding="utf-8")
    apply = APPLY_SCRIPT.read_text(encoding="utf-8")
    assert "TARGET_DATABASE," in apply
    assert "TARGET_DATABASE," in validator
    for source in (apply, validator):
        assert "dbname={TARGET_DATABASE}" in source
        assert "pg_advisory_xact_lock(hashtext(" in source
        assert "assert_runtime_connect_only" in source
    assert "platform_runtime" in validator
    assert "assert_schema_version_probe_only" in apply
    assert "run_probe_as_runtime" in apply
    for column in (
        "id",
        "version_label",
        "applies_to",
        "ddl_uri",
        "ddl_hash",
        "migration_id",
        "status",
        "notes",
        "created_by",
        "created_at",
    ):
        assert f'"{column}"' in validator
    assert "SET LOCAL ROLE platform_admin" in apply
    assert "current_user" in apply
    assert "sha256" in apply


def test_validator_uses_exact_runtime_role_predicate_and_rejects_broader_select() -> None:
    source = VALIDATE_SCRIPT.read_text(encoding="utf-8")
    assert "SET LOCAL ROLE platform_runtime" in source
    assert "SELECT count(*) FROM public.schema_version" in source
    assert "WHERE migration_id = %s AND status = %s" in source
    assert "has_table_privilege" in source
    assert "has_column_privilege" in source
    assert "must not have table-wide SELECT" in source
    assert "must have SELECT only on schema_version migration_id,status" in source


def test_apply_records_one_hashed_platform_admin_receipt() -> None:
    source = APPLY_SCRIPT.read_text(encoding="utf-8")
    insert_match = re.search(r"INSERT INTO public\.schema_version\s*\(([^)]+)\)", source, re.IGNORECASE)
    assert insert_match is not None
    assert [column.strip() for column in insert_match.group(1).split(",")] == [
        "version_label",
        "applies_to",
        "ddl_uri",
        "ddl_hash",
        "migration_id",
        "status",
        "notes",
        "created_by",
    ]
    assert "assert_ledger_entry(cursor, migration_hash)" in source
    assert "--apply" in source


def test_validator_is_rollback_only_and_no_helper_prints_credentials() -> None:
    validator = VALIDATE_SCRIPT.read_text(encoding="utf-8")
    assert 're.search(r"conn\\.commit\\s*\\(", source)' in validator
    assert "conn.rollback()" in validator
    assert "conn.commit(" not in validator
    for path in (APPLY_SCRIPT, VALIDATE_SCRIPT):
        source = path.read_text(encoding="utf-8").lower()
        assert "print(password" not in source
        assert "print(dsn" not in source
        assert "print(user" not in source
