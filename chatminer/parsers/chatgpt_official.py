"""
ChatGPT Official JSON Export Parser
====================================

Parses the official ChatGPT data export (conversations.json).
This is the full backup you download from ChatGPT settings.

Source Format:
    {
      "title": "Conversation Title",
      "create_time": 1712345678.0,  // Unix timestamp
      "update_time": 1712348901.0,
      "mapping": {
        "uuid-1": {
          "message": {
            "author": {"role": "user"},
            "content": {"parts": ["Hello"]},
            "create_time": 1712345678.0
          },
          "children": ["uuid-2"]
        }
      }
    }

Adapted from: gavi/chatgpt-markdown (Python standard library only)
              pionxzh/chatgpt-exporter (multiple format support)

Usage:
    parser = ChatGptOfficialParser()
    result = parser.parse_file("conversations.json")
    print(f"Parsed {result.total_conversations} conversations")
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from chatminer.core.base import BaseParser
from chatminer.core.types import ContentType, MessageRole, ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


class ChatGptOfficialParser(BaseParser):
    """Parser for ChatGPT official JSON data export."""

    SUPPORTED_FORMATS = [".json"]
    SOURCE_NAME = "chatgpt_official"

    def can_parse(self, content: str, path: Optional[str] = None) -> float:
        score = 0.0
        try:
            data = json.loads(content[:4096])
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                if isinstance(first, dict):
                    if "mapping" in first and "title" in first:
                        score += 0.5
                    if "create_time" in first:
                        score += 0.3
            elif isinstance(data, dict) and "mapping" in data:
                score += 0.4
        except (json.JSONDecodeError, ValueError):
            pass

        if path and "conversations" in path.lower() and path.endswith(".json"):
            score += 0.2

        return min(score, 1.0)

    def parse_content(self, content: str, source_file: str = "") -> list[ParsedConversation]:
        data = json.loads(content)
        conversations: list[ParsedConversation] = []

        # conversations.json is an array of conversation objects
        if isinstance(data, list):
            for item in data:
                conv = self._parse_conversation(item, source_file)
                if conv.messages:
                    conversations.append(conv)
        elif isinstance(data, dict):
            conv = self._parse_conversation(data, source_file)
            if conv.messages:
                conversations.append(conv)

        return conversations

    def _parse_conversation(self, data: dict, source_file: str) -> ParsedConversation:
        """Parse a single conversation from the mapping structure."""
        conv = ParsedConversation(
            conversation_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
        )

        conv.title = data.get("title", "Untitled")

        # Timestamps
        if "create_time" in data:
            conv.created_at = self._unix_to_datetime(data["create_time"])
        if "update_time" in data:
            conv.updated_at = self._unix_to_datetime(data["update_time"])

        # Extract messages from mapping tree
        mapping = data.get("mapping", {})
        messages = self._extract_from_mapping(mapping)
        conv.messages = messages

        # Metadata
        conv.metadata["model"] = data.get("model", "unknown")
        conv.metadata["conversation_id"] = data.get("id", "")

        return conv

    def _extract_from_mapping(self, mapping: dict) -> list[ParsedMessage]:
        """Walk the mapping tree to extract messages in order."""
        messages: list[ParsedMessage] = []

        # Find root node (the one with no parent)
        root_ids = [k for k, v in mapping.items() if not v.get("parent")]

        for root_id in root_ids:
            self._walk_tree(mapping, root_id, messages)

        return messages

    def _walk_tree(self, mapping: dict, node_id: str, messages: list, depth: int = 0) -> None:
        """Recursively walk the conversation tree."""
        if depth > 1000:  # Safety limit
            return

        node = mapping.get(node_id, {})
        msg_data = node.get("message")

        if msg_data:
            parsed = self._parse_message(msg_data, len(messages))
            if parsed:
                messages.append(parsed)

        # Follow children (branches in the conversation)
        for child_id in node.get("children", []):
            self._walk_tree(mapping, child_id, messages, depth + 1)

    def _parse_message(self, msg_data: dict, index: int) -> Optional[ParsedMessage]:
        """Parse a single message node."""
        author = msg_data.get("author", {})
        role_str = author.get("role", "unknown")

        # Skip system messages unless configured otherwise
        if role_str == "system":
            return None

        # Extract content
        content_parts = []
        content_data = msg_data.get("content", {})

        if isinstance(content_data, dict):
            parts = content_data.get("parts", [])
            for part in parts:
                if isinstance(part, str):
                    content_parts.append(part)
                elif isinstance(part, dict):
                    # Could be image, etc.
                    content_parts.append(str(part))
        elif isinstance(content_data, str):
            content_parts.append(content_data)

        content = "\n".join(content_parts).strip()
        if not content:
            return None

        # Map role
        role_map = {
            "user": MessageRole.USER,
            "assistant": MessageRole.ASSISTANT,
            "tool": MessageRole.TOOL,
        }
        role = role_map.get(role_str, MessageRole.UNKNOWN)

        # Timestamp
        ts = None
        if "create_time" in msg_data:
            ts = self._unix_to_datetime(msg_data["create_time"])

        # Content type detection
        content_type = ContentType.TEXT
        language: Optional[str] = None
        if "```" in content:
            content_type = ContentType.CODE
            import re

            m = re.search(r"```(\w+)", content)
            if m:
                language = m.group(1)

        return ParsedMessage(
            message_id=str(uuid.uuid4()),
            source_file="",
            source_format=self.SOURCE_NAME,
            source_index=index,
            timestamp=ts,
            sender=role_str.capitalize(),
            sender_role=role,
            content=content,
            content_type=content_type,
            language=language,
            confidence="HIGH",
            metadata={"author_name": author.get("name", "")},
        )

    def _unix_to_datetime(self, ts: float) -> Optional[datetime]:
        """Convert Unix timestamp to datetime."""
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError, TypeError):
            return None
