"""Atomic tool: Gemini JSON export -> NormalizedRecords (chatminer-backed).

One format, one module, swappable. Thin @register wrapper: parsing lives in
the vendored chatminer parser; server/tools/_chatminer_adapter maps
ParsedMessage -> NormalizedRecord (verbatim content + message hash in attrs).
Hard-fails when detection confidence is low or zero messages parse, so the
registry substitution mesh moves to the next parse.transcript candidate.
"""

from __future__ import annotations

from typing import Any

from server.vendored.chatminer.parsers.gemini_json import GeminiJsonParser
from server.tools.registry import register
from server.tools._chatminer_adapter import run_chatminer_parser


@register(
    id="transcripts.gemini-json",
    capability="parse.transcript",
    description="Gemini JSON export -> normalized message records",
    accept=lambda hint, size: hint.endswith((".json",)),
    provenance="vendored: chatminer/parsers/gemini_json.py",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    return run_chatminer_parser(GeminiJsonParser, payload)
