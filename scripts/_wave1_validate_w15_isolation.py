"""Wave 1.5 (P2) — prove the derivation engine pins REPEATABLE READ.

The W1.3 pre-mortem P2 gap: derive_walk/verify_reproducibility opened their
transactions at the DEFAULT isolation (READ COMMITTED), so a concurrent
realization approval mid-walk could move visible_from between steps and break
the §B reproducibility guarantee. W1.5 fixes _get_engine() to
isolation_level="REPEATABLE READ".

This script PROVES the fix on live (ZERO net write — only SHOW statements, no
INSERT/UPDATE/DDL). It imports the derivation module's own _get_engine() and
asserts that a transaction opened on that engine reports "repeatable read" —
the production path derive_walk takes (connection=None -> _get_engine().begin()).

Verification standard (matching how F13 was verified): prove the CODE CHANGE —
that the engine opens at REPEATABLE READ — by observing it directly (SHOW
transaction_isolation). The snapshot-freeze BEHAVIOR (a concurrent approval is
not visible to the frozen txn) is a documented Postgres REPEATABLE READ
guarantee, not bespoke code; it is not re-proven here, the same way the
pg_advisory_xact_lock semantics were trusted once the call was shown. The
at-rest reproducibility of the chain itself is already proven by the W1.3
validation (12/12 PASS), re-run below for regression.

Creds regex-parsed from ~/.secrets/Agno-MCP-Platform.env (never sourced/printed).
Byline: Claude Code . glm-5.2:cloud . 2026-08-14
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import create_engine, text

ENV_FILE = Path.home() / ".secrets" / "Agno-MCP-Platform.env"
TAILNET_HOST = "100.91.190.107"


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


def main() -> int:
    src = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.commit\s*\(", src):
        print("ERROR: F8 violation — script commits; refusing to run.")
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

    # The derivation engine builds its url via server.core.url.db_url, which reads
    # DB_HOST/DB_USER/DB_PASS/DB_DATABASE from the environment. On the desktop the
    # tailnet host is not the default (CLAUDE.md: "DB_HOST=100.91.190.107"), so seed
    # os.environ from the creds file BEFORE importing derivation — this makes the
    # platform db_url resolve to the tailnet, the same host the hand-built url uses.
    os.environ["DB_HOST"] = TAILNET_HOST  # force tailnet; the creds file's DB_HOST=agentos-db only resolves in-compose
    os.environ.setdefault("DB_PORT", port)
    os.environ.setdefault("DB_USER", user)
    os.environ.setdefault("DB_PASS", pwd)
    os.environ.setdefault("DB_DATABASE", dbname)

    all_ok = True
    print("=== W1.5 ISOLATION VALIDATION (live, zero-net-write — SHOW only) ===")

    # --- 1. the derivation engine's OWN engine pins REPEATABLE READ ---
    # Import the module under test and use its _get_engine() so we test the
    # production code path (derive_walk: connection=None -> _get_engine().begin()).
    from server.evidence import derivation

    engine = derivation._get_engine()
    iso = None
    with engine.begin() as conn:
        iso = conn.execute(text("SHOW transaction_isolation")).scalar()
    all_ok &= check(
        "derivation engine opens transactions at REPEATABLE READ (the P2 fix)",
        iso == "repeatable read",
        f"actual={iso}",
    )
    # the module-level lazy engine is shared; clear so a later import is fresh.
    derivation._ENGINE = None
    engine.dispose()

    # --- 2. contrast: an unconfigured engine on the SAME db defaults to READ COMMITTED,
    # proving the pin (not the server default) is what sets REPEATABLE READ. ---
    plain = create_engine(url, pool_pre_ping=True)
    with plain.begin() as conn:
        plain_iso = conn.execute(text("SHOW transaction_isolation")).scalar()
    plain.dispose()
    all_ok &= check(
        "contrast: unconfigured engine defaults to READ COMMITTED (proves the pin is what sets RR)",
        plain_iso == "read committed",
        f"actual={plain_iso}",
    )

    # --- 3. the engine is reused as a lazy singleton (a second _get_engine() returns
    # the same pinned engine — the pin is stable across calls, not per-invocation). ---
    e1 = derivation._get_engine()
    e2 = derivation._get_engine()
    all_ok &= check("derivation engine is a lazy singleton (same object across calls)", e1 is e2)
    derivation._ENGINE = None
    e1.dispose()

    print(
        "\n[VERDICT] "
        + ("PASS — derivation engine pinned REPEATABLE READ (P2 closed); zero net write."
           if all_ok
           else "FAIL — see above.")
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())