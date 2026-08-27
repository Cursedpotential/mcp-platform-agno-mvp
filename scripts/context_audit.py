#!/usr/bin/env python3
# Byline: Codex · GPT-5 · 2026-08-27
"""Audit freshness of all AI context files in a repository.

Scans the AGENT_MEMORY.md and exact-file .agent-memory hierarchy,
reads their freshness markers, computes current hashes from watched files,
and reports which context files are stale.

Usage:
    uv run python scripts/context_audit.py [--root <git-root>]

Exit code is always 0 (report is informational).
Requires: git in PATH.
"""

import subprocess
import sys
from context_lib import (
    compute_hash,
    find_context_files,
    find_git_root,
    matches_watch,
    parse_freshness_marker,
)


def get_changed_files(git_root, watch_globs):
    """Get list of watched files that have changed recently (last 5 commits)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~5..HEAD", "--"],
            capture_output=True,
            text=True,
            check=False,
            cwd=git_root,
        )
        if result.returncode != 0:
            return []
        changed = result.stdout.strip().splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    matched = []
    for f in changed:
        for glob_pattern in watch_globs:
            if matches_watch(f, glob_pattern):
                matched.append(f)
                break
    return matched


def main():
    root_arg = None
    args = sys.argv[1:]
    if "--root" in args:
        idx = args.index("--root")
        if idx + 1 < len(args):
            root_arg = args[idx + 1]

    git_root = find_git_root(root_arg or ".")
    context_files = find_context_files(git_root)

    if not context_files:
        print("No context files found matching known patterns.")
        return

    stale_count = 0
    ok_count = 0
    missing_count = 0
    hold_count = 0

    print("CONTEXT FRESHNESS REPORT")
    print("========================")

    for filepath in context_files:
        rel_path = filepath.relative_to(git_root)

        try:
            content = filepath.read_text(encoding="utf-8")
        except OSError as e:
            print(f"ERROR  {rel_path}")
            print(f"       could not read: {e}")
            continue

        marker = parse_freshness_marker(content)

        if marker is None:
            missing_count += 1
            print(f"NONE   {rel_path}")
            print("       no freshness marker found")
            print()
            continue

        stored_hash = marker["watches_hash"]
        current_hash = compute_hash(git_root, marker["watches"])
        last_verified = marker.get("last_verified", "unknown")

        if stored_hash == current_hash == "0000000":
            hold_count += 1
            print(f"HOLD   {rel_path}")
            print("       no tracked files match the declared watches")
            print(f"       last_verified: {last_verified}")
        elif stored_hash != current_hash:
            stale_count += 1
            print(f"STALE  {rel_path}")
            print(f"       watches_hash: {stored_hash} -> {current_hash} (changed)")
            print(f"       last_verified: {last_verified}")
            changed = get_changed_files(git_root, marker["watches"])
            if changed:
                print("       changed files:")
                for cf in changed[:10]:
                    print(f"         - {cf}")
                if len(changed) > 10:
                    print(f"         ... and {len(changed) - 10} more")
        else:
            ok_count += 1
            print(f"OK     {rel_path}")
            print(f"       watches_hash: {stored_hash} (unchanged)")
            print(f"       last_verified: {last_verified}")

        print()

    print(f"Summary: {stale_count} stale, {ok_count} current, {hold_count} hold, {missing_count} missing markers")


if __name__ == "__main__":
    main()
