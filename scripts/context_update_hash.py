#!/usr/bin/env python3
# Byline: Codex · GPT-5 · 2026-08-27
"""Update the freshness hash of a context file after manual review.

Reads the file's watches globs, recomputes the hash from current git state,
and updates the watches_hash and last_verified fields in-place.

Usage:
    uv run python scripts/context_update_hash.py <file-path>

Requires: git in PATH.
"""

import re
import sys
from datetime import date
from pathlib import Path

from context_lib import (
    FRESHNESS_PATTERN_GROUPS,
    compute_hash,
    find_git_root,
    parse_watches,
)


def main():
    if len(sys.argv) < 2:
        print("Usage: context_update_hash.py <file-path>", file=sys.stderr)
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    content = filepath.read_text(encoding="utf-8")
    match = FRESHNESS_PATTERN_GROUPS.search(content)

    if not match:
        print(f"Error: no freshness marker found in {filepath}", file=sys.stderr)
        sys.exit(1)

    block = match.group(2)
    watches = parse_watches(block)

    if not watches:
        print(f"Error: no watches found in freshness marker of {filepath}", file=sys.stderr)
        sys.exit(1)

    git_root = find_git_root()
    new_hash = compute_hash(git_root, watches)
    today = date.today().isoformat()

    new_block = re.sub(
        r"watches_hash:\s*\S+",
        f"watches_hash: {new_hash}",
        block,
    )
    new_block = re.sub(
        r"last_verified:\s*\S+",
        f"last_verified: {today}",
        new_block,
    )

    new_content = content[: match.start(2)] + new_block + content[match.end(2) :]
    filepath.write_text(new_content, encoding="utf-8")

    print(f"Updated {filepath}")
    print(f"  watches_hash: {new_hash}")
    print(f"  last_verified: {today}")
    print(f"  watches: {', '.join(watches)}")


if __name__ == "__main__":
    main()
