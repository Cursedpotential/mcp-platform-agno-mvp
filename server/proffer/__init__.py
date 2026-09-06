"""Framework-neutral Horizon ingest application layer.

Byline: Codex · GPT-5 · 2026-08-16
"""

from server.proffer.service import IngestError, ingest_file

__all__ = ["IngestError", "ingest_file"]

# Package proffer (formerly server.ingest; renamed D-140, 2026-09-05). "Proffer": to offer
# evidence for consideration - presented, not yet admitted. The Go lane is modules/engine/proffer.
