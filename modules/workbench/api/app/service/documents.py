# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Staging-table stats.

Rewired from the donor kit's documents.py, which reported LanceDB vector-store
stats (chunk counts) and ran semantic search over embedded chunks — this app
never chunks or embeds, so both of those no longer apply. The one concept
that survives is "give me stats", now reporting on the staged_files table
instead of a chunks table.
"""

from __future__ import annotations

from collections import Counter

from app.repo import staging


def get_staging_stats() -> dict:
    """Return counts of staged files by status and detected_type, plus total size."""
    records = staging.list(limit=10_000)
    by_status = Counter(r.get("status", "unknown") for r in records)
    by_type = Counter(r.get("detected_type", "unknown") for r in records)
    total_size = sum(r.get("size", 0) for r in records)
    return {
        "total_files": len(records),
        "total_size_bytes": total_size,
        "by_status": dict(by_status),
        "by_detected_type": dict(by_type),
    }
