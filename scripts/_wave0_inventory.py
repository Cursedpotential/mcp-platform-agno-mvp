"""Wave 0 read-only live inventory baseline (Agno-MCP-Platform).

Reads DB creds from ~/.secrets/Agno-MCP-Platform.env via a tolerant regex
(NEVER sources the file; NEVER prints the values). Overrides DB_HOST to the
tailnet IP 100.91.190.107 (the env file's host only resolves inside the
compose network). Strictly read-only: SELECTs only, no writes, no DDL.

Byline: Claude Code · glm-5.2:cloud · 2026-08-14
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import psycopg

ENV_FILE = Path.home() / ".secrets" / "Agno-MCP-Platform.env"
TAILNET_HOST = "100.91.190.107"

# Schemas of interest (per ADR-0045/0052/0053 and the evidence spine)
WATCH_SCHEMAS = ("evidence", "analysis", "working", "ai", "ops", "context")


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


def main() -> int:
    env = parse_env(ENV_FILE)
    host = TAILNET_HOST  # override: env file host won't resolve from desktop
    port = env.get("DB_PORT", "5432")
    user = env.get("DB_USER") or env.get("POSTGRES_USER", "")
    pwd = env.get("DB_PASS") or env.get("POSTGRES_PASSWORD", "")
    dbname = env.get("DB_DATABASE") or env.get("POSTGRES_DB", "")
    if not (user and pwd and dbname):
        print("ERROR: could not resolve DB_USER/DB_PASS/DB_DATABASE from env file (names parsed, values hidden).")
        return 2

    dsn = f"host={host} port={port} dbname={dbname} user={user}"
    # password passed via connect arg, never in the dsn string/log
    with psycopg.connect(dsn, password=pwd, connect_timeout=10) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            print("=" * 70)
            print(f"WAVE 0 LIVE INVENTORY — {host}:{port} db={dbname}")
            print("(read-only; credentials never printed)")
            print("=" * 70)

            cur.execute("SELECT version()")
            print("\n[server]", cur.fetchone()[0])

            # All non-system schemas
            cur.execute(
                """SELECT schema_name FROM information_schema.schemata
                   WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast')
                     AND schema_name NOT LIKE 'pg_toast_%' AND schema_name NOT LIKE 'pg_temp_%'
                   ORDER BY schema_name"""
            )
            schemas = [r[0] for r in cur.fetchall()]
            print("\n[schemas]", ", ".join(schemas))

            # Extensions
            cur.execute("SELECT extname, extversion FROM pg_extension ORDER BY extname")
            exts = cur.fetchall()
            print("\n[extensions]", ", ".join(f"{n}={v}" for n, v in exts))

            # Per watched schema: table list + row counts
            print("\n[table inventory]")
            for sch in schemas:
                if sch not in WATCH_SCHEMAS:
                    continue
                cur.execute(
                    """SELECT table_name FROM information_schema.tables
                       WHERE table_schema=%s AND table_type='BASE TABLE'
                       ORDER BY table_name""",
                    (sch,),
                )
                tables = [r[0] for r in cur.fetchall()]
                if not tables:
                    continue
                print(f"\n  schema={sch}  ({len(tables)} base tables)")
                for t in tables:
                    cur.execute(f'SELECT COUNT(*) FROM "{sch}"."{t}"')
                    n = cur.fetchone()[0]
                    print(f"    {sch}.{t:42s} {n:>10,}")

            # Horizon clock probe: does working.horizon_visible exist + what it filters on
            print("\n[horizon clock probe]")
            try:
                cur.execute(
                    """SELECT pg_get_functiondef(oid) FROM pg_proc
                       WHERE proname='horizon_visible' AND pronamespace=(
                         SELECT oid FROM pg_namespace WHERE nspname='working')"""
                )
                row = cur.fetchone()
                if row:
                    print("  working.horizon_visible EXISTS. Definition (first 40 lines):")
                    for line in (row[0] or "").splitlines()[:40]:
                        print("    " + line)
                else:
                    print("  working.horizon_visible: NOT FOUND")
            except Exception as e:
                print(f"  horizon_visible probe error: {e}")

            # CDC / outbox (sql/0024 per ADR-0052/0053)
            print("\n[CDC / outbox probe]")
            cur.execute(
                """SELECT table_name FROM information_schema.tables
                   WHERE table_schema='working' AND table_type='BASE TABLE'
                     AND (table_name LIKE '%outbox%' OR table_name LIKE '%cursor%'
                          OR table_name LIKE '%dead_letter%' OR table_name LIKE '%sync%')
                   ORDER BY table_name"""
            )
            cdc = [r[0] for r in cur.fetchall()]
            print("  candidate CDC tables:", cdc or "(none found)")
            for t in cdc:
                cur.execute(f'SELECT COUNT(*) FROM "working"."{t}"')
                print(f"    working.{t}: {cur.fetchone()[0]:,}")

            # Candidate tables (ADR-0052 Q6)
            print("\n[candidate-table probe (ADR-0052 Q6)]")
            for cand in ("entity_candidate", "claim_candidate"):
                cur.execute(
                    """SELECT 1 FROM information_schema.tables
                       WHERE table_schema='working' AND table_name=%s""",
                    (cand,),
                )
                exists = cur.fetchone() is not None
                if exists:
                    cur.execute(f'SELECT COUNT(*) FROM "working"."{cand}"')
                    print(f"  working.{cand}: EXISTS, {cur.fetchone()[0]:,} rows")
                else:
                    print(f"  working.{cand}: NOT BUILT (expected — ADR-0052 unbuilt)")

            # realization_event / walk_ledger (ADR-0045 §A/§B — unbuilt expected)
            print("\n[ADR-0045 build probe (expect unbuilt)]")
            for t in ("realization_event", "walk_ledger"):
                cur.execute(
                    """SELECT 1 FROM information_schema.tables
                       WHERE table_schema='working' AND table_name=%s""",
                    (t,),
                )
                print(f"  working.{t}:", "EXISTS" if cur.fetchone() else "NOT BUILT (expected — Wave 1)")

            print("\n" + "=" * 70)
            print("read-only inventory complete")
            print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())