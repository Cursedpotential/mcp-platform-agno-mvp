# Byline: Claude Code · Sonnet 5 · 2026-08-26
"""`python -m server.timeline <cmd>` — operable entry point for the D02/E02 projector, mirroring
`server/evidence/cli.py`'s spirit (a plain CLI, not a mounted route — see `projector.py`'s
docstring for why the HTTP-mount question is deliberately left for a later packet).
"""

from __future__ import annotations

import argparse
import json
import sys

from server.timeline.db import get_engine
from server.timeline.generation import build_generation
from server.timeline.receipts import expected_manifest


def _cmd_build_generation(args: argparse.Namespace) -> int:
    engine = get_engine()
    with engine.begin() as conn:
        result = build_generation(conn, collection_slug=args.collection, created_by=args.actor)
    print(
        json.dumps(
            {
                "generation_id": result.generation_id,
                "sequence": result.sequence,
                "created": result.created,
                "member_count": result.member_count,
                "skipped_unresolved_governed_members": list(result.skipped_unresolved_governed_members),
            },
            indent=2,
        )
    )
    return 0


def _cmd_show_manifest(args: argparse.Namespace) -> int:
    engine = get_engine()
    with engine.connect() as conn:
        rows = expected_manifest(conn, generation_id=args.generation)
    print(json.dumps([r.__dict__ for r in rows], indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m server.timeline")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-generation", help="Build (or idempotently reuse) a projection generation")
    build.add_argument("--collection", default="primary")
    build.add_argument("--actor", default="timeline_projector")
    build.set_defaults(func=_cmd_build_generation)

    manifest = sub.add_parser("show-manifest", help="Print the expected manifest for a generation")
    manifest.add_argument("--generation", required=True)
    manifest.set_defaults(func=_cmd_show_manifest)

    ns = parser.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    sys.exit(main())
