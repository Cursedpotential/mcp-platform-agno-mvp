"""evidence/normalize.py — DEPRECATED shim. Import from ``server.contracts.records`` instead (ADR-0035, Option A moved the canonical record contract to the import-light contracts package)."""

from __future__ import annotations

from server.contracts.records import *  # noqa: F401,F403
from server.contracts.records import (
    DisclosureTier,
    NormalizedRecord,
    RecordType,
    finalize,
)

__all__ = ["DisclosureTier", "NormalizedRecord", "RecordType", "finalize"]
