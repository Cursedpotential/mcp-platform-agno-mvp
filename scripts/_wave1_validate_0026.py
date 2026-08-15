"""Wave 1.1 — validate sql/0026_realization_event.sql against the LIVE tailnet PG.

Applies the migration inside a transaction, runs adversarial clock assertions,
then ROLLBACKs. ZERO NET WRITE to the live `ai` DB (PG DDL is transactional;
test rows are inserted and rolled back too). This is the only faithful validation
path: a throwaway DB can't apply 0026 in isolation because migrations are not
from-zero (0008 fails without the bootstrapped base schema — Wave 0 finding).

PRE-MORTEM F8 (2026-08-14) — CRITICAL TRANSACTIONAL GUARDS:
  * The migration file carries its own `BEGIN;`/`COMMIT;`. With autocommit=False
    that inner `COMMIT;` would COMMIT THE DDL TO THE LIVE DB and leave only the
    test rows for the finally-rollback — i.e. a *successful* run would APPLY the
    migration for real. We therefore STRIP the migration's transaction-control
    statements before executing, so the DDL runs inside OUR rollback transaction.
  * assert conn.autocommit is False before any execute; a second defensive
    rollback after the cursor block; and NO transaction-commit call anywhere in
    this file (a source-grep guard at the top of main() enforces it).

Scope (ADR-0045 §A + §A.4; pre-mortem F1 deferral):
  1. Objects created: realization_event, realization_event_record, visible_from().
  2. horizon_visible / vw_spine_horizon are NOT repointed in W1.1 (deferred to
     W1.3 per F1) — assert they are UNCHANGED (still on knowledge_time) so we
     know the migration did not silently introduce the slow per-row path.
  3. Degenerate: a record with NO realization event -> visible_from = occurred_at.
  4. Proposed (unapproved) event -> visible_from UNCHANGED (fail-closed).
  5. Approved event with realized_at > occurred_at -> visible_from = realized_at.
  6. Regression: the UNTOUCHED horizon_visible still denies at an early horizon,
     allows at a late one; NULL horizon (hindsight) allows; hindsight tier excluded.

Creds parsed from ~/.secrets/Agno-MCP-Platform.env via regex (never sourced/printed).
Byline: Claude Code . glm-5.2:cloud . 2026-08-14
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import psycopg

ENV_FILE = Path.home() / ".secrets" / "Agno-MCP-Platform.env"
TAILNET_HOST = "100.91.190.107"
MIGRATION = Path(__file__).resolve().parent.parent / "sql" / "0026_realization_event.sql"


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


def check(label: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")
    return cond


def strip_txn_control(sql: str) -> str:
    """F8: remove the migration's own BEGIN;/COMMIT; so the DDL runs inside our
    rollback transaction. Matches only line-leading transaction control so the
    `BEGIN` inside a `DO $$ ... $$` block (which is `BEGIN<newline>`, not
    `BEGIN;`) is untouched."""
    sql = re.sub(r"^\s*BEGIN\s*;", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"^\s*COMMIT\s*;", "", sql, flags=re.MULTILINE)
    return sql


def main() -> int:
    # F8: gate check — this file must NEVER commit the connection. A validation
    # script that commits writes to prod. The guard matches an actual call,
    # not the word in prose.
    src = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"conn\.commit\s*\(", src):
        print("ERROR: F8 violation — validation script commits the connection; refusing to run.")
        return 2

    env = parse_env(ENV_FILE)
    port = env.get("DB_PORT", "5432")
    user = env.get("DB_USER") or env.get("POSTGRES_USER", "")
    pwd = env.get("DB_PASS") or env.get("POSTGRES_PASSWORD", "")
    dbname = env.get("DB_DATABASE") or env.get("POSTGRES_DB", "")
    if not (user and pwd and dbname):
        print("ERROR: could not resolve creds (names parsed, values hidden).")
        return 2

    dsn = f"host={TAILNET_HOST} port={port} user={user} dbname={dbname}"
    sql = strip_txn_control(MIGRATION.read_text(encoding="utf-8"))

    all_ok = True
    with psycopg.connect(dsn, password=pwd, connect_timeout=10) as conn:
        conn.autocommit = False
        # F8: prove the rollback guard is armed before any execute.
        assert conn.autocommit is False, "F8 guard: autocommit must be False"
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(sql)

                    # 1. objects exist
                    cur.execute(
                        "SELECT to_regclass('working.realization_event'),"
                        " to_regclass('working.realization_event_record')"
                    )
                    t1, t2 = cur.fetchone()
                    all_ok &= check("realization_event table created", t1 == "working.realization_event")
                    all_ok &= check("realization_event_record table created", t2 == "working.realization_event_record")

                    cur.execute(
                        "SELECT 1 FROM pg_proc WHERE proname='visible_from' "
                        "AND pronamespace='working'::regnamespace"
                    )
                    all_ok &= check("visible_from() function created", cur.fetchone() is not None)

                    # 2. F1 deferral: the live predicate + view must be UNCHANGED
                    #    (still on knowledge_time) — proves W1.1 did not silently
                    #    introduce the slow per-row visible_from(r.id) path.
                    cur.execute(
                        "SELECT pg_get_functiondef('working.horizon_visible(text,timestamptz,text,text,text,timestamptz,text)'::regprocedure)"
                    )
                    fdef = cur.fetchone()[0]
                    all_ok &= check(
                        "horizon_visible UNCHANGED (repoint deferred to W1.3)",
                        "row_knowledge_time" in fdef and "row_visible_from" not in fdef,
                    )

                    cur.execute("SELECT pg_get_viewdef('working.vw_spine_horizon'::regclass, true)")
                    vdef = cur.fetchone()[0]
                    all_ok &= check(
                        "vw_spine_horizon UNCHANGED (no visible_from(r.id) slow path)",
                        "visible_from(r.id)" not in vdef,
                    )

                    # 3-5. behavioral clock assertions on a REAL normalized_record row.
                    cur.execute(
                        "SELECT id, occurred_at FROM working.normalized_record "
                        "WHERE occurred_at IS NOT NULL ORDER BY occurred_at LIMIT 1"
                    )
                    row = cur.fetchone()
                    if row is None:
                        print("  [SKIP] no normalized_record with occurred_at to test against.")
                        all_ok = False
                    else:
                        rid, occurred = row
                        occ_iso = occurred.isoformat()

                        # degenerate: no events -> occurred_at
                        cur.execute("SELECT working.visible_from(%s)", (rid,))
                        vf0 = cur.fetchone()[0]
                        all_ok &= check(
                            "degenerate visible_from == occurred_at (no events)",
                            vf0 == occurred,
                            f"vf={vf0.isoformat() if vf0 else None} occ={occ_iso}",
                        )

                        # insert a PROPOSED (unapproved) realization event + link
                        cur.execute(
                            "INSERT INTO working.realization_event(case_id, kind, realized_at,"
                            " proposer, approval_state) VALUES ('primary','manual',"
                            " now() + interval '1 year','algorithm','proposed') RETURNING id"
                        )
                        evid = cur.fetchone()[0]
                        cur.execute(
                            "INSERT INTO working.realization_event_record(realization_event_id,"
                            " normalized_record_id) VALUES (%s,%s)",
                            (evid, rid),
                        )
                        cur.execute("SELECT working.visible_from(%s)", (rid,))
                        vf1 = cur.fetchone()[0]
                        all_ok &= check(
                            "PROPOSED event does NOT move visible_from (fail-closed)",
                            vf1 == occurred,
                            f"vf={vf1.isoformat() if vf1 else None} (expected {occ_iso})",
                        )

                        # approve it (with a realized_at strictly after occurred_at)
                        later = occurred.replace(year=occurred.year + 1)
                        cur.execute(
                            "UPDATE working.realization_event SET approval_state='approved',"
                            " approved_at=now(), approved_by='owner', realized_at=%s WHERE id=%s",
                            (later, evid),
                        )
                        cur.execute("SELECT working.visible_from(%s)", (rid,))
                        vf2 = cur.fetchone()[0]
                        all_ok &= check(
                            "APPROVED event moves visible_from to realized_at",
                            vf2 == later,
                            f"vf={vf2.isoformat() if vf2 else None} expected {later.isoformat()}",
                        )

                        # 6. regression: the UNTOUCHED horizon_visible still behaves
                        # (the predicate repoint is deferred to W1.3; this confirms
                        # no behavior regression from leaving it on knowledge_time).
                        early = occurred.replace(year=occurred.year - 1)
                        cur.execute(
                            "SELECT working.horizon_visible('primary',%s,'contemporaneous',"
                            "'owner','primary',%s,'owner')",
                            (vf2, early),
                        )
                        all_ok &= check("horizon_visible DENIES at early horizon", cur.fetchone()[0] is False)
                        cur.execute(
                            "SELECT working.horizon_visible('primary',%s,'contemporaneous',"
                            "'owner','primary',%s,'owner')",
                            (vf2, later),
                        )
                        all_ok &= check("horizon_visible ALLOWS at late horizon", cur.fetchone()[0] is True)
                        cur.execute(
                            "SELECT working.horizon_visible('primary',%s,'contemporaneous',"
                            "'owner','primary',NULL,'owner')",
                            (vf2,),
                        )
                        all_ok &= check("NULL horizon (hindsight) allows", cur.fetchone()[0] is True)

                        # hindsight-tagged disclosure is always excluded for the ignorant path
                        cur.execute(
                            "SELECT working.horizon_visible('primary',%s,'hindsight',"
                            "'owner','primary',%s,'owner')",
                            (vf2, later),
                        )
                        all_ok &= check("hindsight tier excluded even within horizon", cur.fetchone()[0] is False)

                finally:
                    # ALWAYS rollback — zero net write to the live DB.
                    conn.rollback()
            # F8: second defensive rollback after the cursor block closes.
            conn.rollback()
            print("\n[rollback] transaction rolled back — zero net write to live db.")
        except Exception:
            # F8: rollback on ANY exception before re-raising.
            conn.rollback()
            print("\n[rollback] rolled back after exception — zero net write.")
            raise

    print("\n[VERDICT]", "PASS — sql/0026 faithful to ADR-0045 §A/§A.4 (F1-deferred scope)" if all_ok
          else "FAIL — see above; migration did NOT validate.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())