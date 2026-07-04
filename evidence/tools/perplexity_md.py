"""Atomic tool: Perplexity generic markdown export -> NormalizedRecords (chatminer-backed).

One format, one module, swappable. Thin @register wrapper: parsing lives in
the vendored chatminer parser; evidence/tools/_chatminer_adapter maps
ParsedMessage -> NormalizedRecord (verbatim content + message hash in attrs).
Hard-fails when detection confidence is low or zero messages parse, so the
registry substitution mesh moves to the next parse.transcript candidate.
"""

from __future__ import annotations

from typing import Any

from chatminer.parsers.perplexity_md import PerplexityMdParser
from evidence.registry import register
from evidence.tools._chatminer_adapter import run_chatminer_parser


@register(
    id="transcripts.perplexity-md",
    capability="parse.transcript",
    description="Perplexity generic markdown export -> normalized message records",
    accept=lambda hint, size: hint.endswith((".md", ".txt")),
    provenance="vendored: chatminer/parsers/perplexity_md.py",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    return run_chatminer_parser(PerplexityMdParser, payload)
