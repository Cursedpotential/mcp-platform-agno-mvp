"""CLI: drain pending working.context_record rows to Weaviate + Graphiti.

The easy/quick trigger for the batch projection step of the PG-first context
lane (D-048) — the manual stand-in for the always-on CDC worker until the full
workflow is built. Runs the SAME registered tool (`ingest.context-drain`) an
agent/MCP would call, so there is exactly one implementation behind all three
front doors (invariant 7, ADR-0023/0046).

Usage (uv-managed venv, never a bare python — CONVENTIONS.md):
    # drain everything pending into BOTH sinks:
    uv run --no-sync python scripts/drain_context.py --db-host 100.91.190.107
    # preview only (counts, no writes):
    uv run --no-sync python scripts/drain_context.py --dry-run --db-host 100.91.190.107
    # one sink:
    uv run --no-sync python scripts/drain_context.py --sink weaviate --db-host 100.91.190.107

`--db-host` overrides DB_HOST for this process only: the drain reads
working.context_record from Postgres, and the platform default
`DB_HOST=agentos-db` only resolves inside the docker compose network — pass the
tailnet IP (100.91.190.107) when running off-box (CLAUDE.md environment note).
"""
# Byline: Claude Code · Opus 4.8 · 2026-08-12

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--sink",
        choices=["weaviate", "graphiti", "both"],
        default="both",
        help="which sink(s) to drain (default: both)",
    )
    ap.add_argument("--dry-run", action="store_true", help="count what WOULD project; touch no sink, stamp nothing")
    ap.add_argument("--max-chars", type=int, default=6000, help="per-chunk character budget (default 6000)")
    ap.add_argument("--db-host", default=None, help="override DB_HOST for this process (Postgres source of truth)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.db_host:
        os.environ["DB_HOST"] = args.db_host

    from server.tools.registry import load_builtin_tools, registry

    load_builtin_tools()
    tool = reference.get("ingest.context-drain")
    result = tool.run({"sink": args.sink, "dry_run": args.dry_run, "max_chars": args.max_chars})
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
