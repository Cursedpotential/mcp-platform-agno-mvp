"""Atomic tool: Facebook/Messenger "Download Your Information" JSON -> NormalizedRecords.

One format, one module, swappable. Handles the modern Facebook DYI JSON export:
  messages/inbox/<thread>/message_1.json (message_2.json ... for long threads)
Each file: { participants:[{name}], messages:[{sender_name, timestamp_ms,
content, photos/videos/audio_files/gifs/files/sticker, share, reactions,
type, call_duration}], title, thread_path }.

CRITICAL: Facebook double-encodes UTF-8 as latin-1 (mojibake) in every string
field — emoji/accents arrive as `\\u00f0\\u009f...`. We repair with
`s.encode('latin-1').decode('utf-8')` on every text field, or evidence text is
garbage.

Accepts a single message_N.json OR a thread directory (globs message_*.json and
merges chronologically). Validates it's actually a FB export (else raises so the
mesh falls back to another parser).

Provenance: custom (FB DYI JSON). The donor dial-stack FacebookExportParser.ts
covers only the older HTML export (cheerio); a Python HTML variant can follow as
a sibling tool. Part of evidence-spine P1 (forensic message parsers).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evidence.normalize import DisclosureTier, NormalizedRecord, RecordType
from evidence.registry import register
from evidence.tools._common import parse_timestamp, records_out

_MEDIA_KEYS = [
    ("photos", "photo"),
    ("videos", "video"),
    ("audio_files", "audio"),
    ("gifs", "gif"),
    ("files", "file"),
]


def _fix(s: Any) -> str:
    """Repair Facebook's latin-1-over-UTF-8 mojibake. No-op for clean text."""
    if not isinstance(s, str) or not s:
        return s or ""
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _media(msg: dict) -> list[dict]:
    out: list[dict] = []
    for key, label in _MEDIA_KEYS:
        val = msg.get(key)
        if isinstance(val, list):
            out.extend({"kind": label, "uri": (it or {}).get("uri", "")} for it in val)
    sticker = msg.get("sticker")
    if isinstance(sticker, dict) and sticker.get("uri"):
        out.append({"kind": "sticker", "uri": sticker["uri"]})
    return out


def _map_message(msg: dict, participants: list[str], conv_id: str, title: str) -> NormalizedRecord | None:
    sender = _fix(msg.get("sender_name")) or "unknown"
    ts = msg.get("timestamp_ms")
    occurred = parse_timestamp(ts / 1000.0) if isinstance(ts, (int, float)) and ts else None
    content = _fix(msg.get("content"))
    mtype = msg.get("type") or "Generic"
    media = _media(msg)
    _share = msg.get("share")
    share = _share if isinstance(_share, dict) else {}
    call_duration = msg.get("call_duration")
    is_call = mtype == "Call" or call_duration is not None

    if not content:  # synthesize searchable content for non-text messages
        if is_call:
            content = f"Call ({call_duration}s)" if call_duration is not None else "Call"
        elif media:
            kinds = ", ".join(sorted({m["kind"] for m in media}))
            content = f"[sent {len(media)} attachment(s): {kinds}]"
        elif share.get("link"):
            content = f"[shared] {_fix(share.get('share_text'))} {share.get('link')}".strip()
        elif mtype not in ("Generic",):
            content = f"[{mtype}]"

    if not content and not media and not share:
        return None  # reaction-only / empty system noise — nothing evidence-bearing

    reactions = [
        {"reaction": _fix(r.get("reaction")), "actor": _fix(r.get("actor"))}
        for r in (msg.get("reactions") or [])
        if isinstance(r, dict)
    ]
    return NormalizedRecord(
        record_type=RecordType.call if is_call else RecordType.message,
        source="facebook-json",
        conversation_id=conv_id,
        role=sender,
        participants=participants,
        content=content,
        occurred_at=occurred,
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs={
            "platform": "facebook",
            "msg_type": mtype,
            "thread_title": title,
            "media": media,
            "is_call": is_call,
            "call_duration_seconds": call_duration,
            "reactions": reactions,
            "share": {"link": share.get("link", ""), "text": _fix(share.get("share_text"))} if share else {},
        },
    )


@register(
    id="messages.facebook-json",
    capability="parse.facebook",
    description="Facebook/Messenger 'Download Your Information' JSON (message_N.json) -> normalized messages + calls (mojibake-repaired)",
    accept=lambda hint, size: hint.lower().endswith(".json"),
    provenance="custom FB DYI JSON parser (donor FacebookExportParser.ts handles only the HTML variant)",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    files = sorted(path.glob("message_*.json")) if path.is_dir() else [path]
    if not files:
        raise ValueError(f"no message_*.json under {path}")

    records: list[NormalizedRecord] = []
    participants_all: list[str] = []
    title = ""
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        if not (isinstance(data, dict) and "messages" in data and "participants" in data):
            raise ValueError(f"{f.name}: not a Facebook DYI export (no participants/messages)")
        parts = [_fix((p or {}).get("name")) for p in (data.get("participants") or []) if isinstance(p, dict)]
        for p in parts:
            if p and p not in participants_all:
                participants_all.append(p)
        title = _fix(data.get("title")) or title
        conv_id = _fix(data.get("thread_path")) or _fix(data.get("title")) or ""
        for m in data.get("messages") or []:
            if isinstance(m, dict):
                rec = _map_message(m, parts, conv_id, title)
                if rec is not None:
                    records.append(rec)

    records.sort(key=lambda r: r.occurred_at or datetime.min.replace(tzinfo=timezone.utc))
    messages = sum(1 for r in records if r.record_type == RecordType.message)
    calls = sum(1 for r in records if r.record_type == RecordType.call)
    return records_out(records, messages=messages, calls=calls, files=len(files), participants=len(participants_all))
