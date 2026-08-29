"""Rollback-only validation for the 0039 retain-original source lock grant.

The validator executes the migration under a transaction, runs the production
locking SELECT as ``platform_runtime``, proves that the immutable source trigger
still rejects a real UPDATE, and always rolls the transaction back.

Byline: Codex · GPT-5 · 2026-08-27
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Final, cast

import psycopg

from validate_0037_live import (  # type: ignore[import-not-found]  # direct script execution import
    PLATFORM_RUNTIME_ROLE,
    TARGET_DATABASE,
    TAILNET_HOST,
    assert_platform_bootstrap,
    assert_public_is_denied,
    assert_runtime_connect_only,
    connection_parameters,
    strip_transaction_control,
)


ROOT: Final = Path(__file__).resolve().parent.parent
MIGRATION: Final = ROOT / "sql" / "0039_context_source_retention_lock.sql"
MIGRATION_ID: Final = "0039"
MIGRATION_LABEL: Final = "0039_context_source_retention_lock"
APPLIES_TO: Final = "context.source(id)"
DDL_URI: Final = "sql/0039_context_source_retention_lock.sql"
PLATFORM_ADMIN_ROLE: Final = "platform_admin"
WRITER_ROLE: Final = "context_import_writer"
SOURCE_COLUMNS: Final = frozenset({"id", "source_key", "provenance_class", "created_at"})


def _rows(cursor: psycopg.Cursor[object]) -> list[tuple[object, ...]]:
    return cast(list[tuple[object, ...]], cursor.fetchall())


def _single_value(cursor: psycopg.Cursor[object]) -> object:
    row = cast(tuple[object, ...] | None, cursor.fetchone())
    if row is None:
        raise RuntimeError("database verification query unexpectedly returned no row")
    return row[0]


def assert_source_lock_prerequisites(cursor: psycopg.Cursor[object]) -> None:
    """Require the capability role, ownership, membership, and append-only trigger."""
    cursor.execute(
        """SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
           FROM pg_roles WHERE rolname = %s""",
        (WRITER_ROLE,),
    )
    writer = cast(tuple[object, ...] | None, cursor.fetchone())
    if writer is None or bool(writer[0]) or any(bool(value) for value in writer[1:]):
        raise RuntimeError("context_import_writer must be a safe NOLOGIN capability role")
    cursor.execute("SELECT pg_has_role(%s, %s, 'MEMBER')", (PLATFORM_RUNTIME_ROLE, WRITER_ROLE))
    if not bool(_single_value(cursor)):
        raise RuntimeError("platform_runtime is not a member of context_import_writer")
    cursor.execute(
        """SELECT pg_get_userbyid(class.relowner)
           FROM pg_class class JOIN pg_namespace namespace ON namespace.oid = class.relnamespace
           WHERE namespace.nspname = 'context' AND class.relname = 'source'"""
    )
    if _single_value(cursor) != "context_owner":
        raise RuntimeError("context.source must be owned by context_owner")
    cursor.execute(
        """SELECT count(*)
           FROM pg_trigger
           WHERE tgrelid = 'context.source'::regclass
             AND tgname = 'source_append_only'
             AND NOT tgisinternal AND tgenabled <> 'D'"""
    )
    if int(cast(int, _single_value(cursor))) != 1:
        raise RuntimeError("context.source requires one enabled source_append_only trigger")


def update_columns(cursor: psycopg.Cursor[object], role: str) -> set[str]:
    cursor.execute(
        """SELECT column_name,
                  has_column_privilege(%s, 'context.source', column_name, 'UPDATE')
           FROM information_schema.columns
           WHERE table_schema = 'context' AND table_name = 'source'
           ORDER BY ordinal_position""",
        (role,),
    )
    access = {str(row[0]): bool(row[1]) for row in _rows(cursor)}
    if set(access) != set(SOURCE_COLUMNS):
        raise RuntimeError("context.source no longer has the expected columns")
    return {column for column, granted in access.items() if granted}


def assert_source_lock_grant_only(cursor: psycopg.Cursor[object]) -> None:
    """Require only source.id UPDATE, inherited by runtime, with no table-wide grant."""
    for role in (WRITER_ROLE, PLATFORM_RUNTIME_ROLE):
        cursor.execute("SELECT has_table_privilege(%s, 'context.source', 'UPDATE')", (role,))
        if bool(_single_value(cursor)):
            raise RuntimeError(f"{role} must not have table-wide UPDATE on context.source")
        granted = update_columns(cursor, role)
        if granted != {"id"}:
            raise RuntimeError(f"{role} must have UPDATE only on context.source.id; found {sorted(granted)}")

    cursor.execute("SELECT has_table_privilege('context_reader', 'context.source', 'UPDATE')")
    if bool(_single_value(cursor)) or update_columns(cursor, "context_reader"):
        raise RuntimeError("context_reader must not receive UPDATE on context.source")


def run_retain_lock_probe_as_runtime(cursor: psycopg.Cursor[object]) -> None:
    """Execute the exact retain-original locking join under the runtime role."""
    cursor.execute("RESET ROLE")
    cursor.execute("SET LOCAL ROLE platform_runtime")
    cursor.execute(
        """SELECT version.workflow_id, source.source_key, version.status, version.original_object_id
           FROM context.source_version version
           JOIN context.source source ON source.id = version.source_id
           WHERE version.id = %s::uuid
           FOR UPDATE""",
        ("00000000-0000-0000-0000-000000000000",),
    )
    cursor.fetchall()
    cursor.execute("RESET ROLE")


def assert_actual_source_update_is_blocked(cursor: psycopg.Cursor[object]) -> None:
    """Prove the narrow lock privilege cannot mutate the immutable source row."""
    marker = "rollback-validator-0039-source-lock"
    cursor.execute("RESET ROLE")
    cursor.execute("SAVEPOINT source_mutation_probe")
    cursor.execute("SET LOCAL ROLE context_owner")
    cursor.execute(
        """INSERT INTO context.source (source_key, provenance_class)
           VALUES (%s, 'unknown') RETURNING id""",
        (marker,),
    )
    source_id = _single_value(cursor)
    cursor.execute("RESET ROLE")
    cursor.execute("SET LOCAL ROLE platform_runtime")
    try:
        cursor.execute("UPDATE context.source SET id = id WHERE id = %s::uuid", (source_id,))
    except psycopg.errors.RaiseException:
        cursor.execute("ROLLBACK TO SAVEPOINT source_mutation_probe")
        cursor.execute("RELEASE SAVEPOINT source_mutation_probe")
    else:
        raise RuntimeError("context.source mutation unexpectedly bypassed source_append_only")
    finally:
        cursor.execute("RESET ROLE")


def recorded_hashes(cursor: psycopg.Cursor[object]) -> list[bytes]:
    cursor.execute(
        """SELECT ddl_hash FROM public.schema_version
           WHERE migration_id = %s AND status = 'active' ORDER BY created_at""",
        (MIGRATION_ID,),
    )
    return [bytes(cast(bytes | bytearray | memoryview, row[0])) for row in _rows(cursor)]


def assert_ledger_entry(cursor: psycopg.Cursor[object], migration_hash: bytes) -> None:
    cursor.execute(
        """SELECT version_label, applies_to, ddl_uri, ddl_hash, created_by
           FROM public.schema_version
           WHERE migration_id = %s AND status = 'active' ORDER BY created_at""",
        (MIGRATION_ID,),
    )
    rows = _rows(cursor)
    expected = (MIGRATION_LABEL, APPLIES_TO, DDL_URI, migration_hash, PLATFORM_ADMIN_ROLE)
    if len(rows) != 1 or tuple(rows[0]) != expected:
        raise RuntimeError("migration 0039 requires one matching active rich-ledger entry by platform_admin")


def acl_snapshot(cursor: psycopg.Cursor[object]) -> tuple[str | None, tuple[tuple[str, str | None], ...]]:
    cursor.execute("SELECT array_to_string(relacl, E'\\n') FROM pg_class WHERE oid = 'context.source'::regclass")
    table_acl = _single_value(cursor)
    cursor.execute(
        """SELECT attname, array_to_string(attacl, E'\\n')
           FROM pg_attribute
           WHERE attrelid = 'context.source'::regclass
             AND attnum > 0 AND NOT attisdropped
           ORDER BY attnum"""
    )
    return None if table_acl is None else str(table_acl), tuple(
        (str(row[0]), None if row[1] is None else str(row[1])) for row in _rows(cursor)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=TARGET_DATABASE, help="only 'platform' is accepted")
    args = parser.parse_args()
    if args.database.strip() != TARGET_DATABASE:
        parser.error("migration 0039 may be validated only against database 'platform'")

    source = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"conn\.commit\s*\(", source):
        print("ERROR: rollback validator contains a connection commit call; refusing to run")
        return 2
    try:
        user, password, port = connection_parameters()
        migration_bytes = MIGRATION.read_bytes()
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: migration 0039 rollback validation preflight: {type(exc).__name__}: {exc}")
        return 2

    migration_hash = hashlib.sha256(migration_bytes).digest()
    dsn = f"host={TAILNET_HOST} port={port} dbname={TARGET_DATABASE} user={user}"
    before: tuple[str | None, tuple[tuple[str, str | None], ...]] | None = None
    failure: Exception | None = None
    conn: psycopg.Connection[object] | None = None
    try:
        conn = psycopg.connect(dsn, password=password, connect_timeout=10)
        conn.autocommit = False
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext('validate-0039-source-retention-lock'))")
            assert_platform_bootstrap(cursor)
            assert_public_is_denied(cursor)
            assert_runtime_connect_only(cursor)
            assert_source_lock_prerequisites(cursor)
            before = acl_snapshot(cursor)
            cursor.execute(strip_transaction_control(migration_bytes.decode("utf-8")))
            assert_source_lock_grant_only(cursor)
            run_retain_lock_probe_as_runtime(cursor)
            assert_actual_source_update_is_blocked(cursor)
            if hashlib.sha256(MIGRATION.read_bytes()).digest() != migration_hash:
                raise RuntimeError("migration changed during validation; results are discarded")
    except Exception as exc:  # noqa: BLE001 - report exact live validation failure without credentials
        failure = exc
    finally:
        if conn is not None:
            try:
                conn.rollback()
            finally:
                conn.close()

    if failure is not None or before is None:
        detail = "preflight did not capture source ACL state" if failure is None else str(failure)
        error_type = "RuntimeError" if failure is None else type(failure).__name__
        print(f"FAIL: migration 0039 rollback validation: {error_type}: {detail}")
        return 1

    try:
        with psycopg.connect(dsn, password=password, connect_timeout=10, autocommit=True) as post_conn:
            with post_conn.cursor() as cursor:
                assert_platform_bootstrap(cursor)
                assert_public_is_denied(cursor)
                assert_runtime_connect_only(cursor)
                assert_source_lock_prerequisites(cursor)
                after = acl_snapshot(cursor)
    except Exception as exc:  # noqa: BLE001 - postflight reports type and message only
        print(f"FAIL: migration 0039 rollback postflight: {type(exc).__name__}: {exc}")
        return 1
    if after != before:
        print("FAIL: context.source ACL changed after rollback")
        return 1
    print("PASS: migration 0039 rolled back; retain-original locking join succeeded and source stayed immutable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
