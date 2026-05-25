"""
Claude Copy-Paste Markdown Parser
==================================

Parses Claude conversations that were copy-pasted into markdown files.
These don't have a standard export format — they're just pasted text
with "Human:" and "Assistant:" markers (or similar).

Common patterns seen:
    Human: [question]
    
    Assistant: [response]
    
    Human: [follow-up]

Or:
    **You:** message
    **Claude:** response

Or Anthropic console format with XML tags.

Usage:
    parser = ClaudeMdParser()
    result = parser.parse_file("claude_conversation.md")
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Optional

from chatminer.core.base import BaseParser
from chatminer.core.types import ContentType, MessageRole, ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


class ClaudeMdParser(BaseParser):
    """Parser for Claude copy-paste markdown exports."""

    SUPPORTED_FORMATS = [".md", ".txt"]
    SOURCE_NAME = "claude_md"

    # Multiple possible role marker patterns
    _USER_PATTERNS = [
        re.compile(r"^\s*\*\*?(?:You|Human|User)\*\*?:?\s*", re.IGNORECASE),
        re.compile(r"^\s*(?:Human|User):\s*", re.IGNORECASE),
        re.compile(r"^\s*<user>"),
    ]
    _ASSISTANT_PATTERNS = [
        re.compile(r"^\s*\*\*?(?:Claude|Assistant)\*\*?:?\s*", re.IGNORECASE),
        re.compile(r"^\s*(?:Assistant|Claude):\s*", re.IGNORECASE),
        re.compile(r"^\s*<assistant>"),
    ]

    def can_parse(self, content: str, path: Optional[str] = None) -> float:
        score = 0.0
        lines = content.split("\n")[:50]  # Check first 50 lines

        user_markers = 0
        assistant_markers = 0

        for line in lines:
            for pat in self._USER_PATTERNS:
                if pat.match(line):
                    user_markers += 1
                    break
            for pat in self._ASSISTANT_PATTERNS:
                if pat.match(line):
                    assistant_markers += 1
                    break

        if user_markers > 0 and assistant_markers > 0:
            score = min(0.3 + 0.1 * min(user_markers, 3) + 0.1 * min(assistant_markers, 3), 0.9)

        if path and "claude" in path.lower():
            score += 0.1

        return min(score, 1.0)

    def parse_content(self, content: str, source_file: str = "") -> list[ParsedConversation]:
        lines = content.split("\n")
        conv = ParsedConversation(
            conversation_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
        )

        # Try to find a title in first few lines
        for line in lines[:10]:
            stripped = line.strip()
            if stripped and not any(p.match(stripped) for p in self._USER_PATTERNS + self._ASSISTANT_PATTERNS):
                if len(stripped) < 120 and not stripped.startswith("#"):
                    conv.title = stripped[:100]
                    break

        messages = self._extract_messages(lines, source_file)
        conv.messages = messages

        return [conv]

    def _extract_messages(self, lines: list[str], source_file: str) -> list[ParsedMessage]:
        """Extract messages by detecting role marker patterns."""
        messages: list[ParsedMessage] = []
        current_role = MessageRole.USER
        current_content: list[str] = []
        msg_index = 0

        for line in lines:
            # Check if this line starts a new user message
            user_match = False
            for pat in self._USER_PATTERNS:
                if pat.match(line):
                    user_match = True
                    # Save previous
                    if current_content:
                        content = "\n".join(current_content).strip()
                        if content:
                            messages.append(self._create_msg(content, current_role, source_file, msg_index))
                            msg_index += 1
                        current_content = []
                    current_role = MessageRole.USER
                    # Remove the marker from the line
                    line = pat.sub("", line).strip()
                    break

            # Check if this line starts a new assistant message
            assistant_match = False
            if not user_match:
                for pat in self._ASSISTANT_PATTERNS:
                    if pat.match(line):
                        assistant_match = True
                        if current_content:
                            content = "\n".join(current_content).strip()
                            if content:
                                messages.append(self._create_msg(content, current_role, source_file, msg_index))
                                msg_index += 1
                            current_content = []
                        current_role = MessageRole.ASSISTANT
                        line = pat.sub("", line).strip()
                        break

            if line or not (user_match or assistant_match):
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
            sender="You" if role == MessageRole.USER else "Claude",
            sender_role=role,
            content=content,
            content_type=content_type,
            language=language,
            confidence="HIGH",
            metadata={},
        )
