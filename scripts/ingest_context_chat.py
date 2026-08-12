"""CLI: ingest ONE AI-chat export file into the CONTEXT lane, PG-first (owner
ruling 2026-08-12): parse -> working.context_record (Postgres SOURCE OF TRUTH)
-> change-detection projects to Weaviate `platform_context` tier=context +
the Graphiti CASE lane. See `server/analysis/context_chat_ingest.py` for the
full pipeline docstring and the NON-NEGOTIABLE evidence/context boundary this
enforces.

Usage (uv-managed venv, never a bare python — CONVENTIONS.md):
    uv run --no-sync python scripts/ingest_context_chat.py <path> --dry-run
    uv run --no-sync python scripts/ingest_context_chat.py <path> \\
        --conversation-id <id> [--conversation-id <id> ...] \\
        --db-host 100.119.96.29
    # PG-only (write the source of truth now, let a worker project later):
    uv run --no-sync python scripts/ingest_context_chat.py <path> --no-project

`--db-host` overrides DB_HOST for this process only: both the context_record
source-of-truth write AND agno's Knowledge contents_db need Postgres, and the
platform default `DB_HOST=agentos-db` only resolves inside the docker compose
network, not from an external host (CLAUDE.md environment note) — pass the
tailnet IP when running this off-box.

Prints a JSON IngestReport to stdout; nothing here bulk-ingests by default —
pass `--conversation-id` to scope a proof run to specific conversation(s), or
omit it to ingest every conversation the file contains (only do that with
explicit owner sign-off per the task brief: "Do NOT bulk-ingest until the
owner sees the single-file result").
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="chat-export file to ingest")
    ap.add_argument(
        "--conversation-id",
        action="append",
        dest="conversation_ids",
        default=None,
        help="restrict to this conversation_id (repeatable); omit to ingest every conversation in the file",
    )
    ap.add_argument("--dry-run", action="store_true", help="parse+preview only; no PG write, no projection")
    ap.add_argument(
        "--no-project",
        dest="project",
        action="store_false",
        default=True,
        help="write the PG source of truth only; leave Weaviate/Graphiti projection for a later worker",
    )
    ap.add_argument("--max-chars", type=int, default=6000, help="per-chunk character budget (default 6000)")
    ap.add_argument(
        "--engine",
        choices=["auto", "python", "go"],
        default="auto",
        help="which parse engine: 'python' (in-process registry), 'go' (SBV service), or 'auto' (MVP=python)",
    )
    ap.add_argument(
        "--format",
        default=None,
        help="parser/importer OVERRIDE, e.g. 'chatgpt-official-json' — skip detection (MVP; router deferred)",
    )
    ap.add_argument("--db-host", default=None, help="override DB_HOST for this process (Postgres source of truth + contents_db)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.db_host:
        os.environ["DB_HOST"] = args.db_host

    conversation_ids = set(args.conversation_ids) if args.conversation_ids else None

    if args.path.lower().endswith(".zip"):
        # Real exports arrive as a ZIP (conversations*.json + metadata + assets/).
        from server.analysis.chat_archive import ingest_chat_archive

        report = asyncio.run(
            ingest_chat_archive(
                args.path,
                engine=args.engine,
                format=args.format,
                conversation_ids=conversation_ids,
                max_chars=args.max_chars,
                dry_run=args.dry_run,
                project=args.project,
            )
        )
        print(json.dumps(asdict(report), indent=2, default=str))
        return 0

    from server.analysis.context_chat_ingest import ingest_chat_file

    report = asyncio.run(
        ingest_chat_file(
            args.path,
            conversation_ids=conversation_ids,
            max_chars=args.max_chars,
            dry_run=args.dry_run,
            project=args.project,
            engine=args.engine,
            format=args.format,
        )
    )
    print(json.dumps(asdict(report), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
