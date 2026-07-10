"""Atomic tool: Facebook/Messenger HTML export -> NormalizedRecords.

One format, one module, swappable. The owner has BOTH HTML and JSON Facebook
exports — this handles the HTML "Download Your Information" layout; the JSON
variant is facebook_messenger_json.py (preferred where available — HTML is
lossier: fuzzy string timestamps, scraped DOM, no structured media uris).

Handles both Facebook HTML layouts seen in the wild:
  legacy : <div class="message"><div class="meta">Sender - <ts></div><p>body</p>
  card   : <div class="_a6-g"> _a6-h=sender, _a6-p=body, sibling _a6-o>_a72d=<ts>

Provenance: Python port of dial-stack ts-mcp-server FacebookExportParser.ts
(cheerio -> BeautifulSoup). Part of evidence-spine P1 (forensic message parsers),
capability parse.facebook (same as the JSON tool; the registry picks by extension
and falls back across candidates).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.contracts.records import DisclosureTier, NormalizedRecord, RecordType
from server.tools.registry import register
from server.tools._common import records_out

# strptime patterns covering Facebook's HTML timestamp variants.
_DATE_FORMATS = (
    "%b %d, %Y, %I:%M %p",
    "%B %d, %Y, %I:%M %p",
    "%b %d, %Y at %I:%M %p",
    "%B %d, %Y at %I:%M %p",
    "%b %d, %Y %I:%M %p",
    "%B %d, %Y %I:%M %p",
    "%d %b %Y, %H:%M",
    "%d %B %Y, %H:%M",
    "%d %b %Y %H:%M",
    "%b %d, %Y, %H:%M",
    "%b %d, %Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def _parse_fuzzy_date(ts: str):
    if not ts:
        return None
    s = re.sub(r"(\d)\s*(AM|PM|am|pm)\b", r"\1 \2", ts.strip())
    for cand in (s, s.replace(" at ", ", "), s.replace(",", "")):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(cand.strip(), fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _msg_type(body: str) -> str:
    low = body.lower()
    if any(k in low for k in ("sent a photo", "sent a video", "sent an attachment", "shared a file")):
        return "media"
    if any(k in low for k in ("shared a link", "sent a post", "shared a post")):
        return "share"
    if any(k in low for k in ("created a group", "left the group", "changed the group name")) or low.startswith(
        "added "
    ):
        return "system"
    return "text"


def _structure_legacy(soup) -> list[tuple]:
    rows: list[tuple] = []
    for msg in soup.select("div.message"):
        meta = msg.find("div", class_="meta")
        if not meta:
            continue
        meta_text = meta.get_text(" ", strip=True)
        m = re.match(r"^(.*?)\s*[-–—]\s*(.+)$", meta_text)
        if not m:
            continue
        ts = _parse_fuzzy_date(m.group(2))
        if not ts:
            continue
        body_el = msg.find("p")
        body = body_el.get_text(" ", strip=True) if body_el else ""
        if not body:
            continue
        rows.append((m.group(1).strip(), body, ts, meta_text[:200]))
    return rows


def _structure_card(soup) -> list[tuple]:
    rows: list[tuple] = []
    for card in soup.select("div._a6-g"):
        header = card.find("div", class_="_a6-h")
        sender = header.get_text(" ", strip=True) if header else ""
        if not sender:
            continue
        body_el = card.find("div", class_="_a6-p")
        body = body_el.get_text(" ", strip=True) if body_el else ""
        if not body:
            continue
        ts = None
        sib = card.find_next_sibling("div", class_="_a6-o")
        if sib:
            tstag = sib.find("div", class_="_a72d")
            if tstag:
                ts = _parse_fuzzy_date(tstag.get_text(" ", strip=True))
        if not ts:
            continue
        rows.append((sender, body, ts, "card"))
    return rows


@register(
    id="messages.facebook-html",
    capability="parse.facebook",
    description="Facebook/Messenger HTML export (legacy div.message + card _a6-g layouts) -> normalized messages",
    accept=lambda hint, size: hint.lower().endswith((".html", ".htm")),
    provenance="port of dial-stack ts-mcp-server FacebookExportParser.ts (cheerio->BeautifulSoup)",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:  # let the mesh fall back / surface a clear need
        raise RuntimeError("facebook-html parser requires beautifulsoup4 (bs4)") from exc

    path = Path(payload["path"])
    own = ((payload.get("source_meta") or {}).get("owner_name") or payload.get("owner_name") or "").strip()
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")

    rows = _structure_legacy(soup)
    layout = "legacy"
    if not rows:
        rows = _structure_card(soup)
        layout = "card"
    if not rows:
        raise ValueError("not a Facebook HTML export (neither div.message nor div._a6-g messages found)")

    participants: list[str] = []
    for sender, *_ in rows:
        if sender and sender not in participants:
            participants.append(sender)

    records: list[NormalizedRecord] = []
    for sender, body, ts, raw in rows:
        attrs = {"platform": "facebook", "format": "html", "msg_type": _msg_type(body), "meta": raw}
        if own:
            attrs["direction"] = "outbound" if sender.lower().strip() == own.lower() else "inbound"
        records.append(
            NormalizedRecord(
                record_type=RecordType.message,
                source="facebook-html",
                conversation_id=path.stem,
                role=sender,
                participants=participants,
                content=body,
                occurred_at=ts,
                disclosure_tier=DisclosureTier.contemporaneous,
                attrs=attrs,
            )
        )

    records.sort(key=lambda r: r.occurred_at or datetime.min.replace(tzinfo=timezone.utc))
    return records_out(records, messages=len(records), participants=len(participants), layout=layout)
