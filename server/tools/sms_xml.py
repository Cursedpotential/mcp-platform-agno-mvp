"""Atomic tool: "SMS Backup & Restore" XML  ->  NormalizedRecords.

One format, one module, swappable (owner architecture: parsers are separate
atomic units). Handles the Android "SMS Backup & Restore" schema:
  <smses>  with <sms> and <mms> children
  <calls>  with <call> children
Attributes are epoch-MILLISECOND `date`, `address`/`contact_name`, and a
`type` whose meaning differs for messages vs calls.

Streams with xml.etree.ElementTree.iterparse so multi-GB backups don't blow up
RAM (elements are cleared after mapping). Falls back to a sanitize-whole-file
parse only if the stream hits malformed XML (stray ampersands are common in
these dumps).

Provenance: Python port of dev-resources/Archives/dial-stack/mcp-servers/
ts-mcp-server/src/tools/SmsXmlParser.ts (+ the call-blocking forensic logic
from dial-stack ConflictAnalysisApp). Part of evidence-spine P1 (forensic
message parsers); capability parse.sms-xml (Workflow A / SBV vertical).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element

from server.evidence.normalize import DisclosureTier, NormalizedRecord, RecordType
from .registry import register
from ._common import parse_timestamp, records_out

OWNER = "owner"

# type → label. NOTE: the same integer means different things for sms vs call.
_SMS_TYPE = {"1": "received", "2": "sent", "3": "draft", "4": "outbox", "5": "failed", "6": "queued"}
_CALL_TYPE = {"1": "incoming", "2": "outgoing", "3": "missed", "4": "voicemail", "5": "rejected", "6": "refused_list"}


def _epoch_ms_to_dt(value: str | None):
    """`date`/`timestamp` attrs are epoch milliseconds (strings)."""
    try:
        ms = int(value or "0")
    except (TypeError, ValueError):
        return None
    return parse_timestamp(ms / 1000.0) if ms > 0 else None


def _counterparty(attrib: dict[str, str]) -> str:
    name = (attrib.get("contact_name") or "").strip()
    if name and name.lower() not in ("", "unknown", "(unknown)", "null"):
        return name
    return (attrib.get("address") or attrib.get("number") or attrib.get("from") or "unknown").strip()


def _mms_text(elem: Element) -> str:
    """MMS body lives in nested <parts><part ct="text/plain" text="..."/>."""
    chunks: list[str] = []
    for part in elem.iter("part"):
        ct = (part.attrib.get("ct") or "").lower()
        text = part.attrib.get("text") or ""
        if text and (ct == "text/plain" or not ct):
            chunks.append(text)
    return "\n".join(c for c in chunks if c and c != "null").strip()


def _map_sms(attrib: dict[str, str], body: str) -> NormalizedRecord | None:
    text = (body or attrib.get("body") or attrib.get("text") or "").strip()
    if not text or text == "null":
        return None
    raw_type = attrib.get("type") or "0"
    direction = _SMS_TYPE.get(raw_type, "unknown")
    other = _counterparty(attrib)
    role = OWNER if raw_type == "2" else other
    return NormalizedRecord(
        record_type=RecordType.message,
        source="sms-xml",
        conversation_id=other,
        role=role,
        participants=[OWNER, other],
        content=text,
        occurred_at=_epoch_ms_to_dt(attrib.get("date") or attrib.get("timestamp")),
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs={
            "channel": "sms",
            "direction": direction,
            "raw_type": raw_type,
            "address": attrib.get("address") or attrib.get("number") or "",
            "contact_name": attrib.get("contact_name") or "",
        },
    )


def _map_call(attrib: dict[str, str]) -> NormalizedRecord:
    raw_type = attrib.get("type") or "0"
    label = _CALL_TYPE.get(raw_type, "unknown")
    duration = attrib.get("duration") or "0"
    other = _counterparty(attrib)

    # Forensic call-blocking indicators (ported from ConflictAnalysisApp):
    flags: list[str] = []
    if raw_type == "5":
        flags.append("call actively rejected")
    if raw_type == "6":
        flags.append("number on refuse/block list")
    if raw_type == "2" and duration == "0":
        flags.append("outgoing call with 0 duration - did not connect")
    blocked = bool(flags)

    content = f"{label.capitalize()} call with {other} (duration: {duration}s)"
    if flags:
        content += f" [FORENSIC FLAG: {', '.join(flags)}]"

    role = OWNER if raw_type == "2" else other
    return NormalizedRecord(
        record_type=RecordType.call,
        source="sms-xml",
        conversation_id=other,
        role=role,
        participants=[OWNER, other],
        content=content,
        occurred_at=_epoch_ms_to_dt(attrib.get("date") or attrib.get("timestamp")),
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs={
            "channel": "call",
            "call_type": label,
            "raw_type": raw_type,
            "duration_seconds": int(duration) if duration.isdigit() else 0,
            "address": attrib.get("address") or attrib.get("number") or "",
            "contact_name": attrib.get("contact_name") or "",
            "blocked": blocked,
            "forensic_flags": flags,
        },
    )


def _map(tag: str, attrib: dict[str, str], elem: Element | None) -> NormalizedRecord | None:
    if tag == "call":
        return _map_call(attrib)
    if tag == "mms":
        return _map_sms(attrib, _mms_text(elem) if elem is not None else "")
    return _map_sms(attrib, "")


_TAGS = ("sms", "mms", "call")


def _sanitize_xml(raw: str) -> str:
    import re

    raw = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", raw)  # stray control chars
    # escape bare ampersands that aren't already a valid entity
    return re.sub(r"&(?!#\d+;|#x[0-9A-Fa-f]+;|[A-Za-z][A-Za-z0-9._-]*;)", "&amp;", raw)


def _collect(path: Path) -> list[NormalizedRecord]:
    out: list[NormalizedRecord] = []
    try:
        for _event, elem in ET.iterparse(str(path), events=("end",)):
            tag = elem.tag.lower()
            if tag in _TAGS:
                rec = _map(tag, dict(elem.attrib), elem)
                if rec is not None:
                    out.append(rec)
            if tag in _TAGS or tag in ("smses", "calls"):
                elem.clear()
        return out
    except ET.ParseError:
        # malformed dump — sanitize the whole file and retry (more RAM, last resort)
        out.clear()
        root = ET.fromstring(_sanitize_xml(path.read_text(encoding="utf-8", errors="replace")))
        for elem in root.iter():
            tag = elem.tag.lower()
            if tag in _TAGS:
                rec = _map(tag, dict(elem.attrib), elem)
                if rec is not None:
                    out.append(rec)
        return out


@register(
    id="messages.sms-xml",
    capability="parse.sms-xml",
    description='"SMS Backup & Restore" XML (sms/mms/call) -> normalized message + call records, with forensic call-block flags',
    accept=lambda hint, size: hint.lower().endswith(".xml"),
    provenance="port of dial-stack ts-mcp-server/src/tools/SmsXmlParser.ts + ConflictAnalysisApp call-block logic",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    head = path.read_text(encoding="utf-8", errors="replace")[:4096].lower()
    if "<smses" not in head and "<calls" not in head and "<sms " not in head and "<call " not in head:
        raise ValueError("not an SMS Backup & Restore XML (no <smses>/<calls> root)")

    records = _collect(path)
    messages = sum(1 for r in records if r.record_type == RecordType.message)
    calls = sum(1 for r in records if r.record_type == RecordType.call)
    blocked = sum(1 for r in records if r.attrs.get("blocked"))
    return records_out(records, messages=messages, calls=calls, blocked_calls=blocked)
