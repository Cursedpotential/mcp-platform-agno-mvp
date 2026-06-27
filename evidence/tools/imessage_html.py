"""Atomic tool: ReagentX/imessage-exporter HTML export  ->  NormalizedRecords.

One format, one module, swappable. Handles the HTML produced by
`imessage-exporter --format html` (txt + html are the only native formats).

CONTENT SNIFF: `.html`/`.htm` is also the Facebook-export extension, so the
registry will offer this parser AND facebook_messenger_html.py for the same
file. We sniff the DOM in parse() and raise ValueError when it isn't an
iMessage export, so the mesh falls back to the Facebook parser (and vice
versa). The discriminator is the iMessage DOM shape, which Facebook never uses:
  div.message  >  div.sent|div.received  >  p > span.timestamp + span.sender

DOM grammar (exporters/html/templates/*.html):
  <div class="message">
    <div class="sent {service}"|"received">
      <p><span class="timestamp"><a …>{date}</a> {read_after}</span>
         <span class="sender">{sender}</span></p>
      [<span class="deleted">…</span>]
      [<p>Subject: <span class="subject">…</span></p>]
      [<span class="shareplay">…</span>] [<span class="shared_location">…</span>]
      (per part)  <hr><div class="message_part"> … </div>
                  span.bubble | span."bubble jumbo" (text)
                  div.attachment (img/video/audio/download)
                  div.edited > table (tbody/tfoot rows: td span.timestamp + td text)
                  span.unsent  (retracted)
      [<span class="expressive">…</span>]
      [<div class="tapbacks"><hr><p>Tapbacks:</p><div class="tapback">…</div>…</div>]
      [<div class="replies"><div class="reply" id="…">…</div>…</div>]
      [<span class="reply_context">This message responded to an earlier message.</span>]
  Announcements:  <div class="announcement"><p><span class="timestamp">{ts}</span> {who} {action}</p></div>

"sent" => from me ("Me"); "received" => from the contact. All evidence-bearing
fields (read receipt, tapbacks, replies, edits, attachments) are preserved into
attrs (forensic ingest contract).

Provenance: custom parser written to the imessage-exporter HTML template grammar
(extracted-code/imessage-exporter, exporters/html/templates/*.html). Part of
evidence-spine P1 (forensic message parsers); capability parse.imessage. TXT
sibling = imessage_txt.py.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evidence.normalize import DisclosureTier, NormalizedRecord, RecordType
from evidence.registry import register
from evidence.tools._common import records_out

OWNER = "owner"
ME = "Me"

# Same exporter timestamp grammar as the TXT export (shared/time.rs):
#   "%b %d, %Y  %l:%M:%S %p"  (double space before the time)
_TS_CORE = r"[A-Z][a-z]{2} \d{1,2}, \d{4}\s+\d{1,2}:\d{2}:\d{2}\s?[AP]M"
_TS_STRPTIME = "%b %d, %Y %I:%M:%S %p"
_READ_AFTER_RE = re.compile(r"\(Read by (?P<reader>.+?) after (?P<after>.+?)\)")


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    m = re.search(_TS_CORE, raw)
    if not m:
        return None
    collapsed = re.sub(r"\s+", " ", m.group(0).strip())
    try:
        return datetime.strptime(collapsed, _TS_STRPTIME).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el is not None else ""


def looks_like_imessage_html(soup) -> bool:
    """The iMessage DOM shape Facebook never emits: a div.message containing a
    div.sent/div.received with a span.timestamp + span.sender, OR an
    announcement div.announcement."""
    for msg in soup.select("div.message"):
        if msg.find("div", class_=lambda c: c and ("sent" in c.split() or c == "received" or "received" in c.split())):
            if msg.find("span", class_="timestamp") or msg.find("span", class_="sender"):
                return True
    if soup.find("div", class_="announcement"):
        return True
    return False


def _parse_part(part_div) -> dict[str, Any]:
    """Extract one <div class="message_part"> into text/attachments/edits."""
    out = {"text": "", "attachments": [], "edited": [], "retracted": False}
    texts: list[str] = []

    for bubble in part_div.select("span.bubble"):
        t = _text(bubble)
        if t:
            texts.append(t)
    for inline in part_div.select('span[class*="bubble"]'):
        # catch "bubble jumbo" / "bubble medium" not already captured
        cls = inline.get("class", [])
        if "bubble" in cls and inline.get_text(strip=True) and _text(inline) not in texts:
            texts.append(_text(inline))

    for att in part_div.select("div.attachment"):
        img = att.find("img")
        vid = att.find("video")
        aud = att.find("audio")
        src = None
        kind = "file"
        if img is not None:
            src = img.get("src"); kind = "image"
        elif vid is not None:
            s = vid.find("source")
            src = (s.get("src") if s is not None else None) or vid.get("src"); kind = "video"
        elif aud is not None:
            s = aud.find("source")
            src = (s.get("src") if s is not None else None) or aud.get("src"); kind = "audio"
        else:
            a = att.find("a")
            src = a.get("href") if a is not None else _text(att)
            kind = "download"
        out["attachments"].append({"kind": kind, "uri": src or "", "text": _text(att)})

    for err in part_div.select("span.attachment_error"):
        out["attachments"].append({"kind": "missing", "uri": "", "text": _text(err)})

    for ed in part_div.select("div.edited"):
        for row in ed.select("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                ts = _text(cells[0])
                txt = _text(cells[1])
                out["edited"].append({"timestamp": ts, "text": txt})
                if txt:
                    texts.append(txt)

    for uns in part_div.select("span.unsent"):
        out["retracted"] = True
        texts.append(_text(uns))

    out["text"] = "\n".join(t for t in texts if t).strip()
    return out


def _parse_message(msg_div, conv_id: str) -> NormalizedRecord | None:
    inner = msg_div.find("div", class_=lambda c: c and (
        "sent" in c.split() or "received" in c.split()
    ))
    if inner is None:
        return None
    classes = inner.get("class", [])
    is_from_me = "sent" in classes
    service = next((c for c in classes if c not in ("sent", "received", "digital_touch_bubble")), "")

    ts_span = inner.find("span", class_="timestamp")
    date_str = ""
    read_receipt = None
    if ts_span is not None:
        a = ts_span.find("a")
        date_str = _text(a) if a is not None else _text(ts_span)
        rr = _READ_AFTER_RE.search(_text(ts_span))
        if rr:
            read_receipt = {"reader": rr.group("reader"), "after": rr.group("after"), "raw": rr.group(0)}

    sender_span = inner.find("span", class_="sender")
    sender = _text(sender_span) or (ME if is_from_me else "Unknown")

    subject_span = inner.find("span", class_="subject")
    subject = _text(subject_span) if subject_span is not None else None

    is_deleted = inner.find("span", class_="deleted") is not None
    shareplay = inner.find("span", class_="shareplay")
    shared_location = inner.find("span", class_="shared_location")
    is_reply_target = inner.find("span", class_="reply_context") is not None

    # parts
    texts: list[str] = []
    attachments: list[dict] = []
    edited: list[dict] = []
    retracted = False
    for part in inner.select("div.message_part"):
        p = _parse_part(part)
        if p["text"]:
            texts.append(p["text"])
        attachments.extend(p["attachments"])
        edited.extend(p["edited"])
        retracted = retracted or p["retracted"]

    # tapbacks (div.tapbacks > div.tapback)
    tapbacks: list[dict] = []
    for tb in inner.select("div.tapbacks div.tapback"):
        tapbacks.append({"raw": _text(tb)})

    # replies (div.replies > div.reply) — capture verbatim text for the thread
    reply_threads: list[str] = []
    for rep in inner.select("div.replies div.reply"):
        reply_threads.append(_text(rep))

    expressive_span = inner.find("span", class_="expressive")
    expressive = _text(expressive_span) if expressive_span is not None else None

    content_bits = list(texts)
    if subject:
        content_bits.insert(0, f"Subject: {subject}")
    if shareplay is not None:
        content_bits.append(_text(shareplay))
    if shared_location is not None:
        content_bits.append(_text(shared_location))
    content = "\n".join(b for b in content_bits if b).strip()
    if not content:
        if attachments:
            content = f"[{len(attachments)} attachment(s)]"
        elif is_deleted:
            content = "This message was deleted from the conversation!"
        elif tapbacks:
            content = tapbacks[0]["raw"]

    is_call = bool(content) and "call" in content.lower() and any(
        k in content.lower() for k in ("missed call", "facetime", "incoming call", "outgoing call")
    )

    attrs: dict[str, Any] = {
        "platform": "imessage",
        "format": "html",
        "direction": "outbound" if is_from_me else "inbound",
        "service": service,
        "raw_timestamp": date_str,
        "sender_label": sender,
        "attachments": attachments,
        "tapbacks": tapbacks,
        "edited": bool(edited),
        "edited_history": edited,
        "is_deleted": is_deleted,
        "is_reply": is_reply_target,
        "retracted": retracted,
    }
    if read_receipt:
        attrs["read_receipt"] = read_receipt
    if expressive:
        attrs["expressive"] = expressive
    if reply_threads:
        attrs["reply_thread"] = "\n---\n".join(reply_threads)
    if subject:
        attrs["subject"] = subject

    return NormalizedRecord(
        record_type=RecordType.call if is_call else RecordType.message,
        source="imessage-html",
        conversation_id=conv_id,
        role=OWNER if is_from_me else sender,
        participants=[],  # filled by caller once the roster is known
        content=content,
        occurred_at=_parse_ts(date_str),
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs=attrs,
    )


def _parse_announcement(ann_div, conv_id: str) -> NormalizedRecord:
    p = ann_div.find("p")
    full = _text(p) if p is not None else _text(ann_div)
    ts_span = ann_div.find("span", class_="timestamp")
    ts_raw = _text(ts_span) if ts_span is not None else ""
    # action text = the <p> text minus the timestamp prefix
    action = full[len(ts_raw):].strip() if ts_raw and full.startswith(ts_raw) else full
    role = OWNER if action.startswith(("You ", "I ")) else (action.split(" ", 1)[0] or None)
    return NormalizedRecord(
        record_type=RecordType.event,
        source="imessage-html",
        conversation_id=conv_id,
        role=role,
        participants=[],
        content=action or full,
        occurred_at=_parse_ts(ts_raw),
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs={"platform": "imessage", "format": "html", "kind": "announcement", "raw_timestamp": ts_raw},
    )


# ── Owner-CUSTOM imessage-exporter variant ───────────────────────────────────
# The owner customized their exporter ("iMessage Exporter Fix" chat), so the real
# vault HTML is NOT the stock div.message>div.sent/received shape — it's a flat
# list of bubbles, each followed by a .meta line:
#     <div class="bubble from-me|from-them">TEXT</div>
#     <div class="meta">SENDER - YYYY-MM-DD HH:MM AM/PM</div>
#     [<a class="attachment-link" href="…">]
# from-me => owner; from-them => the other party (phone # in .meta + the folder
# name). Selectors PROVEN by PROCESS on the real 325KB sample (1918 msgs,
# speakers Me=1064/+18108532989=854) — specs/imessage-owner-format-PROVEN-prototype.py.
# Minute-precision timestamps => preserve DOCUMENT order (don't reorder same-minute msgs).
_OWNER_META_RE = re.compile(r"^(?P<sender>.*?)\s*-\s*(?P<ts>\d{4}-\d{2}-\d{2}.*)$")
_OWNER_TS_FORMATS = ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %I:%M:%S %p",
                     "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")


def _parse_owner_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    s = re.sub(r"\s+", " ", raw.strip())
    for fmt in _OWNER_TS_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def looks_like_owner_imessage_html(soup) -> bool:
    """Owner-custom shape: a bubble carrying the from-me/from-them class (which
    neither the stock exporter nor Facebook ever emit)."""
    return soup.select_one("div.bubble.from-me, div.bubble.from-them") is not None


def _parse_owner_format(soup, conv_id: str) -> list[NormalizedRecord]:
    records: list[NormalizedRecord] = []
    senders: list[str] = [OWNER]
    for seq, bubble in enumerate(soup.select("div.bubble")):
        cls = bubble.get("class", [])
        is_me = "from-me" in cls
        text = bubble.get_text(" ", strip=True)
        meta = bubble.find_next_sibling("div", class_="meta")
        m = _OWNER_META_RE.match(_text(meta)) if meta is not None else None
        sender_label = (m.group("sender").strip() if m else "") or ("Me" if is_me else conv_id)
        ts_raw = m.group("ts").strip() if m else ""

        att = bubble.find_next_sibling("a", class_="attachment-link")
        attachments: list[dict] = []
        if att is not None:
            attachments.append({"kind": "link", "uri": att.get("href") or "", "text": _text(att)})

        role = OWNER if is_me else (sender_label if sender_label not in ("", "Me") else conv_id)
        if role != OWNER and role not in senders:
            senders.append(role)

        content = text
        if not content and attachments:
            content = f"[{len(attachments)} attachment(s)]"
        is_call = bool(content) and "call" in content.lower() and any(
            k in content.lower() for k in ("missed call", "facetime", "incoming call", "outgoing call")
        )

        records.append(
            NormalizedRecord(
                record_type=RecordType.call if is_call else RecordType.message,
                source="imessage-html",
                conversation_id=conv_id,
                role=role,
                participants=[],  # backfilled below
                content=content,
                occurred_at=_parse_owner_ts(ts_raw),
                disclosure_tier=DisclosureTier.contemporaneous,
                attrs={
                    "platform": "imessage",
                    "format": "html",
                    "variant": "owner-custom",
                    "direction": "outbound" if is_me else "inbound",
                    "sender_label": sender_label,
                    "raw_timestamp": ts_raw,
                    "sequence_number": seq,
                    "attachments": attachments,
                },
            )
        )

    for r in records:
        r.participants = senders
    # Minute-precision ts: keep document order within the same minute (seq tiebreak).
    records.sort(key=lambda r: (
        r.occurred_at or datetime.min.replace(tzinfo=timezone.utc),
        r.attrs.get("sequence_number", 0),
    ))
    return records


@register(
    id="messages.imessage-html",
    capability="parse.imessage",
    description="ReagentX/imessage-exporter HTML export -> normalized iMessage records (content-sniffs vs Facebook HTML; tapbacks/replies/edits/read receipts/attachments preserved)",
    accept=lambda hint, size: hint.lower().endswith((".html", ".htm")),
    provenance="custom parser written to imessage-exporter exporters/html/templates grammar",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:  # let the mesh surface a clear need
        raise RuntimeError("imessage-html parser requires beautifulsoup4 (bs4)") from exc

    path = Path(payload["path"])
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    conv_id = path.stem

    if not looks_like_imessage_html(soup):
        # Owner-CUSTOM export variant (div.bubble.from-me/them + .meta) — the real
        # vault format. Parsed separately; document order preserved.
        if looks_like_owner_imessage_html(soup):
            records = _parse_owner_format(soup, conv_id)
            messages = sum(1 for r in records if r.record_type == RecordType.message)
            calls = sum(1 for r in records if r.record_type == RecordType.call)
            events = sum(1 for r in records if r.record_type == RecordType.event)
            participants = len({r.role for r in records if r.role})
            return records_out(records, messages=messages, calls=calls, announcements=events,
                               participants=participants, variant="owner-custom")
        raise ValueError(
            "not an imessage-exporter HTML export (neither stock div.message>div.sent/received "
            "nor owner-custom div.bubble.from-me/them) — falling back"
        )

    records: list[NormalizedRecord] = []

    # Messages and announcements in document order.
    for el in soup.select("div.message, div.announcement"):
        cls = el.get("class", [])
        if "announcement" in cls:
            records.append(_parse_announcement(el, conv_id))
        else:
            rec = _parse_message(el, conv_id)
            if rec is not None:
                records.append(rec)

    # Build participant roster, then backfill onto every record.
    participants: list[str] = [OWNER]
    for r in records:
        s = r.attrs.get("sender_label")
        if s and s != ME and s not in participants:
            participants.append(s)
    for r in records:
        r.participants = participants

    records.sort(key=lambda r: r.occurred_at or datetime.min.replace(tzinfo=timezone.utc))
    messages = sum(1 for r in records if r.record_type == RecordType.message)
    calls = sum(1 for r in records if r.record_type == RecordType.call)
    events = sum(1 for r in records if r.record_type == RecordType.event)
    return records_out(records, messages=messages, calls=calls, announcements=events, participants=len(participants))
