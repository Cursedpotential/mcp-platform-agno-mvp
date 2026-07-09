"""Atomic tool: iMessage PDF -> NormalizedRecords (via text extraction + the TXT grammar).

ReagentX/imessage-exporter has NO native PDF exporter, so an iMessage PDF is a
PRINT-TO-PDF of the TXT (or HTML) output — it carries a real text layer. So we:
  1. extract the text layer natively (pypdf -> pdfplumber). These PDFs are
     born-digital, so the native layer is present; the general OCR pool
     (tools/extract_text.py, capability extract.text) is only for SCANNED docs.
  2. route the extracted text through imessage_txt.parse_txt_text() — the same
     timestamp/sender/body grammar engine, so PDF, TXT and HTML all normalize
     identically (tapbacks, replies, edits, read receipts preserved).

Extraction is isolated in `_extract_pdf_text` so it can be swapped to call the
shared extract.text tool (Tesseract/vision fallback) for scanned variants later.
Capability parse.imessage; siblings imessage_txt.py / imessage_html.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from server.evidence.normalize import RecordType
from server.evidence.registry import register
from server.evidence.tools._common import records_out
from server.evidence.tools.imessage_txt import looks_like_imessage_txt, parse_txt_text


def _extract_pdf_text(path: Path) -> str:
    """Native PDF text layer (born-digital print-to-PDF). pypdf preferred,
    pdfplumber fallback. For SCANNED/image PDFs the caller should route through
    the extract.text OCR pool instead — these export PDFs aren't scanned."""
    try:
        from pypdf import PdfReader

        return "\n".join((pg.extract_text() or "") for pg in PdfReader(str(path)).pages)
    except Exception:
        pass
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    except ImportError as exc:
        raise RuntimeError(
            "imessage-pdf needs pypdf or pdfplumber for the text layer "
            "(scanned PDFs: route through the extract.text OCR pool)."
        ) from exc


@register(
    id="messages.imessage-pdf",
    capability="parse.imessage",
    description="iMessage PDF (print-to-PDF of imessage-exporter TXT/HTML) -> normalized records via native text extraction + the shared TXT grammar (tapbacks/replies/edits/receipts preserved)",
    accept=lambda hint, size: hint.lower().endswith(".pdf"),
    provenance="native pypdf/pdfplumber text layer -> imessage_txt.parse_txt_text; OCR fallback via extract.text",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    text = _extract_pdf_text(path)
    if not looks_like_imessage_txt(text[:8192]):
        raise ValueError(
            "not an iMessage PDF (no imessage-exporter timestamp headers in the extracted text "
            "-- if it's a scanned/image PDF, run extract.text first)"
        )

    records = parse_txt_text(text, conv_id=path.stem)
    for r in records:  # re-stamp provenance: same grammar, PDF origin
        r.source = "imessage-pdf"
        r.attrs["format"] = "pdf"

    messages = sum(1 for r in records if r.record_type == RecordType.message)
    calls = sum(1 for r in records if r.record_type == RecordType.call)
    events = sum(1 for r in records if r.record_type == RecordType.event)
    return records_out(records, messages=messages, calls=calls, announcements=events, source="pdf")
