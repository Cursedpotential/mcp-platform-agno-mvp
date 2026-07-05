"""Live smoke test for the forensic stores — RUN WHERE THE TAILNET IS REACHABLE
(the owner's desktop or a VPS shell; the cloud sandbox cannot reach these).

    python scripts/smoke_forensic_stores.py

Fail-soft: every section prints PASS / FAIL / SKIP and the script exits nonzero
only if a reachable service actively failed (unreachable = SKIP, since which
services exist depends on where you run it). READ-ONLY throughout: dry-run
plans, SELECT counts, list_collections — no writes, no collection creation.

Sections:
  PG        ontology counts (0006 seed: behavior_category / detection_pattern /
            pattern_lexicon / behavior_category_mcl), evidence.source presence,
            detection.run(dry_run=True, limit=50) against real records
  MILVUS    connect, list_collections, diff vs create_forensic_collections plan
  WIRING    semantica_wiring.full_wiring() renders (no secret values printed)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# runnable as `python scripts/smoke_forensic_stores.py` from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results: list[tuple[str, str, str]] = []


def report(section: str, status: str, detail: str) -> None:
    results.append((section, status, detail))
    print(f"[{status}] {section}: {detail}")


def smoke_pg() -> None:
    try:
        from sqlalchemy import create_engine, text

        from db.url import db_url
    except Exception as exc:
        report("PG", SKIP, f"imports unavailable ({exc})")
        return
    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            # Expected counts derive from the COMMITTED migration chain
            # (evidence.patterns.chain_prefix_counts): live must equal some
            # prefix of the chain — below every prefix = data loss; above/
            # between = uncaptured drift (rows applied live but not in git,
            # exactly how the sweep-2026-07-03 delta was originally caught).
            from evidence.patterns import chain_prefix_counts

            prefixes = chain_prefix_counts()
            live = (
                conn.execute(text("SELECT count(*) FROM analysis.behavior_category")).scalar(),
                conn.execute(text("SELECT count(*) FROM analysis.detection_pattern")).scalar(),
            )
            match = next(
                (p for p in prefixes if (p["categories"], p["patterns"]) == live),
                None,
            )
            if match is None:
                report(
                    "PG ontology",
                    FAIL,
                    f"live counts {live} match NO chain prefix {[(p['categories'], p['patterns']) for p in prefixes]}"
                    " — uncaptured drift (export a new chain migration) or data loss",
                )
            else:
                pending = [p["through"] for p in prefixes[prefixes.index(match) + 1 :]]
                note = f"; pending (committed, not applied): {pending}" if pending else "; chain fully applied"
                report("PG ontology", PASS, f"live {live} == chain through {match['through']}{note}")

            src = conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema='evidence' AND table_name='source'"
                )
            ).scalar()
            report(
                "PG evidence.source",
                PASS if src else FAIL,
                "table present" if src else "MISSING — custody writes will fail",
            )
    except Exception as exc:
        report("PG", SKIP, f"unreachable ({type(exc).__name__}: {exc})")
        return

    try:
        from evidence.detection import run

        stats = run(dry_run=True, limit=50)
        report("PG detection dry-run", PASS, f"scanned OK (rolled back): {stats}")
    except Exception as exc:
        report("PG detection dry-run", FAIL, f"{type(exc).__name__}: {exc}")


def smoke_milvus() -> None:
    try:
        from pymilvus import MilvusClient
    except ImportError:
        report("MILVUS", SKIP, "pymilvus not installed here")
        return
    from evidence.milvus_forensic import MILVUS_TOKEN, MILVUS_URI, create_forensic_collections

    try:
        client = MilvusClient(uri=MILVUS_URI, token=MILVUS_TOKEN, timeout=5)
        live = set(client.list_collections())
    except Exception as exc:
        report("MILVUS", SKIP, f"unreachable at {MILVUS_URI} ({type(exc).__name__})")
        return

    plan = create_forensic_collections(client=None, dry_run=True)  # offline plan only
    wanted = {c["name"] for c in plan["collections"]}
    missing = wanted - live
    if plan["validation_errors"]:
        report("MILVUS plan", FAIL, f"spec validation errors: {plan['validation_errors']}")
    elif missing:
        report(
            "MILVUS collections",
            PASS,
            f"reachable; NOT YET CREATED (expected pre-setup): missing={sorted(missing)}, live={sorted(live)}",
        )
    else:
        report("MILVUS collections", PASS, f"all forensic collections exist: {sorted(wanted)}")


def smoke_wiring() -> None:
    try:
        from evidence.semantica_wiring import full_wiring, secrets_referenced

        wiring = full_wiring()
        body = json.dumps(wiring, default=str)
        leaked = [name for name in secrets_referenced() if (val := os.getenv(name)) and val in body]
        if leaked:
            report("WIRING secrets", FAIL, f"secret VALUES leaked into wiring output: {leaked}")
        else:
            report("WIRING", PASS, f"renders clean; lanes={sorted(wiring.keys())}; secrets by reference only")
    except Exception as exc:
        report("WIRING", FAIL, f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    print("== forensic stores live smoke (read-only) ==")
    smoke_pg()
    smoke_milvus()
    smoke_wiring()
    print("\n== summary ==")
    for section, status, _ in results:
        print(f"  {status:4} {section}")
    sys.exit(1 if any(s == FAIL for _, s, _ in results) else 0)
