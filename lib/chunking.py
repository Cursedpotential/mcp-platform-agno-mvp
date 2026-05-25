"""Shared transcript chunking utilities.

Extracted from scripts/mine_transcripts.py for reuse by both the batch
script and the /v1/transcripts/mine API endpoint.

Provides intelligent transcript splitting that preserves conversational
boundaries (sessions, tool calls, paragraphs) rather than doing naive
token-count slicing.
"""

import re
from pathlib import Path
from typing import Optional

# File extensions we recognize as chat transcripts
TRANSCRIPT_EXTENSIONS = {".txt", ".md", ".json", ".html", ".htm"}

# Max file size in MB
MAX_FILE_MB = 50


def detect_format(content: str, ext: str) -> str:
    """Detect the chat export format from content clues.

    Inspects the first 2000 characters for platform-specific markers
    (ChatGPT, Claude, Cursor) and falls back to the file extension.

    Args:
        content: Raw transcript text.
        ext: File extension (e.g. '.txt', '.json').

    Returns:
        Format identifier: 'chatgpt_json', 'chatgpt', 'claude', 'cursor', 'generic'.
    """
    if ext == ".json":
        return "chatgpt_json"
    if "ChatGPT" in content[:2000] or "chatgpt" in content[:2000].lower():
        return "chatgpt"
    if "Claude" in content[:2000] or "claude.ai" in content[:2000]:
        return "claude"
    if "Cursor" in content[:2000]:
        return "cursor"
    return "generic"


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text.

    This is a fast heuristic. For precise counts use a tokenizer,
    but this is sufficient for chunk-sizing decisions.
    """
    return len(text) // 4


def smart_chunk(content: str, chunk_size: int = 8000) -> list[dict]:
    """Split transcript into intelligent chunks.

    Strategy (in priority order):
    1. Look for explicit session/thread markers
    2. Split on tool call boundaries
    3. Split on topic shifts (double-newline paragraphs)
    4. Fall back to paragraph-aware sliding window

    Args:
        content: Raw transcript text.
        chunk_size: Target max tokens per chunk (default 8000).

    Returns:
        List of dicts, each with keys:
            - position: str label (e.g. 'session_1', 'tool_chunk_3', 'chunk_5')
            - content: str, the chunk text
            - estimated_tokens: int, rough token count for this chunk
    """
    chunks: list[dict] = []
    max_chars = chunk_size * 4  # chars ≈ tokens * 4

    # Try 1: Explicit session markers (common in ChatGPT exports)
    session_markers = [
        r"\n#{1,2}\s*(?:New|Chat|Session|Conversation)",
        r"\n-+'\s*(?:new chat|session)\s*-+",
        r"\n\[\d{4}-\d{2}-\d{2}.*?\]",
    ]
    for marker in session_markers:
        parts = re.split(marker, content, flags=re.IGNORECASE)
        if len(parts) > 2:
            for i, part in enumerate(parts):
                if part.strip():
                    stripped = part.strip()
                    chunks.append({
                        "position": f"session_{i + 1}",
                        "content": stripped[:max_chars],
                        "estimated_tokens": estimate_tokens(stripped),
                    })
            return chunks

    # Try 2: Tool call boundaries (function_call markers)
    if "function_call" in content or "<tool>" in content or "<function>" in content:
        tool_splits = re.split(
            r"(function_call|<tool>|<function>|<function_calls>)",
            content,
            flags=re.IGNORECASE,
        )
        current_chunk = ""
        chunk_num = 1
        for part in tool_splits:
            if len(current_chunk) + len(part) > max_chars and current_chunk:
                chunks.append({
                    "position": f"tool_chunk_{chunk_num}",
                    "content": current_chunk.strip(),
                    "estimated_tokens": estimate_tokens(current_chunk),
                })
                current_chunk = part
                chunk_num += 1
            else:
                current_chunk += part
        if current_chunk.strip():
            chunks.append({
                "position": f"tool_chunk_{chunk_num}",
                "content": current_chunk.strip(),
                "estimated_tokens": estimate_tokens(current_chunk),
            })
        if chunks:
            return chunks

    # Try 3: Paragraph splitting (double-newline = topic boundary)
    paragraphs = content.split("\n\n")
    current_chunk = ""
    chunk_num = 1
    for para in paragraphs:
        if len(current_chunk) + len(para) > max_chars and current_chunk:
            chunks.append({
                "position": f"chunk_{chunk_num}",
                "content": current_chunk.strip(),
                "estimated_tokens": estimate_tokens(current_chunk),
            })
            current_chunk = para
            chunk_num += 1
        else:
            current_chunk += "\n\n" + para if current_chunk else para
    if current_chunk.strip():
        chunks.append({
            "position": f"chunk_{chunk_num}",
            "content": current_chunk.strip(),
            "estimated_tokens": estimate_tokens(current_chunk),
        })

    # Fallback: return what we have, or a single full slice
    return chunks if chunks else [{
        "position": "full",
        "content": content[:max_chars],
        "estimated_tokens": estimate_tokens(content),
    }]
