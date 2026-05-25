"""Transcript parsing system for AI conversation exports.

Supports multiple sources (ChatGPT, Claude, Gemini, Perplexity, Cursor)
and formats (JSON, HTML, Markdown, plain text).

Usage:
    from parsers import detect_format, parse_transcript, discover_transcripts

    # Find all transcripts in a directory
    transcripts = discover_transcripts("./knowledge/conversations")

    # Auto-detect and parse a single file
    result = parse_transcript("./chat-export.json")

    # Parse with known source
    result = parse_transcript("./chat-export.json", source_hint="chatgpt")
"""

from parsers.discovery import discover_transcripts, TranscriptFile
from parsers.detector import detect_format, FormatDetectionResult
from parsers.pipeline import parse_transcript, parse_multiple
from parsers.normalizer import NormalizedMessage, NormalizedConversation

__all__ = [
    "discover_transcripts",
    "TranscriptFile",
    "detect_format",
    "FormatDetectionResult",
    "parse_transcript",
    "parse_multiple",
    "NormalizedMessage",
    "NormalizedConversation",
]
