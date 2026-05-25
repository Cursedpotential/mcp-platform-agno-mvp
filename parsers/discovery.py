"""Transcript file discovery — find all conversation exports in a directory tree.

Scans recursively, identifies potential transcript files by extension and content
cues, and returns them with metadata for batch processing.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# Known transcript file signatures
KNOWN_FILENAMES = {
    # ChatGPT
    "conversations.json",
    "chatgpt_export.json",
    "chatgpt_conversations.json",
    "openai_conversations.json",
    # Claude
    "claude_conversations.json",
    "claude_export.json",
    "conversations.jsonl",
    "chatlog.jsonl",
    # Gemini
    "gemini_export.json",
    "gemini_conversations.json",
    "bard_export.json",
    # Perplexity
    "perplexity_export.json",
    "perplexity_conversations.json",
    # Generic
    "chat_history.json",
    "chat_export.json",
    "conversations.md",
    "chat_history.md",
    "transcript.md",
    "transcript.txt",
    "chat.txt",
    "conversation.txt",
}

# Extensions to scan content of (for auto-detection)
SCAN_EXTENSIONS = {".json", ".jsonl", ".md", ".txt", ".html", ".htm"}

# Maximum file size to scan (bytes)
MAX_SCAN_SIZE = 50 * 1024 * 1024  # 50 MB


@dataclass(frozen=True)
class TranscriptFile:
    """Represents a discovered transcript file with metadata."""

    path: Path
    size_bytes: int
    source_hint: str | None = None
    format_hint: str | None = None
    confidence: float = 0.0  # 0-1, how confident we are this is a transcript

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()

    @property
    def size_human(self) -> str:
        """Human-readable file size."""
        for unit in ["B", "KB", "MB", "GB"]:
            if self.size_bytes < 1024:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024  # type: ignore[assignment]
        return f"{self.size_bytes:.1f} TB"


def _quick_content_check(path: Path) -> tuple[str | None, float]:
    """Quickly peek at file content to detect source and format.

    Returns: (source_hint, confidence)
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            sample = f.read(8192)
    except (IOError, OSError):
        return None, 0.0

    if not sample:
        return None, 0.0

    # JSON checks
    if path.suffix.lower() in (".json", ".jsonl"):
        return _detect_json_source(sample, path)

    # Markdown checks
    if path.suffix.lower() == ".md":
        return _detect_markdown_source(sample)

    # Text checks
    if path.suffix.lower() == ".txt":
        return _detect_text_source(sample)

    # HTML checks
    if path.suffix.lower() in (".html", ".htm"):
        return _detect_html_source(sample)

    return None, 0.0


def _detect_json_source(sample: str, path: Path) -> tuple[str | None, float]:
    """Detect AI source from JSON content."""
    # ChatGPT: conversations.json has "mapping", "title", "create_time"
    if '"mapping"' in sample and '"title"' in sample and '"create_time"' in sample:
        return "chatgpt", 0.95
    # ChatGPT: array of conversations
    if sample.strip().startswith("[") and '"message"' in sample and '"author"' in sample:
        if "'role': 'system'" in sample or '"role": "system"' in sample:
            return "chatgpt", 0.85

    # Claude: has "uuid", "name" fields per conversation
    if '"uuid"' in sample and ("'name'" in sample or '"name"' in sample):
        if "'chatbot'" in sample or '"chatbot"' in sample or "'claude'" in sample.lower():
            return "claude", 0.90

    # Gemini: specific fields
    if (
        "'gemini'" in sample.lower()
        or '"gemini"' in sample.lower()
        or "'bard'" in sample.lower()
    ):
        return "gemini", 0.90

    # Perplexity
    if "'perplexity'" in sample.lower() or '"perplexity"' in sample.lower():
        return "perplexity", 0.90

    # Generic: has messages array with role/content
    if "'messages'" in sample or '"messages"' in sample:
        if "'role'" in sample and "'content'" in sample:
            return "generic_json", 0.60

    # JSONL: check first line
    if path.suffix.lower() == ".jsonl":
        first_line = sample.split("\n")[0]
        if first_line:
            try:
                obj = json.loads(first_line)
                if "role" in obj and "content" in obj:
                    return "generic_jsonl", 0.60
                if "message" in obj or "messages" in obj:
                    return "generic_jsonl", 0.55
            except json.JSONDecodeError:
                pass

    return None, 0.0


def _detect_markdown_source(sample: str) -> tuple[str | None, float]:
    """Detect AI source from Markdown content."""
    # ChatGPT: specific markers
    if "**ChatGPT**" in sample or "**You**" in sample and "**ChatGPT said:**" in sample:
        return "chatgpt", 0.85

    # Claude: specific markers
    if (
        "**Human:**" in sample
        or "**Claude:**" in sample
        or "**Assistant:**" in sample
    ):
        if "**thinking**" in sample.lower() or "**Claude**" in sample:
            return "claude", 0.85

    # Gemini
    if "**Gemini**" in sample or "**Google**" in sample:
        return "gemini", 0.80

    # Perplexity: often has Sources section
    if "**Sources**" in sample and ("**Perplexity**" in sample or "**Answer**" in sample):
        return "perplexity", 0.85

    # Cursor: IDE context markers
    if "```python" in sample and "**User**" in sample and ("**AI**" in sample or "**Assistant**" in sample):
        return "cursor", 0.70

    # Generic: has role markers and code blocks
    role_markers = ["**User**", "**Human**", "**Assistant**", "**AI**"]
    if any(m in sample for m in role_markers) and "```" in sample:
        return "generic_md", 0.50

    return None, 0.0


def _detect_text_source(sample: str) -> tuple[str | None, float]:
    """Detect AI source from plain text content."""
    # ChatGPT
    if "ChatGPT" in sample[:2000] and ("User:" in sample or "Human:" in sample):
        return "chatgpt", 0.70

    # Claude
    if "Claude" in sample[:2000] and ("Human:" in sample or "H:" in sample):
        return "claude", 0.70

    # Gemini
    if "Gemini" in sample[:2000]:
        return "gemini", 0.65

    # Perplexity
    if "Perplexity" in sample[:2000]:
        return "perplexity", 0.65

    # Generic: turn-based with separators
    if ("User:" in sample or "Human:" in sample) and (
        "Assistant:" in sample or "AI:" in sample
    ):
        return "generic_text", 0.40

    return None, 0.0


def _detect_html_source(sample: str) -> tuple[str | None, float]:
    """Detect AI source from HTML content."""
    if "chatgpt" in sample.lower() or "openai" in sample.lower():
        return "chatgpt", 0.60
    if "claude" in sample.lower() or "anthropic" in sample.lower():
        return "claude", 0.60
    if "gemini" in sample.lower() or "bard" in sample.lower():
        return "gemini", 0.55
    if "perplexity" in sample.lower():
        return "perplexity", 0.55

    # Generic: has message bubbles
    if "message" in sample.lower() and ("bubble" in sample.lower() or "chat" in sample.lower()):
        return "generic_html", 0.30

    return None, 0.0


def discover_transcripts(
    root_path: str | Path,
    recursive: bool = True,
    min_confidence: float = 0.3,
) -> list[TranscriptFile]:
    """Find all potential transcript files in a directory.

    Args:
        root_path: Directory to scan
        recursive: Whether to scan subdirectories
        min_confidence: Minimum confidence score to include (0-1)

    Returns:
        List of TranscriptFile objects sorted by confidence
    """
    root = Path(root_path).resolve()
    if not root.exists():
        return []

    results: list[TranscriptFile] = []

    if recursive:
        files = root.rglob("*")
    else:
        files = root.iterdir()

    for path in files:
        if not path.is_file():
            continue

        # Check by known filename
        if path.name.lower() in {f.lower() for f in KNOWN_FILENAMES}:
            source, confidence = _quick_content_check(path)
            results.append(
                TranscriptFile(
                    path=path,
                    size_bytes=path.stat().st_size,
                    source_hint=source,
                    format_hint=path.suffix.lower().lstrip("."),
                    confidence=confidence or 0.8,
                )
            )
            continue

        # Check by extension + content
        if path.suffix.lower() in SCAN_EXTENSIONS:
            size = path.stat().st_size
            if size > MAX_SCAN_SIZE:
                continue  # Skip oversized files

            source, confidence = _quick_content_check(path)
            if confidence >= min_confidence:
                results.append(
                    TranscriptFile(
                        path=path,
                        size_bytes=size,
                        source_hint=source,
                        format_hint=path.suffix.lower().lstrip("."),
                        confidence=confidence,
                    )
                )

    # Sort by confidence descending
    results.sort(key=lambda x: x.confidence, reverse=True)
    return results


def print_discovery_report(results: list[TranscriptFile]) -> None:
    """Print a formatted report of discovered transcript files."""
    if not results:
        print("No transcript files found.")
        return

    print(f"\nFound {len(results)} potential transcript file(s):\n")
    print(f"{'Confidence':>10} {'Size':>10} {'Source':>12} {'Format':>8}  Path")
    print("-" * 80)

    for f in results:
        size_str = f.size_human
        source = f.source_hint or "unknown"
        print(
            f"{f.confidence:>9.0%} {size_str:>10} {source:>12} "
            f"{f.format_hint or '??':>8}  {f.path}"
        )

    # Group by source
    from collections import Counter

    sources = Counter(r.source_hint or "unknown" for r in results)
    print(f"\nBy source:")
    for source, count in sources.most_common():
        print(f"  {source}: {count}")
