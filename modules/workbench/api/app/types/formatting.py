# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Shared formatting utilities used across layers. Unchanged from the donor kit."""

from __future__ import annotations


def humanize_bytes(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024  # type: ignore[assignment]
    return f"{size:.1f} PB"
