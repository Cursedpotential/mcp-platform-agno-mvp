"""Wave 1.4 — validate the default-deny pass-grants migration against LIVE tailnet PG.

Applies 0026 (clock) + 0027 (walk_ledger) + 0029 (pass_grants) inside ONE rollback
transaction, then proves the grants are a REAL enforcement mechanism — not just
structure — by SET ROLE-ing to the non-superuser ``pass_reader`` / ``pass_refresher``
roles created in the SAME transaction and observing what they can and cannot do.

Proves the ADR-0045 §B / ADR-0052 default-deny contract:

  * **Roles exist:** pass_refresher + pass_reader (NOLOGIN).
  * **pass_reader CAN SELECT** the pass corpus (walk_run/walk_step/walk_step_retrieval).
  * **pass_reader CANNOT INSERT** walk_step — the refresher is the SOLE writer
    (the §B contract, enforced at the DB when the role is non-superuser).
  * **pass_reader CANNOT SELECT working.normalized_record** — agents read the DERIVED
    pass corpus, not the canonical base store (one-store-filtered-per-agent).
  * **pass_refresher CAN INSERT** walk_step + walk_step_retrieval, and CAN SELECT
    working.normalized_record (it reads canonical to compute base_version).
  * **Default-deny:** PUBLIC has NO privileges on the pass tables.
  * **The superuser finding:** the app's ``ai`` role is a SUPERUSER, so the grants are
    INERT for the app's current superuser connection (they bite only when the app
    connects via a non-superuser role). This is recorded, not "fixed" — it is the
    owner's connection-model decision (W1.4 pre-mortem item #1).

F8: 0026/0027/0029 BEGIN;+COMMIT; stripped; explicit txn; always rolled back; no
commit anywhere (source-grep guard). SET ROLE + SAVEPOINTs keep the failed-INSERT /
failed-SELECT probes from aborting the validating transaction.
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
    SQL_DIR / "0028_horizon_repoint.sql",  # 0029 grants on working.record_visible_from (0028's table)
    SQL_DIR / "0029_pass_grants.sql",
]


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
    sql = re.sub(r"^\s*BEGIN\s*;", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"^\s*COMMIT\s*;", "", sql, flags=re.MULTILINE)
    return sql


def main() -> int:
    src = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.commit\s*\(", src):
        print("ERROR: F8 violation — validation script commits; refusing to run.")
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
    all_ok = True
    try:
        conn = engine.connect()
        trans = conn.begin()
        try:
            conn.exec_driver_sql(ddl)  # apply 0026 + 0027 + 0029 (roles + grants live in this txn)

            print("=== W1.4 GRANTS VALIDATION (live, rollback) ===\n-- structural --")

            # --- roles exist ---
            roles = {r[0] for r in conn.execute(text(
                "SELECT rolname FROM pg_roles WHERE rolname IN ('pass_refresher','pass_reader')"
            )).fetchall()}
            all_ok &= check("roles pass_refresher + pass_reader exist",
                            {"pass_refresher", "pass_reader"} <= roles, f"found={sorted(roles)}")
            all_ok &= check("pass_refresher is NOLOGIN (rolcanlogin=False)",
                            conn.execute(text("SELECT rolcanlogin FROM pg_roles WHERE rolname='pass_refresher'")).scalar() is False)
            all_ok &= check("pass_reader is NOLOGIN (rolcanlogin=False)",
                            conn.execute(text("SELECT rolcanlogin FROM pg_roles WHERE rolname='pass_reader'")).scalar() is False)

            def has_priv(grantee: str, table: str, priv: str) -> bool:
                return bool(conn.execute(text(
                    "SELECT 1 FROM information_schema.table_privileges "
                    "WHERE grantee=:g AND table_schema='working' AND table_name=:t "
                    "AND privilege_type=:p LIMIT 1"
                ), {"g": grantee, "t": table, "p": priv}).first())

            # --- default-deny: PUBLIC has nothing on the pass tables ---
            pub = conn.execute(text(
                "SELECT count(*) FROM information_schema.table_privileges "
                "WHERE grantee='PUBLIC' AND table_schema='working' "
                "AND table_name IN ('walk_run','walk_step','walk_step_retrieval','record_visible_from')"
            )).scalar()
            all_ok &= check("default-deny: PUBLIC has NO privileges on pass tables", pub == 0, f"public_privs={pub}")

            # --- pass_refresher grants (sole writer + canonical read + attestation) ---
            all_ok &= check("pass_refresher: SELECT working.normalized_record (reads canonical for base_version)",
                            has_priv("pass_refresher", "normalized_record", "SELECT"))
            all_ok &= check("pass_refresher: INSERT working.walk_step (sole writer)",
                            has_priv("pass_refresher", "walk_step", "INSERT"))
            all_ok &= check("pass_refresher: UPDATE working.walk_run",
                            has_priv("pass_refresher", "walk_run", "UPDATE"))
            all_ok &= check("pass_refresher: INSERT ops.audit_ledger (attestation)",
                            bool(conn.execute(text(
                                "SELECT 1 FROM information_schema.table_privileges "
                                "WHERE grantee='pass_refresher' AND table_schema='ops' "
                                "AND table_name='audit_ledger' AND privilege_type='INSERT' LIMIT 1"
                            )).first()))

            # --- pass_reader grants (pass corpus SELECT only) ---
            all_ok &= check("pass_reader: SELECT working.walk_step",
                            has_priv("pass_reader", "walk_step", "SELECT"))
            all_ok &= check("pass_reader: NO INSERT working.walk_step (sole-writer enforced)",
                            not has_priv("pass_reader", "walk_step", "INSERT"))
            all_ok &= check("pass_reader: NO SELECT working.normalized_record (no canonical)",
                            not has_priv("pass_reader", "normalized_record", "SELECT"))

            print("\n-- enforcement (SET ROLE to the non-superuser roles, same txn) --")

            # --- a walk_run must exist for the INSERT probe; create one as the refresher
            # first (as superuser, since no run exists yet). Then SET ROLE pass_reader and
            # try to INSERT a step — should be DENIED. ---

            # As superuser, seed a walk_run so the walk_step FK has a target. Use plain
            # string literals (no pgcrypto dependency) — base_version/genesis_hash are
            # just TEXT here; the real engine computes them in Python (derivation.py).
            run_id = conn.execute(text(
                "INSERT INTO working.walk_run (case_id, agent_id, horizon_policy, "
                "base_version, genesis_hash, status) "
                "VALUES ('primary','w14_probe','hindsight', :bv, :gh, 'running') RETURNING id"
            ), {"bv": "0" * 64, "gh": "0" * 64}).scalar()

            # ---- pass_reader: CAN SELECT walk_step ----
            conn.execute(text("SET ROLE pass_reader"))
            n = conn.execute(text("SELECT count(*) FROM working.walk_step")).scalar()
            all_ok &= check("as pass_reader: SELECT walk_step succeeds", n is not None, f"count={n}")
            conn.execute(text("RESET ROLE"))

            def denied_as(role: str, stmt: str, params: dict | None, label: str) -> bool:
                conn.execute(text(f"SET ROLE {role}"))
                ok = False
                detail = ""
                try:
                    try:
                        with conn.begin_nested():
                            conn.execute(text(stmt), params or {})
                        detail = "succeeded (unexpected — not denied)"
                    except Exception as e:
                        ok = "permission denied" in str(e).lower() or "must have" in str(e).lower()
                        detail = f"{type(e).__name__}: {str(e)[:80]}"
                finally:
                    conn.execute(text("RESET ROLE"))
                return check(label, ok, detail)

            def allowed_as(role: str, stmt: str, params: dict | None, label: str) -> bool:
                conn.execute(text(f"SET ROLE {role}"))
                ok = False
                detail = ""
                try:
                    try:
                        with conn.begin_nested():
                            conn.execute(text(stmt), params or {})
                        ok = True
                        detail = "succeeded"
                    except Exception as e:
                        detail = f"{type(e).__name__}: {str(e)[:80]}"
                finally:
                    conn.execute(text("RESET ROLE"))
                return check(label, ok, detail)

            # ---- pass_reader: CANNOT INSERT walk_step (sole-writer enforced at DB) ----
            all_ok &= denied_as(
                "pass_reader",
                "INSERT INTO working.walk_step (walk_run_id, step_no, corpus_hash, prev_hash) "
                "VALUES (:run, 99, 'x', 'y')",
                {"run": str(run_id)},
                "as pass_reader: INSERT walk_step is DENIED (sole-writer enforced)",
            )
            # ---- pass_reader: CANNOT SELECT normalized_record (no canonical) ----
            all_ok &= denied_as(
                "pass_reader",
                "SELECT count(*) FROM working.normalized_record",
                None,
                "as pass_reader: SELECT normalized_record is DENIED (no canonical base)",
            )

            print("\n-- pass_refresher can write the pass corpus + read canonical --")
            # ---- pass_refresher: CAN INSERT walk_step ----
            all_ok &= allowed_as(
                "pass_refresher",
                "INSERT INTO working.walk_step (walk_run_id, step_no, corpus_hash, prev_hash) "
                "VALUES (:run, 7, 'rhash', 'rprev')",
                {"run": str(run_id)},
                "as pass_refresher: INSERT walk_step succeeds (sole writer)",
            )
            # ---- pass_refresher: CAN SELECT normalized_record ----
            all_ok &= allowed_as(
                "pass_refresher",
                "SELECT count(*) FROM working.normalized_record",
                None,
                "as pass_refresher: SELECT normalized_record succeeds (reads canonical)",
            )
            # ---- pass_refresher: CANNOT DELETE walk_run (not granted DELETE — append-only) ----
            all_ok &= denied_as(
                "pass_refresher",
                "DELETE FROM working.walk_run WHERE id=:run",
                {"run": str(run_id)},
                "as pass_refresher: DELETE walk_run DENIED (append-only; refresher has no DELETE)",
            )

            # --- the superuser finding: document it, do not pretend to fix it ---
            print("\n-- the superuser finding (the reason grants are inert for the app) --")
            is_super = conn.execute(text(
                "SELECT rolsuper FROM pg_roles WHERE rolname=current_user"
            )).scalar()
            all_ok &= check(
                "app connection role `ai` is a SUPERUSER (grants bypass it — inert until connection model changes)",
                bool(is_super),
                f"current_user superuser={is_super}; these grants bite only for non-superuser roles (proven above)",
            )
        finally:
            trans.rollback()
            conn.close()
        print("\n[rollback] validation transaction rolled back — zero net write to live db.")
    except Exception:
        print("\n[rollback] rolled back after exception — zero net write.")
        raise
    finally:
        engine.dispose()

    print(
        "\n[VERDICT] "
        + (
            "PASS — 0029 grants are real enforcement (proven via SET ROLE); inert for the superuser app connection (owner decision pending)"
            if all_ok
            else "FAIL — see above."
        )
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())