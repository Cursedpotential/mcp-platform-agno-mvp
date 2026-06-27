"""Atomic tool: tabular messaging CSV export -> NormalizedRecords.

Covers the CSV message exports that imessage-exporter does NOT produce (it does
txt/html only) but which DO show up in the vault — iMazing / AnyTrans / SMS
Backup CSV / Google Voice / generic spreadsheet dumps. There is no single CSV
schema across those tools, so this parser is COLUMN-FLEXIBLE:

  * a wide set of header ALIASES is mapped onto the normalized fields
    (timestamp / sender / text / direction / service / chat / attachment …);
  * EVERY original column is preserved verbatim in attrs['raw_row'] — forensic
    contract, a field we don't recognise is kept, never silently dropped;
  * platform/source is detected per-row from a service/type column when present
    (iMessage vs SMS), else recorded generically as 'messages-csv'.

stdlib csv only (no pandas) so it stays import-light for the facade/agentos
startup. Delimiter + dialect are sniffed; BOM tolerated. Capability
parse.messages-csv; siblings imessage_txt/html/pdf.py and sms_xml.py.

Provenance: custom column-flexible CSV parser (no upstream app emits a canonical
messaging CSV). Part of evidence-spine P1 (forensic message parsers).
"""

from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evidence.normalize import DisclosureTier, NormalizedRecord, RecordType
from evidence.registry import register
from evidence.tools._common import parse_timestamp, records_out

OWNER = "owner"

# Header aliases (normalized: lowercased, whitespace-collapsed). First match wins.
_TS_KEYS = (
    "message date",
    "date",
    "timestamp",
    "time",
    "datetime",
    "date sent",
    "sent date",
    "date/time",
    "date time",
    "sent at",
)
_TEXT_KEYS = ("text", "message", "body", "content", "message text", "msg")
_SENDER_KEYS = ("sender name", "sender", "from", "from name", "contact", "sender_name", "name", "author")
_SENDER_ID_KEYS = (
    "sender id",
    "from number",
    "address",
    "phone",
    "phone number",
    "number",
    "sender_id",
    "handle",
    "handle id",
)
_RECIPIENT_KEYS = ("recipient", "to", "to number", "recipient id", "recipients")
_DIR_KEYS = ("is from me", "fromme", "type", "direction", "sent/received", "kind", "message type")
_SERVICE_KEYS = ("service", "platform", "protocol", "account")
_CHAT_KEYS = (
    "chat session",
    "conversation",
    "thread",
    "chat",
    "group",
    "chat name",
    "conversation id",
    "chat id",
    "group name",
)
_READ_KEYS = ("read date", "read", "date read", "read receipt")
_ATTACH_KEYS = ("attachment", "attachments", "attachment path", "file", "media", "attachment id", "attachment name")

# Direction tokens. Whole-value or whitespace-token match (so "from me" works).
_OUTBOUND_TOKENS = {"sent", "outgoing", "outbound", "me", "from me", "true", "yes"}
_INBOUND_TOKENS = {"received", "incoming", "inbound", "false", "no"}
# 'is from me' boolean: 1 => me, 0 => them (only honoured for that column).

_CALL_TOKENS = (
    "missed call",
    "facetime",
    "incoming call",
    "outgoing call",
    "phone call",
    "call ended",
    "cancelled call",
)

# Common textual datetime shapes (parse_timestamp already covers ISO + epoch).
_DT_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y %H:%M",
    "%m/%d/%y %I:%M:%S %p",
    "%m/%d/%y %H:%M",
    "%b %d, %Y %I:%M:%S %p",
    "%b %d, %Y %H:%M:%S",
    "%B %d, %Y %I:%M:%S %p",
    "%d/%m/%Y %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%m/%d/%Y",
    "%Y-%m-%d",
)


def _norm_key(k: str) -> str:
    return re.sub(r"\s+", " ", (k or "").strip().lower())


def _pick(row: dict[str, str], keys: tuple[str, ...]) -> str:
    for k in keys:
        if k in row and str(row[k]).strip():
            return str(row[k]).strip()
    return ""


def _parse_dt(raw: str) -> datetime | None:
    if not raw:
        return None
    dt = parse_timestamp(raw)  # ISO-8601 / epoch seconds
    if dt:
        return dt
    s = re.sub(r"\s+", " ", raw.strip())
    if re.fullmatch(r"\d{13}", s):  # epoch milliseconds
        return parse_timestamp(int(s) / 1000)
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _direction(row: dict[str, str]) -> str | None:
    """outbound / inbound / None from the first present direction-ish column."""
    for k in _DIR_KEYS:
        if k not in row or not str(row[k]).strip():
            continue
        val = str(row[k]).strip().lower()
        if k in ("is from me", "fromme"):  # boolean column
            return "outbound" if val in ("1", "true", "yes") else "inbound"
        if val in _OUTBOUND_TOKENS or any(t in val.split() for t in _OUTBOUND_TOKENS):
            return "outbound"
        if val in _INBOUND_TOKENS or any(t in val.split() for t in _INBOUND_TOKENS):
            return "inbound"
    return None


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read the CSV with a sniffed dialect; return (orig_header, normalized-key rows)."""
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    sample = raw[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(raw.splitlines(), dialect=dialect)
    header: list[str] = list(reader.fieldnames or [])
    rows: list[dict[str, str]] = []
    for r in reader:
        rows.append({_norm_key(k): ("" if v is None else str(v)) for k, v in r.items() if k is not None})
    return header, rows


def looks_like_messages_csv(header: list[str]) -> bool:
    """A messaging table: a timestamp-ish column + a text-ish column + at least
    one of sender / direction / service (so we don't grab arbitrary CSVs)."""
    keys = {_norm_key(h) for h in header}
    has_ts = any(k in keys for k in _TS_KEYS)
    has_text = any(k in keys for k in _TEXT_KEYS)
    has_who = any(k in keys for k in _SENDER_KEYS + _DIR_KEYS + _SERVICE_KEYS + _SENDER_ID_KEYS)
    return has_ts and has_text and has_who


def _detect_source(service: str) -> tuple[str, str]:
    """(source, platform) from a service/protocol value."""
    s = service.lower()
    if "imessage" in s or "apple" in s:
        return "imessage-csv", "imessage"
    if "sms" in s or "mms" in s:
        return "sms-csv", "sms"
    if "whatsapp" in s:
        return "whatsapp-csv", "whatsapp"
    return "messages-csv", "messages"


def parse_csv_rows(rows: list[dict[str, str]], conv_id: str = "") -> list[NormalizedRecord]:
    """Shared engine: map normalized-key rows onto NormalizedRecords."""
    records: list[NormalizedRecord] = []
    senders: list[str] = [OWNER]

    for row in rows:
        text = _pick(row, _TEXT_KEYS)
        sender = _pick(row, _SENDER_KEYS)
        sender_id = _pick(row, _SENDER_ID_KEYS)
        service = _pick(row, _SERVICE_KEYS)
        attachment = _pick(row, _ATTACH_KEYS)
        chat = _pick(row, _CHAT_KEYS)
        read = _pick(row, _READ_KEYS)
        direction = _direction(row)
        occurred = _parse_dt(_pick(row, _TS_KEYS))
        source, platform = _detect_source(service)

        # role: outbound => owner; else the sender label (or its id, or Unknown)
        if direction == "outbound":
            role = OWNER
        elif sender:
            role = OWNER if sender.strip().lower() in ("me", "you") else sender
        else:
            role = sender_id or "Unknown"
        if role not in senders and role != OWNER:
            senders.append(role)

        content = text
        if not content and attachment:
            content = f"[attachment: {attachment}]"

        blob = " ".join((text, _pick(row, _DIR_KEYS))).lower()
        is_call = any(tok in blob for tok in _CALL_TOKENS)

        attrs: dict[str, Any] = {
            "platform": platform,
            "format": "csv",
            "raw_row": row,  # forensic: keep the full original row, nothing dropped
        }
        if direction:
            attrs["direction"] = direction
        if sender:
            attrs["sender_label"] = sender
        if sender_id:
            attrs["sender_id"] = sender_id
        if service:
            attrs["service"] = service
        if attachment:
            attrs["attachments"] = [attachment]
        if read:
            attrs["read_receipt"] = {"raw": read}

        records.append(
            NormalizedRecord(
                record_type=RecordType.call if is_call else RecordType.message,
                source=source,
                conversation_id=chat or conv_id,
                role=role,
                participants=[],  # backfilled below
                content=content,
                occurred_at=occurred,
                disclosure_tier=DisclosureTier.contemporaneous,
                attrs=attrs,
            )
        )

    for r in records:
        r.participants = senders
    records.sort(key=lambda r: r.occurred_at or datetime.min.replace(tzinfo=timezone.utc))
    return records


@register(
    id="messages.messaging-csv",
    capability="parse.messages-csv",
    description="Tabular messaging CSV export (iMazing/AnyTrans/SMS/iMessage CSV) -> normalized records; column-flexible header mapping, every original column kept in attrs.raw_row",
    accept=lambda hint, size: hint.lower().endswith(".csv"),
    provenance="custom column-flexible CSV parser (no upstream app emits a canonical messaging CSV)",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    header, rows = _read_rows(path)
    if not looks_like_messages_csv(header):
        raise ValueError(
            "not a messaging CSV (need a timestamp + text column plus a "
            f"sender/direction/service column; saw headers: {header})"
        )

    records = parse_csv_rows(rows, conv_id=path.stem)
    messages = sum(1 for r in records if r.record_type == RecordType.message)
    calls = sum(1 for r in records if r.record_type == RecordType.call)
    return records_out(records, messages=messages, calls=calls, source="csv", rows=len(rows))
