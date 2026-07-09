"""Atomic tool: Claude Code simple JSONL export (role/content lines) -> NormalizedRecords (chatminer-backed).

One format, one module, swappable. Thin @register wrapper: parsing lives in
the vendored chatminer parser; server/tools/_chatminer_adapter maps
ParsedMessage -> NormalizedRecord (verbatim content + message hash in attrs).
Hard-fails when detection confidence is low or zero messages parse, so the
registry substitution mesh moves to the next parse.transcript candidate.
"""

from __future__ import annotations

from typing import Any

from server.vendored.chatminer.parsers.claude_code import ClaudeCodeParser
from .registry import register
from ._chatminer_adapter import run_chatminer_parser


@register(
    id="transcripts.claude-code",
    capability="parse.transcript",
    description="Claude Code simple JSONL export (role/content lines) -> normalized message records",
    accept=lambda hint, size: hint.endswith((".jsonl", ".json")),
    provenance="vendored: chatminer/parsers/claude_code.py",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    return run_chatminer_parser(ClaudeCodeParser, payload)
