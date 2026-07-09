"""
Perplexity GDPR Export Parser
==============================

Parses Perplexity's official GDPR data export.
This is a JSON file (conversations.json) + XLSX spreadsheet + assets/
directory that you request from Perplexity's privacy settings.

Source Format (adapted from FraYoshi/perplexity-export-convert):
    {
      "conversations": [
        {
          "uuid": "abc-123",
          "title": "Timeline Analysis",
          "updated_at": "2026-01-31T14:25:58Z",
          "user_id": "user-123",
          "mode": "copilot",
          "collection_uuid": "coll-456",
          "status": "COMPLETED",
          "citations": [...],
          "answers": [
            {
              "content": "# Answer\nmarkdown content...",
              "citations": [{"title": "Wikipedia", "url": "https://..."}],
              "created_at": "2026-01-31T14:25:58Z"
            }
          ]
        }
      ]
    }

Adapted from: FraYoshi/perplexity-export-convert (Python 3.11)
              Handles: collections, citations, answer modes, filename collision

Usage:
    parser = PerplexityGdprParser()
    result = parser.parse_file("conversations.json")
    for conv in result.conversations:
        print(f"{conv.title} [{conv.metadata.get('mode', '?')}]: {conv.message_count} messages")
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from server.vendored.chatminer.core.base import BaseParser
from server.vendored.chatminer.core.types import ContentType, MessageRole, ParsedConversation, ParsedMessage

logger = logging.getLogger(__name__)


class PerplexityGdprParser(BaseParser):
    """
    Parser for Perplexity GDPR data export (conversations.json).

    Perplexity's GDPR export contains:
    - conversations.json: All conversations with answers, citations, metadata
    - conversations.xlsx: Spreadsheet version
    - assets/: Attached images and files

    This parser handles the JSON format which is the most complete.
    """

    SUPPORTED_FORMATS = [".json"]
    SOURCE_NAME = "perplexity_gdpr"

    # Collection UUID → human-readable name mapping
    # Users can configure this in their .env or settings
    DEFAULT_COLLECTIONS: dict[str, str] = {}

    def can_parse(self, content: str, path: Optional[str] = None) -> float:
        score = 0.0
        try:
            data = json.loads(content[:4096])
            if isinstance(data, dict) and "conversations" in data:
                convs = data["conversations"]
                if isinstance(convs, list) and len(convs) > 0:
                    first = convs[0]
                    # Perplexity-specific fields
                    if "uuid" in first and "answers" in first:
                        score += 0.5
                    if "mode" in first and "collection_uuid" in first:
                        score += 0.3
                    if "citations" in first:
                        score += 0.1
        except (json.JSONDecodeError, ValueError):
            pass

        if path and "perplexity" in path.lower():
            score += 0.1

        return min(score, 1.0)

    def parse_content(self, content: str, source_file: str = "") -> list[ParsedConversation]:
        data = json.loads(content)
        conversations: list[ParsedConversation] = []

        raw_conversations = data.get("conversations", [])
        for item in raw_conversations:
            conv = self._parse_conversation(item, source_file)
            if conv.messages:
                conversations.append(conv)

        return conversations

    def _parse_conversation(self, data: dict, source_file: str) -> ParsedConversation:
        """Parse a single Perplexity conversation."""
        conv = ParsedConversation(
            conversation_id=str(uuid.uuid4()),
            source_file=source_file,
            source_format=self.SOURCE_NAME,
        )

        conv.title = data.get("title", "Untitled")

        # Parse timestamps
        if "updated_at" in data:
            conv.updated_at = self._parse_iso_timestamp(data["updated_at"])
        if "created_at" in data:
            conv.created_at = self._parse_iso_timestamp(data["created_at"])

        # Mode: copilot | pro | sonar | deep_research
        mode = data.get("mode", "unknown")
        status = data.get("status", "unknown")

        conv.metadata["mode"] = mode
        conv.metadata["status"] = status
        conv.metadata["perplexity_uuid"] = data.get("uuid", "")
        conv.metadata["user_id"] = data.get("user_id", "")

        # Collection
        coll_uuid = data.get("collection_uuid")
        if coll_uuid:
            coll_name = self.DEFAULT_COLLECTIONS.get(coll_uuid, coll_uuid)
            conv.metadata["collection"] = coll_name

        # Citations (shared across answers)
        citations = data.get("citations", [])
        conv.metadata["citation_count"] = len(citations)

        # Parse answers as messages
        answers = data.get("answers", [])
        messages = self._parse_answers(answers, citations, source_file)
        conv.messages = messages

        return conv

    def _parse_answers(
        self,
        answers: list[dict],
        citations: list[dict],
        source_file: str,
    ) -> list[ParsedMessage]:
        """
        Parse Perplexity answers into messages.

        Each answer becomes one assistant message.
        We also create a synthetic user message from the query
        (inferred from conversation title or preceding context).
        """
        messages: list[ParsedMessage] = []

        for i, answer in enumerate(answers):
            # Assistant message (the answer)
            content = answer.get("content", "").strip()
            if not content:
                continue

            # Parse answer timestamp
            ans_ts = None
            if "created_at" in answer:
                ans_ts = self._parse_iso_timestamp(answer["created_at"])

            # Extract citations used in this answer
            ans_citations = answer.get("citations", [])
            citation_urls = [c.get("url", "") for c in ans_citations if c.get("url")]

            msg = ParsedMessage(
                message_id=str(uuid.uuid4()),
                source_file=source_file,
                source_format=self.SOURCE_NAME,
                source_index=i * 2 + 1,  # Odd indices for assistant
                timestamp=ans_ts,
                sender="Perplexity",
                sender_role=MessageRole.ASSISTANT,
                content=content,
                content_type=self._detect_content_type(content),
                language=self._detect_language(content),
                confidence="HIGH",
                metadata={
                    "citations": citation_urls,
                    "citation_count": len(ans_citations),
                    "mode": answer.get("mode", ""),
                },
            )
            messages.append(msg)

        return messages

    def _detect_content_type(self, content: str) -> ContentType:
        """Detect if content is code, text, or contains references."""
        if "```" in content:
            return ContentType.CODE
        if content.strip().startswith("http"):
            return ContentType.URL
        return ContentType.TEXT

    def _detect_language(self, content: str) -> Optional[str]:
        """Detect programming language from code fence."""
        import re

        m = re.search(r"```(\w+)", content)
        return m.group(1) if m else None

    def _parse_iso_timestamp(self, ts_str: str) -> Optional[datetime]:
        """Parse ISO 8601 timestamp string."""
        try:
            # Handle various ISO formats
            ts_str = ts_str.replace("Z", "+00:00")
            return datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            try:
                return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")
            except (ValueError, TypeError):
                return None
