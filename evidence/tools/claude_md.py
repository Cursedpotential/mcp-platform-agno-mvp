"""Atomic tool: Claude markdown copy-paste transcript -> NormalizedRecords (chatminer-backed).

One format, one module, swappable. Thin @register wrapper: parsing lives in
the vendored chatminer parser; evidence/tools/_chatminer_adapter maps
ParsedMessage -> NormalizedRecord (verbatim content + message hash in attrs).
Hard-fails when detection confidence is low or zero messages parse, so the
registry substitution mesh moves to the next parse.transcript candidate.
"""

from __future__ import annotations

from typing import Any

from chatminer.parsers.claude_md import ClaudeMdParser
from evidence.registry import register
from evidence.tools._chatminer_adapter import run_chatminer_parser


@register(
    id="transcripts.claude-md",
    capability="parse.transcript",
    description="Claude markdown copy-paste transcript -> normalized message records",
    accept=lambda hint, size: hint.endswith((".md", ".txt")),
    provenance="vendored: chatminer/parsers/claude_md.py",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    return run_chatminer_parser(ClaudeMdParser, payload)
