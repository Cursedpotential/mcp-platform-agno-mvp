"""CLI: ingest AI-chat exports and their created works/attachments, PG-first.

The canonical path is parse -> conversation/message -> message-safe chunks ->
multi-label classification -> selective review -> projection. PostgreSQL is
the source of truth; each canonical chunk is embedded once and its vector may
be reused across platform, legal, personal_history, and context collections.
AI-chat material never enters the evidence lane.

Usage (uv-managed venv, never a bare python — CONVENTIONS.md):
    uv run --no-sync python scripts/ingest_context_chat.py <path> --dry-run
    uv run --no-sync python scripts/ingest_context_chat.py <path> \\
        --conversation-id <id> [--conversation-id <id> ...] \\
        --db-host 100.119.96.29
    # PG-only (write the source of truth now, let a worker project later):
    uv run --no-sync python scripts/ingest_context_chat.py <path> --no-project

`--db-host` overrides DB_HOST for this process only: both the chat source-of-
truth write and Agno's Knowledge contents_db need Postgres, and the
platform default `DB_HOST=agentos-db` only resolves inside the docker compose
network, not from an external host (CLAUDE.md environment note) — pass the
tailnet IP when running this off-box.

Prints a JSON IngestReport to stdout. Use `--dry-run` for a no-write preview.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01
# Byline: Claude Code · Fable 5 · 2026-08-12 (D-053: --format now strict/bypasses the detection router; fail-fast exit 2 with a clear error)
# Byline: Codex · GPT-5 · 2026-08-13 (ADR-0053 chat landing/classification)
# Byline: Codex · GPT-5 · 2026-08-13 (CPU-first hybrid classifier controls)

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
        "--chunker",
        choices=["message-window", "chonkie-semantic", "teraflopai"],
        default="message-window",
        help="message-safe chunking strategy; TeraflopAI is an optional hosted challenger",
    )
    ap.add_argument(
        "--no-classify",
        dest="classify",
        action="store_false",
        default=True,
        help="defer classification; chunks remain searchable in context and pending review",
    )
    ap.add_argument(
        "--classify-mode",
        choices=["keyword", "cpu", "hybrid"],
        default="hybrid",
        help="keyword baseline, CPU semantic challenger, or hybrid (default; safely falls back to keyword)",
    )
    ap.add_argument(
        "--classify-model",
        default=None,
        help="Sentence Transformer model id/path (default: CPU_CLASSIFIER_MODEL or BAAI/bge-small-en-v1.5)",
    )
    ap.add_argument(
        "--engine",
        choices=["auto", "python", "go"],
        default="auto",
        help="which parse engine: 'python' (in-process registry), 'go' (SBV service), "
        "or 'auto' (detection router, Go-primary — the default)",
    )
    ap.add_argument(
        "--format",
        default=None,
        help="force this FORMAT and bypass detection entirely: a router format id ('claude-ai-export', "
        "'perplexity-contexts', 'chatgpt-official'), a Go SBV importer id ('chatgpt-official-json', ...), "
        "or a Python parser id ('transcripts.<name>'). STRICT (D-053): a format the selected --engine "
        "cannot handle, or one the parser rejects, errors with exit 2 — no fallback.",
    )
    ap.add_argument(
        "--db-host", default=None, help="override DB_HOST for this process (Postgres source of truth + contents_db)"
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.db_host:
        os.environ["DB_HOST"] = args.db_host

    conversation_ids = set(args.conversation_ids) if args.conversation_ids else None

    # Fail fast (exit 2) with a one-line error for operator mistakes — a bad
    # --format/--engine combination, an unparsable file under an explicit
    # override, a missing path — instead of a traceback (D-053: an explicit
    # override must error LOUDLY, never silently fall back).
    try:
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
                    chunker=args.chunker,
                    classify=args.classify,
                    classify_mode=args.classify_mode,
                    classify_model=args.classify_model,
                )
            )
        else:
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
                    chunker=args.chunker,
                    classify=args.classify,
                    classify_mode=args.classify_mode,
                    classify_model=args.classify_model,
                )
            )
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(report), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
