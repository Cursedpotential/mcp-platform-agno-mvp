"""
Generic Markdown Chat Parser
============================

Fallback parser for any markdown file with conversation role markers.
Handles formats not covered by source-specific parsers.

Detects patterns like:
    **User:** message
    **Assistant:** response

    > User: message
    > Assistant: response

    # User
    message
    # Assistant
    response

Usage:
    parser = GenericMdParser()
    result = parser.parse_file("unknown_chat.md")
"""

import logging
import re
import uuid
from typing import Optional

from chatminer.core.base import BaseParser
from chatminer.core.types import ContentType, MessageRole, ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


class GenericMdParser(BaseParser):
    """Generic fallback parser for markdown chat exports."""

    SUPPORTED_FORMATS = [".md", ".txt"]
    SOURCE_NAME = "generic_md"

    # Comprehensive role marker patterns (most specific first)
    _ROLE_PATTERNS = [
        # Bold markers: **User:**, **You:**, **Assistant:**, **AI:**, **Bot:**
        (re.compile(r"^\s*\*\*\s*(?:You|User|Human|Person)\s*\*\*\s*[:\-]?\s*", re.I), MessageRole.USER),
        (
            re.compile(
                r"^\s*\*\*\s*(?:Assistant|AI|Bot|Chatbot|GPT|Claude|Gemini|Perplexity|Copilot|System)\s*\*\*\s*[:\-]?\s*",
                re.I,
            ),
            MessageRole.ASSISTANT,
        ),
        # Plain markers: User:, Assistant:, etc.
        (re.compile(r"^\s*(?:You|User|Human)\s*[:\-]\s*", re.I), MessageRole.USER),
        (
            re.compile(r"^\s*(?:Assistant|AI|Bot|GPT|Claude|Gemini|Perplexity|Copilot)\s*[:\-]\s*", re.I),
            MessageRole.ASSISTANT,
        ),
        # Blockquote markers: > User:, > Assistant:
        (re.compile(r"^\s*>\s*(?:You|User|Human)\s*[:\-]?\s*", re.I), MessageRole.USER),
        (
            re.compile(r"^\s*>\s*(?:Assistant|AI|Bot|GPT|Claude|Gemini|Perplexity)\s*[:\-]?\s*", re.I),
            MessageRole.ASSISTANT,
        ),
        # Heading markers: # User, ## Assistant
        (re.compile(r"^\s*#{1,3}\s+(?:You|User|Human)\b", re.I), MessageRole.USER),
        (re.compile(r"^\s*#{1,3}\s+(?:Assistant|AI|Bot|GPT|Claude|Gemini|Perplexity)\b", re.I), MessageRole.ASSISTANT),
    ]

    def can_parse(self, content: str, path: Optional[str] = None) -> float:
        """Generic fallback — low confidence but broad detection."""
        lines = content.split("\n")
        user_count = 0
        assistant_count = 0

        for line in lines[:100]:  # Check first 100 lines
            for pattern, role in self._ROLE_PATTERNS:
                if pattern.match(line):
                    if role == MessageRole.USER:
                        user_count += 1
                    else:
                        assistant_count += 1
                    break

        # Need at least some alternation to be confident
        if user_count > 0 and assistant_count > 0:
            # Scale confidence based on marker density
            min_count = min(user_count, assistant_count)
            return min(0.2 + 0.05 * min_count, 0.6)

        return 0.0

    def parse_content(self, content: str, source_file: str = "") -> list[ParsedConversation]:
        lines = content.split("\n")
        conv = ParsedConversation(
            conversation_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
        )

        # Try to find a title
        for line in lines[:5]:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                if len(stripped) < 120:
                    conv.title = stripped[:100]
                    break

        messages = self._extract_messages(lines, source_file)
        conv.messages = messages
        return [conv]

    def _extract_messages(self, lines: list[str], source_file: str) -> list[ParsedMessage]:
        """Extract messages using generic role patterns."""
        messages: list[ParsedMessage] = []
        current_role = MessageRole.USER
        current_content: list[str] = []
        msg_index = 0

        for line in lines:
            matched_role: Optional[MessageRole] = None
            stripped = line.strip()

            # Check all role patterns
            for pattern, role in self._ROLE_PATTERNS:
                if pattern.match(stripped):
                    matched_role = role
                    # Remove the marker
                    clean_line = pattern.sub("", stripped).strip()
                    break

            if matched_role is not None:
                # Save previous message
                if current_content:
                    content = "\n".join(current_content).strip()
                    if content:
                        messages.append(self._create_msg(content, current_role, source_file, msg_index))
                        msg_index += 1
                    current_content = []
                current_role = matched_role
                if clean_line:
                    current_content.append(clean_line)
            else:
                current_content.append(line)

        # Save final
        if current_content:
            content = "\n".join(current_content).strip()
            if content:
                messages.append(self._create_msg(content, current_role, source_file, msg_index))

        return messages

    def _create_msg(self, content: str, role: MessageRole, source_file: str, index: int) -> ParsedMessage:
        content_type = ContentType.TEXT
        language: Optional[str] = None
        if "```" in content:
            content_type = ContentType.CODE
            m = re.search(r"```(\w+)", content)
            if m:
                language = m.group(1)

        return ParsedMessage(
            message_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
            source_index=index,
            sender="User" if role == MessageRole.USER else "Assistant",
            sender_role=role,
            content=content,
            content_type=content_type,
            language=language,
            confidence="MEDIUM",  # Lower confidence for generic parser
            metadata={},
        )
