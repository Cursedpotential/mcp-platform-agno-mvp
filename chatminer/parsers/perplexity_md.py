"""
Perplexity Markdown (Generic) Parser
=====================================

Fallback parser for Perplexity markdown that doesn't match
the plugin parser pattern. Handles copy-paste from the web
interface without the structured Sources section.

Usage:
    parser = PerplexityMdParser()
    result = parser.parse_file("perplexity_chat.md")
"""

import logging
import re
import uuid
from typing import Optional

from chatminer.core.base import BaseParser
from chatminer.core.types import ContentType, MessageRole, ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


class PerplexityMdParser(BaseParser):
    """Generic fallback parser for Perplexity markdown."""

    SUPPORTED_FORMATS = [".md", ".txt"]
    SOURCE_NAME = "perplexity_md"

    def can_parse(self, content: str, path: Optional[str] = None) -> float:
        score = 0.0

        # Check for Perplexity-specific markers
        if "perplexity" in content.lower()[:500]:
            score += 0.3

        # Check for Sources section (but not the structured plugin format)
        if re.search(r"(?i)sources?\s*:\s*\n\d+\.\s*\[", content):
            score += 0.2

        # Check for citation patterns [1], [2]
        if re.search(r"\[\d+\]\s*\(", content):
            score += 0.2

        if path and "perplexity" in path.lower():
            score += 0.1

        return min(score, 0.7)  # Max 0.7 — generic fallback

    def parse_content(self, content: str, source_file: str = "") -> list[ParsedConversation]:
        # Delegate to generic markdown parser with Perplexity context
        from chatminer.parsers.generic_md import GenericMdParser

        generic = GenericMdParser(self.config)
        result = generic.parse_content(content, source_file)

        # Override source format
        for conv in result:
            conv.source_format = self.SOURCE_NAME
            for msg in conv.messages:
                msg.source_format = self.SOURCE_NAME
                if msg.sender_role == MessageRole.ASSISTANT:
                    msg.sender = "Perplexity"

        return result
