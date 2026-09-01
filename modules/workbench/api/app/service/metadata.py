# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Presentation-only metadata helpers for staged files.

The donor kit's metadata.py extracted image EXIF and PDF info via Pillow and
PyPDF2. The workbench never inspects file internals beyond the text preview
already captured on the staged_files row (repo/staging.py) — pdf/docx are
staged with text="" (see service/upload.py) — so Pillow/PyPDF2 are dropped
from requirements.txt entirely. This module only derives display fields from
data already on the record; it does not open or parse the file itself.
"""

from __future__ import annotations

from app.types.formatting import humanize_bytes


def extension_of(filename: str) -> str:
    """Return the lowercased extension (no dot), or "" if none."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def build_display_metadata(name: str, size: int, mime: str) -> dict:
    """Derive presentation fields for a staged file's API response."""
    return {
        "extension": extension_of(name),
        "size_human": humanize_bytes(size),
        "mime": mime,
    }
