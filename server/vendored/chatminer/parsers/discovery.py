"""
chatminer.parsers.discovery — scan a directory and report which transcript
parser (if any) claims each file.

Backs the CLI `discover` command (chatminer/cli/main.py). The command imported
this module, but it was never created — so `chatminer discover` raised
ImportError. Implemented as a thin layer over the existing auto-detector
(`get_parser_for_file`); no new parsing logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from server.vendored.chatminer.parsers import get_parser_for_file

# Text-ish suffixes worth probing — skip binaries/media outright.
_CANDIDATE_SUFFIXES = {".md", ".txt", ".json", ".jsonl", ".html", ".htm", ".csv"}


@dataclass
class DiscoveryResult:
    """One scanned file and the parser that claimed it (None = unrecognized)."""

    path: Path
    source_name: str | None


def discover_transcripts(root: str | Path, recursive: bool = False) -> list[DiscoveryResult]:
    """Walk ``root`` and classify each candidate file via the parser registry."""
    root = Path(root)
    walker = root.rglob("*") if recursive else root.glob("*")

    results: list[DiscoveryResult] = []
    for path in sorted(walker):
        if not path.is_file() or path.suffix.lower() not in _CANDIDATE_SUFFIXES:
            continue
        parser = get_parser_for_file(str(path))
        source_name = parser.SOURCE_NAME if parser is not None else None
        results.append(DiscoveryResult(path=path, source_name=source_name))
    return results


def print_discovery_report(results: list[DiscoveryResult]) -> None:
    """Print a grouped summary of a ``discover_transcripts`` run."""
    if not results:
        print("No candidate transcript files found.")
        return

    by_parser: dict[str, list[DiscoveryResult]] = {}
    unknown: list[DiscoveryResult] = []
    for result in results:
        if result.source_name is None:
            unknown.append(result)
        else:
            by_parser.setdefault(result.source_name, []).append(result)

    recognized = len(results) - len(unknown)
    print(f"Scanned {len(results)} candidate file(s): {recognized} recognized, {len(unknown)} unrecognized.\n")

    for source_name in sorted(by_parser):
        rows = by_parser[source_name]
        print(f"  {source_name} ({len(rows)}):")
        for row in rows:
            print(f"    - {row.path}")

    if unknown:
        print(f"\n  unrecognized ({len(unknown)}):")
        for row in unknown:
            print(f"    - {row.path}")
