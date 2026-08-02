"""Create a disposable, schema-only clone of the live database for ingest testing.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

Owner directive 2026-08-02: "to test ingestion you could always just make a clone of
a database, mark it as [test] or just wipe it after it gets to the database, just so
we can make sure it's properly adjusted, hits the database correctly."

Structure only - no rows. The point is to prove a load LANDS correctly, and a test
that starts from an empty schema proves more than one that starts from a pile of
earlier test data.

CREATE DATABASE ... TEMPLATE is deliberately not used: it requires zero active
connections to the template, which never holds on a live box.

The database name is prefixed `ai_test_` so it is obviously disposable. It lives on
the data box but is NOT part of the ovh-data -> ovh-files migration: drop it, do not
move it.

Credentials come from the environment or the repo .env and are handed to pg_dump /
psql through the subprocess environment - never on a command line, never printed.

usage:
    uv run python scripts/make_test_db.py --host <ip>            # create/refresh
    uv run python scripts/make_test_db.py --host <ip> --drop     # tear down
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess

from sqlalchemy import create_engine, text

REPO = pathlib.Path(__file__).resolve().parents[1]
PGBIN = pathlib.Path(r"C:\Program Files\PostgreSQL\18\bin")
TEST_DB = "ai_test_ingest"


def settings(host: str | None) -> dict[str, str]:
    env: dict[str, str] = {}
    dotenv = REPO / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"^\s*([A-Z_]+)\s*=\s*(.+?)\s*$", line)
            if m:
                env[m.group(1)] = m.group(2).strip("\"'")
    for k in ("DB_USER", "DB_PASS", "DB_DATABASE", "DB_HOST", "DB_PORT"):
        if k in os.environ:
            env[k] = os.environ[k]
    if host:
        env["DB_HOST"] = host
    env.setdefault("DB_PORT", "5432")
    if not env.get("DB_HOST") or env["DB_HOST"] == "agentos-db":
        raise SystemExit("pass --host: .env holds the compose-internal name agentos-db")
    return env


def url(env: dict[str, str], db: str) -> str:
    return (f"postgresql+psycopg://{env['DB_USER']}:{env['DB_PASS']}"
            f"@{env['DB_HOST']}:{env['DB_PORT']}/{db}")


def run(cmd: list[str], env: dict[str, str], stdin=None, stdout=None) -> None:
    """Run a PG client binary with the password supplied via the environment."""
    child = dict(os.environ)
    child["PGPASSWORD"] = env["DB_PASS"]
    proc = subprocess.run(cmd, env=child, stdin=stdin, stdout=stdout,
                          stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        # never echo the command: it carries host/user, and a future edit could
        # carry more
        raise SystemExit(f"{pathlib.Path(cmd[0]).stem} failed:\n{proc.stderr[-1500:]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default=None)
    ap.add_argument("--drop", action="store_true", help="tear the test database down")
    args = ap.parse_args()
    env = settings(args.host)

    admin = create_engine(url(env, "postgres"), isolation_level="AUTOCOMMIT",
                          connect_args={"connect_timeout": 60})

    with admin.connect() as c:
        exists = c.execute(text("SELECT 1 FROM pg_database WHERE datname = :d"),
                           {"d": TEST_DB}).scalar()
        if exists:
            # kill stragglers so DROP cannot hang on an idle session
            c.execute(text("""
                SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                 WHERE datname = :d AND pid <> pg_backend_pid()"""), {"d": TEST_DB})
            c.execute(text(f'DROP DATABASE "{TEST_DB}"'))
            print(f"  dropped {TEST_DB}")
        if args.drop:
            if not exists:
                print(f"  {TEST_DB} did not exist")
            return
        c.execute(text(f'CREATE DATABASE "{TEST_DB}"'))
        print(f"  created {TEST_DB}")

    dump = REPO / ".test-db-schema.sql"
    print("  dumping live schema (structure only, no rows)...")
    with dump.open("w", encoding="utf-8") as fh:
        run([str(PGBIN / "pg_dump.exe"),
             "--schema-only", "--no-owner", "--no-privileges",
             "-h", env["DB_HOST"], "-p", env["DB_PORT"], "-U", env["DB_USER"],
             "-d", env["DB_DATABASE"]], env, stdout=fh)
    print(f"  schema dump: {dump.stat().st_size / 1024:,.0f} KiB")

    print("  restoring into the test database...")
    with dump.open("r", encoding="utf-8") as fh:
        run([str(PGBIN / "psql.exe"), "-q", "-v", "ON_ERROR_STOP=0",
             "-h", env["DB_HOST"], "-p", env["DB_PORT"], "-U", env["DB_USER"],
             "-d", TEST_DB], env, stdin=fh, stdout=subprocess.DEVNULL)
    dump.unlink()

    test = create_engine(url(env, TEST_DB), connect_args={"connect_timeout": 60})
    with test.connect() as c:
        rows = c.execute(text("""
            SELECT table_schema, count(*) FILTER (WHERE table_type = 'BASE TABLE'),
                   count(*) FILTER (WHERE table_type = 'VIEW')
              FROM information_schema.tables
             WHERE table_schema IN ('evidence','working','reference','analysis','ops')
             GROUP BY 1 ORDER BY 1""")).all()
        # Count for real. pg_stat_user_tables.n_live_tup is an ESTIMATE and on a
        # freshly restored database it reports leftover garbage until ANALYZE runs —
        # the first run of this script claimed 8,500 rows in a schema-only clone
        # that actually contained none.
        total = c.execute(text("""
            SELECT COALESCE(sum(cnt), 0) FROM (
              SELECT (xpath('/row/c/text()',
                       query_to_xml('SELECT count(*) AS c FROM '
                         || quote_ident(table_schema) || '.' || quote_ident(table_name),
                         false, true, '')))[1]::text::bigint AS cnt
                FROM information_schema.tables
               WHERE table_schema IN ('evidence','working','reference','analysis','ops')
                 AND table_type = 'BASE TABLE'
            ) t""")).scalar()

    print()
    print(f"  {TEST_DB} ready:")
    for sch, tables, views in rows:
        print(f"    {sch:12s} {tables:>4} tables  {views:>3} views")
    print(f"    rows carried over: {total}  (expected 0 - structure only)")
    print()
    print(f"  point an ingest at it with:  DB_DATABASE={TEST_DB}")
    print("  tear down with:              --drop")


if __name__ == "__main__":
    main()
