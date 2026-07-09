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

from server.evidence.normalize import DisclosureTier, NormalizedRecord, RecordType
from server.evidence.registry import register
from server.evidence.tools._common import parse_timestamp, records_out
from server.evidence.tools._sbv_client import SBVClient, SBVError

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
            # H2 per-record custody hash (sha256 of the RAW source XML element,
            # h2-rawelement-v1) as computed by SBV BEFORE normalization. This is
            # the evidence hash — NOT a hash of this NormalizedRecord.
            "content_hash": msg.get("content_hash") or "",
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
            # H2 per-record custody hash of the RAW <call> element (see _map_message).
            "content_hash": call.get("content_hash") or "",
        },
    )


def _reconcile_custody(
    path: Path, payload: dict[str, Any], client: SBVClient, records: list[NormalizedRecord]
) -> dict[str, Any] | None:
    """Forensic custody cross-check (Phase 4): pull SBV's independently-computed
    H1/H3 for this import + the per-record H2s, and reconcile against our OWN H1
    via the custody gate (verified vs integrity_violation, plus H2/H3 evidence
    rows). SBV holds no DB creds — every write happens in custody.py.

    Opt-in (SBV_CUSTODY_ENABLED) and defensively lazy: the slim tools-facade has
    no sqlalchemy, so importing custody there would fail — we skip cleanly. This
    is why the custody import is INSIDE the function, never at module top (which
    load_builtin_tools() imports to register the parser)."""
    if not os.getenv("SBV_CUSTODY_ENABLED"):
        return None
    try:
        from server.evidence import custody  # lazy: pulls in sqlalchemy — facade lacks it
    except Exception:
        return None

    try:
        hashes = client.hashes("latest")
    except SBVError:
        return None
    sbv_file_hash = (hashes or {}).get("file_hash")
    sbv_chain_hash = (hashes or {}).get("chain_hash")
    # Per-record H2s SBV computed over the raw source elements (from the records
    # we just built). These are recorded as-is; H3 is stored from SBV, not
    # re-derived here, so record order does not need to match the chain order.
    sbv_record_hashes = [str(r.attrs.get("content_hash")) for r in records if r.attrs.get("content_hash")]

    source_meta = dict(payload.get("source_meta") or {})
    source_meta.setdefault("source_type", "chat_export")
    source_meta.setdefault("source_platform", "sms-backup-restore")
    source_meta.setdefault("acquisition_source", "sbv")
    return custody.reconcile_sbv_import(
        path,
        source_meta,
        sbv_file_hash=sbv_file_hash,
        sbv_record_hashes=sbv_record_hashes,
        sbv_chain_hash=sbv_chain_hash,
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
    description="SMS Backup & Restore XML via SBV (primary) -> normalized message + call records, with forensic call-block flags + MMS media handling",
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

    # Forensic custody cross-check (opt-in; no-op where custody/DB is unavailable).
    custody_result = _reconcile_custody(path, payload, client, records)

    messages = sum(1 for r in records if r.record_type == RecordType.message)
    calls = sum(1 for r in records if r.record_type == RecordType.call)
    blocked = sum(1 for r in records if r.attrs.get("blocked"))
    extra: dict[str, Any] = {"parser": "sbv"}
    if custody_result is not None:
        extra["custody"] = custody_result
    return records_out(records, messages=messages, calls=calls, blocked_calls=blocked, **extra)
