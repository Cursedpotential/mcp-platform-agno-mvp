"""Atomic structured document extraction through optional Docling.

Docling is imported lazily so registry discovery remains safe in lightweight
containers.

Fallback behaviour is asymmetric — read this before assuming coverage:

- ``.pdf`` — the caller (``server/proffer/service.py:_extract_document``) also appends
  ``documents.extract-text``, so a missing ``document-ai`` extra degrades to
  native/Tesseract extraction as intended.
- ``.docx`` / ``.pptx`` / ``.xlsx`` / ``.html`` / ``.htm`` — **no fallback is registered**
  (``service.py:155-158`` adds ``extract-text`` for ``.pdf`` only). Because the import below
  is lazy, this module imports cleanly without docling, gets registered, and then raises at
  call time; the caller exhausts its extractor list and fails the whole ingest.

So without the ``document-ai`` extra installed, those five office formats do not degrade —
they fail. Tracked as URGENT-TODO #17.

Byline: Codex · GPT-5 · 2026-08-13
Byline amendment: Claude Code · Opus 5 · 2026-08-23 (corrected the fallback claim — the
previous docstring stated the caller falls through to native/Tesseract, which holds for
``.pdf`` only)
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
