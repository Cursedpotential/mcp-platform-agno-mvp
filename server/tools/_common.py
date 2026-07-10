"""Shared helpers for atomic parser tools (not a tool module itself —
underscore prefix excludes it from auto-discovery)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from server.contracts.records import NormalizedRecord


def parse_timestamp(value: Any) -> datetime | None:
    """Best-effort timestamp: epoch seconds (int/float) or ISO-8601 string."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str) and value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OSError, OverflowError):
        return None
    return None


def records_out(records: list[NormalizedRecord], **stats: Any) -> dict[str, Any]:
    """Standard tool output: JSON-safe record dicts + stats."""
    return {
        "records": [json.loads(r.model_dump_json()) for r in records],
        "stats": {"record_count": len(records), **stats},
    }
