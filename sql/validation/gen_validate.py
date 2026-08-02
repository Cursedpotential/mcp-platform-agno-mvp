"""Build a transaction-rollback validation harness for a numbered migration.

The harness is the migration VERBATIM with its trailing COMMIT replaced by the
matching probes file and a ROLLBACK — so what gets tested is byte-identical to
what would be applied, and a run against production writes nothing.

Layout (all beside this script):
    probes_<NNNN>.sql              hand-written probes for that migration
    validate_<NNNN>_<name>.sql     generated; do not hand-edit

Usage:
    uv run --no-sync python sql/validation/gen_validate.py 0009
    uv run --no-sync python sql/validation/gen_validate.py          # all found

Then:
    ssh <db-host> "docker exec -i <pg-container> psql -U ai -d ai" \
      < sql/validation/validate_<NNNN>_<name>.sql

Byline: Claude Code - Opus 5 - 2026-08-01
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SQL = HERE.parent
REPO = SQL.parent


def build(migration: pathlib.Path, probes: pathlib.Path) -> pathlib.Path:
    src = migration.read_text(encoding="utf-8").rstrip()
    if not src.endswith("COMMIT;"):
        raise SystemExit(f"ERROR: {migration.name} does not end with COMMIT; refusing")
    out = HERE / f"validate_{migration.stem}.sql"
    out.write_text(
        src[: -len("COMMIT;")] + "\n" + probes.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return out


def main(argv: list[str]) -> int:
    wanted = argv[1] if len(argv) > 1 else None
    found = 0
    for probes in sorted(HERE.glob("probes_*.sql")):
        number = probes.stem.removeprefix("probes_")
        if wanted and number != wanted:
            continue
        matches = sorted(SQL.glob(f"{number}_*.sql"))
        if not matches:
            print(f"WARN: no migration matching {number}_*.sql", file=sys.stderr)
            continue
        out = build(matches[0], probes)
        print(f"wrote {out.relative_to(REPO)} ({out.stat().st_size} bytes) "
              f"from {matches[0].name} + {probes.name}")
        found += 1
    if not found:
        print("nothing to build", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
