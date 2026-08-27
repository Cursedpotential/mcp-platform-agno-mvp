"""Apply migration 0038 with a hashed, platform-admin rich-ledger receipt."""

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
from validate_0038_live import (  # type: ignore[import-not-found]  # direct script execution import
    APPLIES_TO,
    DDL_URI,
    MIGRATION,
    MIGRATION_ID,
    MIGRATION_LABEL,
    assert_ledger_entry,
    assert_schema_version_probe_only,
    recorded_hashes,
    run_probe_as_runtime,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="perform the production transaction")
    parser.add_argument("--database", default=TARGET_DATABASE, help="only 'platform' is accepted")
    args = parser.parse_args()
    if not args.apply:
        parser.error("refusing to run without explicit --apply")
    if args.database.strip() != TARGET_DATABASE:
        parser.error("migration 0038 may be applied only to database 'platform'")

    migration_bytes = MIGRATION.read_bytes()
    migration_hash = hashlib.sha256(migration_bytes).digest()
    user, password, port = connection_parameters()
    dsn = f"host={TAILNET_HOST} port={port} dbname={TARGET_DATABASE} user={user}"
    no_op = False

    with psycopg.connect(dsn, password=password, connect_timeout=10) as conn:
        conn.autocommit = False
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SET LOCAL statement_timeout = '30s'")
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext('apply-0038-schema-version-probe'))")
            assert_platform_bootstrap(cursor)
            assert_public_is_denied(cursor)
            assert_runtime_connect_only(cursor)
            if recorded_hashes(cursor):
                assert_ledger_entry(cursor, migration_hash)
                assert_schema_version_probe_only(cursor)
                run_probe_as_runtime(cursor)
                conn.rollback()
                no_op = True
            else:
                cursor.execute(strip_transaction_control(migration_bytes.decode("utf-8")))
                assert_schema_version_probe_only(cursor)
                run_probe_as_runtime(cursor)
                cursor.execute("SET LOCAL ROLE platform_admin")
                cursor.execute(
                    """INSERT INTO public.schema_version
                           (version_label, applies_to, ddl_uri, ddl_hash, migration_id,
                            status, notes, created_by)
                       VALUES (%s, %s, %s, %s, %s, 'active', %s, current_user)""",
                    (
                        MIGRATION_LABEL,
                        APPLIES_TO,
                        DDL_URI,
                        migration_hash,
                        MIGRATION_ID,
                        "Applied by scripts/apply_0038_live.py under an advisory lock; "
                        "recovery is forward-fix after commit.",
                    ),
                )
                assert_ledger_entry(cursor, migration_hash)
                conn.commit()

    with psycopg.connect(dsn, password=password, connect_timeout=10) as conn:
        with conn.cursor() as cursor:
            assert_platform_bootstrap(cursor)
            assert_public_is_denied(cursor)
            assert_runtime_connect_only(cursor)
            assert_schema_version_probe_only(cursor)
            run_probe_as_runtime(cursor)
            assert_ledger_entry(cursor, migration_hash)

    disposition = "NO-OP" if no_op else "APPLIED"
    print(f"{disposition}: migration 0038 independently verified; sha256={migration_hash.hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
