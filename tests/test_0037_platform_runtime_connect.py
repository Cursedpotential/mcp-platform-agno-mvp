"""Offline invariants for the forward-only platform runtime CONNECT correction."""

from __future__ import annotations

import re
from pathlib import Path

import sqlparse


ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "sql" / "0037_platform_runtime_connect.sql"
APPLY_SCRIPT = ROOT / "scripts" / "apply_0037_live.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate_0037_live.py"


def _normalized(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").lower())


def test_migration_is_transactional_platform_only_and_forward_safe() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    statements = [statement for statement in sqlparse.split(sql) if statement.strip()]
    assert statements[0].strip().lower().endswith("begin;")
    assert statements[-1].strip().lower() == "commit;"
    normalized = _normalized(MIGRATION)
    assert "current_database() <> 'platform'" in normalized
    assert "set local role platform_admin" in normalized
    assert "grant connect on database platform to platform_runtime" in normalized
    assert "revoke temporary, create on database platform from platform_runtime" in normalized
    for forbidden in ("drop ", "delete ", "truncate ", "alter role ", "create role "):
        assert forbidden not in normalized


def test_migration_never_grants_temp_or_create_to_runtime() -> None:
    executable = sqlparse.format(MIGRATION.read_text(encoding="utf-8"), strip_comments=True).lower()
    runtime_grants = [line for line in executable.splitlines() if "grant" in line and "platform_runtime" in line]
    assert runtime_grants == ["grant connect on database platform to platform_runtime;"]
    assert "grant temporary" not in executable
    assert "grant create on database platform to platform_runtime" not in executable


def test_apply_and_validator_lock_target_platform_and_use_the_rich_ledger() -> None:
    required_ledger_columns = (
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
    )
    validator_source = VALIDATE_SCRIPT.read_text(encoding="utf-8")
    assert 'TARGET_DATABASE: Final = "platform"' in validator_source
    assert "dbname={TARGET_DATABASE}" in validator_source
    assert "current_database()" in validator_source
    assert "platform_runtime" in validator_source
    assert "TEMPORARY" in validator_source and "CREATE" in validator_source
    for column in required_ledger_columns:
        assert f'"{column}"' in validator_source
    apply_source = APPLY_SCRIPT.read_text(encoding="utf-8")
    assert "--apply" in apply_source
    assert "TARGET_DATABASE," in apply_source
    assert "assert_platform_bootstrap" in apply_source
    assert "assert_runtime_connect_only" in apply_source
    assert "pg_advisory_xact_lock(hashtext(" in apply_source
    assert "SET LOCAL ROLE platform_admin" in apply_source
    assert "current_user" in apply_source
    assert "sha256" in apply_source


def test_apply_ledger_entry_is_versioned_hashed_and_authored_by_platform_admin() -> None:
    source = APPLY_SCRIPT.read_text(encoding="utf-8")
    assert "MIGRATION_ID" in source and "MIGRATION_LABEL" in source
    assert "ddl_hash" in source
    assert "assert_ledger_entry(cursor, migration_hash)" in source
    assert "SET LOCAL ROLE platform_admin" in source
    insert_match = re.search(r"INSERT INTO public\.schema_version\s*\(([^)]+)\)", source, re.IGNORECASE)
    assert insert_match is not None
    columns = [column.strip() for column in insert_match.group(1).split(",")]
    assert columns == [
        "version_label",
        "applies_to",
        "ddl_uri",
        "ddl_hash",
        "migration_id",
        "status",
        "notes",
        "created_by",
    ]


def test_validator_is_rollback_only_and_both_helpers_avoid_secret_output() -> None:
    validator = VALIDATE_SCRIPT.read_text(encoding="utf-8")
    assert 're.search(r"conn\\.commit\\s*\\(", source)' in validator
    assert "conn.rollback()" in validator
    assert "conn.commit(" not in validator
    for path in (APPLY_SCRIPT, VALIDATE_SCRIPT):
        source = path.read_text(encoding="utf-8").lower()
        assert "print(password" not in source
        assert "print(dsn" not in source
        assert "print(user" not in source
