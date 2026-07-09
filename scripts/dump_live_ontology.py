"""Read-only dump of the live behavioral-ontology tables -> live-dumps/ (gitignored).

Captures live truth for seed reconciliation (the committed 0006 seed drifted behind
the live DB). NEVER commits output: rows can contain sealed-lexicon real values.
The reconciler redacts sealed tiers before anything reaches git.

    DB_HOST=100.119.96.29 python scripts/dump_live_ontology.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

from db.url import db_url  # noqa: E402

TABLES = [
    "analysis.detection_pattern_set",
    "analysis.behavior_category",
    "analysis.detection_pattern",
    "analysis.pattern_lexicon",
    "analysis.behavior_category_mcl",
]

OUT_DIR = Path(__file__).resolve().parent.parent / "live-dumps"


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"ontology_{stamp}.json"
    engine = create_engine(db_url, connect_args={"connect_timeout": 10})
    payload: dict = {"dumped_at": stamp, "read_only": True, "tables": {}}
    with engine.connect() as conn:  # read-only: SELECTs only
        for tbl in TABLES:
            rows = [dict(r) for r in conn.execute(text(f"SELECT * FROM {tbl}")).mappings()]
            payload["tables"][tbl] = rows
            print(f"{tbl}: {len(rows)} rows")
    out.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB) — gitignored, do not commit")


if __name__ == "__main__":
    main()
