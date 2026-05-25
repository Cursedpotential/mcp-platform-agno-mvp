"""
ChatGPT "Share" Export Parser
==============================

Parses ChatGPT conversation exports created via the "Share" feature.
These are markdown files with a specific header format and structured
message blocks.

Source Format (from your actual files):
    **User:** Matthew Salem (matt.salemnet@gmail.com)
    Created: 7/25/2025 7:48 | Updated: 7/25/2025 13:00 | Exported: 8/21/2025 13:53
    Link: https://chatgpt.com/c/...
    [File attachment description]
    [Your message content]

    **Response:**
    [Assistant response content]
    [Code blocks, etc.]

    [Continue Conversation](link)

Adapted from: rashidazarang/chatgpt-chat-exporter (console-based export)
              pionxzh/chatgpt-exporter (userscript export)

Usage:
    parser = ChatGptShareParser()
    result = parser.parse_file("conversations/chat-export.md")
    for conv in result.conversations:
        print(f"{conv.title}: {conv.message_count} messages")
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Optional

from chatminer.core.base import BaseParser, ParserConfig
from chatminer.core.types import (
    ContentType,
    MessageRole,
    ParsedConversation,
    ParsedMessage,
)

logger = logging.getLogger(__name__)


class ChatGptShareParser(BaseParser):
    """
    Parser for ChatGPT "Share" markdown exports.

    These files are generated when you use ChatGPT's built-in Share
    feature and export the conversation. They have a distinctive
    header with user info, timestamps, and a link.
    """

    SUPPORTED_FORMATS = [".md", ".txt"]
    SOURCE_NAME = "chatgpt_share"

    # --- Detection patterns ---
    # The header line with user name and email
    _HEADER_RE = re.compile(
        r"\*\*User:\*\*\s+(.+?)\s*\(([^)]+)\)",
        re.IGNORECASE,
    )
    # Created/Updated/Exported timestamps
    _TIMESTAMP_RE = re.compile(
        r"(?:Created|Updated|Exported):\s+(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2})",
        re.IGNORECASE,
    )
    # The chatgpt.com/c/ link
    _LINK_RE = re.compile(r"https://chatgpt\.com/c/[a-f0-9-]+", re.IGNORECASE)
    # Message separator: **Response:** or **ChatGPT said:**
    _RESPONSE_HEADER_RE = re.compile(
        r"\*\*(?:Response|ChatGPT\s+said|Assistant):\*\*",
        re.IGNORECASE,
    )
    # Continue Conversation link
    _CONTINUE_RE = re.compile(r"\[Continue Conversation\]", re.IGNORECASE)
    # File attachment indicator
    _FILE_ATTACHMENT_RE = re.compile(
        r"\[?(?:File|Prompt)\s+(.+?)\s*\]?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    # Code block fence
    _CODE_FENCE_RE = re.compile(r"```(\w+)?")
    # URL in content
    _URL_RE = re.compile(r"https?://[^\s<>\"{}|\\^`[\]]+")

    def can_parse(self, content: str, path: Optional[str] = None) -> float:
        """Detect ChatGPT Share format from content signatures."""
        score = 0.0

        # Check for the distinctive header
        if self._HEADER_RE.search(content):
            score += 0.4

        # Check for ChatGPT link
        if self._LINK_RE.search(content):
            score += 0.3

        # Check for **Response:** separator
        if self._RESPONSE_HEADER_RE.search(content):
            score += 0.2

        # Check for Continue Conversation link
        if self._CONTINUE_RE.search(content):
            score += 0.1

        # Filename hint
        if path and "chatgpt" in path.lower():
            score += 0.1

        return min(score, 1.0)

    def parse_content(self, content: str, source_file: str = "") -> list[ParsedConversation]:
        """
        Parse ChatGPT Share markdown into structured conversations.

        Strategy:
            1. Extract header metadata (user, timestamps, link)
            2. Split into user/assistant message pairs
            3. Detect content types (code, file refs, URLs)
            4. Return single conversation (share exports are one convo per file)
        """
        lines = content.split("\n")
        conv = ParsedConversation(
            conversation_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
        )

        # --- Step 1: Extract header metadata ---
        header_end = 0
        for i, line in enumerate(lines):
            # User header
            m = self._HEADER_RE.match(line)
            if m:
                conv.metadata["user_name"] = m.group(1).strip()
                conv.metadata["user_email"] = m.group(2).strip()
                header_end = max(header_end, i + 1)
                continue

            # Timestamps
            m = self._TIMESTAMP_RE.search(line)
            if m:
                ts_str = m.group(1)
                try:
                    dt = datetime.strptime(ts_str, "%m/%d/%Y %H:%M")
                    if "created" in line.lower():
                        conv.created_at = dt
                    elif "updated" in line.lower():
                        conv.updated_at = dt
                    elif "exported" in line.lower():
                        conv.metadata["exported_at"] = dt.isoformat()
                except ValueError:
                    pass
                header_end = max(header_end, i + 1)
                continue

            # Link
            m = self._LINK_RE.search(line)
            if m:
                conv.metadata["chatgpt_url"] = m.group(0)
                header_end = max(header_end, i + 1)
                continue

            # Empty line after header block signals end of header
            if i > header_end and line.strip() == "" and header_end > 0:
                break

        # --- Step 2: Extract messages ---
        messages = self._extract_messages(lines, header_end, source_file)
        conv.messages = messages

        # Derive title from first user message if not set
        if not conv.title:
            for m in conv.user_messages:
                first_line = m.content.strip().split("\n")[0]
                if len(first_line) > 5:
                    conv.title = first_line[:100]
                    break

        return [conv]

    def _extract_messages(
        self,
        lines: list[str],
        start_index: int,
        source_file: str,
    ) -> list[ParsedMessage]:
        """
        Extract individual messages from the body of the export.

        ChatGPT share exports alternate between user messages
        (no header) and assistant responses (marked with **Response:**).
        """
        messages: list[ParsedMessage] = []
        current_role: MessageRole = MessageRole.USER
        current_content: list[str] = []
        msg_index = 0

        # Skip empty lines at start
        i = start_index
        while i < len(lines) and lines[i].strip() == "":
            i += 1

        while i < len(lines):
            line = lines[i]

            # Detect response header → switch to assistant
            if self._RESPONSE_HEADER_RE.match(line.strip()):
                # Save previous message
                if current_content:
                    content = "\n".join(current_content).strip()
                    if content:
                        msg = self._create_message(
                            content=content,
                            role=current_role,
                            source_file=source_file,
                            index=msg_index,
                        )
                        messages.append(msg)
                        msg_index += 1
                    current_content = []
                current_role = MessageRole.ASSISTANT
                i += 1
                continue

            # Detect "Continue Conversation" link → end of conversation
            if self._CONTINUE_RE.search(line):
                break

            # Detect file attachment line
            if self._FILE_ATTACHMENT_RE.match(line.strip()):
                # File attachment is metadata, not message content
                # But we note it as a file_ref message
                m = self._FILE_ATTACHMENT_RE.match(line.strip())
                if m:
                    fname = m.group(1).strip()
                    messages.append(
                        self._create_message(
                            content=f"[File attachment: {fname}]",
                            role=current_role,
                            source_file=source_file,
                            index=msg_index,
                            content_type=ContentType.FILE_REF,
                            metadata={"attached_file": fname},
                        )
                    )
                    msg_index += 1
                i += 1
                continue

            # Regular content line
            current_content.append(line)
            i += 1

        # Save final message
        if current_content:
            content = "\n".join(current_content).strip()
            if content:
                msg = self._create_message(
                    content=content,
                    role=current_role,
                    source_file=source_file,
                    index=msg_index,
                )
                messages.append(msg)

        return messages

    def _create_message(
        self,
        content: str,
        role: MessageRole,
        source_file: str,
        index: int,
        content_type: ContentType | None = None,
        metadata: dict | None = None,
    ) -> ParsedMessage:
        """
        Create a ParsedMessage with automatic content type detection.

        If content_type is not specified, we auto-detect:
        - Code blocks (```fence```)
        - URLs
        - File references
        """
        msg_meta = metadata or {}

        # Auto-detect content type
        detected_type = content_type or ContentType.TEXT
        detected_language: Optional[str] = None

        if not content_type:
            # Check for code fence
            if "```" in content:
                detected_type = ContentType.CODE
                # Extract language from first fence
                m = self._CODE_FENCE_RE.search(content)
                if m and m.group(1):
                    detected_language = m.group(1)
            # Check for URL-only content
            elif content.strip().startswith("http") and self._URL_RE.match(content.strip()):
                detected_type = ContentType.URL

        return ParsedMessage(
            message_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
            source_index=index,
            sender="Matthew Salem" if role == MessageRole.USER else "ChatGPT",
            sender_role=role,
            content=content,
            content_type=detected_type,
            language=detected_language,
            confidence="HIGH",
            metadata=msg_meta,
        )
