"""Apply migration 0036 once to the fresh ``platform`` PostgreSQL database.

The operation is deliberately explicit: callers must pass ``--apply``. The
migration executes inside one transaction under an advisory lock, refuses a
partially applied target, verifies its core relations before commit, and then
reconnects for an independent post-commit check. Credentials are read from the
established secrets file and are never printed.
"""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Sequence

import psycopg

from validate_0036_live import (
    ENV_FILES,
    EXPECTED_RELATIONS,
    MIGRATION,
    TAILNET_HOST,
    parse_env,
    relation_inventory,
    strip_transaction_control,
)


EXPECTED_LEDGER_COLUMNS = {
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
CONTEXT_ROLES = (
    "platform_admin",
    "platform_runtime",
    "context_owner",
    "context_import_writer",
    "context_reader",
)
LIFECYCLE_TABLES = {
    "source_version",
    "raw_generation",
    "normalized_generation",
    "hash_batch",
    "hash_manifest",
}
OWNER_VALIDATED_INSERT_TABLES = {"raw_format_registry"}


def connection_parameters(database: str) -> tuple[str, str, str]:
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


def _single_value(cursor: psycopg.Cursor[object]) -> object:
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("database verification query unexpectedly returned no row")
    return row[0]


def verify_platform_bootstrap(cursor: psycopg.Cursor[object]) -> None:
    """Fail closed unless this is the fresh platform database with safe roles."""
    cursor.execute("SELECT current_database()")
    if _single_value(cursor) != "platform":
        raise RuntimeError("migration 0036 connection is not the platform database")
    cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'ai')")
    if not _single_value(cursor):
        raise RuntimeError("legacy ai database is absent; refusing an unexpected cluster")

    cursor.execute(
        """SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
                  rolreplication, rolbypassrls
           FROM pg_roles WHERE rolname = ANY(%s)""",
        (list(CONTEXT_ROLES),),
    )
    roles = {str(row[0]): row[1:] for row in cursor.fetchall()}
    missing = sorted(set(CONTEXT_ROLES) - roles.keys())
    if missing:
        raise RuntimeError(f"missing platform bootstrap roles: {', '.join(missing)}")
    for role in CONTEXT_ROLES:
        _can_login, *dangerous = roles[role]
        if any(bool(value) for value in dangerous):
            raise RuntimeError(f"role {role} has a forbidden elevated PostgreSQL attribute")
    for role in ("platform_admin", "context_owner", "context_import_writer", "context_reader"):
        if bool(roles[role][0]):
            raise RuntimeError(f"ownership/grant role {role} must be NOLOGIN")
    if not bool(roles["platform_runtime"][0]):
        raise RuntimeError("platform_runtime must be the dedicated LOGIN role")

    cursor.execute("SELECT pg_has_role('platform_admin', 'context_owner', 'MEMBER')")
    if not _single_value(cursor):
        raise RuntimeError("platform_admin is not a member of context_owner")
    cursor.execute("SELECT pg_has_role('platform_runtime', 'context_import_writer', 'MEMBER')")
    if not _single_value(cursor):
        raise RuntimeError("platform_runtime is not a member of context_import_writer")

    cursor.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'schema_version'"""
    )
    ledger_columns = {str(row[0]) for row in cursor.fetchall()}
    missing_columns = sorted(EXPECTED_LEDGER_COLUMNS - ledger_columns)
    if missing_columns:
        raise RuntimeError("public.schema_version lacks rich ledger columns: " + ", ".join(missing_columns))
    cursor.execute(
        """SELECT pg_get_userbyid(c.relowner)
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relname = 'schema_version'"""
    )
    if _single_value(cursor) != "platform_admin":
        raise RuntimeError("public.schema_version must be owned by platform_admin")


def verify_shape(cursor: psycopg.Cursor[object]) -> None:
    inventory = relation_inventory(cursor)
    missing = [name for name, exists in inventory.items() if not exists]
    if missing:
        raise RuntimeError(f"migration is missing expected relations: {', '.join(missing)}")

    cursor.execute(
        """SELECT count(*) FROM information_schema.columns
           WHERE table_schema = 'context'
             AND table_name = 'activity_receipt'
             AND column_name IN ('source_version_id', 'raw_generation_id',
                                 'normalized_generation_id')"""
    )
    if _single_value(cursor) != 0:
        raise RuntimeError("activity_receipt contains forbidden redundant subject columns")


def verify_owner_and_acl_contract(cursor: psycopg.Cursor[object]) -> None:
    """Verify owners, effective grants, and future-object default privileges."""
    cursor.execute("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = 'context'")
    if _single_value(cursor) != "context_owner":
        raise RuntimeError("context schema is not owned by context_owner")
    cursor.execute(
        """SELECT privilege_type
           FROM pg_namespace n
           CROSS JOIN LATERAL aclexplode(COALESCE(n.nspacl, acldefault('n', n.nspowner))) acl
           WHERE n.nspname = 'context' AND acl.grantee = 0"""
    )
    public_schema_privileges = {str(row[0]) for row in cursor.fetchall()}
    if public_schema_privileges & {"USAGE", "CREATE"}:
        raise RuntimeError("PUBLIC retains a privilege on context schema")
    for role, privilege, expected in (
        ("context_import_writer", "USAGE", True),
        ("context_import_writer", "CREATE", False),
        ("context_reader", "USAGE", True),
        ("context_reader", "CREATE", False),
        ("platform_runtime", "USAGE", True),
        ("platform_runtime", "CREATE", False),
    ):
        cursor.execute("SELECT has_schema_privilege(%s, 'context', %s)", (role, privilege))
        if bool(_single_value(cursor)) is not expected:
            raise RuntimeError(f"unexpected {privilege} privilege for {role} on context schema")

    cursor.execute(
        """SELECT c.relname, pg_get_userbyid(c.relowner)
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'context' AND c.relkind IN ('r', 'p')"""
    )
    relation_owners = {str(row[0]): str(row[1]) for row in cursor.fetchall()}
    wrong_relations = sorted(name for name, owner in relation_owners.items() if owner != "context_owner")
    if wrong_relations:
        raise RuntimeError("context relations have an unexpected owner: " + ", ".join(wrong_relations))
    cursor.execute(
        """SELECT DISTINCT c.relname
           FROM pg_class c
           JOIN pg_namespace n ON n.oid = c.relnamespace
           CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl, acldefault('r', c.relowner))) acl
           WHERE n.nspname = 'context' AND c.relkind IN ('r', 'p')
             AND acl.grantee = 0"""
    )
    public_relations = sorted(str(row[0]) for row in cursor.fetchall())
    if public_relations:
        raise RuntimeError("PUBLIC retains a context relation privilege: " + ", ".join(public_relations))

    cursor.execute(
        """SELECT p.proname, pg_get_userbyid(p.proowner)
           FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
           WHERE n.nspname = 'context'"""
    )
    wrong_functions = sorted(str(row[0]) for row in cursor.fetchall() if str(row[1]) != "context_owner")
    if wrong_functions:
        raise RuntimeError("context functions have an unexpected owner: " + ", ".join(wrong_functions))
    cursor.execute(
        """SELECT DISTINCT p.proname
           FROM pg_proc p
           JOIN pg_namespace n ON n.oid = p.pronamespace
           CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) acl
           WHERE n.nspname = 'context' AND acl.grantee = 0"""
    )
    public_functions = sorted(str(row[0]) for row in cursor.fetchall())
    if public_functions:
        raise RuntimeError("PUBLIC retains context function execution: " + ", ".join(public_functions))

    for table in sorted(relation_owners):
        qualified = f"context.{table}"
        for role, privilege, expected in (
            ("context_reader", "SELECT", True),
            ("context_reader", "INSERT", False),
            ("context_reader", "UPDATE", False),
            ("context_reader", "DELETE", False),
            ("context_import_writer", "SELECT", True),
            ("context_import_writer", "INSERT", table not in OWNER_VALIDATED_INSERT_TABLES),
            ("context_import_writer", "DELETE", False),
            ("platform_runtime", "SELECT", True),
            ("platform_runtime", "INSERT", table not in OWNER_VALIDATED_INSERT_TABLES),
            ("platform_runtime", "DELETE", False),
        ):
            cursor.execute("SELECT has_table_privilege(%s, %s, %s)", (role, qualified, privilege))
            if bool(_single_value(cursor)) is not expected:
                raise RuntimeError(f"unexpected {privilege} privilege for {role} on {qualified}")
        cursor.execute(
            "SELECT has_table_privilege('context_import_writer', %s, 'UPDATE')",
            (qualified,),
        )
        if bool(_single_value(cursor)) != (table in LIFECYCLE_TABLES):
            raise RuntimeError(f"writer UPDATE privilege does not match lifecycle policy on {qualified}")
        cursor.execute("SELECT has_table_privilege('platform_runtime', %s, 'UPDATE')", (qualified,))
        if bool(_single_value(cursor)) != (table in LIFECYCLE_TABLES):
            raise RuntimeError(f"runtime UPDATE privilege does not match lifecycle policy on {qualified}")

    cursor.execute(
        """SELECT defaclobjtype, grantee.rolname, privilege_type
           FROM pg_default_acl d
           JOIN pg_namespace n ON n.oid = d.defaclnamespace
           CROSS JOIN LATERAL aclexplode(d.defaclacl) acl
           LEFT JOIN pg_roles grantee ON grantee.oid = acl.grantee
           WHERE n.nspname = 'context'
             AND pg_get_userbyid(d.defaclrole) = 'context_owner'"""
    )
    defaults = {(str(row[0]), row[1], str(row[2])) for row in cursor.fetchall()}
    required_defaults = {
        ("r", "context_import_writer", "SELECT"),
        ("r", "context_import_writer", "INSERT"),
        ("r", "context_reader", "SELECT"),
        ("f", "context_import_writer", "EXECUTE"),
    }
    if not required_defaults <= defaults:
        raise RuntimeError("context_owner default privileges are incomplete")
    if any(grantee is None for _kind, grantee, _privilege in defaults):
        raise RuntimeError("PUBLIC retains a context_owner default privilege")


def recorded_hashes(cursor: psycopg.Cursor[object]) -> list[bytes]:
    cursor.execute(
        """SELECT ddl_hash
           FROM public.schema_version
           WHERE migration_id = '0036' AND status = 'active'
           ORDER BY created_at"""
    )
    return [bytes(row[0]) for row in cursor.fetchall()]


def verify_ledger_entry(cursor: psycopg.Cursor[object], migration_hash: bytes) -> None:
    cursor.execute(
        """SELECT ddl_hash, created_by
           FROM public.schema_version
           WHERE migration_id = '0036' AND status = 'active'
           ORDER BY created_at"""
    )
    rows: Sequence[tuple[object, object]] = cursor.fetchall()
    if len(rows) != 1 or bytes(rows[0][0]) != migration_hash:
        raise RuntimeError("migration 0036 requires exactly one matching active rich-ledger entry")
    if str(rows[0][1]) != "platform_admin":
        raise RuntimeError("migration 0036 ledger entry was not authored as platform_admin")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the production transaction; without this flag no DDL runs",
    )
    parser.add_argument(
        "--database",
        default="platform",
        help="fresh target database; only 'platform' is accepted",
    )
    args = parser.parse_args()
    if not args.apply:
        parser.error("refusing to run without explicit --apply")
    database = args.database.strip()
    if database != "platform":
        parser.error("migration 0036 may be applied only to the fresh 'platform' database")

    migration_bytes = MIGRATION.read_bytes()
    migration_hash = hashlib.sha256(migration_bytes).hexdigest()
    migration_sql = strip_transaction_control(migration_bytes.decode("utf-8"))
    user, password, port = connection_parameters(database)
    dsn = f"host={TAILNET_HOST} port={port} dbname={database} user={user}"

    no_op = False
    with psycopg.connect(dsn, password=password, connect_timeout=10) as conn:
        conn.autocommit = False
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '120s'")
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext('apply-0036-context-import'))")
            verify_platform_bootstrap(cursor)

            before = relation_inventory(cursor)
            existing = [name for name, exists in before.items() if exists]
            if existing:
                if len(existing) == len(EXPECTED_RELATIONS):
                    verify_shape(cursor)
                    verify_owner_and_acl_contract(cursor)
                    verify_ledger_entry(cursor, bytes.fromhex(migration_hash))
                    conn.rollback()
                    no_op = True
                else:
                    raise RuntimeError(
                        "refusing partially applied migration 0036; existing relations: " + ", ".join(existing)
                    )

            if not no_op:
                cursor.execute(migration_sql)
                verify_shape(cursor)
                verify_owner_and_acl_contract(cursor)
                if recorded_hashes(cursor):
                    raise RuntimeError("migration 0036 ledger entry exists before first apply")
                cursor.execute("SET LOCAL ROLE platform_admin")
                cursor.execute(
                    """INSERT INTO public.schema_version
                           (version_label, applies_to, ddl_uri, ddl_hash, migration_id,
                            status, notes, created_by)
                       VALUES
                           ('0036_context_import_foundation', 'context',
                            'sql/0036_context_import_foundation.sql', %s, '0036',
                            'active',
                            'Applied by scripts/apply_0036_live.py under an advisory lock; '
                            'production recovery is forward-fix after commit.',
                            current_user)""",
                    (bytes.fromhex(migration_hash),),
                )
                verify_ledger_entry(cursor, bytes.fromhex(migration_hash))
                conn.commit()

    with psycopg.connect(dsn, password=password, connect_timeout=10) as conn:
        with conn.cursor() as cursor:
            verify_platform_bootstrap(cursor)
            verify_shape(cursor)
            verify_owner_and_acl_contract(cursor)
            verify_ledger_entry(cursor, bytes.fromhex(migration_hash))
            cursor.execute(
                """SELECT count(*)
                   FROM pg_class c
                   JOIN pg_namespace n ON n.oid = c.relnamespace
                   WHERE n.nspname = 'context'
                     AND c.relkind IN ('r', 'p')"""
            )
            table_count = cursor.fetchone()[0]

    disposition = "NO-OP" if no_op else "APPLIED"
    print(
        f"{disposition}: migration 0036 independently verified after transaction end; "
        f"context_tables={table_count}; sha256={migration_hash}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
