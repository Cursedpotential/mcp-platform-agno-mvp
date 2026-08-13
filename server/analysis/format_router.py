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

Detection is only the DEFAULT (`engine="auto"`, no explicit `format`); an
explicit `engine=`/`format=` override always wins (the MVP escape hatch). An
explicit `format=` BYPASSES this router entirely (D-053) via
`resolve_format_override()` — strictly, so an unresolvable override errors
loudly instead of silently falling back. On no match, the caller falls back
to the full registry mesh as a last resort — so an unknown format still gets a
best-effort parse, it just isn't the primary path.
"""
# Byline: Claude Code · Opus 4.8 · 2026-08-12
# Byline: Claude Code · Fable 5 · 2026-08-12 (D-053: explicit format/engine override resolver + GO_IMPORTER_FORMATS mirror)

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
    FormatSig(
        "chatgpt-official", ('"mapping"', '"create_time"'), "transcripts.chatgpt-official", "chatgpt-official-json"
    ),
    FormatSig(
        "perplexity-contexts", ('"context_uuid"', '"entries"', '"query"', '"answer"'), "transcripts.perplexity-contexts"
    ),
    FormatSig("claude-ai-export", ('"chat_messages"',), "transcripts.claude-ai-export"),
)

# Stable SBV Go importer ids an explicit `format` override may name — a MIRROR
# of the Format* const block in `vendored/sbv/internal/importer.go` (Python
# cannot read the Go registry, and the SBV service's own /imports validation is
# a network round-trip away; this list enables LOCAL fail-fast validation,
# D-053). MAINTENANCE CONTRACT: when a Go decoder lands in importer.go, add its
# id here in the SAME change.
GO_IMPORTER_FORMATS: tuple[str, ...] = (
    "chatgpt-official-json",  # the only AI-chat Go decoder so far (D-047/D-049)
    "smsbackuprestore-xml",
    "facebook-messenger-json",
    "facebook-messenger-html",
    "google-chat-json",
    "google-voice-html",
    "imessage-txt",
    "imessage-html",
    "messages-transcript",
    "email-eml",
    "email-mbox",
    "ndjson",
    "csv",
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


# ---------------------------------------------------------------------------
# Explicit override (D-053): operator-named format, NO detection involved
# ---------------------------------------------------------------------------


def resolve_format_override(format: str, engine: str = "auto") -> tuple[str, str | None, str | None]:
    """Resolve an EXPLICIT format override (the operator's `--format`, D-053)
    into `(engine, go_format_id, python_tool_id)` — WITHOUT running detection.

    The override is STRICT by contract: the operator named the parser, so an
    unresolvable combination raises ValueError here rather than silently
    falling back to detection, to the registry mesh, or to the other engine.

    Accepted spellings:
      * a SIGNATURES `format_id` ('chatgpt-official', 'claude-ai-export', ...)
      * a Go importer id (GO_IMPORTER_FORMATS, e.g. 'chatgpt-official-json')
      * a Python registry tool id ('transcripts.<name>'; registry validity is
        checked by the caller, which owns `load_builtin_tools()`)

    `engine="go"` / `"python"` constrains the resolution to that engine —
    a format the chosen engine has no decoder/parser for raises ValueError
    listing the valid values. `engine="auto"` resolves Go-primary, the same
    preference `detect_format` encodes (a Go decoder wins when one exists).
    """
    sig = next((s for s in SIGNATURES if s.format_id == format), None)
    go_id = format if format in GO_IMPORTER_FORMATS else (sig.go_format if sig else None)
    py_id = format if format.startswith("transcripts.") else (sig.python_parser_id if sig else None)

    if engine == "go":
        if go_id is None:
            raise ValueError(
                f"engine 'go' has no SBV decoder for format {format!r}; "
                f"Go decoders exist for: {sorted(GO_IMPORTER_FORMATS)}"
            )
        return "go", go_id, None
    if engine == "python":
        if py_id is None:
            raise ValueError(
                f"engine 'python' has no parser for format {format!r}; known python formats: "
                f"{sorted(s.format_id for s in SIGNATURES)} (or a 'transcripts.<name>' registry tool id)"
            )
        return "python", None, py_id
    # auto: Go-primary — the same engine preference the router encodes.
    if go_id is not None:
        return "go", go_id, None
    if py_id is not None:
        return "python", None, py_id
    raise ValueError(
        f"unknown format override {format!r}; known: router formats "
        f"{sorted(s.format_id for s in SIGNATURES)}, Go importer ids {sorted(GO_IMPORTER_FORMATS)}, "
        "or a 'transcripts.<name>' registry tool id"
    )
