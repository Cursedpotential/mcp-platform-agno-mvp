"""Shared, import-light identities for the pinned Chonkie runtime.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations


CHONKIE_PIN = "1.7.0"

_CHUNK_UNITS = {
    "recursive": "chars",
    "sentence": "chars",
    "token": "chars",
    "fast": "chars",
    "semantic": "tokens",
    "code": "chars",
    "table": "rows",
}


def chunker_id(name: str, chunk_size: int | None = None) -> str:
    """Return the durable algorithm/version identifier stored in receipts."""
    unit = _CHUNK_UNITS.get(name, "units")
    suffix = "" if chunk_size is None else f":{chunk_size}-{unit}"
    return f"chonkie.{name}@{CHONKIE_PIN}{suffix}"
