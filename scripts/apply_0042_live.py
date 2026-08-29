"""Apply migration 0042 to the ``platform`` database under an advisory lock.

Forward-only repair: redefines ``context.guard_hash_receipt_insert`` so the
inline byte-range slice uses safe ``::int4`` arguments with explicit range
guards, then records one rich-ledger entry. Requires ``--apply``; the
independent second connection verifies the committed result.
"""

# Byline: Claude Code · glm-5.3:cloud · 2026-08-28

from __future__ import annotations

import argparse
import hashlib

import psycopg

from validate_0037_live import (  # type: ignore[import-not-found]  # direct script execution import
    TARGET_DATABASE,
    TAILNET_HOST,
    assert_platform_bootstrap,
    assert_public_is_denied,
    assert_runtime_connect_only,
    connection_parameters,
    strip_transaction_control,
)
from validate_0042_live import (  # type: ignore[import-not-found]  # direct script execution import
    APPLIES_TO,
    DDL_URI,
    MIGRATION,
    MIGRATION_ID,
    MIGRATION_LABEL,
    assert_bytea_slice_prerequisites,
    assert_ledger_entry,
    assert_redefined_function,
    guard_function_definition,
    recorded_hashes,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="apply migration 0042 to the platform database")
    parser.add_argument("--apply", action="store_true", help="perform the production transaction")
    parser.add_argument("--database", default=TARGET_DATABASE)
    args = parser.parse_args()
    if not args.apply:
        parser.error("refusing to run without explicit --apply")
    if args.database.strip() != TARGET_DATABASE:
        parser.error("migration 0042 may be applied only to database 'platform'")

    user, password, port = connection_parameters()
    migration_bytes = MIGRATION.read_bytes()
    migration_hash = hashlib.sha256(migration_bytes).digest()
    dsn = f"host={TAILNET_HOST} port={port} dbname={TARGET_DATABASE} user={user}"

    no_op = False
    with psycopg.connect(dsn, password=password, connect_timeout=10) as conn:
        conn.autocommit = False
        cursor = conn.cursor()
        cursor.execute("SET LOCAL lock_timeout = '5s'")
        cursor.execute("SET LOCAL statement_timeout = '30s'")
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('apply-0042-context-hash-bytea-slice'))")
        assert_platform_bootstrap(cursor)
        assert_public_is_denied(cursor)
        assert_runtime_connect_only(cursor)
        assert_bytea_slice_prerequisites(cursor)
        if recorded_hashes(cursor):
            assert_ledger_entry(cursor, migration_hash)
            assert_redefined_function(guard_function_definition(cursor))
            conn.rollback()
            no_op = True
        else:
            cursor.execute(strip_transaction_control(migration_bytes.decode("utf-8")))
            assert_redefined_function(guard_function_definition(cursor))
            cursor.execute("SET LOCAL ROLE platform_admin")
            cursor.execute(
                """
                INSERT INTO public.schema_version
                    (version_label, applies_to, ddl_uri, ddl_hash, migration_id, status, notes, created_by)
                VALUES (%s, %s, %s, %s, %s, 'active', %s, current_user)
                """,
                (
                    MIGRATION_LABEL,
                    APPLIES_TO,
                    DDL_URI,
                    migration_hash,
                    MIGRATION_ID,
                    "Applied by scripts/apply_0042_live.py under an advisory lock; "
                    "forward-only CREATE OR REPLACE of context.guard_hash_receipt_insert; "
                    "recovery is forward-fix after commit.",
                ),
            )
            assert_ledger_entry(cursor, migration_hash)
            conn.commit()

    with psycopg.connect(dsn, password=password, connect_timeout=10) as conn:
        cursor = conn.cursor()
        assert_platform_bootstrap(cursor)
        assert_public_is_denied(cursor)
        assert_runtime_connect_only(cursor)
        assert_bytea_slice_prerequisites(cursor)
        assert_redefined_function(guard_function_definition(cursor))
        assert_ledger_entry(cursor, migration_hash)

    disposition = "NO-OP" if no_op else "APPLIED"
    print(f"{disposition}: migration 0042 independently verified; sha256={migration_hash.hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
