#!/usr/bin/env python3
"""scripts/ingest_chat.py — Manual AI-chat ingest into working.chat_conversation + working.chat_message.

Usage:
    python scripts/ingest_chat.py <chat_file> [--format FORMAT] [--dry-run]
    python scripts/ingest_chat.py <chat_file> --sync-weaviate
    python scripts/ingest_chat.py <chat_file> --sync-graphiti
    python scripts/ingest_chat.py <chat_file> --sync-all
    python scripts/ingest_chat.py <chat_file> --classify          # add lane classification
    python scripts/ingest_chat.py <chat_file> --classify --sync-all  # full pipeline with classification

Examples:
    # Dry run — parse only, show what would be written
    python scripts/ingest_chat.py exports/chatgpt_my_history.json --dry-run

    # Parse + store to PG (source of truth)
    python scripts/ingest_chat.py exports/chatgpt_my_history.json

    # Full pipeline: parse + PG + classify + Weaviate + Graphiti
    python scripts/ingest_chat.py exports/chatgpt_my_history.json --classify --sync-all

    # Force a specific format (bypass auto-detection)
    python scripts/ingest_chat.py exports/conversation.json --format chatgpt-official-json

    # Force Go engine for non-auto-detected formats (SMS, email, etc.)
    python scripts/ingest_chat.py exports/sms_backup.xml --format smsbackuprestore-xml --engine go

    # Force Python engine (e.g. for perplexity-contexts which is Python-only)
    python scripts/ingest_chat.py exports/perplexity.json --engine python

    # List all supported formats (Go + Python)
    python scripts/ingest_chat.py --list-formats
"""
# Byline: Claude Code · opencode/mimo-v2.5-free · 2026-08-12
# Byline: 2026-08-12 (rewrite for 5-lane schema + human review gate)

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# Ensure server/ is importable
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))


def _list_formats():
    """Show all registered parse.transcript tools + Go SBV formats."""
    from server.analysis.format_router import GO_IMPORTER_FORMATS, SIGNATURES
    from server.tools.registry import load_builtin_tools, registry

    print("=== Go SBV Formats (engine=go, primary route) ===")
    print(f"{'Format ID':<30} {'Notes'}")
    print("-" * 60)
    for fmt in GO_IMPORTER_FORMATS:
        sig = next((s for s in SIGNATURES if s.go_format == fmt), None)
        note = f"auto-detected: {sig.format_id}" if sig else ""
        print(f"  {fmt:<28} {note}")

    print("\n=== Python Parsers (engine=python, fallback) ===")
    load_builtin_tools()
    tools = registry.resolve("parse.transcript")
    print(f"{'Tool ID':<40} {'Description'}")
    print("-" * 70)
    for t in tools:
        print(f"  {t.id:<38} {t.description[:50]}")

    print(f"\nTotal: {len(GO_IMPORTER_FORMATS)} Go + {len(tools)} Python parsers")
    print("\nAuto-detection routes by default:")
    print("  chatgpt-official JSON → Go (primary)")
    print("  perplexity-contexts   → Python only")
    print("  claude-ai-export      → Python only")
    print("  SMS/Email/iMessage/etc → Go (use --format <id>)")
    print("\nUse --format <id> to force a specific parser (bypasses auto-detection).")
    print("Use --engine go or --engine python to constrain engine choice.")


def main():
    parser = argparse.ArgumentParser(
        description="Manual AI-chat ingest into working.chat_conversation + working.chat_message",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", nargs="?", help="Chat export file to ingest")
    parser.add_argument("--list-formats", action="store_true", help="List supported parser formats")
    parser.add_argument("--format", "-f", help="Force a specific format (bypasses auto-detection)")
    parser.add_argument(
        "--engine",
        "-e",
        default="auto",
        choices=["auto", "python", "go"],
        help="Parser engine (default: auto → Go-primary for known formats)",
    )
    parser.add_argument("--dry-run", "-n", action="store_true", help="Parse only, don't write to PG")
    parser.add_argument("--no-project", action="store_true", help="Store to PG but skip Weaviate/Graphiti sync")
    parser.add_argument("--sync-weaviate", action="store_true", help="Sync pending records to Weaviate")
    parser.add_argument("--sync-graphiti", action="store_true", help="Sync pending records to Graphiti")
    parser.add_argument("--sync-all", action="store_true", help="Sync to both Weaviate and Graphiti")
    parser.add_argument("--classify", action="store_true", help="Run lane classification after storing")
    parser.add_argument(
        "--classify-mode", default="keyword", choices=["keyword", "llm"], help="Classification mode (default: keyword)"
    )
    parser.add_argument("--classify-model", default="glm-5.1", help="Model for LLM classification (default: glm-5.1)")
    parser.add_argument("--max-chars", type=int, default=6000, help="Max chars per chunk (default: 6000)")
    parser.add_argument("--json", action="store_true", help="Output as JSON (for piping)")
    parser.add_argument("--sbv-url", default=None, help="SBV Go service URL (default: auto-discover from compose)")

    args = parser.parse_args()

    if args.list_formats:
        _list_formats()
        return

    if not args.file:
        parser.print_help()
        sys.exit(1)

    fpath = Path(args.file)
    if not fpath.is_file():
        print(f"Error: file not found: {fpath}", file=sys.stderr)
        sys.exit(1)

    print(f"Ingesting: {fpath.name}")
    print(f"Size: {fpath.stat().st_size:,} bytes")
    print(f"Engine: {args.engine}" + (f", Format: {args.format}" if args.format else ""))
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    if args.classify:
        print(f"Classification: {args.classify_mode} ({args.classify_model})")

    # Use the new ingest_chat_file pipeline
    from server.analysis.context_chat_ingest import ingest_chat_file

    t0 = time.time()
    report = asyncio.run(
        ingest_chat_file(
            fpath,
            source_meta=None,
            conversation_ids=None,
            max_chars=args.max_chars,
            dry_run=args.dry_run,
            project=not args.no_project and (args.sync_weaviate or args.sync_graphiti or args.sync_all),
            engine=args.engine,
            format=args.format,
            classify=args.classify,
            classify_mode=args.classify_mode,
            classify_model=args.classify_model,
        )
    )
    elapsed = time.time() - t0

    print(f"\n{'Total time':>14}: {elapsed:.1f}s")
    print(f"{'Parsed':>14}: {report.record_count} records")
    print(f"{'Parser':>14}: {report.parser_id}")
    print(f"{'Stored to PG':>14}: {report.records_stored} records")
    if report.classified:
        print(f"{'Classified':>14}: yes ({args.classify_mode})")
    if report.weaviate_chunks > 0 or report.graphiti_chunks > 0:
        print(f"{'Weaviate':>14}: {report.weaviate_chunks} chunks, {report.weaviate_records_synced} records synced")
        print(f"{'Graphiti':>14}: {report.graphiti_chunks} chunks, {report.graphiti_records_synced} records synced")
    print(f"{'Conversations':>14}: {len(report.conversation_ids)}")

    if args.json:
        print(
            json.dumps(
                {
                    "file": str(fpath),
                    "records_parsed": report.record_count,
                    "records_stored": report.records_stored,
                    "classified": report.classified,
                    "weaviate_chunks": report.weaviate_chunks,
                    "weaviate_records_synced": report.weaviate_records_synced,
                    "graphiti_chunks": report.graphiti_chunks,
                    "graphiti_records_synced": report.graphiti_records_synced,
                    "conversation_ids": report.conversation_ids,
                    "dry_run": report.dry_run,
                }
            )
        )
    else:
        print("\nDone. Records are in working.chat_conversation + working.chat_message (PG source of truth).")
        if not args.classify:
            print("Run with --classify to add lane classification before sync.")
        if not (args.sync_weaviate or args.sync_graphiti or args.sync_all):
            print("To sync to Weaviate/Graphiti, re-run with --sync-all")


if __name__ == "__main__":
    main()
