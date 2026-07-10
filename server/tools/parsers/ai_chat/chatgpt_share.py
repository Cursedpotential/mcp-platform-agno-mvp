"""Atomic tool: ChatGPT 'Share' markdown export -> NormalizedRecords (chatminer-backed).

One format, one module, swappable. Thin @register wrapper: parsing lives in
the vendored chatminer parser; server/tools/_chatminer_adapter maps
ParsedMessage -> NormalizedRecord (verbatim content + message hash in attrs).
Hard-fails when detection confidence is low or zero messages parse, so the
registry substitution mesh moves to the next parse.transcript candidate.
"""

from __future__ import annotations

from typing import Any

from server.vendored.chatminer.parsers.chatgpt_share import ChatGptShareParser
from server.tools.registry import register
from server.tools._chatminer_adapter import run_chatminer_parser


@register(
    id="transcripts.chatgpt-share",
    capability="parse.transcript",
    description="ChatGPT 'Share' markdown export -> normalized message records",
    accept=lambda hint, size: hint.endswith((".md", ".txt")),
    provenance="vendored: chatminer/parsers/chatgpt_share.py",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    return run_chatminer_parser(ChatGptShareParser, payload)
