"""
ChatMiner Core Types — shared data structures for all parsers and tools.

Every parser outputs these standardized types. Every tool consumes them.
This is the contract between format parsing, artifact extraction, topic
segmentation, and knowledge assembly.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional


class ContentType(Enum):
    """Classification of message content type."""
    TEXT = "text"           # Plain text conversation
    CODE = "code"           # Fenced code block (```...```)
    FILE_REF = "file_ref"   # Reference to attached file
    IMAGE_REF = "image_ref" # Reference to image/attachment
    URL = "url"             # URL/link reference
    SYSTEM = "system"       # System/instruction message
    ERROR = "error"         # Error/debug output


class ArtifactType(Enum):
    """Classification of extracted artifacts."""
    CODE_SNIPPET = "code_snippet"       # Extracted code block
    DOCUMENT = "document"               # .docx, .pdf created in chat
    DATA_FILE = "data_file"             # .json, .csv attached
    IMAGE = "image"                     # Image/screenshot
    URL = "url"                         # External link
    STRATEGY_DOC = "strategy_doc"       # Legal strategy discussed
    ANALYSIS_REPORT = "analysis_report" # Analysis output
    TIMELINE_EVENT = "timeline_event"   # Dated event mentioned
    ENTITY = "entity"                   # Named person/place/org


class MessageRole(Enum):
    """Role of the message sender."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"          # Tool/function call result
    UNKNOWN = "unknown"


class TopicTag(Enum):
    """Semantic topic classification for conversation segments.

    NOTE (platform 2026-06-13): RELATIONSHIP_HISTORY is its own first-class lane
    (owner decision) — the factual who/what/when narrative substrate that drives
    heavy entity extraction + timeline construction. PERSONAL_LEGAL is narrowed to
    legal strategy / case-handling. TopicTag is a SEPARATE metadata field, NOT a
    knowledge-engine domain. Tag at SEGMENT/TURN level; MIXED/UNKNOWN are catch-alls.
    """
    RELATIONSHIP_HISTORY = "relationship_history"  # Personal/relationship history — entities + timeline
    PERSONAL_LEGAL = "personal_legal"   # Legal strategy / case-handling
    DEVELOPMENT = "development"         # Code, architecture, platform
    EMOTIONAL = "emotional"             # Feelings, trauma processing
    EVIDENCE = "evidence"               # Evidence artifacts, documents
    MIXED = "mixed"                     # Interleaved topics
    UNKNOWN = "unknown"                 # Cannot classify


@dataclass
class ParsedMessage:
    """
    Single normalized message from any chat source.

    All parsers convert their source-specific format into this
    standardized structure. This is the atom of ChatMiner.
    """
    message_id: str                          # Stable UUID
    source_file: str                         # Origin filename
    source_format: str                       # e.g. "chatgpt_share", "gemini_chrome"
    source_index: int                        # Position in original file
    timestamp: Optional[datetime] = None     # When message was sent
    sender: str = "unknown"                  # Display name
    sender_role: MessageRole = MessageRole.UNKNOWN
    content: str = ""                        # Verbatim content (NEVER summarized)
    content_type: ContentType = ContentType.TEXT
    language: Optional[str] = None           # For code blocks: python, json, etc.
    confidence: str = "HIGH"                 # HIGH | MEDIUM | LOW
    metadata: dict[str, Any] = field(default_factory=dict)
    # ^ source-specific extras: turn_index, model_name, citations, etc.

    def compute_hash(self) -> str:
        """SHA-256 hash of verbatim content for chain of custody."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat() if self.timestamp else None
        d["sender_role"] = self.sender_role.value
        d["content_type"] = self.content_type.value
        d["message_hash"] = self.compute_hash()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ParsedMessage:
        """Deserialize from dict."""
        ts = d.get("timestamp")
        return cls(
            message_id=d.get("message_id", str(uuid.uuid4())),
            source_file=d.get("source_file", ""),
            source_format=d.get("source_format", "unknown"),
            source_index=d.get("source_index", 0),
            timestamp=datetime.fromisoformat(ts) if ts else None,
            sender=d.get("sender", "unknown"),
            sender_role=MessageRole(d.get("sender_role", "unknown")),
            content=d.get("content", ""),
            content_type=ContentType(d.get("content_type", "text")),
            language=d.get("language"),
            confidence=d.get("confidence", "HIGH"),
            metadata=d.get("metadata", {}),
        )


@dataclass
class ParsedConversation:
    """
    A complete conversation — collection of messages with metadata.

    Produced by every format parser. The standard unit of work.
    """
    conversation_id: str                     # UUID
    source_file: str                         # Origin file path
    source_format: str                       # Parser that produced this
    title: Optional[str] = None              # Conversation title
    created_at: Optional[datetime] = None    # When conversation started
    updated_at: Optional[datetime] = None    # When last updated
    messages: list[ParsedMessage] = field(default_factory=list)
    # ^ Chronologically ordered messages
    metadata: dict[str, Any] = field(default_factory=dict)
    # ^ Source-specific: model name, collection, mode, URL, etc.

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def user_messages(self) -> list[ParsedMessage]:
        return [m for m in self.messages if m.sender_role == MessageRole.USER]

    @property
    def assistant_messages(self) -> list[ParsedMessage]:
        return [m for m in self.messages if m.sender_role == MessageRole.ASSISTANT]

    @property
    def code_blocks(self) -> list[ParsedMessage]:
        return [m for m in self.messages if m.content_type == ContentType.CODE]

    def to_dict(self) -> dict:
        """Serialize full conversation to dict."""
        return {
            "conversation_id": self.conversation_id,
            "source_file": self.source_file,
            "source_format": self.source_format,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": self.message_count,
            "metadata": self.metadata,
            "messages": [m.to_dict() for m in self.messages],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class Artifact:
    """
    Something created or referenced IN a conversation.

    Could be code written, a document generated, a file attached,
    a URL shared, or a legal strategy discussed. These are the
    tangible outputs of your AI conversations.
    """
    artifact_id: str
    artifact_type: ArtifactType
    source_message_id: str           # Which message produced this
    source_conversation_id: str      # Which conversation
    title: Optional[str] = None     # Display name
    content: Optional[str] = None   # Code text, document text, etc.
    file_path: Optional[str] = None # If saved to disk
    language: Optional[str] = None  # For code: python, json, etc.
    metadata: dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["artifact_type"] = self.artifact_type.value
        d["extracted_at"] = self.extracted_at.isoformat()
        return d


@dataclass
class TopicSegment:
    """
    A semantically coherent chunk of a conversation.

    Produced by the topic segmenter. Messages within a segment
    discuss the same topic. Segments span conversation boundaries.
    """
    segment_id: str
    messages: list[ParsedMessage]
    topic_tag: TopicTag
    topic_confidence: float  # 0.0 - 1.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    keywords: list[str] = field(default_factory=list)
    summary: Optional[str] = None  # Auto-generated, not used for evidence

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def char_count(self) -> int:
        return sum(len(m.content) for m in self.messages)

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "topic_tag": self.topic_tag.value,
            "topic_confidence": round(self.topic_confidence, 4),
            "message_count": self.message_count,
            "char_count": self.char_count,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "keywords": self.keywords,
            "summary": self.summary,
            "messages": [m.to_dict() for m in self.messages],
        }


@dataclass
class ParseResult:
    """
    Complete result of parsing one or more files.

    Used by CLI, GUI, MCP tools, and agents.
    """
    conversations: list[ParsedConversation] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    segments: list[TopicSegment] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    # ^ Files that failed to parse: [{"file": str, "error": str}]
    processed_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_messages(self) -> int:
        return sum(c.message_count for c in self.conversations)

    @property
    def total_conversations(self) -> int:
        return len(self.conversations)

    @property
    def total_artifacts(self) -> int:
        return len(self.artifacts)

    def to_dict(self) -> dict:
        return {
            "processed_at": self.processed_at.isoformat(),
            "total_conversations": self.total_conversations,
            "total_messages": self.total_messages,
            "total_artifacts": self.total_artifacts,
            "errors": self.errors,
            "conversations": [c.to_dict() for c in self.conversations],
            "artifacts": [a.to_dict() for a in self.artifacts],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
