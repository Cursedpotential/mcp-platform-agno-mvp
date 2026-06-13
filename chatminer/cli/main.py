#!/usr/bin/env python3
"""
ChatMiner CLI — command-line interface for conversation parsing.

Subcommands:
    parse       Parse a single chat export file
    batch       Batch parse a directory of chat exports
    segment     Segment parsed messages by topic
    artifacts   Extract artifacts (code, docs, URLs) from parsed messages
    discover    Find all chat exports in a directory
    pipeline    Full pipeline: parse → segment → extract → save

Usage:
    # Parse a single file (auto-detect format)
    python -m chatminer parse chat_export.md -o output.json

    # Parse with explicit source hint
    python -m chatminer parse chat_export.md --source chatgpt_share -o output.json

    # Batch parse a directory
    python -m chatminer batch ./conversations/ --recursive -o ./parsed/

    # Segment parsed messages by topic
    python -m chatminer segment parsed.json --method local -o segments.json

    # Extract artifacts
    python -m chatminer artifacts parsed.json -o artifacts.json

    # Full pipeline
    python -m chatminer pipeline ./conversations/ --recursive \
        --segment --extract-artifacts -o ./output/

    # Discover chat files
    python -m chatminer discover ./conversations/ --recursive
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from chatminer.core.artifacts import extract_artifacts
from chatminer.core.types import ParseResult
from chatminer.parsers import get_parser_for_file, PARSER_REGISTRY
from chatminer.segmenters import get_segmenter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("chatminer")


def cmd_parse(args: argparse.Namespace) -> int:
    """Parse a single chat export file."""
    path = Path(args.input)
    if not path.exists():
        logger.error(f"File not found: {path}")
        return 1

    # Auto-detect or use explicit source
    if args.source:
        # Find parser by source name
        parser = None
        for parser_cls in PARSER_REGISTRY:
            if parser_cls.SOURCE_NAME == args.source:
                parser = parser_cls()
                break
        if not parser:
            logger.error(f"Unknown source: {args.source}")
            return 1
    else:
        parser = get_parser_for_file(str(path))
        if not parser:
            logger.error(f"Could not auto-detect format for {path}")
            return 1
        logger.info(f"Auto-detected format: {parser.SOURCE_NAME}")

    # Parse
    result = parser.parse_file(path)

    # Print summary
    for conv in result.conversations:
        print(f"  {conv.title or 'Untitled'}: {conv.message_count} messages")
    if result.errors:
        for err in result.errors:
            print(f"  ERROR: {err['file']}: {err['error']}")

    # Save
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(result.to_json(), encoding="utf-8")
        logger.info(f"Saved to {out_path}")

    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """Batch parse a directory of chat exports."""
    root = Path(args.input)
    if not root.exists():
        logger.error(f"Directory not found: {root}")
        return 1

    result = ParseResult()

    # Find all files
    if args.recursive:
        files = list(root.rglob("*"))
    else:
        files = list(root.iterdir())

    files = [f for f in files if f.is_file()]
    logger.info(f"Found {len(files)} files in {root}")

    parsed_count = 0
    for f in files:
        parser = get_parser_for_file(str(f))
        if not parser:
            continue

        logger.info(f"Parsing: {f.name} ({parser.SOURCE_NAME})")
        file_result = parser.parse_file(f)

        result.conversations.extend(file_result.conversations)
        result.errors.extend(file_result.errors)
        parsed_count += 1

    logger.info(
        f"Parsed {parsed_count} files, "
        f"{result.total_conversations} conversations, "
        f"{result.total_messages} messages"
    )

    if args.output:
        out_path = Path(args.output)
        out_path.mkdir(parents=True, exist_ok=True)
        out_file = out_path / "parsed_conversations.json"
        out_file.write_text(result.to_json(), encoding="utf-8")
        logger.info(f"Saved to {out_file}")

    return 0


def cmd_segment(args: argparse.Namespace) -> int:
    """Segment parsed messages by topic."""
    path = Path(args.input)
    if not path.exists():
        logger.error(f"File not found: {path}")
        return 1

    # Load parsed conversations
    data = json.loads(path.read_text())
    conversations = data.get("conversations", [data] if "messages" in data else [])

    # Get segmenter
    segmenter = get_segmenter(args.method)

    all_segments = []
    for conv_data in conversations:
        from chatminer.core.types import ParsedMessage

        messages = [ParsedMessage.from_dict(m) for m in conv_data.get("messages", [])]
        if not messages:
            continue

        segments = segmenter.segment(messages)
        for seg in segments:
            print(
                f"  [{seg.topic_tag.value:15s}] "
                f"{seg.message_count:3d} msgs  "
                f"conf={seg.topic_confidence:.2f}  "
                f"keywords={seg.keywords[:3]}"
            )
        all_segments.extend(segments)

    logger.info(f"Created {len(all_segments)} segments")

    if args.output:
        out_path = Path(args.output)
        segments_data = [s.to_dict() for s in all_segments]
        out_path.write_text(
            json.dumps(segments_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Saved to {out_path}")

    return 0


def cmd_artifacts(args: argparse.Namespace) -> int:
    """Extract artifacts from parsed messages."""
    path = Path(args.input)
    if not path.exists():
        logger.error(f"File not found: {path}")
        return 1

    data = json.loads(path.read_text())
    conversations = data.get("conversations", [data] if "messages" in data else [])

    all_artifacts = []
    for conv_data in conversations:
        from chatminer.core.types import ParsedMessage

        messages = [ParsedMessage.from_dict(m) for m in conv_data.get("messages", [])]
        if not messages:
            continue

        artifacts = extract_artifacts(messages)

        # Print summary
        from collections import Counter

        types = Counter(a.artifact_type.value for a in artifacts)
        print(f"  Found {len(artifacts)} artifacts:")
        for t, c in types.most_common():
            print(f"    {t}: {c}")

        all_artifacts.extend(artifacts)

    if args.output:
        out_path = Path(args.output)
        artifacts_data = [a.to_dict() for a in all_artifacts]
        out_path.write_text(
            json.dumps(artifacts_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Saved to {out_path}")

    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    """Find all chat exports in a directory."""
    root = Path(args.input)
    if not root.exists():
        logger.error(f"Directory not found: {root}")
        return 1

    from chatminer.parsers.discovery import discover_transcripts, print_discovery_report

    results = discover_transcripts(root, recursive=args.recursive)
    print_discovery_report(results)

    return 0


def cmd_pipeline(args: argparse.Namespace) -> int:
    """Full pipeline: parse → segment → extract → save."""
    root = Path(args.input)
    if not root.exists():
        logger.error(f"Directory not found: {root}")
        return 1

    out_dir = Path(args.output) if args.output else Path("./chatminer_output")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Parse
    logger.info("=" * 60)
    logger.info("STEP 1: Parsing")
    logger.info("=" * 60)

    result = ParseResult()
    files = list(root.rglob("*") if args.recursive else root.iterdir())
    files = [f for f in files if f.is_file()]

    for f in files:
        parser = get_parser_for_file(str(f))
        if not parser:
            continue
        file_result = parser.parse_file(f)
        result.conversations.extend(file_result.conversations)
        result.errors.extend(file_result.errors)

    logger.info(
        f"Parsed {result.total_conversations} conversations, "
        f"{result.total_messages} messages"
    )

    # Save parsed
    parsed_file = out_dir / "01_parsed.json"
    parsed_file.write_text(result.to_json(), encoding="utf-8")
    logger.info(f"Saved parsed to {parsed_file}")

    # Step 2: Segment (if requested)
    if args.segment:
        logger.info("=" * 60)
        logger.info("STEP 2: Topic Segmentation")
        logger.info("=" * 60)

        segmenter = get_segmenter(args.segment_method)
        all_segments = []

        for conv in result.conversations:
            segments = segmenter.segment(conv.messages)
            all_segments.extend(segments)

        # Save segments
        segments_file = out_dir / "02_segments.json"
        segments_data = [s.to_dict() for s in all_segments]
        segments_file.write_text(
            json.dumps(segments_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Created {len(all_segments)} segments")
        logger.info(f"Saved segments to {segments_file}")

    # Step 3: Extract artifacts (if requested)
    if args.extract_artifacts:
        logger.info("=" * 60)
        logger.info("STEP 3: Artifact Extraction")
        logger.info("=" * 60)

        all_artifacts = []
        for conv in result.conversations:
            artifacts = extract_artifacts(conv.messages)
            all_artifacts.extend(artifacts)

        # Save artifacts
        artifacts_file = out_dir / "03_artifacts.json"
        artifacts_data = [a.to_dict() for a in all_artifacts]
        artifacts_file.write_text(
            json.dumps(artifacts_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"Extracted {len(all_artifacts)} artifacts")
        logger.info(f"Saved artifacts to {artifacts_file}")

    logger.info("=" * 60)
    logger.info("Pipeline complete!")
    logger.info(f"Output directory: {out_dir}")
    logger.info("=" * 60)

    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ChatMiner — AI conversation parser and analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # --- parse ---
    parse_p = subparsers.add_parser("parse", help="Parse a single chat export file")
    parse_p.add_argument("input", help="Input file path")
    parse_p.add_argument("-o", "--output", help="Output JSON file")
    parse_p.add_argument("--source", help="Source format hint (e.g. chatgpt_share)")

    # --- batch ---
    batch_p = subparsers.add_parser("batch", help="Batch parse a directory")
    batch_p.add_argument("input", help="Input directory")
    batch_p.add_argument("-o", "--output", help="Output directory")
    batch_p.add_argument("-r", "--recursive", action="store_true", help="Recurse into subdirectories")

    # --- segment ---
    seg_p = subparsers.add_parser("segment", help="Segment parsed messages by topic")
    seg_p.add_argument("input", help="Parsed JSON file")
    seg_p.add_argument("-o", "--output", help="Output JSON file")
    seg_p.add_argument("--method", default="local", choices=["local", "colab", "configurable"])

    # --- artifacts ---
    art_p = subparsers.add_parser("artifacts", help="Extract artifacts from parsed messages")
    art_p.add_argument("input", help="Parsed JSON file")
    art_p.add_argument("-o", "--output", help="Output JSON file")

    # --- discover ---
    disc_p = subparsers.add_parser("discover", help="Find all chat exports in a directory")
    disc_p.add_argument("input", help="Directory to scan")
    disc_p.add_argument("-r", "--recursive", action="store_true")

    # --- pipeline ---
    pipe_p = subparsers.add_parser("pipeline", help="Full pipeline: parse → segment → extract")
    pipe_p.add_argument("input", help="Input directory")
    pipe_p.add_argument("-o", "--output", help="Output directory")
    pipe_p.add_argument("-r", "--recursive", action="store_true")
    pipe_p.add_argument("--segment", action="store_true", help="Run topic segmentation")
    pipe_p.add_argument("--segment-method", default="local", choices=["local", "colab", "configurable"])
    pipe_p.add_argument("--extract-artifacts", action="store_true", help="Extract artifacts")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "parse": cmd_parse,
        "batch": cmd_batch,
        "segment": cmd_segment,
        "artifacts": cmd_artifacts,
        "discover": cmd_discover,
        "pipeline": cmd_pipeline,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
