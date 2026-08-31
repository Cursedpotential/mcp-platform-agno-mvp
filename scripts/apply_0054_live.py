"""Apply and ledger migration 0054 under one transaction and advisory lock.

Byline: Codex · GPT-5.6-Sol · 2026-08-30.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import psycopg

from validate_0054_live import (
    APPLIES_TO,
    DDL_URI,
    DEFAULT_SERVICE,
    MIGRATION,
    MIGRATION_ID,
    MIGRATION_LABEL,
    TARGET_DATABASE,
    assert_cross_matter_rejected,
    assert_constraint_identity,
    assert_expand_prestate,
    assert_ledger_entry,
    assert_prerequisite_ledger,
    assert_schema,
    backfill_source_version_scope,
    connection_string,
    migration_hash,
    import_registry,
    load_registry_manifest,
    strip_transaction_control,
    validate_scope_constraints,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="apply migration 0054 to platform")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--database", default=TARGET_DATABASE)
    parser.add_argument("--registry-import", type=Path)
    args = parser.parse_args()
    if not args.apply:
        parser.error("refusing to run without explicit --apply")
    dsn = connection_string(args.service, args.database)
    ddl_hash = migration_hash(MIGRATION)
    with psycopg.connect(dsn, connect_timeout=10) as conn:
        conn.autocommit = False
        cursor = conn.cursor()
        cursor.execute("SET LOCAL lock_timeout='5s'")
        cursor.execute("SET LOCAL statement_timeout='30s'")
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('apply-0054-platform-case-registry'))")
        assert_prerequisite_ledger(cursor)
        cursor.execute(
            "SELECT ddl_hash FROM public.schema_version WHERE migration_id=%s AND status='active'",
            (MIGRATION_ID,),
        )
        existing = cursor.fetchall()
        if existing:
            assert_ledger_entry(cursor, ddl_hash)
            assert_schema(cursor)
            if args.registry_import is not None:
                manifest, manifest_hash = load_registry_manifest(args.registry_import)
                if import_registry(cursor, manifest, manifest_hash) != "NO-OP":
                    raise RuntimeError("active 0054 ledger exists without its exact immutable import receipt")
            conn.rollback()
            print(f"NO-OP: migration 0054 independently verified; sha256={ddl_hash.hex()}; target=platform")
            return 0
        else:
            if args.registry_import is None:
                raise RuntimeError("registry adoption manifest is required for first application of migration 0054")
            assert_expand_prestate(cursor)
            cursor.execute(strip_transaction_control(MIGRATION.read_text(encoding="utf-8")))
            assert_constraint_identity(cursor, validated=False)
        import_disposition = "NO-IMPORT"
        if args.registry_import is not None:
            manifest, manifest_hash = load_registry_manifest(args.registry_import)
            import_disposition = import_registry(cursor, manifest, manifest_hash)
        backfill_source_version_scope(cursor)
        validate_scope_constraints(cursor)
        assert_schema(cursor)
        assert_cross_matter_rejected(cursor)
        if migration_hash(MIGRATION) != ddl_hash:
            raise RuntimeError("migration 0054 changed during apply")
        cursor.execute("SET LOCAL ROLE platform_admin")
        cursor.execute(
            """INSERT INTO public.schema_version
               (version_label,applies_to,ddl_uri,ddl_hash,migration_id,status,notes,created_by)
               VALUES(%s,%s,%s,%s,%s,'active',%s,current_user)""",
            (
                MIGRATION_LABEL,
                APPLIES_TO,
                DDL_URI,
                ddl_hash,
                MIGRATION_ID,
                "Ledgered last after registry import/backfill/constraint validation and admission proof.",
            ),
        )
        assert_ledger_entry(cursor, ddl_hash)
        conn.commit()
    with psycopg.connect(dsn, connect_timeout=10, autocommit=True) as conn:
        cursor = conn.cursor()
        assert_schema(cursor)
        assert_ledger_entry(cursor, ddl_hash)
    print(
        f"APPLIED/{import_disposition}: migration 0054 independently verified; sha256={ddl_hash.hex()}; target=platform"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
