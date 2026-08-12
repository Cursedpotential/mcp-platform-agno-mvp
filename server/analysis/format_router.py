"""server/analysis/format_router.py — the detection ROUTER for chat parsing.

Owner, 2026-08-12: "I thought we were designing a router so that the whole
fail-through doesn't have to be in a row like failing each one." Right — instead
of running every `parse.transcript` parser in registration order until one
stops raising, the router reads a signature ONCE and dispatches to the correct
parser + engine.

It is signature-based: read a bounded head of the file, check which format's
markers are ALL present, and return that format's canonical id, its Python
parser id, and its preferred ENGINE. **Go is the primary route** — a format is
routed to the SBV Go engine whenever a Go decoder exists for it (memory-safe);
otherwise Python. As Go decoders are added (a `go_format` below), that format
auto-upgrades to Go with no caller change.

Detection is only the DEFAULT (`engine="auto"`); an explicit `engine=`/`format=`
override always wins (the MVP escape hatch). On no match, the caller falls back
to the full registry mesh as a last resort — so an unknown format still gets a
best-effort parse, it just isn't the primary path.
"""
# Byline: Claude Code · Opus 4.8 · 2026-08-12

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_HEAD_BYTES = 65536  # enough to see the first conversation's keys in any known export


@dataclass(frozen=True)
class FormatSig:
    """One recognisable export format. `markers` must ALL appear in the head
    for a match. `go_format` is the SBV importer id if a Go decoder exists
    (=> Go-primary), else None (=> Python)."""

    format_id: str
    markers: tuple[str, ...]
    python_parser_id: str
    go_format: str | None = None


# Order = specificity (most specific first). A file that matches an earlier sig
# never reaches a later one; markers are chosen so real files match exactly one.
SIGNATURES: tuple[FormatSig, ...] = (
    FormatSig("chatgpt-official", ('"mapping"', '"create_time"'), "transcripts.chatgpt-official", "chatgpt-official-json"),
    FormatSig("perplexity-contexts", ('"context_uuid"', '"entries"', '"query"', '"answer"'), "transcripts.perplexity-contexts"),
    FormatSig("claude-ai-export", ('"chat_messages"',), "transcripts.claude-ai-export"),
)


@dataclass(frozen=True)
class Detection:
    format_id: str | None  # None => unknown (caller falls back to the registry mesh)
    python_parser_id: str | None
    engine: str  # "go" | "python"
    parse_format: str | None  # the format string to hand the chosen engine (SBV id for go)
    confidence: float
    matched_markers: tuple[str, ...] = ()


def _read_head(path: Path) -> str:
    with open(path, "rb") as f:
        return f.read(_HEAD_BYTES).decode("utf-8", "replace")


def detect_format(path: str | Path, *, head: str | None = None) -> Detection:
    """Detect the export format from a bounded head sample. Returns the winning
    format's parser id + preferred engine (Go-primary), or an unknown Detection
    (format_id=None) if nothing matches."""
    if head is None:
        head = _read_head(Path(path))
    for sig in SIGNATURES:
        if all(m in head for m in sig.markers):
            engine = "go" if sig.go_format else "python"
            parse_format = sig.go_format if engine == "go" else sig.format_id
            return Detection(
                format_id=sig.format_id,
                python_parser_id=sig.python_parser_id,
                engine=engine,
                parse_format=parse_format,
                confidence=1.0,
                matched_markers=sig.markers,
            )
    return Detection(format_id=None, python_parser_id=None, engine="python", parse_format=None, confidence=0.0)
