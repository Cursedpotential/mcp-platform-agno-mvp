# Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)
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

Body-less records (attachment-only MMS, empty sends) are KEPT and flagged rather
than dropped — see _map_sms. Byline: Claude Code . Opus 5 (1M) . 2026-08-01.

Provenance: Python port of dev-resources/Archives/dial-stack/mcp-servers/
ts-mcp-server/src/tools/SmsXmlParser.ts (+ the call-blocking forensic logic
from dial-stack ConflictAnalysisApp). Part of evidence-spine P1 (forensic
message parsers); capability parse.sms-xml (Workflow A / SBV vertical).
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element

from server.contracts.records import DisclosureTier, NormalizedRecord, RecordType
from server.tools.registry import register
from server.tools._common import parse_timestamp, records_out
from ._source_parties import enrich_message_parties

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


def _has_counterparty(attrib: dict[str, str]) -> bool:
    return bool(
        (attrib.get("address") or attrib.get("number") or attrib.get("from") or "").strip()
        or (attrib.get("contact_name") or "").strip()
    )


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


_NON_ATTACHMENT_CT = ("text/plain", "application/smil")


def _attachment_parts(elem: Element | None) -> list[dict[str, Any]]:
    """Describe the non-text MMS parts WITHOUT retaining their payload.

    The base64 `data` attribute of a photo part is megabytes. It is already resident
    (iterparse built the element), so hashing it is free, but keeping it is not — it
    would be copied into the record, the JSON blob, and the raw row. So each part is
    reduced to identity + provenance: content type, filename, byte length, and a
    digest of the base64 text.

    That digest is what makes an attachment-only message DEDUPABLE. Without it two
    different photos sent in the same second to the same number are indistinguishable.
    """
    if elem is None:
        return []
    out: list[dict[str, Any]] = []
    for part in elem.iter("part"):
        ct = (part.attrib.get("ct") or "").lower()
        if not ct or ct in _NON_ATTACHMENT_CT:
            continue
        data = part.attrib.get("data") or ""
        out.append(
            {
                "ct": ct,
                "name": part.attrib.get("cl") or part.attrib.get("name") or "",
                "b64_len": len(data),
                # Digest of the BASE64 TEXT, deliberately not the decoded bytes:
                # an INTRA-EXPORT dedup key only. Not a durable attachment
                # identity — the same bytes wrapped differently (76-col MIME vs
                # unwrapped) hash differently, and we have NOT verified that
                # SMS Backup & Restore emits canonical b64 across versions.
                # Decode-then-hash when a cross-export identity is needed
                # (2026-08-02 hashing audit, finding 3).
                "b64_sha256": hashlib.sha256(data.encode("utf-8")).hexdigest() if data else None,
            }
        )
    return out


def _map_sms(
    attrib: dict[str, str],
    body: str,
    elem: Element | None = None,
    channel: str = "sms",
) -> NormalizedRecord | None:
    text = (body or attrib.get("body") or attrib.get("text") or "").strip()
    attachments: list[dict[str, Any]] = []
    if not text or text == "null":
        # An MMS with no text body is still evidence — a photo, video, or voice note
        # sent with no caption. Returning None here silently DISCARDED 516 of 7,815
        # MMS in a real 636 MiB export (proven 2026-08-01 against the export's own
        # declared count). Keep the record with empty content; the attachment parts
        # carry its identity. Only a genuinely empty element is still dropped.
        #
        # A message with no body AND no attachment is still an EVENT: it has a
        # timestamp, a counterparty, and a direction. One such record exists in the
        # 636 MiB export (a sent MMS whose only text part is a newline). Keep it and
        # mark it empty rather than deciding, in a parser, that it did not happen.
        # Only a record with no timestamp and no counterparty is truly unusable.
        attachments = _attachment_parts(elem)
        if not (attrib.get("date") or attrib.get("timestamp")) and not _has_counterparty(attrib):
            return None
        text = ""
    raw_type = attrib.get("type") or "0"
    direction = _SMS_TYPE.get(raw_type, "unknown")
    other = _counterparty(attrib)
    # 2 sent / 4 outbox / 5 failed / 6 queued are all owner-authored
    # (was "2" only; fixed 2026-08-02 for parity with messaging_csv + sbv_sms).
    role = OWNER if raw_type in ("2", "4", "5", "6") else other
    attrs: dict[str, Any] = {
        "channel": channel,
        "direction": direction,
        "raw_type": raw_type,
        "address": attrib.get("address") or attrib.get("number") or "",
        "contact_name": attrib.get("contact_name") or "",
    }
    if not text:
        attrs["body_present"] = False
        if attachments:
            attrs["attachments"] = attachments
            attrs["attachment_count"] = len(attachments)
        else:
            attrs["empty_body"] = True
    return NormalizedRecord(
        record_type=RecordType.message,
        source="sms-xml",
        conversation_id=other,
        role=role,
        participants=[OWNER, other],
        content=text,
        occurred_at=_epoch_ms_to_dt(attrib.get("date") or attrib.get("timestamp")),
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs=attrs,
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
        return _map_sms(attrib, _mms_text(elem) if elem is not None else "", elem, "mms")
    return _map_sms(attrib, "")


_TAGS = ("sms", "mms", "call")


def _sanitize_xml(raw: str) -> str:
    import re

    raw = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", raw)  # stray control chars
    # escape bare ampersands that aren't already a valid entity
    return re.sub(r"&(?!#\d+;|#x[0-9A-Fa-f]+;|[A-Za-z][A-Za-z0-9._-]*;)", "&amp;", raw)


def iter_records(
    path: Path,
    on_reject: Callable[[str, int, dict[str, str]], None] | None = None,
) -> Iterator[NormalizedRecord]:
    """Stream records one at a time — never materialises the whole export.

    `_collect` below parses incrementally but accumulates every record into a list,
    so a real "SMS Backup & Restore" dump (these run 0.6-1.3 GB) still peaks at the
    full corpus in RAM. That is fine for the registry contract, which hands back a
    list, but unusable for bulk ingest.

    This yields instead, so a caller can batch straight into the raw layer with flat
    memory. Same mapping logic as `_collect` — only the accumulation differs.

    NOTE: the malformed-XML fallback is deliberately NOT mirrored here. That path
    calls `path.read_text()` on the whole file, which is exactly what streaming
    exists to avoid. On a ParseError this raises so the caller can decide, rather
    than silently ballooning to multi-GB.

    `on_reject(tag, index, attrib)` is called for every element the mapper refuses.
    A dropped record is an ABSENCE and cannot be recovered by querying afterwards —
    the caller only gets one chance to write it down. Defaulting this to None keeps
    the old signature working, but any ingest that stores evidence should pass it
    (see evidence.raw_rejected, migration 0012).
    """
    index = 0
    for _event, elem in ET.iterparse(str(path), events=("end",)):
        tag = elem.tag.lower()
        if tag in _TAGS:
            attrib = dict(elem.attrib)
            rec = _map(tag, attrib, elem)
            if rec is not None:
                yield rec
            elif on_reject is not None:
                # never hand back the base64 payload
                on_reject(tag, index, {k: v for k, v in attrib.items() if k != "data"})
            index += 1
        if tag in _TAGS or tag in ("smses", "calls"):
            elem.clear()


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
    records = enrich_message_parties(records, payload)
    return records_out(records, messages=messages, calls=calls, blocked_calls=blocked)
