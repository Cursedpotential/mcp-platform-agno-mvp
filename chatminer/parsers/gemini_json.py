"""
Gemini JSON Export Parser
=========================

Parses Gemini JSON exports (different from Chrome extension HTML exports).
These may come from Google Takeout or other export mechanisms.

Source Format:
    {
      "messages": [
        {"author": "user", "content": "...", "timestamp": "..."},
        {"author": "model", "content": "...", "timestamp": "..."}
      ]
    }

Usage:
    parser = GeminiJsonParser()
    result = parser.parse_file("gemini_export.json")
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from chatminer.core.base import BaseParser
from chatminer.core.types import ContentType, MessageRole, ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


class GeminiJsonParser(BaseParser):
    """Parser for Gemini JSON exports."""

    SUPPORTED_FORMATS = [".json"]
    SOURCE_NAME = "gemini_json"

    def can_parse(self, content: str, path: Optional[str] = None) -> float:
        score = 0.0
        try:
            data = json.loads(content[:4096])
            if isinstance(data, dict) and "messages" in data:
                msgs = data["messages"]
                if isinstance(msgs, list) and len(msgs) > 0:
                    first = msgs[0]
                    if "author" in first and "content" in first:
                        # Check for Gemini-specific author values
                        author = first.get("author", "")
                        if author in ("user", "model", "gemini"):
                            score += 0.6
                        else:
                            score += 0.3
        except (json.JSONDecodeError, ValueError):
            pass

        if path and "gemini" in path.lower():
            score += 0.1

        return min(score, 1.0)

    def parse_content(self, content: str, source_file: str = "") -> list[ParsedConversation]:
        data = json.loads(content)
        messages_data = data.get("messages", [])

        conv = ParsedConversation(
            conversation_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
            title=data.get("title", "Gemini Conversation"),
        )

        for i, msg_data in enumerate(messages_data):
            author = msg_data.get("author", "").lower()
            content_text = msg_data.get("content", "")

            if not content_text:
                continue

            role = MessageRole.ASSISTANT if author in ("model", "gemini", "assistant") else MessageRole.USER
            sender = "Gemini" if role == MessageRole.ASSISTANT else "You"

            # Parse timestamp
            ts = None
            if "timestamp" in msg_data:
                ts = self._parse_timestamp(msg_data["timestamp"])

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
                metadata={},
            )
            conv.messages.append(msg)

        return [conv]

    def _parse_timestamp(self, ts) -> Optional[datetime]:
        """Parse various timestamp formats."""
        if isinstance(ts, (int, float)):
            try:
                return datetime.fromtimestamp(ts)
            except (ValueError, OSError):
                return None
        elif isinstance(ts, str):
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %I:%M %p"]:
                try:
                    return datetime.strptime(ts, fmt)
                except ValueError:
                    continue
        return None
