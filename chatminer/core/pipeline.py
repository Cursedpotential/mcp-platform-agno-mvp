"""
chatminer.core.pipeline — top-level parse entry points.

The package's public API (`from chatminer import parse_file, parse_multiple,
parse_directory`) and the module docstring promise these three functions, but
the module was never created — importing ``chatminer`` raised ImportError.
This restores them as thin orchestration over the existing parser registry
(`get_parser_for_file`) and ``BaseParser.parse_file``; no new parsing logic.

Each function returns a single aggregated ``ParseResult`` (the same type the
CLI and MCP tools already consume). Files with no matching parser are recorded
in ``result.errors`` rather than raising, so a bad file in a batch never aborts
the run.
"""

from __future__ import annotations

from pathlib import Path

from chatminer.core.types import ParseResult
from chatminer.parsers import PARSER_REGISTRY, get_parser_for_file


def _parser_for_source_hint(source_hint: str):
    """Return an instance of the registered parser the hint identifies, or None.

    Resolution is exact-match-first (case-insensitive on SOURCE_NAME). A
    substring match is only accepted when it is *unambiguous* — e.g. "chatgpt"
    matches both ``chatgpt_official`` and ``chatgpt_share``, so it resolves to
    neither (returns None) rather than silently picking the first by registry
    order and misrouting the file.
    """
    from chatminer.core.base import ParserConfig

    hint = source_hint.lower()
    by_name = {getattr(c, "SOURCE_NAME", "").lower(): c for c in PARSER_REGISTRY if getattr(c, "SOURCE_NAME", "")}

    parser_cls = by_name.get(hint)
    if parser_cls is None:
        candidates = [c for name, c in by_name.items() if hint in name]
        if len(candidates) == 1:
            parser_cls = candidates[0]

    return parser_cls(ParserConfig()) if parser_cls is not None else None


def parse_file(path: str | Path, source_hint: str | None = None) -> ParseResult:
    """Parse a single file into a ``ParseResult``.

    Picks the parser explicitly via ``source_hint`` (e.g. "chatgpt", "claude_code")
    when given, otherwise auto-detects with ``get_parser_for_file``. A file that
    no parser can handle yields a result carrying one entry in ``errors``.
    """
    path = Path(path)

    parser = _parser_for_source_hint(source_hint) if source_hint else get_parser_for_file(str(path))
    if parser is None:
        return ParseResult(errors=[{"file": str(path), "error": "no parser matched"}])

    return parser.parse_file(path)


def parse_multiple(paths: list[str | Path], source_hint: str | None = None) -> ParseResult:
    """Parse many files into one aggregated ``ParseResult``."""
    combined = ParseResult()
    for p in paths:
        result = parse_file(p, source_hint=source_hint)
        combined.conversations.extend(result.conversations)
        combined.artifacts.extend(result.artifacts)
        combined.segments.extend(result.segments)
        combined.errors.extend(result.errors)
    return combined


def parse_directory(
    directory: str | Path,
    recursive: bool = False,
    pattern: str = "*",
    source_hint: str | None = None,
) -> ParseResult:
    """Parse every file in a directory (optionally recursing) into one result."""
    directory = Path(directory)
    if not directory.is_dir():
        return ParseResult(errors=[{"file": str(directory), "error": "not a directory"}])

    globber = directory.rglob if recursive else directory.glob
    files = sorted(p for p in globber(pattern) if p.is_file())
    return parse_multiple(list(files), source_hint=source_hint)
