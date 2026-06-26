"""Atomic tool: SMS backup XML -> NormalizedRecords via SBV (PRIMARY parser).

SBV ("SMS Backup Viewer", ghcr.io/lowcarbdev/sbv) is the owner-chosen primary
SMS-XML engine: a Go service that parses "SMS Backup & Restore" XML (sms/mms +
call logs), converts MMS media (HEIC/3GP/AMR), and serves the result over a
session-authenticated REST API. This module uploads the XML to SBV, waits for
processing, fetches the parsed messages + calls, and maps them into the SAME
NormalizedRecord shape (incl. forensic call-block flags) that the pure-Python
fallback evidence/tools/sms_xml.py produces — so Workflow A, store, and the
knowledge engine never care which parser ran.

DUAL-PARSER / MESH SUBSTITUTION (ADR-0023, owner architecture): this tool and
sms_xml.py BOTH register capability `parse.sms-xml`. The registry returns them
in registration order, so importing this module FIRST makes SBV the preferred
parser and sms_xml.py the automatic fallback when SBV is unreachable/unhealthy
or rejects the input. Import order is enforced in evidence/tools/__init__... no —
auto-discovery imports modules alphabetically, and "sbv_sms" sorts before
"sms_xml", so SBV registers first naturally. (Verified: `sbv_sms` < `sms_xml`.)

Auth + endpoints: see evidence/tools/_sbv_client.py (session-cookie, /api/...).

Provenance: new module wrapping the SBV REST API (sbv-client.ts blueprint +
SBV_MCP_INTEGRATION.md). Forensic call-block logic mirrors sms_xml.py
(ported from dial-stack ConflictAnalysisApp).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from evidence.normalize import DisclosureTier, NormalizedRecord, RecordType
from evidence.registry import register
from evidence.tools._common import parse_timestamp, records_out
from evidence.tools._sbv_client import SBVClient, SBVError

OWNER = "owner"

# SBV message `type` (Android SMS Backup & Restore convention; same integers as
# sms_xml.py): meaning differs sms vs call.
_SMS_TYPE = {1: "received", 2: "sent", 3: "draft", 4: "outbox", 5: "failed", 6: "queued"}
_CALL_TYPE = {1: "incoming", 2: "outgoing", 3: "missed", 4: "voicemail", 5: "rejected", 6: "refused_list"}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_dt(value: Any):
    """SBV returns `date` as epoch milliseconds (number or numeric string) or an
    ISO string. Normalize to a tz-aware datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        ms = _as_int(value)
        return parse_timestamp(ms / 1000.0) if ms > 0 else None
    return parse_timestamp(str(value))


def _counterparty(msg: dict[str, Any]) -> str:
    name = (msg.get("contact_name") or "").strip()
    if name and name.lower() not in ("", "unknown", "(unknown)", "null"):
        return name
    return (msg.get("address") or msg.get("number") or "unknown").strip() or "unknown"


def _map_message(msg: dict[str, Any]) -> NormalizedRecord | None:
    text = (msg.get("body") or msg.get("text") or "").strip()
    if not text or text == "null":
        return None
    raw_type = _as_int(msg.get("type"), 0)
    direction = _SMS_TYPE.get(raw_type, "unknown")
    other = _counterparty(msg)
    role = OWNER if raw_type == 2 else other
    channel = "mms" if (msg.get("media_type") or msg.get("content_type") or msg.get("message_type")) else "sms"
    return NormalizedRecord(
        record_type=RecordType.message,
        source="sms-xml",
        conversation_id=other,
        role=role,
        participants=[OWNER, other],
        content=text,
        occurred_at=_to_dt(msg.get("date")),
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs={
            "channel": channel,
            "direction": direction,
            "raw_type": str(raw_type),
            "address": msg.get("address") or msg.get("number") or "",
            "contact_name": msg.get("contact_name") or "",
            "parser": "sbv",
            "media_type": msg.get("media_type") or "",
            "thread_id": msg.get("thread_id"),
        },
    )


def _map_call(call: dict[str, Any]) -> NormalizedRecord:
    raw_type = _as_int(call.get("type"), 0)
    label = _CALL_TYPE.get(raw_type, "unknown")
    duration = _as_int(call.get("duration"), 0)
    other = _counterparty(call)

    # Forensic call-blocking indicators (mirrors sms_xml.py / ConflictAnalysisApp).
    flags: list[str] = []
    if raw_type == 5:
        flags.append("call actively rejected")
    if raw_type == 6:
        flags.append("number on refuse/block list")
    if raw_type == 2 and duration == 0:
        flags.append("outgoing call with 0 duration - did not connect")
    blocked = bool(flags)

    content = f"{label.capitalize()} call with {other} (duration: {duration}s)"
    if flags:
        content += f" [FORENSIC FLAG: {', '.join(flags)}]"

    role = OWNER if raw_type == 2 else other
    return NormalizedRecord(
        record_type=RecordType.call,
        source="sms-xml",
        conversation_id=other,
        role=role,
        participants=[OWNER, other],
        content=content,
        occurred_at=_to_dt(call.get("date")),
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs={
            "channel": "call",
            "call_type": label,
            "raw_type": str(raw_type),
            "duration_seconds": duration,
            "address": call.get("number") or call.get("address") or "",
            "contact_name": call.get("contact_name") or "",
            "blocked": blocked,
            "forensic_flags": flags,
            "parser": "sbv",
        },
    )


def _sbv_enabled() -> bool:
    """SBV is the primary ONLY when explicitly wired (URL reachable + service
    creds present). Without creds, accept() returns False so the registry falls
    straight through to the pure-Python sms_xml.py fallback — no hard dep on a
    running SBV for SMS-XML to work."""
    return bool(os.getenv("SBV_SERVICE_PASS"))


@register(
    id="messages.sms-xml-sbv",
    capability="parse.sms-xml",
    description='SMS Backup & Restore XML via SBV (primary) -> normalized message + call records, with forensic call-block flags + MMS media handling',
    # Only accept .xml AND only when SBV is wired; else defer to sms_xml.py.
    accept=lambda hint, size: hint.lower().endswith(".xml") and _sbv_enabled(),
    provenance="SBV REST API wrapper (lowcarbdev/sbv) — primary SMS-XML parser; sms_xml.py is the pure-Python fallback",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    if not path.is_file():
        raise FileNotFoundError(f"sbv: file not found: {path}")

    client = SBVClient(
        base_url=payload.get("sbv_base_url"),
        username=payload.get("sbv_user"),
        password=payload.get("sbv_pass"),
    )

    # Fail loudly so the workflow's substitution layer moves to sms_xml.py.
    if not client.health():
        raise SBVError("SBV not healthy/reachable — falling back to pure-Python parser")

    client.upload(str(path))
    # SBV ALWAYS processes asynchronously (HandleUpload returns immediately with
    # processing=true and parses in a background goroutine) — so always wait.
    client.wait_for_processing()

    # /api/activity is SBV's "everything" stream: []ActivityItem, each wrapping
    # either a `message` or a `call` (there is no list-all-messages endpoint —
    # /api/messages requires an address). This avoids per-conversation fan-out.
    records: list[NormalizedRecord] = []
    for item in client.all_activity():
        kind = (item.get("type") or "").lower()
        if kind == "call":
            call = item.get("call") or item  # call fields may be nested or flat
            records.append(_map_call(call))
        else:
            msg = item.get("message") or item  # message fields nested or flat
            rec = _map_message(msg)
            if rec is not None:
                records.append(rec)

    if not records:
        # Empty result from SBV on a non-empty file is suspicious -> let the
        # workflow try the fallback rather than silently storing nothing.
        raise SBVError("SBV returned 0 records — falling back to pure-Python parser")

    messages = sum(1 for r in records if r.record_type == RecordType.message)
    calls = sum(1 for r in records if r.record_type == RecordType.call)
    blocked = sum(1 for r in records if r.attrs.get("blocked"))
    return records_out(records, messages=messages, calls=calls, blocked_calls=blocked, parser="sbv")
