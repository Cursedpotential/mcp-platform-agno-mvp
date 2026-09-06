"""Rollback-only validation of migration 0036 against live PostgreSQL 18.

The migration's own BEGIN/COMMIT lines are stripped before execution so every
DDL statement remains inside this script's transaction. The transaction is
always rolled back and the preflight/postflight relation inventory must match.
Credentials are parsed from the established local secrets file and never
printed or written elsewhere.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import psycopg
from psycopg import sql as psycopg_sql


ROOT = Path(__file__).resolve().parent.parent
ENV_FILES = (Path.home() / ".secrets" / "probata.env", ROOT / ".env")
TAILNET_HOST = "100.91.190.107"
MIGRATION = ROOT / "sql" / "0036_context_import_foundation.sql"
EXPECTED_RELATIONS = (
    "context.activity_execution",
    "context.activity_receipt",
    "context.hash_batch",
    "context.hash_batch_member",
    "context.hash_manifest",
    "context.hash_manifest_member",
    "context.hash_receipt",
    "context.normalization_lineage",
    "context.normalized_generation",
    "context.normalized_generation_publication",
    "context.normalized_record_identity",
    "context.raw_format_registry",
    "context.raw_generation",
    "context.raw_record_identity",
    "context.reconciliation_receipt",
    "context.retained_object",
    "context.source",
    "context.source_metadata",
    "context.source_version",
    "context.source_version_object",
)
CRITICAL_FUNCTIONS = (
    "assert_hash_manifest_complete",
    "assert_normalized_generation_open",
    "assert_raw_generation_open",
    "assert_raw_subtype_completeness",
    "assert_source_version_retained",
    "forbid_mutation",
    "guard_activity_execution_insert",
    "guard_hash_batch_member_insert",
    "guard_hash_batch_transition",
    "guard_hash_manifest_member_insert",
    "guard_hash_manifest_transition",
    "guard_hash_receipt_insert",
    "guard_normalized_generation_transition",
    "guard_normalized_publication",
    "guard_raw_generation_transition",
    "guard_reconciliation_receipt_insert",
    "guard_source_metadata_insert",
    "guard_source_version_mutation",
    "guard_source_version_object_insert",
    "register_raw_format_subtype",
    "seal_hash_manifest_from_receipt",
)
CRITICAL_TRIGGERS = (
    "activity_execution_retention_gate",
    "hash_batch_member_open_gate",
    "hash_batch_transition_gate",
    "hash_manifest_member_open_gate",
    "hash_manifest_seal_gate",
    "hash_receipt_insert_gate",
    "normalization_lineage_open_generation_gate",
    "normalized_generation_publication_receipt_gate",
    "normalized_generation_seal_publish_gate",
    "raw_generation_seal_gate",
    "raw_record_identity_open_generation_gate",
    "reconciliation_receipt_insert_gate",
    "source_metadata_open_generation_gate",
    "source_version_object_insert_gate",
)
FORBIDDEN_ACTIVITY_RECEIPT_COLUMNS = (
    "source_version_id",
    "raw_generation_id",
    "normalized_generation_id",
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


def parse_env(path: Path) -> dict[str, str]:
    pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2)
        if value.startswith(("'", '"')) and value.endswith(value[0]) and len(value) >= 2:
            value = value[1:-1]
        values[key] = value
    return values


def strip_transaction_control(sql: str) -> str:
    sql = re.sub(r"^\s*BEGIN\s*;", "", sql, flags=re.MULTILINE | re.IGNORECASE)
    return re.sub(r"^\s*COMMIT\s*;", "", sql, flags=re.MULTILINE | re.IGNORECASE)


def relation_inventory(cursor: psycopg.Cursor[object]) -> dict[str, bool]:
    inventory: dict[str, bool] = {}
    for relation in EXPECTED_RELATIONS:
        cursor.execute("SELECT to_regclass(%s) IS NOT NULL", (relation,))
        inventory[relation] = bool(cursor.fetchone()[0])
    return inventory


def single_value(cursor: psycopg.Cursor[object]) -> object:
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("database verification query unexpectedly returned no row")
    return row[0]


def assert_platform_bootstrap(cursor: psycopg.Cursor[object]) -> None:
    cursor.execute("SELECT current_database()")
    if single_value(cursor) != "platform":
        raise RuntimeError("rollback validation is not connected to database platform")
    cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'ai')")
    if not single_value(cursor):
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
    if not single_value(cursor):
        raise RuntimeError("platform_admin is not a member of context_owner")
    cursor.execute("SELECT pg_has_role('platform_runtime', 'context_import_writer', 'MEMBER')")
    if not single_value(cursor):
        raise RuntimeError("platform_runtime is not a member of context_import_writer")

    cursor.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'public' AND table_name = 'schema_version'"""
    )
    columns = {str(row[0]) for row in cursor.fetchall()}
    missing_columns = sorted(EXPECTED_LEDGER_COLUMNS - columns)
    if missing_columns:
        raise RuntimeError("public.schema_version lacks rich ledger columns: " + ", ".join(missing_columns))
    cursor.execute(
        """SELECT pg_get_userbyid(c.relowner)
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relname = 'schema_version'"""
    )
    if single_value(cursor) != "platform_admin":
        raise RuntimeError("public.schema_version must be owned by platform_admin")


def assert_owner_acl_contract(cursor: psycopg.Cursor[object]) -> None:
    cursor.execute("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = 'context'")
    if single_value(cursor) != "context_owner":
        raise RuntimeError("context schema is not owned by context_owner")
    cursor.execute(
        """SELECT privilege_type
           FROM pg_namespace n
           CROSS JOIN LATERAL aclexplode(COALESCE(n.nspacl, acldefault('n', n.nspowner))) acl
           WHERE n.nspname = 'context' AND acl.grantee = 0"""
    )
    if {str(row[0]) for row in cursor.fetchall()} & {"USAGE", "CREATE"}:
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
        if bool(single_value(cursor)) is not expected:
            raise RuntimeError(f"unexpected {privilege} privilege for {role} on context schema")

    cursor.execute(
        """SELECT c.relname, pg_get_userbyid(c.relowner)
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'context' AND c.relkind IN ('r', 'p')"""
    )
    relations = {str(row[0]): str(row[1]) for row in cursor.fetchall()}
    wrong = sorted(table for table, owner in relations.items() if owner != "context_owner")
    if wrong:
        raise RuntimeError("context relations have an unexpected owner: " + ", ".join(wrong))
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
    for table in sorted(relations):
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
            if bool(single_value(cursor)) is not expected:
                raise RuntimeError(f"unexpected {privilege} privilege for {role} on {qualified}")
        cursor.execute("SELECT has_table_privilege('context_import_writer', %s, 'UPDATE')", (qualified,))
        if bool(single_value(cursor)) != (table in LIFECYCLE_TABLES):
            raise RuntimeError(f"writer UPDATE privilege does not match lifecycle policy on {qualified}")
        cursor.execute("SELECT has_table_privilege('platform_runtime', %s, 'UPDATE')", (qualified,))
        if bool(single_value(cursor)) != (table in LIFECYCLE_TABLES):
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
    if (
        not {
            ("r", "context_import_writer", "SELECT"),
            ("r", "context_import_writer", "INSERT"),
            ("r", "context_reader", "SELECT"),
            ("f", "context_import_writer", "EXECUTE"),
        }
        <= defaults
    ):
        raise RuntimeError("context_owner default privileges are incomplete")
    if any(grantee is None for _kind, grantee, _privilege in defaults):
        raise RuntimeError("PUBLIC retains a context_owner default privilege")


def assert_dependencies(cursor: psycopg.Cursor[object]) -> None:
    assert_platform_bootstrap(cursor)
    cursor.execute("SELECT current_setting('server_version_num')::integer")
    if int(cursor.fetchone()[0]) < 180000:
        raise RuntimeError("migration 0036 requires PostgreSQL 18 or newer")
    cursor.execute("SELECT to_regprocedure('uuidv7()') IS NOT NULL")
    if not cursor.fetchone()[0]:
        raise RuntimeError("required uuidv7() function is unavailable")
    cursor.execute(
        """SELECT EXISTS (
               SELECT 1 FROM pg_proc p
               WHERE p.proname = 'digest'
                 AND pg_get_function_identity_arguments(p.oid) = 'bytea, text')"""
    )
    if not cursor.fetchone()[0]:
        raise RuntimeError("required digest(bytea, text) function is unavailable")
    cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto')")
    if not cursor.fetchone()[0]:
        raise RuntimeError("required pgcrypto extension is unavailable")
    cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_language WHERE lanname = 'plpgsql')")
    if not cursor.fetchone()[0]:
        raise RuntimeError("required plpgsql language is unavailable")


def assert_catalog_contract(cursor: psycopg.Cursor[object]) -> None:
    missing = [name for name, exists in relation_inventory(cursor).items() if not exists]
    if missing:
        raise RuntimeError(f"migration did not create expected relations: {', '.join(missing)}")

    cursor.execute(
        """SELECT p.proname FROM pg_proc p
           JOIN pg_namespace n ON n.oid = p.pronamespace
           WHERE n.nspname = 'context' AND p.proname = ANY(%s)""",
        (list(CRITICAL_FUNCTIONS),),
    )
    missing = sorted(set(CRITICAL_FUNCTIONS) - {str(row[0]) for row in cursor.fetchall()})
    if missing:
        raise RuntimeError(f"missing critical functions: {', '.join(missing)}")

    cursor.execute(
        """SELECT t.tgname FROM pg_trigger t
           JOIN pg_class c ON c.oid = t.tgrelid
           JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'context' AND NOT t.tgisinternal
             AND t.tgenabled <> 'D' AND t.tgname = ANY(%s)""",
        (list(CRITICAL_TRIGGERS),),
    )
    missing = sorted(set(CRITICAL_TRIGGERS) - {str(row[0]) for row in cursor.fetchall()})
    if missing:
        raise RuntimeError(f"missing or disabled critical triggers: {', '.join(missing)}")

    cursor.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema = 'context' AND table_name = 'activity_receipt'
             AND column_name = ANY(%s)""",
        (list(FORBIDDEN_ACTIVITY_RECEIPT_COLUMNS),),
    )
    redundant = sorted(str(row[0]) for row in cursor.fetchall())
    if redundant:
        raise RuntimeError(f"activity_receipt has redundant subject columns: {', '.join(redundant)}")

    cursor.execute(
        """SELECT lower(regexp_replace(pg_get_constraintdef(con.oid), '\\s+', ' ', 'g'))
           FROM pg_constraint con
           JOIN pg_class rel ON rel.oid = con.conrelid
           JOIN pg_namespace n ON n.oid = rel.relnamespace
           WHERE n.nspname = 'context' AND rel.relname = 'source_version_object'
             AND con.contype = 'f'"""
    )
    definitions = {str(row[0]) for row in cursor.fetchall()}
    expected_fk = (
        "foreign key (source_version_id, parent_object_id) references "
        "context.source_version_object(source_version_id, object_id)"
    )
    if not any(expected_fk in definition for definition in definitions):
        raise RuntimeError("source_version_object lacks a same-source composite parent FK")

    cursor.execute(
        """SELECT lower(regexp_replace(pg_get_functiondef(p.oid), '\\s+', ' ', 'g'))
           FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
           WHERE n.nspname = 'context'
             AND p.proname = 'guard_source_version_object_insert'"""
    )
    row = cursor.fetchone()
    if row is None or "for update" not in str(row[0]):
        raise RuntimeError("source_version_object insert guard lacks parent row locking")
    assert_owner_acl_contract(cursor)


def insert_retained_source(cursor: psycopg.Cursor[object], label: str, payload: bytes) -> tuple[object, object]:
    cursor.execute(
        """INSERT INTO context.retained_object
               (storage_class, object_uri, content_sha256, byte_length, inline_bytes)
           VALUES ('inline', %s, digest(%s, 'sha256'), %s, %s) RETURNING id""",
        (f"rollback-validator://{label}/original", payload, len(payload), payload),
    )
    object_id = cursor.fetchone()[0]
    cursor.execute(
        "INSERT INTO context.source (source_key, provenance_class) VALUES (%s, 'unknown') RETURNING id",
        (f"rollback-validator-{label}",),
    )
    source_id = cursor.fetchone()[0]
    cursor.execute(
        """INSERT INTO context.source_version
               (source_id, version_ordinal, workflow_id, submission_idempotency_key,
                declared_format, acquired_at)
           VALUES (%s, 1, %s, %s, 'test', now()) RETURNING id""",
        (source_id, f"rollback-workflow-{label}", f"rollback-key-{label}"),
    )
    source_version_id = cursor.fetchone()[0]
    cursor.execute(
        """INSERT INTO context.source_version_object
               (source_version_id, object_id, object_role) VALUES (%s, %s, 'original')""",
        (source_version_id, object_id),
    )
    cursor.execute(
        """INSERT INTO context.activity_execution
               (source_version_id, workflow_id, activity_name, idempotency_key)
           VALUES (%s, %s, 'retain_original_activity', %s) RETURNING id""",
        (source_version_id, f"rollback-workflow-{label}", f"retain-{label}"),
    )
    execution_id = cursor.fetchone()[0]
    cursor.execute(
        """INSERT INTO context.activity_receipt
               (activity_execution_id, attempt, status, started_at, completed_at, result_ref)
           VALUES (%s, 1, 'success', now(), now(),
                   jsonb_build_object('ref_kind', 'retained_object', 'ref_id', %s::text))""",
        (execution_id, object_id),
    )
    cursor.execute(
        "UPDATE context.source_version SET original_object_id = %s, status = 'retained' WHERE id = %s",
        (object_id, source_version_id),
    )
    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    cursor.execute("SET CONSTRAINTS ALL DEFERRED")
    return source_version_id, object_id


def assert_parent_membership_behavior(cursor: psycopg.Cursor[object]) -> None:
    source_a, parent_a = insert_retained_source(cursor, "a", b"source-a")
    _source_b, parent_b = insert_retained_source(cursor, "b", b"source-b")
    child_ids: list[object] = []
    for label in ("same-source-child", "cross-source-child"):
        payload = label.encode()
        cursor.execute(
            """INSERT INTO context.retained_object
                   (storage_class, object_uri, content_sha256, byte_length, inline_bytes)
               VALUES ('inline', %s, digest(%s, 'sha256'), %s, %s) RETURNING id""",
            (f"rollback-validator://{label}", payload, len(payload), payload),
        )
        child_ids.append(cursor.fetchone()[0])
    cursor.execute(
        """INSERT INTO context.source_version_object
               (source_version_id, object_id, object_role, parent_object_id)
           VALUES (%s, %s, 'container_member', %s)""",
        (source_a, child_ids[0], parent_a),
    )

    cursor.execute("SAVEPOINT cross_source_parent_probe")
    try:
        cursor.execute(
            """INSERT INTO context.source_version_object
                   (source_version_id, object_id, object_role, parent_object_id)
               VALUES (%s, %s, 'container_member', %s)""",
            (source_a, child_ids[1], parent_b),
        )
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    except psycopg.errors.ForeignKeyViolation:
        cursor.execute("ROLLBACK TO SAVEPOINT cross_source_parent_probe")
        cursor.execute("RELEASE SAVEPOINT cross_source_parent_probe")
        cursor.execute("SET CONSTRAINTS ALL DEFERRED")
    else:
        raise RuntimeError("cross-source parent object was incorrectly accepted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        default="platform",
        help="fresh rollback-validation target; only 'platform' is accepted",
    )
    args = parser.parse_args()
    database = args.database.strip()
    if database != "platform":
        parser.error("migration 0036 may be validated only against the fresh 'platform' database")

    source = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"conn\.commit\s*\(", source):
        print("ERROR: rollback validator contains a connection commit call; refusing to run")
        return 2
    env_file = next((path for path in ENV_FILES if path.is_file()), None)
    if env_file is None:
        print("ERROR: established PostgreSQL credentials file is unavailable")
        return 2

    values = parse_env(env_file)
    user = values.get("DB_USER") or values.get("POSTGRES_USER", "")
    password = values.get("DB_PASS") or values.get("POSTGRES_PASSWORD", "")
    port = values.get("DB_PORT", "5432")
    if not (user and password and database):
        print("ERROR: required PostgreSQL credential names could not be resolved; values remain hidden")
        return 2

    migration_bytes = MIGRATION.read_bytes()
    migration_hash = hashlib.sha256(migration_bytes).digest()
    migration_sql = migration_bytes.decode("utf-8")
    declared_tables = set(
        re.findall(
            r"(?im)^\s*create\s+table\s+if\s+not\s+exists\s+context\.([a-z0-9_]+)\s*\(",
            migration_sql,
        )
    )
    expected_tables = {name.split(".", 1)[1] for name in EXPECTED_RELATIONS}
    if declared_tables != expected_tables:
        print("ERROR: migration does not declare the exact 20-table foundation; refusing live execution")
        return 2

    ddl = strip_transaction_control(migration_sql)
    dsn = f"host={TAILNET_HOST} port={port} dbname={database} user={user}"
    before: dict[str, bool] | None = None
    failure: Exception | None = None
    conn: psycopg.Connection[object] | None = None
    try:
        conn = psycopg.connect(dsn, password=password, connect_timeout=10)
        conn.autocommit = False
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '120s'")
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext('validate-0036-context-import'))")
            assert_dependencies(cursor)
            before = relation_inventory(cursor)
            cursor.execute(psycopg_sql.SQL(ddl))
            assert_catalog_contract(cursor)
            assert_parent_membership_behavior(cursor)
            if hashlib.sha256(MIGRATION.read_bytes()).digest() != migration_hash:
                raise RuntimeError("migration changed during validation; results are discarded")
    except Exception as exc:  # noqa: BLE001 - validation must report the database error class
        failure = exc
    finally:
        if conn is not None:
            try:
                conn.rollback()
            finally:
                conn.close()

    if failure is not None:
        print(f"FAIL: migration 0036 rollback validation: {type(failure).__name__}: {failure}")
        return 1
    if before is None:
        print("FAIL: migration 0036 rollback validation did not capture preflight inventory")
        return 1

    try:
        with psycopg.connect(dsn, password=password, connect_timeout=10, autocommit=True) as post_conn:
            with post_conn.cursor() as cursor:
                after = relation_inventory(cursor)
    except Exception as exc:  # noqa: BLE001 - postflight must report connection failure
        print(f"FAIL: migration 0036 rollback postflight: {type(exc).__name__}: {exc}")
        return 1

    if after != before:
        print("FAIL: live relation inventory changed after rollback")
        return 1
    print(
        "PASS: migration 0036 executed on live PostgreSQL and rolled back; "
        "20 tables, dependencies, owners/ACLs, critical catalog objects, parent membership, "
        "and rollback inventory verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
