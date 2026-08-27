"""Rollback-only validation for 0038's column-level worker schema probe grant."""

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
MIGRATION: Final = ROOT / "sql" / "0038_platform_runtime_schema_version_probe.sql"
MIGRATION_ID: Final = "0038"
MIGRATION_LABEL: Final = "0038_platform_runtime_schema_version_probe"
APPLIES_TO: Final = "public.schema_version"
DDL_URI: Final = "sql/0038_platform_runtime_schema_version_probe.sql"
PLATFORM_ADMIN_ROLE: Final = "platform_admin"
PROBE_MIGRATION_ID: Final = "0036"
PROBE_STATUS: Final = "active"
LEDGER_COLUMNS: Final = (
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
PROBE_COLUMNS: Final = frozenset({"migration_id", "status"})


def _rows(cursor: psycopg.Cursor[object]) -> list[tuple[object, ...]]:
    return cast(list[tuple[object, ...]], cursor.fetchall())


def _single_value(cursor: psycopg.Cursor[object]) -> object:
    row = cast(tuple[object, ...] | None, cursor.fetchone())
    if row is None:
        raise RuntimeError("database verification query unexpectedly returned no row")
    return row[0]


def assert_schema_version_probe_only(cursor: psycopg.Cursor[object]) -> None:
    """Require the two predicate columns, no table-wide or extra column SELECT."""
    cursor.execute("SELECT has_schema_privilege(%s, 'public', 'USAGE')", (PLATFORM_RUNTIME_ROLE,))
    if not bool(_single_value(cursor)):
        raise RuntimeError("platform_runtime lacks pre-existing USAGE on public schema")
    cursor.execute("SELECT has_table_privilege(%s, 'public.schema_version', 'SELECT')", (PLATFORM_RUNTIME_ROLE,))
    if bool(_single_value(cursor)):
        raise RuntimeError("platform_runtime must not have table-wide SELECT on public.schema_version")
    cursor.execute(
        """SELECT column_name,
                  has_column_privilege(%s, 'public.schema_version', column_name, 'SELECT')
           FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'schema_version'
           ORDER BY ordinal_position""",
        (PLATFORM_RUNTIME_ROLE,),
    )
    column_access = {str(row[0]): bool(row[1]) for row in _rows(cursor)}
    if set(column_access) != set(LEDGER_COLUMNS):
        raise RuntimeError("public.schema_version no longer has the expected rich-ledger columns")
    granted_columns = {column for column, granted in column_access.items() if granted}
    if granted_columns != PROBE_COLUMNS:
        raise RuntimeError(
            "platform_runtime must have SELECT only on schema_version migration_id,status; found "
            + ", ".join(sorted(granted_columns))
        )


def run_probe_as_runtime(cursor: psycopg.Cursor[object]) -> int:
    """Execute the worker's predicate under the actual runtime role identity."""
    cursor.execute("RESET ROLE")
    cursor.execute("SET LOCAL ROLE platform_runtime")
    cursor.execute(
        """SELECT count(*) FROM public.schema_version
           WHERE migration_id = %s AND status = %s""",
        (PROBE_MIGRATION_ID, PROBE_STATUS),
    )
    result = int(cast(int, _single_value(cursor)))
    cursor.execute("RESET ROLE")
    return result


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
        raise RuntimeError("migration 0038 requires one matching active rich-ledger entry by platform_admin")


def acl_snapshot(cursor: psycopg.Cursor[object]) -> tuple[str | None, tuple[tuple[str, str | None], ...]]:
    cursor.execute(
        """SELECT array_to_string(relacl, E'\\n')
           FROM pg_class WHERE oid = 'public.schema_version'::regclass"""
    )
    table_acl = _single_value(cursor)
    cursor.execute(
        """SELECT attname, array_to_string(attacl, E'\\n')
           FROM pg_attribute
           WHERE attrelid = 'public.schema_version'::regclass
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
        parser.error("migration 0038 may be validated only against database 'platform'")

    source = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"conn\.commit\s*\(", source):
        print("ERROR: rollback validator contains a connection commit call; refusing to run")
        return 2
    try:
        user, password, port = connection_parameters()
        migration_bytes = MIGRATION.read_bytes()
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: migration 0038 rollback validation preflight: {type(exc).__name__}: {exc}")
        return 2

    migration_hash = hashlib.sha256(migration_bytes).digest()
    dsn = f"host={TAILNET_HOST} port={port} dbname={TARGET_DATABASE} user={user}"
    before: tuple[str | None, tuple[tuple[str, str | None], ...]] | None = None
    probe_count: int | None = None
    failure: Exception | None = None
    conn: psycopg.Connection[object] | None = None
    try:
        conn = psycopg.connect(dsn, password=password, connect_timeout=10)
        conn.autocommit = False
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext('validate-0038-schema-version-probe'))")
            assert_platform_bootstrap(cursor)
            assert_public_is_denied(cursor)
            assert_runtime_connect_only(cursor)
            before = acl_snapshot(cursor)
            cursor.execute(strip_transaction_control(migration_bytes.decode("utf-8")))
            assert_schema_version_probe_only(cursor)
            probe_count = run_probe_as_runtime(cursor)
            if hashlib.sha256(MIGRATION.read_bytes()).digest() != migration_hash:
                raise RuntimeError("migration changed during validation; results are discarded")
    except Exception as exc:  # noqa: BLE001 - report the exact live failure class without credentials
        failure = exc
    finally:
        if conn is not None:
            try:
                conn.rollback()
            finally:
                conn.close()

    if failure is not None or before is None or probe_count is None:
        detail = "preflight did not complete" if failure is None else str(failure)
        error_type = "RuntimeError" if failure is None else type(failure).__name__
        print(f"FAIL: migration 0038 rollback validation: {error_type}: {detail}")
        return 1

    try:
        with psycopg.connect(dsn, password=password, connect_timeout=10, autocommit=True) as post_conn:
            with post_conn.cursor() as cursor:
                assert_platform_bootstrap(cursor)
                assert_public_is_denied(cursor)
                assert_runtime_connect_only(cursor)
                after = acl_snapshot(cursor)
    except Exception as exc:  # noqa: BLE001 - postflight must report connection failure
        print(f"FAIL: migration 0038 rollback postflight: {type(exc).__name__}: {exc}")
        return 1
    if after != before:
        print("FAIL: schema_version ACL changed after rollback")
        return 1
    print(f"PASS: migration 0038 rolled back; runtime worker probe succeeded; matched_rows={probe_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
