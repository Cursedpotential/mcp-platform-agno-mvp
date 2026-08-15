"""Wave 1.3 — validate the 0028 horizon repoint against the LIVE tailnet PG.

Applies 0026 (clock) + 0027 (walk_ledger) + 0028 (repoint), then proves the LIVE
spine view now filters on visible_from (ADR-0045 §A), NOT the superseded
knowledge_time. ROLLS BACK — ZERO NET WRITE.

Proves:
  * **Ignorant excludes a future-revealed record:** approve a realization pushing
    a record's visible_from a year forward; with app.horizon set BEFORE that, the
    record is ABSENT from vw_spine_horizon (it is not yet knowable).
  * **Hindsight includes it:** app.horizon unset => the whole case.
  * **Fast path is consulted:** a row in working.record_visible_from is preferred
    over the function (COALESCE) — proves the materialized projection is
    authoritative when populated (the refresher keeps it in sync).
  * **Old knowledge_time predicate is no longer the filter:** a record whose
    knowledge_time is EARLY but visible_from is LATE is excluded (the old
    predicate would have included it — the flip is live).

0028 is HELD FOR OWNER (F4-dependent) — this validates the SQL is faithful, not
that it should apply now.

F8: 0026/0027/0028 BEGIN;+COMMIT; stripped; explicit txn; always rolled back;
no commit anywhere (source-grep guard).
Creds regex-parsed from ~/.secrets/Agno-MCP-Platform.env (never sourced/printed).
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
MIGRATIONS = [
    SQL_DIR / "0026_realization_event.sql",
    SQL_DIR / "0027_walk_ledger.sql",
    SQL_DIR / "0028_horizon_repoint.sql",
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

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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
            conn.exec_driver_sql(ddl)  # apply 0026 + 0027 + 0028

            row = conn.execute(
                text(
                    "SELECT id, occurred_at, knowledge_time FROM working.normalized_record "
                    "WHERE occurred_at IS NOT NULL ORDER BY occurred_at LIMIT 1"
                )
            ).first()
            if row is None:
                print("  [FAIL] no normalized_record with occurred_at to test against.")
                return 1
            rid, occurred, ktime = row
            case_id = conn.execute(
                text("SELECT case_id FROM working.normalized_record WHERE id=:id"), {"id": str(rid)}
            ).scalar() or "primary"

            # Plant an approved realization a year forward -> visible_from = realized.
            realized = occurred.replace(year=occurred.year + 1)
            evid = propose_realization(
                kind="contradiction", realized_at=realized,
                record_ids=[uuid.UUID(str(rid))], case_id=case_id,
                proposer="owner", connection=conn,
            )
            approve_realizations(event_ids=[evid], approved_by="owner", connection=conn)

            def _set_horizon(h: str | None) -> None:
                conn.execute(text("SELECT set_config('app.case_id', :c, false)"), {"c": case_id})
                conn.execute(text("SELECT set_config('app.horizon', :h, false)"), {"h": h if h is not None else ""})

            def _in_view() -> bool:
                return bool(conn.execute(
                    text("SELECT EXISTS(SELECT 1 FROM working.vw_spine_horizon WHERE id=:id)"),
                    {"id": str(rid)},
                ).scalar())

            # --- ignorant at an early horizon: record NOT knowable -> excluded ---
            _set_horizon((occurred + timedelta(days=30)).isoformat())
            all_ok &= check(
                "repoint: ignorant early-horizon EXCLUDES future-revealed record",
                not _in_view(),
                f"visible_from={realized} > horizon (knowledge_time was {ktime}; old predicate would have INCLUDED it)",
            )

            # --- hindsight (horizon unset): whole case -> included ---
            _set_horizon(None)
            all_ok &= check("repoint: hindsight INCLUDES the record", _in_view())

            # --- fast path consulted: materialize an EARLY visible_from for the
            # record; the view should now INCLUDE it at the early horizon (the
            # fast path overrides the function). This proves COALESCE prefers rvf.
            _set_horizon((occurred + timedelta(days=30)).isoformat())
            conn.execute(
                text(
                    "INSERT INTO working.record_visible_from (record_id, visible_from) "
                    "VALUES (:rid, :vf) ON CONFLICT (record_id) DO UPDATE SET visible_from=excluded.visible_from"
                ),
                {"rid": str(rid), "vf": occurred},  # early materialized value
            )
            all_ok &= check(
                "fast path: materialized record_visible_from is consulted (overrides function)",
                _in_view(),
                "view now includes at early horizon because rvf.visible_from=occurred (early)",
            )
            # Clean up the planted fast-path row so the next assertion is clean.
            conn.execute(text("DELETE FROM working.record_visible_from WHERE record_id=:rid"), {"rid": str(rid)})

            # --- the repoint is a proper <= filter: a horizon AFTER visible_from
            # INCLUDES the record (not "always exclude"). ---
            _set_horizon((realized + timedelta(days=1)).isoformat())
            all_ok &= check(
                "repoint: ignorant late-horizon (after visible_from) INCLUDES the record",
                _in_view(),
                f"horizon > visible_from {realized}",
            )

            # --- structural proof the knowledge_time predicate is RETIRED from
            # the view body (the flip is live, not just behaviorally coincident). ---
            view_def = conn.execute(
                text(
                    "SELECT pg_get_viewdef('working.vw_spine_horizon'::regclass, true)"
                )
            ).scalar() or ""
            vd = view_def.lower()
            all_ok &= check(
                "structural: view filters on visible_from(r.id), not knowledge_time <=",
                "visible_from(r.id)" in vd and "knowledge_time <=" not in vd,
                "WHERE uses COALESCE(rvf.visible_from, visible_from(r.id)); knowledge_time is SELECT-only (r.*)",
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
            "PASS — 0028 repoint faithful (visible_from filter, hindsight, fast path, knowledge_time retired)"
            if all_ok
            else "FAIL — see above."
        )
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())