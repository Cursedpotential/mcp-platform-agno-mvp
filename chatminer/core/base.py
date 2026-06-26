"""
Base parser class — all format parsers inherit from this.

Provides shared functionality: file reading, encoding detection,
SHA-256 hashing, error handling, and standardized output.
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from chatminer.core.types import ParsedConversation, ParseResult

logger = logging.getLogger(__name__)


@dataclass
class ParserConfig:
    """Configuration options for all parsers."""

    encoding: str = "utf-8"  # File encoding
    fallback_encodings: list[str] = field(default_factory=lambda: ["utf-8-sig", "latin-1", "cp1252"])
    max_file_size_mb: int = 50  # Skip files larger than this
    compute_hash: bool = True  # SHA-256 hash of raw content
    preserve_line_breaks: bool = True
    extract_code_blocks: bool = True
    extract_urls: bool = True


class BaseParser(ABC):
    """
    Abstract base class for all chat format parsers.

    Every format-specific parser (ChatGPT, Gemini, Claude, etc.)
    inherits from this and implements the parse_* methods.

    Usage:
        parser = ChatGptShareParser(config)
        result = parser.parse_file("export.md")
        for conv in result.conversations:
            print(f"{conv.title}: {conv.message_count} messages")
    """

    # Override in subclass
    SUPPORTED_FORMATS: list[str] = []
    SOURCE_NAME: str = "unknown"

    def __init__(self, config: Optional[ParserConfig] = None):
        self.config = config or ParserConfig()
        self.errors: list[dict] = []

    def read_file(self, path: str | Path) -> str:
        """
        Read file content with encoding fallback.

        Tries primary encoding first, then fallbacks.
        Logs which encoding succeeded for debugging.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.config.max_file_size_mb:
            raise ValueError(f"File too large: {size_mb:.1f} MB (max: {self.config.max_file_size_mb} MB)")

        encodings = [self.config.encoding] + self.config.fallback_encodings
        last_error = None

        for enc in encodings:
            try:
                content = path.read_text(encoding=enc)
                if enc != self.config.encoding:
                    logger.info(f"Used fallback encoding {enc} for {path.name}")
                return content
            except (UnicodeDecodeError, LookupError) as e:
                last_error = e
                continue

        raise last_error or ValueError(f"Could not decode {path} with any encoding")

    def compute_file_hash(self, path: str | Path) -> str:
        """SHA-256 hash of file contents for chain of custody."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @abstractmethod
    def can_parse(self, content: str, path: Optional[str] = None) -> float:
        """
        Confidence (0.0-1.0) that this parser can handle the content.

        Used by the auto-detector to pick the right parser.
        Should be FAST — just check signatures, don't parse everything.
        """
        ...

    @abstractmethod
    def parse_content(self, content: str, source_file: str = "") -> list[ParsedConversation]:
        """
        Parse file content into standardized conversations.

        This is the main work method. Every subclass implements
        its format-specific parsing logic here.
        """
        ...

    def parse_file(self, path: str | Path) -> ParseResult:
        """
        Full pipeline: read file → parse → return result.

        This is what CLI, GUI, MCP tools, and agents call.
        """
        path = Path(path)
        result = ParseResult()

        try:
            content = self.read_file(path)
            file_hash = self.compute_file_hash(path) if self.config.compute_hash else None

            conversations = self.parse_content(content, source_file=str(path))

            for conv in conversations:
                conv.source_file = str(path)
                conv.source_format = self.SOURCE_NAME
                if file_hash and not conv.metadata.get("file_hash"):
                    conv.metadata["file_hash"] = file_hash

            result.conversations = conversations

        except Exception as e:
            logger.error(f"Failed to parse {path}: {e}")
            result.errors.append({"file": str(path), "error": str(e)})

        return result

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(source={self.SOURCE_NAME})"
