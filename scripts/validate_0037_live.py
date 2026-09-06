"""Rollback-only validation for migration 0037 on the ``platform`` database.

The validator executes the idempotent database-ACL migration inside one locked
transaction and always rolls it back.  It never writes a schema-version ledger
row and never prints connection credentials.  It is intentionally narrow: its
only subject is the effective database privileges of ``platform_runtime``.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Final, cast

import psycopg


ROOT: Final = Path(__file__).resolve().parent.parent
MIGRATION: Final = ROOT / "sql" / "0037_platform_runtime_connect.sql"
TARGET_DATABASE: Final = "platform"
MIGRATION_ID: Final = "0037"
MIGRATION_LABEL: Final = "0037_platform_runtime_connect"
DDL_URI: Final = "sql/0037_platform_runtime_connect.sql"
TAILNET_HOST: Final = "100.91.190.107"
ENV_FILES: Final = (Path.home() / ".secrets" / "probata.env", ROOT / ".env")
PLATFORM_ADMIN_ROLE: Final = "platform_admin"
PLATFORM_RUNTIME_ROLE: Final = "platform_runtime"
EXPECTED_LEDGER_COLUMNS: Final = {
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
}


def parse_env(path: Path) -> dict[str, str]:
    pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        key, value = match.groups()
        if value.startswith(("'", '"')) and value.endswith(value[0]) and len(value) >= 2:
            value = value[1:-1]
        values[key] = value
    return values


def connection_parameters() -> tuple[str, str, str]:
    env_file = next((path for path in ENV_FILES if path.is_file()), None)
    if env_file is None:
        raise RuntimeError("established PostgreSQL credentials file is unavailable")
    values = parse_env(env_file)
    user = values.get("DB_USER") or values.get("POSTGRES_USER", "")
    password = values.get("DB_PASS") or values.get("POSTGRES_PASSWORD", "")
    port = values.get("DB_PORT", "5432")
    if not (user and password):
        raise RuntimeError("required PostgreSQL credential names could not be resolved")
    return user, password, port


def strip_transaction_control(sql: str) -> str:
    sql = re.sub(r"^\s*BEGIN\s*;", "", sql, flags=re.MULTILINE | re.IGNORECASE)
    return re.sub(r"^\s*COMMIT\s*;", "", sql, flags=re.MULTILINE | re.IGNORECASE)


def _single_value(cursor: psycopg.Cursor[object]) -> object:
    row = cast(tuple[object, ...] | None, cursor.fetchone())
    if row is None:
        raise RuntimeError("database verification query unexpectedly returned no row")
    return row[0]


def _rows(cursor: psycopg.Cursor[object]) -> list[tuple[object, ...]]:
    return cast(list[tuple[object, ...]], cursor.fetchall())


def assert_platform_bootstrap(cursor: psycopg.Cursor[object]) -> None:
    """Require the exact target, its expected owner, safe runtime, and rich ledger."""
    cursor.execute("SELECT current_database()")
    if _single_value(cursor) != TARGET_DATABASE:
        raise RuntimeError("0037 validation is not connected to database platform")
    cursor.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = current_database()")
    if _single_value(cursor) != PLATFORM_ADMIN_ROLE:
        raise RuntimeError("database platform must be owned by platform_admin")
    cursor.execute(
        """SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
           FROM pg_roles WHERE rolname = %s""",
        (PLATFORM_RUNTIME_ROLE,),
    )
    runtime = cast(tuple[object, ...] | None, cursor.fetchone())
    if runtime is None:
        raise RuntimeError("missing platform_runtime role")
    can_login, *dangerous = runtime
    if not bool(can_login) or any(bool(value) for value in dangerous):
        raise RuntimeError("platform_runtime is not the safe dedicated LOGIN role")
    cursor.execute(
        """WITH RECURSIVE role_closure AS (
               SELECT oid FROM pg_roles WHERE rolname = %s
               UNION
               SELECT membership.roleid
               FROM pg_auth_members membership
               JOIN role_closure closure ON closure.oid = membership.member
           )
           SELECT COALESCE(bool_or(role.rolsuper OR role.rolcreatedb OR role.rolcreaterole
                                   OR role.rolreplication OR role.rolbypassrls), false)
           FROM role_closure closure
           JOIN pg_roles role ON role.oid = closure.oid""",
        (PLATFORM_RUNTIME_ROLE,),
    )
    if bool(_single_value(cursor)):
        raise RuntimeError("platform_runtime inherits a forbidden elevated PostgreSQL attribute")
    cursor.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'schema_version'"""
    )
    columns = {str(row[0]) for row in _rows(cursor)}
    missing = sorted(EXPECTED_LEDGER_COLUMNS - columns)
    if missing:
        raise RuntimeError("public.schema_version lacks rich ledger columns: " + ", ".join(missing))
    cursor.execute(
        """SELECT pg_get_userbyid(c.relowner)
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relname = 'schema_version'"""
    )
    if _single_value(cursor) != PLATFORM_ADMIN_ROLE:
        raise RuntimeError("public.schema_version must be owned by platform_admin")


def assert_public_is_denied(cursor: psycopg.Cursor[object]) -> None:
    cursor.execute(
        """SELECT privilege_type
           FROM pg_database database
           CROSS JOIN LATERAL aclexplode(COALESCE(database.datacl, acldefault('d', database.datdba))) acl
           WHERE database.datname = current_database() AND acl.grantee = 0"""
    )
    public_privileges = {str(row[0]) for row in _rows(cursor)}
    prohibited = public_privileges & {"CONNECT", "TEMPORARY", "CREATE"}
    if prohibited:
        raise RuntimeError("PUBLIC retains platform database privilege(s): " + ", ".join(sorted(prohibited)))


def runtime_access_snapshot(cursor: psycopg.Cursor[object]) -> tuple[bool, bool, bool, str | None]:
    cursor.execute(
        """SELECT has_database_privilege(%s, current_database(), 'CONNECT'),
                  has_database_privilege(%s, current_database(), 'TEMPORARY'),
                  has_database_privilege(%s, current_database(), 'CREATE'),
                  array_to_string(datacl, E'\\n')
           FROM pg_database WHERE datname = current_database()""",
        (PLATFORM_RUNTIME_ROLE, PLATFORM_RUNTIME_ROLE, PLATFORM_RUNTIME_ROLE),
    )
    row = cast(tuple[object, ...] | None, cursor.fetchone())
    if row is None:
        raise RuntimeError("database privilege query unexpectedly returned no row")
    return bool(row[0]), bool(row[1]), bool(row[2]), None if row[3] is None else str(row[3])


def assert_runtime_connect_only(cursor: psycopg.Cursor[object]) -> None:
    has_connect, has_temporary, has_create, _acl = runtime_access_snapshot(cursor)
    if not has_connect or has_temporary or has_create:
        raise RuntimeError("platform_runtime must have CONNECT only (no TEMPORARY or CREATE) on platform")


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
    expected = (MIGRATION_LABEL, TARGET_DATABASE, DDL_URI, migration_hash, PLATFORM_ADMIN_ROLE)
    if len(rows) != 1 or tuple(rows[0]) != expected:
        raise RuntimeError("migration 0037 requires one matching active rich-ledger entry by platform_admin")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=TARGET_DATABASE, help="only 'platform' is accepted")
    args = parser.parse_args()
    if args.database.strip() != TARGET_DATABASE:
        parser.error("migration 0037 may be validated only against database 'platform'")

    source = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"conn\.commit\s*\(", source):
        print("ERROR: rollback validator contains a connection commit call; refusing to run")
        return 2

    try:
        user, password, port = connection_parameters()
        migration_bytes = MIGRATION.read_bytes()
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: migration 0037 rollback validation preflight: {type(exc).__name__}: {exc}")
        return 2
    migration_hash = hashlib.sha256(migration_bytes).digest()
    dsn = f"host={TAILNET_HOST} port={port} dbname={TARGET_DATABASE} user={user}"
    before: tuple[bool, bool, bool, str | None] | None = None
    failure: Exception | None = None
    conn: psycopg.Connection[object] | None = None
    try:
        conn = psycopg.connect(dsn, password=password, connect_timeout=10)
        conn.autocommit = False
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext('validate-0037-platform-runtime-connect'))")
            assert_platform_bootstrap(cursor)
            assert_public_is_denied(cursor)
            before = runtime_access_snapshot(cursor)
            cursor.execute(strip_transaction_control(migration_bytes.decode("utf-8")))
            assert_public_is_denied(cursor)
            assert_runtime_connect_only(cursor)
            if hashlib.sha256(MIGRATION.read_bytes()).digest() != migration_hash:
                raise RuntimeError("migration changed during validation; results are discarded")
    except Exception as exc:  # noqa: BLE001 - must report the database error class
        failure = exc
    finally:
        if conn is not None:
            try:
                conn.rollback()
            finally:
                conn.close()

    if failure is not None or before is None:
        detail = "preflight did not capture database ACL state" if before is None else str(failure)
        error_type = "RuntimeError" if failure is None else type(failure).__name__
        print(f"FAIL: migration 0037 rollback validation: {error_type}: {detail}")
        return 1

    try:
        with psycopg.connect(dsn, password=password, connect_timeout=10, autocommit=True) as post_conn:
            with post_conn.cursor() as cursor:
                assert_platform_bootstrap(cursor)
                assert_public_is_denied(cursor)
                after = runtime_access_snapshot(cursor)
    except Exception as exc:  # noqa: BLE001 - postflight must report connection failure
        print(f"FAIL: migration 0037 rollback postflight: {type(exc).__name__}: {exc}")
        return 1
    if after != before:
        print("FAIL: platform database ACL changed after rollback")
        return 1
    print("PASS: migration 0037 executed and rolled back; platform runtime CONNECT-only contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
