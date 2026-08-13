"""Atomic structured document extraction through optional Docling.

Docling is imported lazily so registry discovery remains safe in lightweight
containers. The extraction caller falls through to native/Tesseract when the
``document-ai`` extra is unavailable or conversion fails.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from server.tools.registry import register

_SUPPORTED = (".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".png", ".jpg", ".jpeg", ".tiff", ".webp")


@register(
    id="documents.extract-docling",
    capability="extract.text",
    description="Docling structured document extraction with layout, tables, reading order, and OCR.",
    accept=lambda hint, size: hint.lower().endswith(_SUPPORTED),
    provenance="Docling optional document-ai tier; structured Markdown output; local execution",
)
def extract_docling(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        from docling.document_converter import DocumentConverter  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError('Docling is unavailable; install the "document-ai" extra') from exc

    result = DocumentConverter().convert(str(path))
    markdown = result.document.export_to_markdown()
    return {
        "text": markdown,
        "pages": [markdown],
        "stats": {
            "method": "docling",
            "ocr_used": path.suffix.lower() in {".png", ".jpg", ".jpeg", ".tiff", ".webp"},
            "page_count": 1,
            "char_count": len(markdown),
            "low_confidence": not markdown.strip(),
            "structured": True,
        },
    }
