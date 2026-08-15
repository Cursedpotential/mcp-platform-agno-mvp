"""Wave 1.2 — validate realization writers against the LIVE tailnet PG.

Applies sql/0026 (the clock objects) + runs the W1.2 writer functions
(propose / approve / supersede) against a REAL normalized_record, then
ROLLBACKS. ZERO NET WRITE to the live `ai` DB.

Uses a real SQLAlchemy engine + connection (the same path
``server/evidence/store.py`` uses in prod), so the writer is exercised against
a true SQLAlchemy ``Connection`` — its expanding bindparams work natively.
0026's multi-statement DDL runs via ``exec_driver_sql`` (psycopg3 simple-query
protocol). Everything shares ONE transaction we always roll back.

PRE-MORTEM F6 (2026-08-14) — what this proves vs. what it defers:
  * DB-level gate (visible_from reads only 'approved'): PROVEN here. A
    'proposed' event leaves visible_from == occurred_at; approve moves it to
    realized_at; supersede reverts it. This is the backstop that catches any
    writer that bypasses the @approval tool.
  * agno @approval run-level gate (the run PAUSES before approve/supersede
    bodies): NOT exercised here — it requires a live agno run with a pending
    approval row. Verified at the WAVE GATE by running an agent that calls
    realization_approve and confirming the pause + resolve. Code-level
    confirmation that the decorators are stacked on the wrappers is asserted
    here (approval_type / requires_confirmation attributes).

PRE-MORTEM F5 (2026-08-14): the realized_at >= min(linked occurred_at) guard
is PROVEN here — propose with realized_at < occurred_at raises ValueError and
no row is inserted.

F8 (carry-over from W1.1): sql/0026 carries its own BEGIN;/COMMIT; — stripped
before execution so the DDL runs inside OUR rollback transaction. The
transaction is explicit (``conn.begin()``) and ALWAYS rolled back in ``finally``;
NO commit call anywhere (source-grep guard at the top of main()).

Creds parsed from ~/.secrets/Agno-MCP-Platform.env via regex (never sourced/printed).
Byline: Claude Code . glm-5.2:cloud . 2026-08-14
"""

from __future__ import annotations

import re
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy import create_engine, text

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
    sql = re.sub(r"^\s*BEGIN\s*;", "", sql, flags=re.MULTILINE)
    sql = re.sub(r"^\s*COMMIT\s*;", "", sql, flags=re.MULTILINE)
    return sql


def main() -> int:
    # F8: this file must NEVER commit the transaction. A validation script that
    # commits writes to prod. The guard matches any commit() call.
    src = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.commit\s*\(", src):
        print("ERROR: F8 violation — validation script commits; refusing to run.")
        return 2

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    # F6 code-level: the @approval gate must be stacked on approve/supersede
    # and NOT on propose. agno stamps approval_type / requires_confirmation on
    # the Function object. Assert before touching the DB.
    try:
        from server.agents.tools.realization_tools import (
            realization_approve,
            realization_propose,
            realization_supersede,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: could not import realization tools: {exc}")
        return 2

    def _attr(fn: Any, name: str) -> Any:
        return getattr(fn, name, getattr(getattr(fn, "function", None), name, None))

    all_ok = True
    all_ok &= check(
        "F6: realization_propose has NO @approval gate", _attr(realization_propose, "approval_type") != "required"
    )
    all_ok &= check(
        "F6: realization_approve carries @approval", _attr(realization_approve, "approval_type") == "required"
    )
    all_ok &= check(
        "F6: realization_supersede carries @approval", _attr(realization_supersede, "approval_type") == "required"
    )
    all_ok &= check(
        "F6: realization_approve requires_confirmation=True",
        bool(_attr(realization_approve, "requires_confirmation")),
    )

    from server.evidence.realization import (
        approve_realizations,
        propose_realization,
        supersede_realization,
    )

    env = parse_env(ENV_FILE)
    port = env.get("DB_PORT", "5432")
    user = env.get("DB_USER") or env.get("POSTGRES_USER", "")
    pwd = env.get("DB_PASS") or env.get("POSTGRES_PASSWORD", "")
    dbname = env.get("DB_DATABASE") or env.get("POSTGRES_DB", "")
    if not (user and pwd and dbname):
        print("ERROR: could not resolve creds (names parsed, values hidden).")
        return 2

    url = f"postgresql+psycopg://{user}:{quote(pwd, safe='')}@{TAILNET_HOST}:{port}/{dbname}"
    sql = strip_txn_control(MIGRATION.read_text(encoding="utf-8"))

    engine = create_engine(url, pool_pre_ping=True)
    try:
        conn = engine.connect()
        trans = conn.begin()  # explicit; ALWAYS rolled back in finally
        try:
            conn.exec_driver_sql(sql)  # apply 0026 clock objects (multi-stmt DDL)

            row = conn.execute(
                text(
                    "SELECT id, occurred_at FROM working.normalized_record "
                    "WHERE occurred_at IS NOT NULL ORDER BY occurred_at LIMIT 1"
                )
            ).first()
            if row is None:
                print("  [FAIL] no normalized_record with occurred_at to test against.")
                all_ok = False
            else:
                rid, occurred = row
                rid_str = str(rid)

                # --- degenerate: no events -> occurred_at ---
                vf0 = conn.execute(text("SELECT working.visible_from(:rid)"), {"rid": rid}).scalar()
                all_ok &= check("degenerate visible_from == occurred_at", vf0 == occurred, f"vf={vf0} occ={occurred}")

                # --- F5: propose with realized_at < occurred_at MUST raise ---
                too_early = occurred - timedelta(days=30)
                raised = False
                try:
                    propose_realization(
                        kind="manual",
                        realized_at=too_early,
                        record_ids=[uuid.UUID(rid_str)],
                        connection=conn,
                    )
                except ValueError:
                    raised = True
                all_ok &= check(
                    "F5: propose rejects realized_at < occurred_at", raised, f"realized_at={too_early} occ={occurred}"
                )
                all_ok &= check(
                    "F5: rejected propose left visible_from unchanged",
                    conn.execute(text("SELECT working.visible_from(:rid)"), {"rid": rid}).scalar() == occurred,
                )

                # --- propose a VALID future realization (inert) ---
                later = occurred.replace(year=occurred.year + 1)
                evid = propose_realization(
                    kind="contradiction",
                    realized_at=later,
                    record_ids=[uuid.UUID(rid_str)],
                    proposer="algorithm",
                    notes="w1.2 validation",
                    connection=conn,
                )
                all_ok &= check("propose returned a uuid", isinstance(evid, uuid.UUID))

                st = conn.execute(
                    text("SELECT approval_state FROM working.realization_event WHERE id=:id"),
                    {"id": str(evid)},
                ).scalar()
                all_ok &= check("proposed row is 'proposed'", st == "proposed")

                # --- DB-level gate: proposed event does NOT move visible_from ---
                vf_proposed = conn.execute(text("SELECT working.visible_from(:rid)"), {"rid": rid}).scalar()
                all_ok &= check(
                    "DB gate: PROPOSED event leaves visible_from == occurred_at (fail-closed)",
                    vf_proposed == occurred,
                    f"vf={vf_proposed} (expected {occurred})",
                )

                # --- approve (the writer) flips to approved ---
                res = approve_realizations(event_ids=[evid], approved_by="owner", connection=conn)
                all_ok &= check("approve reports exactly one approved", res["approved"] == [str(evid)])

                vf_approved = conn.execute(text("SELECT working.visible_from(:rid)"), {"rid": rid}).scalar()
                all_ok &= check(
                    "DB gate: APPROVED event moves visible_from to realized_at",
                    vf_approved == later,
                    f"vf={vf_approved} (expected {later})",
                )

                ap_at, ap_by = conn.execute(
                    text("SELECT approved_at, approved_by FROM working.realization_event WHERE id=:id"),
                    {"id": str(evid)},
                ).first()
                all_ok &= check("approved row stamped approved_at/by", ap_at is not None and ap_by == "owner")

                # --- idempotent re-approve is a no-op ---
                res2 = approve_realizations(event_ids=[evid], approved_by="owner", connection=conn)
                all_ok &= check("re-approve is idempotent (not_proposed)", res2["approved"] == [])

                # --- supersede reverts the clock ---
                ok = supersede_realization(event_id=evid, connection=conn)
                all_ok &= check("supersede returns True for an approved row", ok is True)
                vf_super = conn.execute(text("SELECT working.visible_from(:rid)"), {"rid": rid}).scalar()
                all_ok &= check(
                    "supersede reverts visible_from to occurred_at",
                    vf_super == occurred,
                    f"vf={vf_super} (expected {occurred})",
                )

                # --- idempotent re-supersede is a no-op ---
                ok2 = supersede_realization(event_id=evid, connection=conn)
                all_ok &= check("re-supersede is idempotent (False)", ok2 is False)
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
            "PASS — W1.2 writers faithful (F5 reject, F6 DB-level gate, lifecycle, idempotency)"
            if all_ok
            else "FAIL — see above."
        )
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
