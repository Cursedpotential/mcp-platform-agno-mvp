"""
Claude Code JSONL Export Parser
===============================

Parses Claude Code JSONL exports (one JSON object per line).
These come from the Claude Code CLI tool's conversation export.

Source Format:
    {"role": "user", "content": "...", "timestamp": "2025-01-15T10:30:00Z"}
    {"role": "assistant", "content": "...", "timestamp": "2025-01-15T10:30:05Z"}

Usage:
    parser = ClaudeCodeParser()
    result = parser.parse_file("claude_conversation.jsonl")
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from chatminer.core.base import BaseParser
from chatminer.core.types import ContentType, MessageRole, ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


class ClaudeCodeParser(BaseParser):
    """Parser for Claude Code JSONL exports."""

    SUPPORTED_FORMATS = [".jsonl", ".json"]
    SOURCE_NAME = "claude_code"

    def can_parse(self, content: str, path: Optional[str] = None) -> float:
        score = 0.0
        lines = content.strip().split("\n")[:10]

        valid_lines = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    if "role" in obj and "content" in obj:
                        role = obj.get("role", "")
                        if role in ("user", "assistant", "human"):
                            valid_lines += 1
            except json.JSONDecodeError:
                continue

        if valid_lines >= 2:
            score = min(0.3 + 0.1 * valid_lines, 0.9)

        if path and ("claude" in path.lower() or ".jsonl" in path.lower()):
            score += 0.1

        return min(score, 1.0)

    def parse_content(self, content: str, source_file: str = "") -> list[ParsedConversation]:
        conv = ParsedConversation(
            conversation_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
        )

        for i, line in enumerate(content.strip().split("\n")):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            role_str = obj.get("role", "").lower()
            content_text = obj.get("content", "")

            if not content_text:
                continue

            role = MessageRole.USER if role_str in ("user", "human") else MessageRole.ASSISTANT
            sender = "You" if role == MessageRole.USER else "Claude"

            # Parse timestamp
            ts = None
            if "timestamp" in obj:
                ts_str = obj["timestamp"]
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            content_type = ContentType.TEXT
            language: Optional[str] = None
            if "```" in content_text:
                content_type = ContentType.CODE
                import re

                m = re.search(r"```(\w+)", content_text)
                if m:
                    language = m.group(1)

            msg = ParsedMessage(
                message_id=str(uuid.uuid4()),
                source_file=source_file,
                source_format=self.SOURCE_NAME,
                source_index=i,
                timestamp=ts,
                sender=sender,
                sender_role=role,
                content=content_text,
                content_type=content_type,
                language=language,
                confidence="HIGH",
                metadata={k: v for k, v in obj.items() if k not in ("role", "content", "timestamp")},
            )
            conv.messages.append(msg)

        return [conv]
