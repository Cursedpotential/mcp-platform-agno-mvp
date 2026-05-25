"""
ChatMiner — Forensic-grade AI conversation parsing and analysis system.

Parses chat exports from ChatGPT, Claude, Gemini, Perplexity, Cursor, and
generic sources. Extracts artifacts (code, documents, files), segments by
topic, and prepares structured data for evidence processing.

Usage:
    # CLI — parse a single file
    python -m chatminer parse input.md --source chatgpt --output output.json

    # CLI — batch process a directory
    python -m chatminer batch ./conversations/ --recursive --output ./parsed/

    # CLI — segment parsed messages by topic
    python -m chatminer segment input.json --method local --output chunks.json

    # CLI — extract artifacts from parsed messages
    python -m chatminer artifacts input.json --output artifacts.json

    # Programmatic
    from chatminer import parse_file, segment_messages, extract_artifacts
    result = parse_file("export.md", source_hint="chatgpt")
    segments = segment_messages(result.messages, method="local")
    artifacts = extract_artifacts(result.messages)

    # MCP Tool (via Agno agent)
    ts_tools.call("parse_chatgpt_share", file_path="/path/to/export.md")
"""

__version__ = "0.1.0"
__author__ = "MCP Platform Team"

from chatminer.core.types import (
    ParsedMessage,
    ParsedConversation,
    Artifact,
    TopicSegment,
    ParseResult,
    ArtifactType,
)
from chatminer.core.pipeline import parse_file, parse_multiple, parse_directory
from chatminer.core.artifacts import extract_artifacts

__all__ = [
    "ParsedMessage",
    "ParsedConversation",
    "Artifact",
    "TopicSegment",
    "ParseResult",
    "ArtifactType",
    "parse_file",
    "parse_multiple",
    "parse_directory",
    "extract_artifacts",
]
