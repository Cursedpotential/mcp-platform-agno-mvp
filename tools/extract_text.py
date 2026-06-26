"""Atomic tool: extract text from a document — the general OCR / text-extraction
pass that runs BEFORE format parsing (capability `extract.text`).

WHY (owner, 2026-06-25): any non-OCR'd doc needs a text layer before a parser
can read it. Make ONE shared pass, not a per-parser hack: PDF parsers
(imessage_pdf, future doc parsers) + general evidence ingestion all resolve
`extract.text` to get text, THEN parse.

TIERED + COST-AWARE (owner is cost-conscious — no $ unless asked):
  1. NATIVE text layer (pypdf -> pdfplumber) — free, instant. Born-digital PDFs
     (incl. print-to-PDF of iMessage TXT/HTML) carry a real text layer, so this
     is the path for the owner's iMessage PDFs.
  2. OCR fallback (Tesseract: pytesseract + pdf2image / Pillow) — for image-only
     or scanned PDFs where the native layer is empty/sparse. Local, CPU-only
     (fits the no-GPU constraint), no $ cost.
  3. HEAVY OCR / document-AI (PROVIDER-PLURAL, dedicated OCR — NOT Claude: preserve
     Claude budget for reasoning; NOT Gemini-Pro). FREE-TIER-FIRST: IBM Docling
     (self-host via Colab Pro / a scale-to-zero GPU VPS), Google Cloud Vision /
     Document AI (free tier), Azure Document Intelligence, AWS Textract, z.AI/GLM.
     A stateless tool can't call a remote provider here, so when the result is
     low_confidence the CALLER escalates to the configured provider ($-gated, opt-in).

THIS IS A GENERAL CROSS-DOMAIN TOOL (any domain/surface calls it via MCP), not
evidence-specific — its current location under evidence/tools/ is just where the
mesh registry auto-discovers it; HOME it in a platform tool registry (pending
owner decision). All deps are OPTIONAL (graceful import) so this module imports
fine in the slim facade; a missing backend surfaces a clear error at RUN time.
Output: {"text", "pages": [per-page text], "stats": {method, ocr_used,
page_count, char_count, low_confidence, ext}} — NOT NormalizedRecords (this is a
pre-parse utility, not a parser).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evidence.registry import register

_PDF_EXT = (".pdf",)
_IMG_EXT = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif")
# avg chars/page below this -> treat the native text layer as absent (scanned).
_SPARSE_CHARS_PER_PAGE = 16


def _native_pdf_text(path: Path) -> tuple[list[str] | None, str]:
    """Tier 1: native text layer. pypdf preferred, pdfplumber fallback.
    Returns (pages, backend) or (None, '') if no native lib is installed."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [(pg.extract_text() or "") for pg in reader.pages], "pypdf"
    except ImportError:
        pass
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            return [(pg.extract_text() or "") for pg in pdf.pages], "pdfplumber"
    except ImportError:
        return None, ""


def _ocr_pdf(path: Path) -> tuple[list[str], str]:
    """Tier 2: Tesseract OCR over rasterized pages."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise RuntimeError(
            "extract.text: native text layer absent/sparse -> OCR needed, but the OCR "
            "stack is missing. Install: pip install pytesseract pdf2image + system "
            "`tesseract-ocr` & `poppler`. (Or run via the pdf-processing-anthropic skill.)"
        ) from exc
    return [pytesseract.image_to_string(img) for img in convert_from_path(str(path))], "tesseract"


def _ocr_image(path: Path) -> tuple[list[str], str]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("extract.text: image OCR needs pytesseract + Pillow (+ system tesseract-ocr).") from exc
    return [pytesseract.image_to_string(Image.open(str(path)))], "tesseract"


@register(
    id="documents.extract-text",
    capability="extract.text",
    description="General text/OCR extraction (run BEFORE format parsing): native PDF text layer -> Tesseract OCR fallback for image/scanned docs. Returns text+pages+stats; low_confidence flags caller to escalate to vision OCR ($-gated).",
    accept=lambda hint, size: hint.lower().endswith(_PDF_EXT + _IMG_EXT),
    provenance="document-intelligence layer (native pypdf/pdfplumber + Tesseract); vision OCR tier escalated by the caller",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    if not path.is_file():
        raise FileNotFoundError(f"extract.text: not found: {path}")
    ext = path.suffix.lower()
    ocr_used = False

    pages: list[str] | None
    if ext in _IMG_EXT:
        pages, method = _ocr_image(path)
        ocr_used = True
    else:  # PDF
        pages, method = _native_pdf_text(path)
        native_chars = sum(len(p) for p in pages) if pages else 0
        per_page = native_chars / max(len(pages or [1]), 1)
        sparse = pages is None or per_page < _SPARSE_CHARS_PER_PAGE
        if sparse and not payload.get("native_only"):
            # absent/sparse native layer -> scanned/image PDF -> OCR
            pages, method = _ocr_pdf(path)
            ocr_used = True
        elif pages is None:
            raise RuntimeError("extract.text: no PDF backend (install pypdf or pdfplumber)")

    text = "\n".join(pages).strip()
    return {
        "text": text,
        "pages": pages,
        "stats": {
            "method": method,
            "ocr_used": ocr_used,
            "page_count": len(pages),
            "char_count": len(text),
            # caller (agent/skill) may escalate to vision OCR ($-gated) when low_confidence:
            "low_confidence": not text,
            "ext": ext,
        },
    }
