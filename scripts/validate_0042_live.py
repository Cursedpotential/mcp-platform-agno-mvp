"""Rollback-only validation for migration 0042 on the ``platform`` database.

The validator locks a transaction, redefines ``context.guard_hash_receipt_insert``
with the safe ``::int4`` inline slice, probes the resulting function definition,
and always rolls back so the live function is never left modified. It never
writes a ledger row and never prints credentials.
"""

# Byline: Claude Code · glm-5.3:cloud · 2026-08-28

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
MIGRATION: Final = ROOT / "sql" / "0042_context_hash_bytea_slice.sql"
MIGRATION_ID: Final = "0042"
MIGRATION_LABEL: Final = "0042_context_hash_bytea_slice"
APPLIES_TO: Final = "context.guard_hash_receipt_insert()"
DDL_URI: Final = "sql/0042_context_hash_bytea_slice.sql"
PLATFORM_ADMIN_ROLE: Final = "platform_admin"
OWNER_ROLE: Final = "context_owner"
WRITER_ROLE: Final = "context_import_writer"
FUNCTION_NAME: Final = "guard_hash_receipt_insert"
TRIGGER_TABLE: Final = "context.hash_receipt"
TRIGGER_NAME: Final = "hash_receipt_insert_gate"

SAFE_INLINE_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "(raw.byte_offset + 1)::int4",
        "raw.byte_length::int4",
        "raw.byte_offset >= 0",
        "raw.byte_offset <= 2147483646",
        "raw.byte_length >= 0",
        "raw.byte_length <= 2147483647",
        "raw.byte_offset + raw.byte_length <= locator_object.byte_length",
        "octet_length(locator_object.inline_bytes)",
    }
)

BEHAVIOR_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "hash_source_activity",
        "hash_raw_records_activity",
        "hash_raw_generation_activity",
        "hash_normalized_records_activity",
        "hash_normalized_generation_activity",
        "hash receipt requires successful same-source % receipt",
        "H1 receipt must equal the retained original content_sha256",
        "raw H2 receipt does not match DB-resident stored bytes or inline byte range",
        "normalized record digest must hash its exact canonical_bytes and canonicalization",
        "generation hash receipt requires its matching open manifest",
        "context.assert_hash_manifest_complete",
        "RETURN NEW;",
    }
)

FORBIDDEN_RAW_FORM: Final = "FROM raw.byte_offset + 1 FOR raw.byte_length"


def _rows(cursor: psycopg.Cursor[object]) -> list[tuple[object, ...]]:
    return cast("list[tuple[object, ...]]", cursor.fetchall())


def _single_value(cursor: psycopg.Cursor[object]) -> object:
    row = cast("tuple[object, ...] | None", cursor.fetchone())
    if row is None:
        raise RuntimeError("database verification query unexpectedly returned no row")
    return row[0]


def assert_bytea_slice_prerequisites(cursor: psycopg.Cursor[object]) -> None:
    writer = _rows(
        cursor.execute(
            """
            SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
            FROM pg_roles
            WHERE rolname = %s
            """,
            (WRITER_ROLE,),
        )
        or cursor
    )
    if len(writer) != 1 or bool(writer[0][0]) or any(bool(value) for value in writer[0][1:]):
        raise RuntimeError("context_import_writer must be a safe NOLOGIN capability role")
    cursor.execute("SELECT pg_has_role(%s, %s, 'MEMBER')", (PLATFORM_RUNTIME_ROLE, WRITER_ROLE))
    if _single_value(cursor) is not True:
        raise RuntimeError("platform_runtime must be a member of context_import_writer")
    owner = _single_value(
        cursor.execute(
            """
            SELECT pg_get_userbyid(proc.proowner)
            FROM pg_proc proc
            JOIN pg_namespace nsp ON nsp.oid = proc.pronamespace
            WHERE nsp.nspname = 'context' AND proc.proname = %s
            """,
            (FUNCTION_NAME,),
        )
        or cursor
    )
    if cast(str, owner) != OWNER_ROLE:
        raise RuntimeError("context.guard_hash_receipt_insert() must be owned by context_owner")
    cursor.execute(
        """
        SELECT count(*)
        FROM pg_trigger trigger
        WHERE trigger.tgrelid = %s::regclass
          AND trigger.tgname = %s
          AND NOT trigger.tgisinternal
          AND trigger.tgenabled <> 'D'
        """,
        (TRIGGER_TABLE, TRIGGER_NAME),
    )
    if int(cast(int, _single_value(cursor))) != 1:
        raise RuntimeError("context.hash_receipt requires the enabled hash_receipt_insert_gate trigger")


def guard_function_definition(cursor: psycopg.Cursor[object]) -> str:
    definition = _single_value(
        cursor.execute(
            """
            SELECT pg_get_functiondef(proc.oid)
            FROM pg_proc proc
            JOIN pg_namespace nsp ON nsp.oid = proc.pronamespace
            WHERE nsp.nspname = 'context' AND proc.proname = %s
            """,
            (FUNCTION_NAME,),
        )
        or cursor
    )
    return cast(str, definition)


def assert_redefined_function(definition: str) -> None:
    for marker in sorted(SAFE_INLINE_MARKERS):
        if marker not in definition:
            raise RuntimeError(f"redefined guard is missing the safe inline-slice marker {marker!r}")
    for marker in sorted(BEHAVIOR_MARKERS):
        if marker not in definition:
            raise RuntimeError(f"redefined guard is missing the preserved 0036 behavior marker {marker!r}")
    if FORBIDDEN_RAW_FORM in definition:
        raise RuntimeError("redefined guard still contains the raw bigint substring form")


def recorded_hashes(cursor: psycopg.Cursor[object]) -> list[bytes]:
    rows = _rows(
        cursor.execute(
            """
            SELECT ddl_hash
            FROM public.schema_version
            WHERE migration_id = %s AND status = 'active'
            ORDER BY created_at
            """,
            (MIGRATION_ID,),
        )
        or cursor
    )
    return [cast(bytes, row[0]) for row in rows]


def assert_ledger_entry(cursor: psycopg.Cursor[object], migration_hash: bytes) -> None:
    rows = _rows(
        cursor.execute(
            """
            SELECT version_label, applies_to, ddl_uri, ddl_hash, created_by
            FROM public.schema_version
            WHERE migration_id = %s AND status = 'active'
            ORDER BY created_at
            """,
            (MIGRATION_ID,),
        )
        or cursor
    )
    expected = (MIGRATION_LABEL, APPLIES_TO, DDL_URI, migration_hash, PLATFORM_ADMIN_ROLE)
    if len(rows) != 1 or tuple(rows[0]) != expected:
        raise RuntimeError("migration 0042 requires one matching active rich-ledger entry by platform_admin")


def main() -> int:
    parser = argparse.ArgumentParser(description="rollback-only live validation for migration 0042")
    parser.add_argument("--database", default=TARGET_DATABASE)
    args = parser.parse_args()
    if args.database.strip() != TARGET_DATABASE:
        parser.error(f"migration 0042 may be validated only against database {TARGET_DATABASE!r}")

    source = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"conn\.commit\s*\(", source):
        print("ERROR: rollback validator contains a connection commit call; refusing to run")
        return 2

    try:
        user, password, port = connection_parameters()
    except (OSError, RuntimeError) as exc:
        print(f"FAIL: migration 0042 rollback validation: {type(exc).__name__}: {exc}")
        return 2

    migration_bytes = MIGRATION.read_bytes()
    migration_hash = hashlib.sha256(migration_bytes).digest()
    dsn = f"host={TAILNET_HOST} port={port} dbname={TARGET_DATABASE} user={user}"

    failure: str | None = None
    before: str | None = None
    conn = psycopg.connect(dsn, password=password, connect_timeout=10)
    try:
        conn.autocommit = False
        cursor = conn.cursor()
        cursor.execute("SET LOCAL lock_timeout = '5s'")
        cursor.execute("SET LOCAL statement_timeout = '30s'")
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('validate-0042-context-hash-bytea-slice'))")
        assert_platform_bootstrap(cursor)
        assert_public_is_denied(cursor)
        assert_runtime_connect_only(cursor)
        assert_bytea_slice_prerequisites(cursor)
        before = guard_function_definition(cursor)
        cursor.execute(strip_transaction_control(migration_bytes.decode("utf-8")))
        assert_redefined_function(guard_function_definition(cursor))
        if hashlib.sha256(MIGRATION.read_bytes()).digest() != migration_hash:
            raise RuntimeError("migration changed during validation; results are discarded")
    except Exception as exc:  # noqa: BLE001
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        conn.rollback()
        conn.close()

    if failure is not None or before is None:
        if failure is None:
            failure = "migration 0042 validation ended without a before-snapshot"
        print(f"FAIL: migration 0042 rollback validation: {failure}")
        return 1

    with psycopg.connect(dsn, password=password, connect_timeout=10, autocommit=True) as post_conn:
        post_cursor = post_conn.cursor()
        assert_platform_bootstrap(post_cursor)
        assert_public_is_denied(post_cursor)
        assert_runtime_connect_only(post_cursor)
        assert_bytea_slice_prerequisites(post_cursor)
        after = guard_function_definition(post_cursor)
    if after != before:
        print("FAIL: context.guard_hash_receipt_insert definition changed after rollback")
        return 1

    print("PASS: migration 0042 rollback validation left the live function definition unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
