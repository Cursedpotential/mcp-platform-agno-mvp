# Byline: Codex · GPT-5 · 2026-08-03
"""Durable, hash-chained audit records for atomic tool execution.

The ledger stores hashes of payloads/results rather than their contents so an
execution can be proven without duplicating evidence or secrets into logs.
Repair calls fail closed when this ledger cannot be appended.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "platform-tool-execution-audit-v1"
CHAIN_CONSTRUCTION = "sha256(prev_hex + LF + canonical_event_json)"
GENESIS = ""

_LOCK = threading.Lock()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def content_sha256(value: Any) -> str:
    """Hash a JSON-compatible value using the ledger's canonical encoding."""
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _last_row(path: Path) -> dict[str, Any] | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    last: bytes | None = None
    with path.open("rb") as handle:
        for line in handle:
            if line.strip():
                last = line
    if last is None:
        return None
    try:
        value = json.loads(last)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"audit ledger has an invalid final row: {path}") from exc
    if not isinstance(value, dict) or not value.get("event_hash"):
        raise RuntimeError(f"audit ledger has an invalid final row: {path}")
    return value


def append_event(path: Path, event: dict[str, Any]) -> dict[str, Any]:
    """Append and fsync one event linked to the previous ledger head."""
    path = Path(path)
    with _LOCK:
        previous = _last_row(path)
        previous_hash = str(previous["event_hash"]) if previous else GENESIS
        sequence = int(previous["sequence"]) + 1 if previous else 1
        body = {
            "schema": SCHEMA,
            "chain_construction": CHAIN_CONSTRUCTION,
            "sequence": sequence,
            "previous_hash": previous_hash,
            **event,
        }
        event_hash = hashlib.sha256(f"{previous_hash}\n{_canonical(body)}".encode()).hexdigest()
        row = {**body, "event_hash": event_hash}
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(_canonical(row) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return row


def append_execution_event(
    path: Path,
    *,
    operation_id: str,
    phase: str,
    tool_id: str,
    capability: str,
    execution_policy: str,
    side_effect: str,
    execution_mode: str,
    payload_sha256: str,
    status: str,
    result_sha256: str | None = None,
    input_sha256: str | None = None,
    error_type: str | None = None,
) -> dict[str, Any]:
    """Append a privacy-preserving execution event."""
    return append_event(
        path,
        {
            "recorded_at": datetime.now(UTC).isoformat(),
            "operation_id": operation_id,
            "phase": phase,
            "tool_id": tool_id,
            "capability": capability,
            "execution_policy": execution_policy,
            "side_effect": side_effect,
            "execution_mode": execution_mode,
            "payload_sha256": payload_sha256,
            "input_sha256": input_sha256,
            "result_sha256": result_sha256,
            "status": status,
            "error_type": error_type,
        },
    )


def verify_ledger(path: Path) -> dict[str, Any]:
    """Verify every sequence number, previous link, and event hash."""
    path = Path(path)
    previous_hash = GENESIS
    count = 0
    errors: list[str] = []
    if not path.exists():
        return {"valid": True, "entries": 0, "chain_head": None, "errors": []}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"line {line_number}: invalid JSON")
                continue
            count += 1
            claimed = str(row.pop("event_hash", ""))
            expected = hashlib.sha256(f"{previous_hash}\n{_canonical(row)}".encode()).hexdigest()
            if row.get("sequence") != count:
                errors.append(f"line {line_number}: sequence mismatch")
            if row.get("previous_hash") != previous_hash:
                errors.append(f"line {line_number}: previous hash mismatch")
            if claimed != expected:
                errors.append(f"line {line_number}: event hash mismatch")
            previous_hash = claimed
    return {
        "valid": not errors,
        "entries": count,
        "chain_head": previous_hash or None,
        "errors": errors,
        "schema": SCHEMA,
        "chain_construction": CHAIN_CONSTRUCTION,
    }
