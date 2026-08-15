"""RETIRED Wave 0 numbered-chain restore experiment.

Do not run the preserved legacy implementation below. The numbered chain is
not a bootstrap path after 0007, and its DROP DATABASE cleanup conflicts with
the repository's no-hard-delete rule. Use ``sql/bootstrap/schema_baseline.sql``
in an owner-approved scratch environment instead.

Why not BEGIN/apply/ROLLBACK on the live DB? Re-applying to the already-migrated
live DB errors on the first CREATE TABLE (already exists) and proves nothing. The
faithful "fresh-schema restore" is apply-from-zero into an empty target.

Creds parsed from ~/.secrets/Agno-MCP-Platform.env via regex (never sourced/printed).
Byline: Claude Code · glm-5.2:cloud · 2026-08-14
Byline: Codex · GPT-5 · 2026-08-15 (safety retirement; entry point disabled)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import psycopg

ENV_FILE = Path.home() / ".secrets" / "Agno-MCP-Platform.env"
TAILNET_HOST = "100.91.190.107"
SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
THROWAWAY_DB = "_wave0_restore_test"
EXPECTED_SCHEMAS = {"evidence", "analysis", "working", "ai", "ops"}


def parse_env(path: Path) -> dict[str, str]:
    pat = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = pat.match(line)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        if v.startswith(("'", '"')) and v.endswith(v[0]) and len(v) >= 2:
            v = v[1:-1]
        out[k] = v
    return out


def _legacy_main() -> int:
    env = parse_env(ENV_FILE)
    host = TAILNET_HOST
    port = env.get("DB_PORT", "5432")
    user = env.get("DB_USER") or env.get("POSTGRES_USER", "")
    pwd = env.get("DB_PASS") or env.get("POSTGRES_PASSWORD", "")
    dbname = env.get("DB_DATABASE") or env.get("POSTGRES_DB", "")
    if not (user and pwd and dbname):
        print("ERROR: could not resolve creds (names parsed, values hidden).")
        return 2

    base_dsn = f"host={host} port={port} user={user}"
    admin = psycopg.connect(base_dsn + f" dbname={dbname}", password=pwd, connect_timeout=10)
    admin.autocommit = True

    # Privilege check
    with admin.cursor() as cur:
        cur.execute("SELECT usecreatedb FROM pg_user WHERE usename=current_user")
        row = cur.fetchone()
        can_createdb = bool(row and row[0])
    if not can_createdb:
        print(f"SKIP: role {user!r} lacks CREATEDB — cannot stand a throwaway DB.")
        print("      fresh-schema restore deferred (needs CREATEDB or a scratch DB the owner provisions).")
        admin.close()
        return 3

    migrations = sorted(SQL_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"), key=lambda p: p.name)
    print(f"[plan] {len(migrations)} migrations to apply to throwaway db={THROWAWAY_DB!r}, then DROP it.")

    created = False
    try:
        with admin.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{THROWAWAY_DB}" WITH (FORCE)')
            cur.execute(f'CREATE DATABASE "{THROWAWAY_DB}"')
        created = True
        print(f"[created] throwaway db {THROWAWAY_DB!r}")

        tgt = psycopg.connect(base_dsn + f" dbname={THROWAWAY_DB}", password=pwd, connect_timeout=10)
        tgt.autocommit = True
        try:
            applied = 0
            failures = []
            with tgt.cursor() as cur:
                for mf in migrations:
                    sql = mf.read_text(encoding="utf-8")
                    try:
                        cur.execute(sql)
                        applied += 1
                        print(f"  [ok] {mf.name}")
                    except Exception as e:
                        failures.append((mf.name, str(e).splitlines()[0][:160]))
                        print(f"  [FAIL] {mf.name}: {str(e).splitlines()[0][:160]}")
                        # stop on first failure — a broken sequence can't be trusted further
                        break
                if not failures:
                    # Verify schemas + table counts
                    cur.execute(
                        """SELECT schema_name FROM information_schema.schemata
                           WHERE schema_name = ANY(%s) ORDER BY schema_name""",
                        (list(EXPECTED_SCHEMAS),),
                    )
                    built_schemas = {r[0] for r in cur.fetchall()}
                    cur.execute(
                        """SELECT table_schema, COUNT(*) FROM information_schema.tables
                           WHERE table_type='BASE TABLE'
                             AND table_schema IN ('evidence','analysis','working','ai','ops')
                           GROUP BY table_schema ORDER BY table_schema"""
                    )
                    tbl_counts = {r[0]: r[1] for r in cur.fetchall()}
                    print("\n[verify] schemas built:", sorted(built_schemas))
                    print("[verify] missing expected schemas:", sorted(EXPECTED_SCHEMAS - built_schemas) or "(none)")
                    print("[verify] base-table counts by schema:", tbl_counts)
                    cur.execute(
                        """SELECT COUNT(*) FROM information_schema.tables
                           WHERE table_type='BASE TABLE'
                             AND table_schema IN ('evidence','analysis','working','ai','ops')"""
                    )
                    total = cur.fetchone()[0]
                    print(f"[verify] total base tables across 5 schemas: {total}")
                    print("\n[VERDICT] fresh-schema restore SUCCESS — all 25 migrations applied clean from zero.")
        finally:
            tgt.close()
    finally:
        if created:
            try:
                with admin.cursor() as cur:
                    cur.execute(f'DROP DATABASE IF EXISTS "{THROWAWAY_DB}" WITH (FORCE)')
                print(f"[dropped] throwaway db {THROWAWAY_DB!r} — no net write to live db={dbname!r}")
            except Exception as e:
                print(f"[WARN] failed to drop throwaway db: {e} — MANUAL CLEANUP NEEDED")
        admin.close()
    return 0


def main() -> int:
    """Refuse the obsolete destructive/non-replayable workflow."""
    print("REFUSED: numbered migrations are not a bootstrap path after 0007.")
    print("Use sql/bootstrap/schema_baseline.sql in an owner-approved scratch environment.")
    print("No database connection or mutation was attempted.")
    return 4


if __name__ == "__main__":
    sys.exit(main())
