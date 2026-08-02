"""Format routing from a BOUNDED head read.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

CONTENT WINS OVER EXTENSION, ALWAYS. Every corpus in this project has files
whose extension lies: `.txt` holding XML, `.csv` that is really tab-separated,
`.json` that is actually newline-delimited JSON. Routing on `path.suffix` is how
a parser ends up rejecting a file it could have read perfectly.

The extension is used only to break a genuine tie, and when it disagrees with
the content a note is recorded on the Detection so the mismatch is visible
rather than silently resolved.
"""

from __future__ import annotations

import re
from pathlib import Path

from server.tools.repair.encoding import HEAD_BYTES, detect_encoding, read_head, sniff_bom
from server.tools.repair.types import Detection

#: Extension -> format. A hint only; never authoritative.
_EXT_HINT: dict[str, str] = {
    ".xml": "xml",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".jsonl": "ndjson",
    ".ndjson": "ndjson",
    ".csv": "csv",
    ".tsv": "csv",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tif": "image",
    ".tiff": "image",
    ".txt": "",  # says nothing
}

#: Binary magic numbers, checked BEFORE any text heuristic. A PDF starts with
#: "%PDF-" and is not text at all; decoding it and hunting for delimiters would
#: classify it as garbage or, worse, as a CSV.
_BINARY_SIGS: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "image"),
    (b"\xff\xd8\xff", "image"),
    (b"GIF87a", "image"),
    (b"GIF89a", "image"),
    (b"II*\x00", "image"),  # TIFF little-endian
    (b"MM\x00*", "image"),  # TIFF big-endian
    (b"BM", "image"),
    (b"PK\x03\x04", "zip"),  # also .docx/.xlsx/.odt — a container, not our text
)

_XML_DECL = re.compile(rb"^\s*<\?xml[\s?]", re.IGNORECASE)
_HTML_HINT = re.compile(rb"^\s*(<!doctype\s+html|<html[\s>])", re.IGNORECASE)
_OPEN_TAG = re.compile(rb"^\s*<[A-Za-z_]")
_CANDIDATE_DELIMS = (",", "\t", ";", "|")


def _strip_bom(sample: bytes) -> bytes:
    bom = sniff_bom(sample)
    if bom == "utf-8-sig":
        return sample[3:]
    if bom and bom.startswith("utf-16"):
        return sample[2:]
    if bom and bom.startswith("utf-32"):
        return sample[4:]
    return sample


def _looks_ndjson(text: str) -> bool:
    """Two or more consecutive lines that each parse as a standalone object.

    Checked before plain JSON: an NDJSON file also starts with '{', so testing
    for JSON first would claim every NDJSON export and then fail to parse it.
    """
    lines = [ln for ln in text.splitlines()[:20] if ln.strip()]
    if len(lines) < 2:
        return False
    objectish = sum(1 for ln in lines if ln.lstrip().startswith(("{", "[")) and ln.rstrip().endswith(("}", "]")))
    return objectish >= 2 and objectish >= len(lines) - 1


def _delimiter_score(text: str) -> tuple[str | None, float]:
    """Best delimiter and how consistently it splits the first lines.

    Consistency, not frequency, is the signal: prose contains plenty of commas,
    but only a real delimiter yields the SAME field count on every row.
    """
    lines = [ln for ln in text.splitlines()[:30] if ln.strip()]
    if len(lines) < 2:
        return None, 0.0

    best: tuple[str | None, float] = (None, 0.0)
    for delim in _CANDIDATE_DELIMS:
        counts = [ln.count(delim) for ln in lines]
        if counts[0] == 0:  # must appear in the header row
            continue
        agree = sum(1 for c in counts if c == counts[0])
        score = agree / len(counts)
        # Require a real header: one column is not a table.
        if counts[0] >= 1 and score > best[1]:
            best = (delim, score)
    return best


def detect(path: Path, sample: bytes | None = None) -> Detection:
    """Identify format + encoding without reading more than HEAD_BYTES."""
    if sample is None:
        sample = read_head(path, HEAD_BYTES)

    encoding, enc_conf = detect_encoding(path, sample)
    had_bom = sniff_bom(sample) is not None
    body = _strip_bom(sample).lstrip()
    notes: list[str] = []

    ext_hint = _EXT_HINT.get(path.suffix.lower(), "")

    if not body:
        return Detection(
            fmt="unknown", encoding=encoding, confidence=0.0, had_bom=had_bom,
            notes=["file is empty or contains only whitespace"],
        )

    fmt, confidence = _classify(body, encoding, notes)

    if ext_hint and fmt != "unknown" and ext_hint != fmt:
        notes.append(f"extension suggests {ext_hint!r} but content parses as {fmt!r}; content wins")
    elif fmt == "unknown" and ext_hint:
        fmt, confidence = ext_hint, 0.3
        notes.append(f"content inconclusive; fell back to the {ext_hint!r} extension hint")

    if enc_conf < 0.7:
        notes.append(f"encoding confidence only {enc_conf:.2f}")

    # Resolved late so a missing library shows up as engine=None (degraded) rather
    # than an ImportError at routing time.
    from server.tools.repair.engines import engine_for

    return Detection(
        fmt=fmt,
        encoding=encoding,
        engine=engine_for(fmt),
        confidence=confidence,
        had_bom=had_bom,
        notes=notes,
    )


def _classify(body: bytes, encoding: str, notes: list[str]) -> tuple[str, float]:
    """Order matters: the most specific signature is tested first."""
    for sig, fmt in _BINARY_SIGS:
        if body.startswith(sig):
            return fmt, 1.0  # a magic number is a declaration, not a guess

    if _XML_DECL.match(body):
        return ("html", 0.9) if _HTML_HINT.search(body[:2048]) else ("xml", 0.99)
    if _HTML_HINT.match(body):
        return "html", 0.97
    if _OPEN_TAG.match(body):
        # A markup document with no declaration. HTML tags near the top are the
        # only thing distinguishing it from XML at this point.
        head = body[:4096].lower()
        if any(tag in head for tag in (b"<div", b"<span", b"<body", b"<table", b"<meta")):
            return "html", 0.75
        return "xml", 0.85

    text = body[:HEAD_BYTES].decode(encoding, errors="replace")

    if _looks_ndjson(text):
        return "ndjson", 0.9
    if body[:1] in (b"{", b"["):
        return "json", 0.95

    delim, score = _delimiter_score(text)
    if delim and score >= 0.8:
        if delim != ",":
            notes.append(f"delimiter detected as {delim!r}, not a comma")
        return "csv", min(0.95, score)
    if delim and score >= 0.5:
        notes.append(f"delimiter {delim!r} only consistent across {score:.0%} of sampled rows")
        return "csv", score

    return "unknown", 0.0
