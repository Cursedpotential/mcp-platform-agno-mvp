"""Wave 1.4 — READ-ONLY recon of the live tailnet PG role/grant state.

Zero write. Gathers the facts needed to design the default-deny grants migration:
  * the app's connection role + whether it is a SUPERUSER (decides whether DB grants
    can possibly restrain the app at all),
  * every role on the instance,
  * table owners + existing privileges on the canonical + pass tables (applied in a
    rollback txn so 0026/0027/0028 objects exist for the query),
  * whether CREATE ROLE / GRANT are permitted on this (self-hosted) PG, tested by
    issuing then ROLLING BACK (DDL is transactional in Postgres).

Creds regex-parsed from ~/.secrets/Agno-MCP-Platform.env (never sourced/printed).
Byline: Claude Code . glm-5.2:cloud . 2026-08-14
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import create_engine, text

ENV_FILE = Path.home() / ".secrets" / "Agno-MCP-Platform.env"
TAILNET_HOST = "100.91.190.107"
SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
MIGRATIONS = [
    SQL_DIR / "0026_realization_event.sql",
    SQL_DIR / "0027_walk_ledger.sql",
]


def parse_env(path: Path) -> dict[str, str]:
    pat = re.compile(r"^\s*([A-Za-z_][A-Za-z00-9_]*)\s*=\s*(.+?)\s*$")
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


def strip_txn_control(sql: str) -> str:
    sql = re.sub(r"^\s*BEGIN\s*;", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"^\s*COMMIT\s*;", "", sql, flags=re.MULTILINE)
    return sql


def show(title: str, rows: list) -> None:
    print(f"\n--- {title} ---")
    if not rows:
        print("  (none)")
        return
    for r in rows:
        print("  " + " | ".join(str(v) for v in r))


def main() -> int:
    src = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.commit\s*\(", src):
        print("ERROR: F8 violation — recon script commits; refusing to run.")
        return 2

    env = parse_env(ENV_FILE)
    port = env.get("DB_PORT", "5432")
    user = env.get("DB_USER") or env.get("POSTGRES_USER", "")
    pwd = env.get("DB_PASS") or env.get("POSTGRES_PASSWORD", "")
    dbname = env.get("DB_DATABASE") or env.get("POSTGRES_DB", "")
    if not (user and pwd and dbname):
        print("ERROR: could not resolve creds (names parsed, values hidden).")
        return 2

    url = f"postgresql+psycopg://{user}:{quote(pwd, safe='')}@{TAILNET_HOST}:{port}/{dbname}"
    ddl = "\n".join(strip_txn_control(p.read_text(encoding="utf-8")) for p in MIGRATIONS)

    engine = create_engine(url, pool_pre_ping=True)
    try:
        conn = engine.connect()
        trans = conn.begin()
        try:
            conn.exec_driver_sql(ddl)  # 0026 + 0027 so pass tables exist for the recon

            print("=== W1.4 GRANTS RECON (live, rollback) ===")
            print("(connecting role name parsed from env, value hidden)")

            show("current user + superuser flag", conn.execute(text(
                "SELECT current_user, current_database(), "
                "(SELECT rolsuper FROM pg_roles WHERE rolname=current_user) AS is_super, "
                "(SELECT rolcreaterole FROM pg_roles WHERE rolname=current_user) AS can_create_role"
            )).fetchall())

            show("all roles (name, super, login, createrole, createdb)",
                 conn.execute(text(
                     "SELECT rolname, rolsuper, rolcanlogin, rolcreaterole, rolcreatedb "
                     "FROM pg_roles ORDER BY rolname"
                 )).fetchall())

            show("schema ownership (working, ops, public)",
                 conn.execute(text(
                     "SELECT n.nspname, r.rolname "
                     "FROM pg_namespace n JOIN pg_roles r ON n.nspowner=r.oid "
                     "WHERE n.nspname IN ('working','ops','public','ai') ORDER BY n.nspname"
                 )).fetchall())

            show("canonical + pass table owners",
                 conn.execute(text(
                     "SELECT schemaname, tablename, tableowner "
                     "FROM pg_tables WHERE schemaname IN ('working','ops') "
                     "ORDER BY schemaname, tablename"
                 )).fetchall())

            show("default privileges on pass tables (walk_run, walk_step, walk_step_retrieval, record_visible_from)",
                 conn.execute(text(
                     "SELECT grantee, privilege_type, is_grantable "
                     "FROM information_schema.table_privileges "
                     "WHERE table_schema='working' "
                     "AND table_name IN ('walk_run','walk_step','walk_step_retrieval',"
                     "'record_visible_from','realization_event','realization_event_record','normalized_record') "
                     "ORDER BY table_name, grantee, privilege_type"
                 )).fetchall())

            show("canonical table column grants (working.normalized_record)",
                 conn.execute(text(
                     "SELECT grantee, privilege_type FROM information_schema.column_privileges "
                     "WHERE table_schema='working' AND table_name='normalized_record' "
                     "ORDER BY grantee, privilege_type"
                 )).fetchall())

            # Can we CREATE ROLE on this host? DDL is transactional -> safe to test + rollback.
            test_role = "w14_recon_probe"
            try:
                conn.execute(text(f"CREATE ROLE {test_role}"))
                print("\n--- CREATE ROLE probe: SUCCESS (role created; will rollback) ---")
                can_create_role = True
            except Exception as e:
                print(f"\n--- CREATE ROLE probe: FAILED -> {type(e).__name__}: {str(e)[:120]} ---")
                can_create_role = False

            # Can we GRANT on a pass table? (requires ownership or grant option)
            try:
                conn.execute(text(f"GRANT SELECT ON working.walk_run TO {test_role}"))
                print("--- GRANT SELECT probe: SUCCESS (will rollback) ---")
                can_grant = True
            except Exception as e:
                print(f"--- GRANT SELECT probe: FAILED -> {type(e).__name__}: {str(e)[:120]} ---")
                can_grant = can_create_role  # if role didn't exist, grant fails for that reason

            print(f"\n[probe summary] can_create_role={can_create_role}  can_grant={can_grant}")
        finally:
            trans.rollback()
            conn.close()
        print("\n[rollback] recon transaction rolled back — zero net write.")
    finally:
        engine.dispose()

    print("\n[VERDICT] recon complete — see above for role/grant state.")
    return 0


if __name__ == "__main__":
    sys.exit(main())