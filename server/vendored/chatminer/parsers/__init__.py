"""
ChatMiner Format Parsers — one per AI chat source.

Each parser converts a source-specific export format into the standardized
ParsedConversation / ParsedMessage types used throughout the system.

To add a new parser:
    1. Create a new file in this directory
    2. Inherit from BaseParser
    3. Implement can_parse() and parse_content()
    4. Register in PARSER_REGISTRY below

Registered parsers (checked in order):
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.vendored.chatminer.core.base import BaseParser

from server.vendored.chatminer.parsers.chatgpt_share import ChatGptShareParser
from server.vendored.chatminer.parsers.chatgpt_official import ChatGptOfficialParser
from server.vendored.chatminer.parsers.gemini_chrome import GeminiChromeParser
from server.vendored.chatminer.parsers.gemini_json import GeminiJsonParser
from server.vendored.chatminer.parsers.claude_md import ClaudeMdParser
from server.vendored.chatminer.parsers.claude_code import ClaudeCodeParser
from server.vendored.chatminer.parsers.perplexity_gdpr import PerplexityGdprParser
from server.vendored.chatminer.parsers.perplexity_plugin import PerplexityPluginParser
from server.vendored.chatminer.parsers.perplexity_md import PerplexityMdParser
from server.vendored.chatminer.parsers.generic_md import GenericMdParser

# Registry: parsers are tried in this order for auto-detection.
# More specific formats first, generic fallbacks last.
PARSER_REGISTRY: list[type] = [
    # Source-specific — high confidence detectors
    ChatGptOfficialParser,  # ChatGPT official JSON export
    ChatGptShareParser,  # ChatGPT "Share" markdown
    GeminiChromeParser,  # Gemini Chrome extension
    GeminiJsonParser,  # Gemini JSON export
    ClaudeCodeParser,  # Claude Code JSONL
    PerplexityGdprParser,  # Perplexity GDPR export
    PerplexityPluginParser,  # Perplexity plugin copy-paste
    ClaudeMdParser,  # Claude markdown copy-paste
    PerplexityMdParser,  # Perplexity markdown (generic)
    # Fallbacks
    GenericMdParser,  # Any markdown with role markers
]


def get_parser_for_file(path: str, content: str | None = None) -> "BaseParser | None":
    """
    Auto-detect the best parser for a file.

    Reads file content if not provided, then asks each parser
    in the registry for its confidence score. Returns the highest
    confidence parser, or None if no parser matches.
    """
    from server.vendored.chatminer.core.base import BaseParser, ParserConfig

    if content is None:
        # Read first 8KB for detection (fast)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(8192)
        except Exception:
            return None

    best_parser: BaseParser | None = None
    best_score = 0.0

    for parser_cls in PARSER_REGISTRY:
        try:
            parser = parser_cls(ParserConfig())
            score = parser.can_parse(content, path)
            if score > best_score and score >= 0.5:  # Minimum threshold
                best_score = score
                best_parser = parser
        except Exception:
            continue

    return best_parser


__all__ = [
    "PARSER_REGISTRY",
    "get_parser_for_file",
    "ChatGptShareParser",
    "ChatGptOfficialParser",
    "GeminiChromeParser",
    "GeminiJsonParser",
    "ClaudeMdParser",
    "ClaudeCodeParser",
    "PerplexityGdprParser",
    "PerplexityPluginParser",
    "PerplexityMdParser",
    "GenericMdParser",
]
