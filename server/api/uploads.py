"""Shared upload-filename normalization for parser routing.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

from email.header import decode_header, make_header


def safe_upload_name(filename: str | None) -> str:
    """Decode RFC 2047 names and return a traversal-safe filename leaf."""
    raw = filename or "upload.bin"
    try:
        decoded = str(make_header(decode_header(raw)))
    except (LookupError, UnicodeError):
        decoded = raw
    leaf = decoded.replace("\\", "/").rsplit("/", 1)[-1]
    leaf = "".join(char for char in leaf if char not in {"\x00", "\r", "\n"})
    return leaf or "upload.bin"
