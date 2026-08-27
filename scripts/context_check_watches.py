#!/usr/bin/env python3
# Byline: Codex · GPT-5 · 2026-08-27
"""Check if modified files affect any freshness-tracked context files.

Takes one or more file paths (files that were modified) and checks if they
match any watch globs in freshness-tracked context files. Designed to be
fast and silent for git hooks — only prints warnings when matches are found.

Usage:
    uv run python scripts/context_check_watches.py <file1> [file2] ...

Exit code is always 0 (warnings are informational, never block commits).
Requires: git in PATH.
"""

import sys
from context_lib import (
    FRESHNESS_PATTERN,
    find_context_files,
    find_git_root,
    matches_watch,
    parse_watches,
)


def find_tracked_context_files(git_root):
    """Find all context files with freshness markers, return (path, watches) pairs."""
    results = []
    for fpath in find_context_files(git_root):
        try:
            content = fpath.read_text(encoding="utf-8")
        except OSError:
            continue
        match = FRESHNESS_PATTERN.search(content)
        if match:
            watches = parse_watches(match.group(1))
            if watches:
                results.append((fpath, watches))
    return results


def main():
    if len(sys.argv) < 2:
        sys.exit(0)

    modified_files = sys.argv[1:]
    git_root = find_git_root(exit_on_error=False)
    tracked = find_tracked_context_files(git_root)

    if not tracked:
        sys.exit(0)

    for context_file, watches in tracked:
        matched = False
        for modified in modified_files:
            for glob_pattern in watches:
                if matches_watch(modified, glob_pattern):
                    try:
                        rel_context = context_file.relative_to(git_root)
                    except ValueError:
                        rel_context = context_file
                    print(f"[context] Warning: {rel_context} may be stale (watched file changed: {modified})")
                    matched = True
                    break
            if matched:
                break

    sys.exit(0)


if __name__ == "__main__":
    main()
