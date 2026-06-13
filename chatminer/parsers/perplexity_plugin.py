"""
Perplexity Plugin/Copy-Paste Parser
====================================

Parses Perplexity conversations exported via browser plugin
or copy-paste. These are markdown files with Perplexity's
distinctive formatting including Sources sections.

Source Format (from copy-paste):
    # [Query Title]
    
    [Answer content with markdown formatting]
    
    ## Sources
    1. [Title](URL)
    2. [Title](URL)

    ---
    
    # [Next Query]
    ...

Adapted from: greasyfork/Perplexity-AI-Chat-Exporter (userscript)
              Features: citation styles, Deep Research support,
              frontmatter, configurable output

Usage:
    parser = PerplexityPluginParser()
    result = parser.parse_file("perplexity_export.md")
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Optional

from chatminer.core.base import BaseParser
from chatminer.core.types import ContentType, MessageRole, ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


class PerplexityPluginParser(BaseParser):
    """Parser for Perplexity plugin copy-paste markdown exports."""

    SUPPORTED_FORMATS = [".md", ".txt"]
    SOURCE_NAME = "perplexity_plugin"

    # Perplexity uses H1 (#) for each query/answer pair
    _H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
    # Sources section
    _SOURCES_RE = re.compile(r"^##\s*Sources\s*$", re.IGNORECASE | re.MULTILINE)
    # Source entry: 1. [Title](URL)
    _SOURCE_ENTRY_RE = re.compile(r"^\d+\.\s*\[([^\]]+)\]\(([^)]+)\)")
    # Related section (end marker)
    _RELATED_RE = re.compile(r"^##\s*(?:Related|Follow-up)\b", re.IGNORECASE | re.MULTILINE)
    # Code fence
    _CODE_FENCE_RE = re.compile(r"```(\w+)?")

    def can_parse(self, content: str, path: Optional[str] = None) -> float:
        score = 0.0

        # Check for Sources section
        if self._SOURCES_RE.search(content):
            score += 0.4

        # Check for H1 headings (query titles)
        h1_count = len(self._H1_RE.findall(content))
        if h1_count > 0:
            score += min(0.1 * h1_count, 0.3)

        # Check for source entries with URLs
        source_entries = len(self._SOURCE_ENTRY_RE.findall(content))
        if source_entries > 0:
            score += min(0.05 * source_entries, 0.2)

        if path and "perplexity" in path.lower():
            score += 0.1

        return min(score, 1.0)

    def parse_content(self, content: str, source_file: str = "" ) -> list[ParsedConversation]:
        """Parse Perplexity plugin export into conversations."""
        # Split by H1 headings — each H1 is a separate query/answer
        sections = self._H1_RE.split(content)

        conversations: list[ParsedConversation] = []

        # sections[0] is preamble, sections[1:] alternates title/content
        for i in range(1, len(sections), 2):
            if i + 1 >= len(sections):
                break

            title = sections[i].strip()
            body = sections[i + 1]

            conv = self._parse_section(title, body, source_file)
            if conv.messages:
                conversations.append(conv)

        return conversations

    def _parse_section(self, title: str, body: str, source_file: str) -> ParsedConversation:
        """Parse a single query/answer section."""
        conv = ParsedConversation(
            conversation_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
            title=title[:200],
        )

        # Split body into answer and sources
        parts = self._SOURCES_RE.split(body, maxsplit=1)
        answer_content = parts[0].strip()

        # Extract sources if present
        sources: list[dict] = []
        if len(parts) > 1:
            sources = self._extract_sources(parts[1])

        # Remove Related/Follow-up section
        answer_content = self._RELATED_RE.split(answer_content)[0].strip()

        # Create user message (the query/title)
        user_msg = ParsedMessage(
            message_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
            source_index=0,
            sender="You",
            sender_role=MessageRole.USER,
            content=title,
            content_type=ContentType.TEXT,
            confidence="HIGH",
            metadata={},
        )

        # Create assistant message (the answer)
        content_type = ContentType.TEXT
        language: Optional[str] = None
        if "```" in answer_content:
            content_type = ContentType.CODE
            m = self._CODE_FENCE_RE.search(answer_content)
            if m and m.group(1):
                language = m.group(1)

        assistant_msg = ParsedMessage(
            message_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
            source_index=1,
            sender="Perplexity",
            sender_role=MessageRole.ASSISTANT,
            content=answer_content,
            content_type=content_type,
            language=language,
            confidence="HIGH",
            metadata={"sources": sources, "source_count": len(sources)},
        )

        conv.messages = [user_msg, assistant_msg]
        return conv

    def _extract_sources(self, sources_section: str) -> list[dict]:
        """Extract source entries from Sources section."""
        sources: list[dict] = []
        for line in sources_section.split("\n"):
            m = self._SOURCE_ENTRY_RE.match(line.strip())
            if m:
                sources.append({"title": m.group(1), "url": m.group(2)})
        return sources
