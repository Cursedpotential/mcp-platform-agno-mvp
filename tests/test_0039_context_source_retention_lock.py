"""Offline invariants for migration 0039's narrow retain-original lock grant.

Byline: Codex · GPT-5 · 2026-08-27
"""

from __future__ import annotations

import re
from pathlib import Path

import sqlparse


ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "sql" / "0039_context_source_retention_lock.sql"
APPLY_SCRIPT = ROOT / "scripts" / "apply_0039_live.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate_0039_live.py"


def test_migration_is_platform_only_transactional_and_column_level() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    statements = [statement for statement in sqlparse.split(sql) if statement.strip()]
    assert statements[0].strip().lower().endswith("begin;")
    assert statements[-1].strip().lower() == "commit;"
    normalized = re.sub(r"\s+", " ", sql.lower())
    assert "current_database() <> 'platform'" in normalized
    assert "set local role context_owner" in normalized
    assert "grant update (id) on table context.source to context_import_writer" in normalized
    assert "grant update on table context.source" not in normalized
    assert "platform_runtime membership in context_import_writer" in normalized
    assert "source_append_only" in normalized
    for forbidden in ("drop ", "delete ", "truncate ", "alter role ", "create role "):
        assert forbidden not in normalized


def test_validator_checks_only_id_update_and_exact_production_locking_join() -> None:
    source = VALIDATE_SCRIPT.read_text(encoding="utf-8")
    assert 'granted != {"id"}' in source
    assert "must not have table-wide UPDATE on context.source" in source
    assert "SET LOCAL ROLE platform_runtime" in source
    assert "SELECT version.workflow_id, source.source_key, version.status, version.original_object_id" in source
    assert "JOIN context.source source ON source.id = version.source_id" in source
    assert "FOR UPDATE" in source
    assert "source_append_only" in source
    assert "psycopg.errors.RaiseException" in source


def test_apply_uses_lock_hash_ledger_and_explicit_gate() -> None:
    source = APPLY_SCRIPT.read_text(encoding="utf-8")
    assert "--apply" in source
    assert "pg_advisory_xact_lock(hashtext('apply-0039-source-retention-lock'))" in source
    assert "assert_source_lock_grant_only(cursor)" in source
    assert "run_retain_lock_probe_as_runtime(cursor)" in source
    assert "assert_actual_source_update_is_blocked(cursor)" in source
    assert "SET LOCAL ROLE platform_admin" in source
    assert "INSERT INTO public.schema_version" in source
    assert "assert_ledger_entry(cursor, migration_hash)" in source
    assert "sha256" in source


def test_validator_is_rollback_only_and_helpers_do_not_print_credentials() -> None:
    validator = VALIDATE_SCRIPT.read_text(encoding="utf-8")
    assert 're.search(r"conn\\.commit\\s*\\(", source)' in validator
    assert "conn.rollback()" in validator
    assert "conn.commit(" not in validator
    assert "acl_snapshot" in validator
    assert "after != before" in validator
    for path in (APPLY_SCRIPT, VALIDATE_SCRIPT):
        source = path.read_text(encoding="utf-8").lower()
        assert "print(password" not in source
        assert "print(dsn" not in source
        assert "print(user" not in source
