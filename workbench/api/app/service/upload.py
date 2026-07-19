# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Upload service — hash, dedupe, stage to the object store + LanceDB.

Never chunks, embeds, or writes Milvus/Postgres — this only stages a whole
file (object-store copy + a `staged_files` row) for later promotion through
the existing platform ingestion API (see service/promote.py).

The runtime layer streams the incoming upload to a temp file while computing
its sha256 and enforcing the size cap (see runtime/upload.py); this module
receives that path + hash and never re-reads more than the 2MB text-extraction
window into memory.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from app.repo import object_store_client
from app.repo import staging
from app.config import settings
from app.service.detect import detect_type

logger = logging.getLogger(__name__)

MAX_TEXT_BYTES = 2 * 1024 * 1024  # 2MB extracted-text cap
_TEXT_EXTENSIONS = {"md", "txt", "json", "csv", "jsonl"}
_SNIFF_BYTES = 4096


class UploadError(Exception):
    """Raised when upload validation fails."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _extract_text(path: Path, filename: str) -> str:
    """Read up to MAX_TEXT_BYTES and decode for known text formats only.

    pdf/docx and anything else are staged with text="" — the workbench does
    not parse binary document formats itself; that happens downstream in the
    platform ingestion API after promotion.
    """
    if _extension(filename) not in _TEXT_EXTENSIONS:
        return ""
    with path.open("rb") as f:
        raw = f.read(MAX_TEXT_BYTES)
    return raw.decode("utf-8", errors="replace")


def stage_upload(tmp_path: str, sha256: str, size: int, filename: str) -> dict:
    """Stage an already-hashed, already-on-disk upload.

    Returns the staged_files record with an extra `duplicate` key: True if a
    row for this sha256 already existed (no new object-store write happens
    in that case).
    """
    if not filename:
        raise UploadError("No filename provided")
    if size == 0:
        raise UploadError("Empty file")
    if size > settings.max_upload_bytes:
        raise UploadError(f"File too large. Max size: {settings.max_upload_mb}MB", 413)

    existing = staging.get(sha256)
    if existing is not None:
        return {**existing, "duplicate": True}

    path = Path(tmp_path)
    mime, _ = mimetypes.guess_type(filename)
    mime = mime or "application/octet-stream"

    text = _extract_text(path, filename)
    if _extension(filename) in ("json", "jsonl"):
        detected_type = detect_type(filename, text)
    else:
        with path.open("rb") as f:
            sample = f.read(_SNIFF_BYTES)
        detected_type = detect_type(filename, sample)

    key = f"{settings.object_store_prefix}/{sha256}/{filename}"
    with path.open("rb") as f:
        object_store_client.put_object(key, f, content_type=mime)

    record = {
        "id": sha256,
        "name": filename,
        "size": size,
        "mime": mime,
        "detected_type": detected_type,
        "text": text,
        "meta": {},
        "r2_key": key,
        "status": "staged",
        "promote_result": None,
    }
    saved = staging.upsert_staged(record)
    logger.info("Staged upload: id=%s name=%s size=%d type=%s", sha256, filename, size, detected_type)
    return {**saved, "duplicate": False}
