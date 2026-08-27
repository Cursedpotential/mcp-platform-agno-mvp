#!/usr/bin/env python3
# Byline: Codex · GPT-5 · 2026-08-27
"""Bootstrap freshness tracking for context files.

Two modes:
  1. Add marker:  uv run python scripts/context_bootstrap.py <file> "glob1" ...
     Appends a freshness marker to the file with computed initial hash.

  2. Scan mode:   uv run python scripts/context_bootstrap.py --scan <directory>
     Finds all .md files in the directory tree that lack freshness markers.

Idempotent: if a marker already exists, prints a message and exits.

Requires: git in PATH.
"""

import os
import sys
from pathlib import Path

from context_lib import (
    build_marker,
    compute_hash,
    find_git_root,
    has_freshness_marker,
)


def add_marker(filepath: Path, watch_globs: list[str]) -> None:
    """Add a freshness marker to a file."""
    content = filepath.read_text(encoding="utf-8")

    if has_freshness_marker(content):
        print(f"Already tracked: {filepath}")
        return

    git_root = find_git_root()
    watches_hash = compute_hash(git_root, watch_globs)
    marker = build_marker(watches_hash, watch_globs)

    if not content.endswith("\n"):
        content += "\n"
    content += marker

    filepath.write_text(content, encoding="utf-8")
    print(f"Added freshness marker to {filepath}")
    print(f"  watches_hash: {watches_hash}")
    print(f"  watches: {', '.join(watch_globs)}")


def scan_directory(directory: Path) -> None:
    """Find all .md files without freshness markers."""
    found = []
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            if not fname.endswith(".md"):
                continue
            fpath = Path(root) / fname
            try:
                content = fpath.read_text(encoding="utf-8")
                if not has_freshness_marker(content):
                    found.append(fpath)
            except OSError:
                continue

    if not found:
        print("All .md files already have freshness markers (or none found).")
        return

    print(f"Found {len(found)} .md file(s) without freshness markers:\n")
    for f in sorted(found):
        try:
            rel = f.relative_to(directory)
        except ValueError:
            rel = f
        print(f"  {rel}")

    print("\nTo add tracking, run:")
    print('  uv run python scripts/context_bootstrap.py <file> "src/**" "other/glob"')


def main():
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            '  context_bootstrap.py <file> "glob1" "glob2" ...  — add marker\n'
            "  context_bootstrap.py --scan <directory>           — find untracked files",
            file=sys.stderr,
        )
        sys.exit(1)

    if sys.argv[1] == "--scan":
        directory = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        if not directory.is_dir():
            print(f"Error: not a directory: {directory}", file=sys.stderr)
            sys.exit(1)
        scan_directory(directory)
    else:
        filepath = Path(sys.argv[1])
        if not filepath.exists():
            print(f"Error: file not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        watch_globs = sys.argv[2:]
        if not watch_globs:
            print("Error: at least one watch glob is required", file=sys.stderr)
            sys.exit(1)
        add_marker(filepath, watch_globs)


if __name__ == "__main__":
    main()
