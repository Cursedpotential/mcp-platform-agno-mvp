#!/usr/bin/env python3
# Byline: Codex · GPT-5 · 2026-08-27
"""Shared utilities for context freshness tracking scripts.

All context_* scripts import from this module to avoid duplication.
Python 3 stdlib-only — no external dependencies.
"""

import re
import subprocess
import sys
from datetime import date
from fnmatch import fnmatch
from pathlib import Path

FRESHNESS_PATTERN = re.compile(
    r"<!--\s*freshness\s*\n(.*?)\n\s*-->",
    re.DOTALL,
)

FRESHNESS_PATTERN_GROUPS = re.compile(
    r"(<!--\s*freshness\s*\n)(.*?)(\n\s*-->)",
    re.DOTALL,
)


def matches_watch(filepath: str, glob_pattern: str) -> bool:
    """Match a watch glob, allowing ``/**/`` to include zero directories."""
    variants = {glob_pattern}
    collapsed = glob_pattern
    while "/**/" in collapsed:
        collapsed = collapsed.replace("/**/", "/", 1)
        variants.add(collapsed)
    return any(fnmatch(filepath, variant) for variant in variants)


def find_git_root(start: str = ".", *, exit_on_error: bool = True) -> Path:
    """Find the git repository root from a starting directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            cwd=start,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        if exit_on_error:
            print("Error: not inside a git repository", file=sys.stderr)
            sys.exit(1)
        return Path(".")


def find_context_files(git_root: Path) -> list[Path]:
    """Find repository-local progressive memory files.

    Runtime memory lanes and ordinary AGENTS/README files are deliberately
    excluded. This audit covers only the sourced AGENT_MEMORY hierarchy.
    """
    files = set(git_root.rglob("AGENT_MEMORY.md"))
    files.update(git_root.rglob(".agent-memory/*.md"))

    contract = git_root / "docs" / "agent-memory" / "README.md"
    if contract.exists():
        files.add(contract)

    excluded_parts = {".git", "node_modules", "_stale", "to_be_deleted", ".venv"}

    def belongs_to_this_repo(path: Path) -> bool:
        parent = path.parent
        while parent != git_root and git_root in parent.parents:
            if (parent / ".git").exists():
                return False
            parent = parent.parent
        return True

    return sorted(path for path in files if not excluded_parts.intersection(path.parts) and belongs_to_this_repo(path))


def compute_hash(git_root: Path, watch_globs: list[str]) -> str:
    """Compute a content-aware hash from git-tracked files matching watch_globs.

    Uses ``git ls-files -s`` to obtain per-file blob hashes (which change
    when file content changes), filters by watch_globs via fnmatch, then
    hashes the sorted "blob_hash path" pairs.  Returns the first 7 hex chars.

    Note: fnmatch does not treat '/' specially, so both '*' and '**' match
    across directory boundaries.  We standardize on '**' by convention.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "-s"],
            capture_output=True,
            text=True,
            check=True,
            cwd=git_root,
        )
    except subprocess.CalledProcessError:
        return "ERROR"

    matched = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        filepath = parts[1]
        blob_hash = parts[0].split()[1]
        for glob_pattern in watch_globs:
            if matches_watch(filepath, glob_pattern):
                matched.append((filepath, blob_hash))
                break

    if not matched:
        return "0000000"

    matched.sort(key=lambda x: x[0])
    hash_input = "\n".join(f"{h} {p}" for p, h in matched) + "\n"
    try:
        result = subprocess.run(
            ["git", "hash-object", "--stdin"],
            input=hash_input,
            capture_output=True,
            text=True,
            check=True,
            cwd=git_root,
        )
        return result.stdout.strip()[:7]
    except subprocess.CalledProcessError:
        return "ERROR"


def parse_freshness_marker(content: str) -> dict | None:
    """Extract freshness marker data from file content.

    Returns dict with keys: watches_hash, last_verified, watches
    or None if no marker found.
    """
    match = FRESHNESS_PATTERN.search(content)
    if not match:
        return None

    block = match.group(1)
    data = {}

    hash_match = re.search(r"watches_hash:\s*(\S+)", block)
    if hash_match:
        data["watches_hash"] = hash_match.group(1)

    date_match = re.search(r"last_verified:\s*(\S+)", block)
    if date_match:
        data["last_verified"] = date_match.group(1)

    data["watches"] = parse_watches(block)

    return data if data.get("watches_hash") else None


def parse_watches(block: str) -> list[str]:
    """Extract watch glob patterns from a freshness marker block."""
    watches = []
    in_watches = False
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("watches:"):
            in_watches = True
            continue
        if in_watches:
            if stripped.startswith("- "):
                watches.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("-"):
                break
    return watches


def has_freshness_marker(content: str) -> bool:
    """Check if content contains a freshness marker."""
    return bool(FRESHNESS_PATTERN.search(content))


def build_marker(watches_hash: str, watch_globs: list[str]) -> str:
    """Build a freshness marker HTML comment."""
    today = date.today().isoformat()
    watches_lines = "\n".join(f"  - {g}" for g in watch_globs)
    return f"\n<!-- freshness\nwatches_hash: {watches_hash}\nlast_verified: {today}\nwatches:\n{watches_lines}\n-->\n"
