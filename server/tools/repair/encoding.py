"""Encoding detection and STREAMING text access.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

There is exactly one rule in this module: never call `path.read_text()`.

Nine parsers in this repo currently do, including `sms_xml.py:311`, which reads
an entire 667 MB export in order to look at its first 4096 characters. Decoded
to `str`, that export peaks around 1.3 GB before a single record is mapped.

`open_text()` returns an incrementally-decoding handle instead:
`io.TextIOWrapper` over a binary file object decodes as it is read, so memory
stays flat regardless of file size, and the returned object is a normal text
file usable by `csv.reader`, `iterparse`, etc.

Encoding is detected from a BOUNDED head sample. charset-normalizer is used
when available and falls back to a BOM/UTF-8 probe otherwise — the fallback
exists because this module must keep working in the dep-light facade.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import IO, TextIO

from server.tools.repair.types import COSMETIC, LOSSY, RepairEvent

#: How much of the file detection is allowed to look at. 64 KiB comfortably
#: covers an XML prolog, a CSV header + several rows, and a JSON preamble,
#: while staying O(1) against a multi-gigabyte export.
HEAD_BYTES = 65_536

_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


def read_head(path: Path, n: int = HEAD_BYTES) -> bytes:
    """Read at most `n` bytes. Opens, reads, closes — never holds the file."""
    with path.open("rb") as fh:
        return fh.read(n)


def sniff_bom(sample: bytes) -> str | None:
    """Return the encoding implied by a byte-order mark, if any.

    Checked longest-first: the UTF-32-LE BOM starts with the UTF-16-LE BOM, so
    naive ordering silently misreads every UTF-32-LE file as UTF-16-LE.
    """
    for bom, enc in _BOMS:
        if sample.startswith(bom):
            return enc
    return None


def detect_encoding(path: Path, sample: bytes | None = None) -> tuple[str, float]:
    """(encoding, confidence 0.0-1.0) from a bounded head read.

    A BOM is authoritative — it is a declaration by the writer, not a guess, so
    it short-circuits before any statistical detection runs.
    """
    if sample is None:
        sample = read_head(path)

    bom = sniff_bom(sample)
    if bom:
        return bom, 1.0

    if not sample:
        return "utf-8", 1.0  # an empty file decodes identically under anything

    # Plain UTF-8 is overwhelmingly the common case; prove it cheaply before
    # paying for statistical detection. Trailing bytes may be a split multi-byte
    # sequence at the sample boundary, so ignore a failure in the last 4 bytes.
    try:
        sample.decode("utf-8")
        return "utf-8", 1.0
    except UnicodeDecodeError as exc:
        if exc.start >= len(sample) - 4:
            return "utf-8", 0.95

    try:
        from charset_normalizer import from_bytes
    except ImportError:
        # Facade / minimal install: utf-8 with replacement is the safe default.
        # It is lossy, and open_text() reports it as such.
        return "utf-8", 0.3

    best = from_bytes(sample).best()
    if best is None or not best.encoding:
        return "utf-8", 0.3
    # charset-normalizer's `chaos` is a badness score, so confidence inverts it.
    return str(best.encoding), max(0.0, 1.0 - float(best.chaos))


def open_binary(path: Path) -> IO[bytes]:
    """Buffered binary handle. ijson and lxml both prefer bytes — they do their
    own decoding and are faster and more correct when not pre-decoded."""
    return path.open("rb")


def open_text(
    path: Path,
    encoding: str | None = None,
    events: list[RepairEvent] | None = None,
) -> TextIO:
    """A STREAMING decoded text handle. The only sanctioned way to read text here.

    `errors="replace"` never raises on a bad byte — it substitutes U+FFFD. That
    is the right call for forensic ingest (one corrupt byte must not cost the
    other 600 MB) but it IS lossy, so when the detected encoding is low
    confidence a LOSSY event is appended to `events` for the caller to record.
    """
    if encoding is None:
        encoding, confidence = detect_encoding(path)
    else:
        confidence = 1.0

    if events is not None:
        if encoding == "utf-8-sig":
            events.append(
                RepairEvent(
                    kind="bom_stripped",
                    detail="byte-order mark removed during decode",
                    severity=COSMETIC,
                    byte_offset=0,
                )
            )
        if confidence < 0.7:
            events.append(
                RepairEvent(
                    kind="uncertain_encoding",
                    detail=(
                        f"encoding detected as {encoding!r} at confidence "
                        f"{confidence:.2f}; undecodable bytes become U+FFFD"
                    ),
                    severity=LOSSY,
                )
            )

    return io.TextIOWrapper(path.open("rb"), encoding=encoding, errors="replace", newline="")
