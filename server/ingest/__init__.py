"""Framework-neutral Horizon ingest application layer.

Byline: Codex · GPT-5 · 2026-08-16
"""

from server.ingest.service import IngestError, ingest_file

__all__ = ["IngestError", "ingest_file"]
