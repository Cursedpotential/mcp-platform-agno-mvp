"""Wave 1.3 — validate the derivation engine against the LIVE tailnet PG.

Applies sql/0026 (clock) + sql/0027 (walk_ledger), then runs the W1.3 derivation
engine (``server/evidence/derivation.py``) against REAL normalized_records, then
ROLLS BACK. ZERO NET WRITE to the live ``ai`` DB.

Proves the ADR-0045 §B contract before any agent binds:

  * **Contamination guard (the point of the project, canon §1):** approve a
    realization that pushes a record's ``visible_from`` a year forward; an
    IGNORANT step whose horizon is before that realization EXCLUDES the record
    (its ``visible_from`` is after the horizon) — the future fact does not
    leak into the earlier step. A HINDSIGHT step INCLUDES it. The delta is real.
  * **Sole-writer lock (F13):** while a derivation txn holds
    ``pg_advisory_xact_lock(hashtext('working.walk_ledger'))``, a SECOND
    connection's ``pg_try_advisory_xact_lock`` returns False (two refreshers
    cannot interleave).
  * **Version-pinned reproducibility (§B):** ``verify_reproducibility`` on the
    ignorant run returns ``reproducible=True`` — re-deriving at the recorded
    base_version reproduces the identical corpus_hash chain.
  * **Hash-attestation:** each step attested to ``ops.audit_ledger`` (action_type
    'derivation', payload_hash=corpus_hash) in the same transaction.

F8 (carry-over): 0026 + 0027 carry their own BEGIN;/COMMIT; — stripped before
execution so the DDL runs inside OUR rollback transaction. Explicit
``conn.begin()``, ALWAYS rolled back in ``finally``; NO commit anywhere
(source-grep guard at the top of main()).

Creds parsed from ~/.secrets/Agno-MCP-Platform.env via regex (never sourced/printed).
Byline: Claude Code . glm-5.2:cloud . 2026-08-14
"""

from __future__ import annotations

import re
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import create_engine, text

ENV_FILE = Path.home() / ".secrets" / "Agno-MCP-Platform.env"
TAILNET_HOST = "100.91.190.107"
SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
MIGRATIONS = [SQL_DIR / "0026_realization_event.sql", SQL_DIR / "0027_walk_ledger.sql"]


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

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from server.evidence.derivation import derive_walk, verify_reproducibility
    from server.evidence.realization import approve_realizations, propose_realization

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
            conn.exec_driver_sql(ddl)  # apply 0026 + 0027 (multi-stmt DDL)

            # Pick a record with a known occurred_at to plant a realization on.
            row = conn.execute(
                text(
                    "SELECT id, occurred_at FROM working.normalized_record "
                    "WHERE occurred_at IS NOT NULL ORDER BY occurred_at LIMIT 1"
                )
            ).first()
            if row is None:
                print("  [FAIL] no normalized_record with occurred_at to test against.")
                return 1
            rid, occurred = row
            case_id = conn.execute(
                text("SELECT case_id FROM working.normalized_record WHERE id=:id"), {"id": str(rid)}
            ).scalar() or "primary"

            # --- plant an approved realization a year forward ---
            realized = occurred.replace(year=occurred.year + 1)
            evid = propose_realization(
                kind="contradiction",
                realized_at=realized,
                record_ids=[uuid.UUID(str(rid))],
                case_id=case_id,
                proposer="owner",
                connection=conn,
            )
            approve_realizations(event_ids=[evid], approved_by="owner", connection=conn)
            vf = conn.execute(text("SELECT working.visible_from(:rid)"), {"rid": rid}).scalar()
            all_ok &= check("realization pushed visible_from forward", vf == realized, f"vf={vf} expected {realized}")

            # --- IGNORANT walk: early horizon (before the realization) ---
            early_horizon = occurred + timedelta(days=30)  # after occurrence, before realization
            ignorant_run = derive_walk(
                case_id=case_id,
                agent_id="validation_ignorant",
                horizon_policy="ignorant",
                horizon_schedule=[early_horizon],
                bound_lane="test-lane",
                connection=conn,
            )
            all_ok &= check("ignorant walk created a run", isinstance(ignorant_run, uuid.UUID))

            # The planted record (visible_from = realized) must NOT be in the
            # early step's visible slice (contamination guard).
            early_retrieved = conn.execute(
                text(
                    "SELECT count(*) FROM working.walk_step_retrieval ret "
                    "JOIN working.walk_step s ON s.id=ret.walk_step_id "
                    "WHERE s.walk_run_id=:run AND ret.record_id=:rid"
                ),
                {"run": str(ignorant_run), "rid": str(rid)},
            ).scalar()
            all_ok &= check(
                "contamination guard: future-revealed record EXCLUDED from early ignorant step",
                early_retrieved == 0,
                f"retrieved={early_retrieved} (expected 0 — visible_from {realized} > horizon {early_horizon})",
            )

            # vw_walk_contamination must be empty for this run (nothing leaked).
            contam = conn.execute(
                text("SELECT count(*) FROM working.vw_walk_contamination WHERE walk_run_id=:run"),
                {"run": str(ignorant_run)},
            ).scalar()
            all_ok &= check("vw_walk_contamination empty (no leak)", contam == 0, f"contam={contam}")

            # --- HINDSIGHT walk: sees everything including the planted record ---
            hindsight_run = derive_walk(
                case_id=case_id,
                agent_id="validation_hindsight",
                horizon_policy="hindsight",
                horizon_schedule=None,
                connection=conn,
            )
            hindsight_retrieved = conn.execute(
                text(
                    "SELECT count(*) FROM working.walk_step_retrieval ret "
                    "JOIN working.walk_step s ON s.id=ret.walk_step_id "
                    "WHERE s.walk_run_id=:run AND ret.record_id=:rid"
                ),
                {"run": str(hindsight_run), "rid": str(rid)},
            ).scalar()
            all_ok &= check(
                "hindsight step INCLUDES the planted record",
                hindsight_retrieved >= 1,
                f"retrieved={hindsight_retrieved}",
            )

            # --- reproducibility (§B gate) ---
            rep = verify_reproducibility(walk_run_id=ignorant_run, connection=conn)
            all_ok &= check(
                "verify_reproducibility: identical chain at same base_version",
                rep["reproducible"] is True,
                f"reason={rep.get('reason', 'none')} steps={rep.get('step_count')}",
            )

            # --- hash-attestation: each step attested to ops.audit_ledger ---
            attest = conn.execute(
                text(
                    "SELECT count(*) FROM ops.audit_ledger "
                    "WHERE action_type='derivation' AND object_ref=:run"
                ),
                {"run": str(ignorant_run)},
            ).scalar()
            all_ok &= check(
                "every step hash-attested to ops.audit_ledger",
                attest >= 1,
                f"derivation rows={attest}",
            )

            # --- F13 sole-writer lock: the ignorant derive held it; a second
            # connection's pg_try_advisory_xact_lock must return False while we
            # still hold the txn. The lock is held until our rollback. ---
            conn2 = engine.connect()
            try:
                got = conn2.execute(
                    text("SELECT pg_try_advisory_xact_lock(hashtext('working.walk_ledger'))")
                ).scalar()
                # The lock was acquired (and released at txn end) by derive_walk
                # above; within our still-open txn the xact lock is NOT held
                # between calls (xact locks release at transaction end, and
                # derive_walk used our connection — the lock IS held for the
                # whole txn). So conn2 should fail to acquire.
                all_ok &= check(
                    "F13: second connection cannot acquire the sole-writer lock",
                    got is False or got == 0,
                    f"pg_try returned {got} (expected False/0 — lock held by our txn)",
                )
            finally:
                conn2.close()

            # --- MULTI-STEP ignorant walk: canon §1 — the horizon ADVANCES and
            # the record is DISCOVERED at the later step. Step 1 (horizon before
            # the realization) excludes it; step 2 (horizon after) includes it.
            # This is the as-lived discovery the whole project exists to model. ---
            multi_run = derive_walk(
                case_id=case_id,
                agent_id="validation_ignorant_multistep",
                horizon_policy="ignorant",
                horizon_schedule=[early_horizon, realized + timedelta(days=1)],
                connection=conn,
            )
            step1_ret = conn.execute(
                text(
                    "SELECT count(*) FROM working.walk_step_retrieval ret "
                    "JOIN working.walk_step s ON s.id=ret.walk_step_id "
                    "WHERE s.walk_run_id=:run AND s.step_no=1 AND ret.record_id=:rid"
                ),
                {"run": str(multi_run), "rid": str(rid)},
            ).scalar()
            step2_ret = conn.execute(
                text(
                    "SELECT count(*) FROM working.walk_step_retrieval ret "
                    "JOIN working.walk_step s ON s.id=ret.walk_step_id "
                    "WHERE s.walk_run_id=:run AND s.step_no=2 AND ret.record_id=:rid"
                ),
                {"run": str(multi_run), "rid": str(rid)},
            ).scalar()
            all_ok &= check(
                "canon §1: multi-step ignorant walk — step 1 EXCLUDES the future-revealed record",
                step1_ret == 0,
                f"step1={step1_ret}",
            )
            all_ok &= check(
                "canon §1: multi-step ignorant walk — step 2 DISCOVERS the record (horizon advanced)",
                step2_ret == 1,
                f"step2={step2_ret}",
            )
            # Multi-step reproducibility + chain.
            rep2 = verify_reproducibility(walk_run_id=multi_run, connection=conn)
            all_ok &= check(
                "multi-step verify_reproducibility: identical 2-step chain",
                rep2["reproducible"] is True,
                f"reason={rep2.get('reason', 'none')} steps={rep2.get('step_count')}",
            )
            chain_ok = conn.execute(
                text(
                    "SELECT NOT EXISTS ("
                    "  SELECT 1 FROM working.walk_step s1 "
                    "  JOIN working.walk_step s2 ON s2.walk_run_id=s1.walk_run_id AND s2.step_no=s1.step_no+1 "
                    "  WHERE s2.prev_hash <> s1.corpus_hash) AS ok, "
                    " (SELECT count(*) FROM working.walk_step WHERE walk_run_id=:run) AS n"
                ),
                {"run": str(multi_run)},
            ).first()
            all_ok &= check(
                "multi-step chain integrity: each step prev_hash = prior corpus_hash",
                chain_ok[0] is True,
                f"steps={chain_ok[1]}",
            )
        finally:
            trans.rollback()
            conn.close()
        print("\n[rollback] transaction rolled back — zero net write to live db.")
    except Exception:
        print("\n[rollback] rolled back after exception — zero net write.")
        raise
    finally:
        engine.dispose()

    print(
        "\n[VERDICT] "
        + (
            "PASS — W1.3 derivation engine faithful (contamination guard, sole-writer lock, reproducibility, hash-attestation)"
            if all_ok
            else "FAIL — see above."
        )
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())