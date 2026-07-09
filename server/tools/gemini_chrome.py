"""Atomic tool: Gemini Chrome-extension markdown export -> NormalizedRecords (chatminer-backed).

One format, one module, swappable. Thin @register wrapper: parsing lives in
the vendored chatminer parser; server/tools/_chatminer_adapter maps
ParsedMessage -> NormalizedRecord (verbatim content + message hash in attrs).
Hard-fails when detection confidence is low or zero messages parse, so the
registry substitution mesh moves to the next parse.transcript candidate.
"""

from __future__ import annotations

from typing import Any

from server.vendored.chatminer.parsers.gemini_chrome import GeminiChromeParser
from .registry import register
from ._chatminer_adapter import run_chatminer_parser


@register(
    id="transcripts.gemini-chrome",
    capability="parse.transcript",
    description="Gemini Chrome-extension markdown export -> normalized message records",
    accept=lambda hint, size: hint.endswith((".md", ".txt")),
    provenance="vendored: chatminer/parsers/gemini_chrome.py",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    return run_chatminer_parser(GeminiChromeParser, payload)
