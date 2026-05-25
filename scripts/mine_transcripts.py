#!/usr/bin/env python3
"""Batch transcript mining script.

Walks a directory of chat transcripts, chunks them intelligently,
and sends each chunk to the transcript_miner agent via the API.

Usage:
    # Mine a single file
    python scripts/mine_transcripts.py /path/to/chat-export.txt --source "chatgpt-june-2024"

    # Batch mine a directory
    python scripts/mine_transcripts.py /path/to/transcripts/ --batch --recursive

    # Dry run (extract without storing)
    python scripts/mine_transcripts.py /path/to/chat.txt --source "test" --dry-run

    # Custom chunk size
    python scripts/mine_transcripts.py /path/to/chat.txt --chunk-size 6000

Environment:
    Set PLATFORM_API_URL (default: http://localhost:8000)
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

import httpx

# Allow imports from the project root (lib.chunking)
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.chunking import detect_format, estimate_tokens, smart_chunk

DEFAULT_API_URL = os.getenv("PLATFORM_API_URL", "http://localhost:8000")

# File extensions we recognize as chat transcripts
TRANSCRIPT_EXTENSIONS = {".txt", ".md", ".json", ".html", ".htm"}

# Max file size in MB
MAX_FILE_MB = 50


async def mine_chunk(
    client: httpx.AsyncClient,
    source_name: str,
    chunk: dict,
    dry_run: bool = False,
    chunk_size: int = 8000,
) -> dict:
    """Send a single chunk to the transcript mining API."""
    payload = {
        "sourceName": source_name,
        "content": chunk["content"],
        "chunkSize": chunk_size,
        "dryRun": dry_run,
    }
    resp = await client.post(f"{DEFAULT_API_URL}/v1/transcripts/mine", json=payload)
    resp.raise_for_status()
    return resp.json()


async def process_file(
    file_path: Path,
    source_name: Optional[str] = None,
    dry_run: bool = False,
    chunk_size: int = 8000,
) -> dict:
    """Process a single transcript file."""
    if file_path.stat().st_size > MAX_FILE_MB * 1024 * 1024:
        return {"file": str(file_path), "error": f"File exceeds {MAX_FILE_MB}MB limit", "insights": 0}

    content = file_path.read_text(encoding="utf-8", errors="replace")
    if not content.strip():
        return {"file": str(file_path), "error": "Empty file", "insights": 0}

    # Auto-generate source name from filename if not provided
    if not source_name:
        source_name = file_path.stem.lower().replace(" ", "-")

    fmt = detect_format(content, file_path.suffix)
    print(f"  Format: {fmt}, Size: {len(content):,} chars (~{estimate_tokens(content):,} tokens)")

    # Chunk the content
    chunks = smart_chunk(content, chunk_size)
    print(f"  Split into {len(chunks)} chunk(s)")

    # Process each chunk
    all_insights = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        for i, chunk in enumerate(chunks):
            print(f"    Processing chunk {i + 1}/{len(chunks)} ({estimate_tokens(chunk['content']):,} tokens)...", end=" ")
            try:
                result = await mine_chunk(client, source_name, chunk, dry_run, chunk_size)
                count = result.get("insightsExtracted", 0)
                all_insights.extend(result.get("insights", []))
                print(f"OK ({count} insights)")
            except Exception as e:
                print(f"ERROR: {e}")

    return {
        "file": str(file_path),
        "source": source_name,
        "format": fmt,
        "chunks": len(chunks),
        "insights": len(all_insights),
        "dry_run": dry_run,
    }


async def batch_process(
    directory: Path,
    recursive: bool = False,
    dry_run: bool = False,
    chunk_size: int = 8000,
) -> list[dict]:
    """Process all transcript files in a directory."""
    pattern = "**/*" if recursive else "*"
    files = [
        f for f in directory.glob(pattern)
        if f.is_file() and f.suffix.lower() in TRANSCRIPT_EXTENSIONS
    ]

    if not files:
        print(f"No transcript files found in {directory}")
        return []

    print(f"Found {len(files)} transcript file(s) in {directory}")
    results = []
    for f in files:
        print(f"\nProcessing: {f.name}")
        result = await process_file(f, dry_run=dry_run, chunk_size=chunk_size)
        results.append(result)

    return results


def print_summary(results: list[dict]):
    """Print a summary of all processed files."""
    print("\n" + "=" * 60)
    print("TRANSCRIPT MINING SUMMARY")
    print("=" * 60)

    total_files = len(results)
    total_insights = sum(r.get("insights", 0) for r in results)
    errors = [r for r in results if r.get("error")]

    print(f"Files processed: {total_files}")
    print(f"Total insights:  {total_insights}")
    print(f"Errors:          {len(errors)}")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  {e['file']}: {e['error']}")

    print("\nBy file:")
    for r in results:
        status = "OK" if not r.get("error") else "ERR"
        print(f"  [{status}] {Path(r['file']).name:40s} -> {r.get('insights', 0):3d} insights")

    print("=" * 60)


async def main():
    global DEFAULT_API_URL  # must be at top of function scope

    parser = argparse.ArgumentParser(description="Batch mine AI chat transcripts for structured insights")
    parser.add_argument("path", help="Path to transcript file or directory")
    parser.add_argument("--source", default=None, help="Source name override")
    parser.add_argument("--batch", action="store_true", help="Process directory of transcripts")
    parser.add_argument("--recursive", "-r", action="store_true", help="Recurse into subdirectories")
    parser.add_argument("--dry-run", action="store_true", help="Extract without storing to DB")
    parser.add_argument("--chunk-size", type=int, default=8000, help="Max tokens per chunk (default: 8000)")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Platform API base URL")
    args = parser.parse_args()

    DEFAULT_API_URL = args.api_url

    target = Path(args.path)
    if not target.exists():
        print(f"Error: Path not found: {target}")
        sys.exit(1)

    if args.batch or target.is_dir():
        results = await batch_process(
            target, args.recursive, args.dry_run, args.chunk_size
        )
    else:
        result = await process_file(
            target, args.source, args.dry_run, args.chunk_size
        )
        results = [result]

    print_summary(results)

    # Save results to JSON if any insights were found
    total_insights = sum(r.get("insights", 0) for r in results)
    if total_insights > 0:
        out_file = f"transcript_mining_{target.stem}.json"
        with open(out_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nSaved summary to: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
