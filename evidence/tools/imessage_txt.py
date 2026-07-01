"""Atomic tool: ReagentX/imessage-exporter TXT export  ->  NormalizedRecords.

One format, one module, swappable (owner architecture: parsers are separate
atomic units). Handles the plain-text export produced by
`imessage-exporter --format txt` (the only two native formats are txt + html;
there is NO native PDF exporter — see imessage_pdf.py).

The exporter writes one flat text file per conversation. There is no machine
delimiter between messages: a message BLOCK is recognised structurally by its
header — a timestamp line followed by a sender line — exactly as emitted by the
`message.txt` askama template. We reconstruct that grammar here.

Per-message line order (from exporters/txt/templates/message.txt, verified
against the exporter's own unit tests):

    {timestamp}[ (Read by …)]          <- header line 1
    {sender}                           <- header line 2  ("Me" / contact / "Unknown")
    [This message was deleted from the conversation!]
    [{subject}]
    [SharePlay Message / Ended]
    [Started sharing location! / Stopped sharing location!]
    {part bodies …}                    <- text / attachment paths / stickers
    [{expressive}]                     <- e.g. "Sent with Confetti"
    [Tapbacks:                         <- header, then 4-space-indented lines
        {tapback} by {who}]
    [{replies, every line indented 4 spaces}]
    [This message responded to an earlier message.]
    <blank line>

Announcements are a single line: "{timestamp} {who} {action}." (template
announcement.txt) followed by a blank line — i.e. a timestamp with trailing
text on the SAME line, which is how we tell them apart from a message header
(where the timestamp line carries only the timestamp / read-receipt).

Read-receipt, tapbacks, replies, edited history and attachments are all
preserved into `attrs` (forensic ingest contract — never silently dropped).

Provenance: custom parser written to the imessage-exporter TXT template grammar
(extracted-code/imessage-exporter, exporters/txt/templates/*.txt + shared/*.rs).
Part of evidence-spine P1 (forensic message parsers); capability parse.imessage.
The HTML sibling is imessage_html.py; the PDF sibling (imessage_pdf.py) extracts
text then re-uses this module's `parse_txt_text`.
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
REPLY_INDENT = "    "  # exporter REPLY_INDENT (exporters/txt/mod.rs)

# Timestamp grammar emitted by shared/time.rs -> util::dates::format:
#   "%b %d, %Y  %l:%M:%S %p"  with a DOUBLE space before the time.
# e.g. "May 17, 2022  5:29:42 PM".  `%l` is a space-padded 12-hour clock, so a
# single-digit hour renders as " 5"; we tolerate one-or-more spaces / a leading
# space defensively.
_TS_CORE = r"[A-Z][a-z]{2} \d{1,2}, \d{4}\s+\d{1,2}:\d{2}:\d{2}\s?[AP]M"
_TS_RE = re.compile(rf"^(?P<ts>{_TS_CORE})\b")

# A read receipt is appended to the header timestamp line, separated by a space:
#   "May 17, 2022  5:29:42 PM (Read by you after 1 hour, 49 seconds)"
_HEADER_TS_RE = re.compile(
    rf"^(?P<ts>{_TS_CORE})"
    r"(?:\s+\((?P<receipt>Read by (?P<reader>.+?) after (?P<after>.+?))\))?\s*$"
)

# Announcement line: a timestamp with trailing actor+action text on the SAME line.
_ANNOUNCEMENT_RE = re.compile(rf"^(?P<ts>{_TS_CORE})\s+(?P<rest>\S.*)$")

# strptime format for the exporter's timestamp. %I is zero-padded 12h, which
# also parses the space-padded value once we collapse internal whitespace.
_TS_STRPTIME = "%b %d, %Y %I:%M:%S %p"

# Sticker/file lines and other markers we recognise inside a message body.
_DELETED = "This message was deleted from the conversation!"
_REPLY_CONTEXT = "This message responded to an earlier message."
_SHAREPLAY = ("SharePlay Message", "Ended")
_SHARED_LOCATION = ("Started sharing location!", "Stopped sharing location!")
_TAPBACKS_HEADER = "Tapbacks:"
_ATTACHMENT_MISSING = ("Attachment missing!", "Attachment does not exist!")
_TRANSCRIPTION_PREFIX = "Transcription: "
# Tapback / sticker line shapes (tapback.txt): "<X> by <who>", "<X> from <who>",
# "Sticker from <who> not found!".
_TAPBACK_BY_RE = re.compile(r"^(?P<kind>.+?) by (?P<who>.+)$")
_TAPBACK_FROM_RE = re.compile(r"^(?P<kind>.+?) from (?P<who>.+)$")
# Edit-history subsequent rows (edited.txt): "Edited {diff} later: {text}".
_EDITED_LATER_RE = re.compile(r"^Edited .+? later: ")
# Attachment path heuristics: an exported attachment renders as a bare path line.
_PATH_RE = re.compile(r"(^[~/]|^[A-Za-z]:[\\/]|/Attachments/|/Library/|\.\w{1,5}$)")


def _parse_ts(raw: str) -> datetime | None:
    """Parse an exporter timestamp string to an aware UTC datetime.

    The export is already timezone-corrected to local time by the exporter; we
    have no offset to recover, so we record the wall-clock instant as UTC (the
    normalize layer requires tz-aware). Downstream the literal string is also
    retained in attrs['raw_timestamp'] for forensic fidelity.
    """
    if not raw:
        return None
    collapsed = re.sub(r"\s+", " ", raw.strip())
    try:
        return datetime.strptime(collapsed, _TS_STRPTIME).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_indented(line: str) -> bool:
    return line.startswith(REPLY_INDENT)


def _looks_like_path(line: str) -> bool:
    return bool(_PATH_RE.search(line.strip()))


class _Block:
    """Accumulates the raw lines of one top-level message block."""

    __slots__ = ("header_line", "receipt", "reader", "after", "sender", "body")

    def __init__(self) -> None:
        self.header_line = ""
        self.receipt: str | None = None
        self.reader: str | None = None
        self.after: str | None = None
        self.sender = ""
        self.body: list[str] = []


def _split_blocks(lines: list[str]) -> tuple[list[dict], list[_Block]]:
    """Walk the flat line list, emitting announcement dicts and message blocks.

    A message block opens on a *bare* timestamp header line (timestamp only,
    optionally + read receipt) whose NEXT non-empty line is the sender. An
    announcement is a timestamp line carrying trailing action text.
    """
    announcements: list[dict] = []
    blocks: list[_Block] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.rstrip("\n")
        if not stripped.strip():
            i += 1
            continue

        header = _HEADER_TS_RE.match(stripped)
        if header:
            # Bare timestamp header -> a message block. The following line is the
            # sender; everything up to the next header/announcement is the body.
            blk = _Block()
            blk.header_line = stripped
            blk.receipt = header.group("receipt")
            blk.reader = header.group("reader")
            blk.after = header.group("after")
            i += 1
            # sender = next non-blank line
            while i < n and not lines[i].strip():
                i += 1
            if i < n:
                blk.sender = lines[i].rstrip("\n").strip()
                i += 1
            # body until the next top-level header/announcement or EOF
            while i < n:
                nxt = lines[i].rstrip("\n")
                if not _is_indented(lines[i]) and (_HEADER_TS_RE.match(nxt) or _ANNOUNCEMENT_RE.match(nxt)):
                    break
                blk.body.append(nxt)
                i += 1
            blocks.append(blk)
            continue

        ann = _ANNOUNCEMENT_RE.match(stripped)
        if ann:
            announcements.append({"ts": ann.group("ts"), "text": ann.group("rest").strip()})
            i += 1
            continue

        # Stray line with no recognisable header (shouldn't happen in a clean
        # export); skip it so a malformed line can't abort the whole parse.
        i += 1
    return announcements, blocks


def _parse_body(body: list[str]) -> dict[str, Any]:
    """Extract structured features from a message block's body lines.

    Returns content text + forensic attrs (tapbacks, replies, edits,
    attachments, stickers, markers). Reply sub-blocks (4-space indented) are
    captured verbatim AND recursively re-parsed so nested message data is kept.
    """
    content_lines: list[str] = []
    attachments: list[str] = []
    tapbacks: list[dict] = []
    reply_lines: list[str] = []
    markers: list[str] = []
    edited_history: list[str] = []
    transcriptions: list[str] = []
    expressive: str | None = None
    is_deleted = False
    is_reply_target = False

    in_tapbacks = False
    idx = 0
    n = len(body)
    while idx < n:
        line = body[idx]
        stripped = line.strip()

        if _is_indented(line):
            # Reply content (recursively rendered, every line indented).
            reply_lines.append(line[len(REPLY_INDENT) :] if line.startswith(REPLY_INDENT) else line)
            idx += 1
            continue

        if not stripped:
            in_tapbacks = False
            idx += 1
            continue

        if stripped == _TAPBACKS_HEADER:
            in_tapbacks = True
            idx += 1
            # tapback lines follow, indented 4 spaces (handled by the indent
            # branch above only if indented; the exporter indents them, but be
            # lenient and also accept un-indented immediate followers).
            while idx < n:
                t = body[idx]
                tstr = t.strip()
                if not tstr:
                    break
                if t.startswith(REPLY_INDENT) or in_tapbacks:
                    tapbacks.append(_parse_tapback(tstr))
                    idx += 1
                    continue
                break
            in_tapbacks = False
            continue

        if stripped == _DELETED:
            is_deleted = True
            markers.append("deleted")
            idx += 1
            continue

        if stripped == _REPLY_CONTEXT:
            is_reply_target = True
            idx += 1
            continue

        if stripped in _SHARED_LOCATION:
            markers.append(stripped)
            content_lines.append(stripped)
            idx += 1
            continue

        if stripped == _SHAREPLAY[0]:
            markers.append("shareplay")
            content_lines.append("SharePlay Message")
            idx += 1
            if idx < n and body[idx].strip() == _SHAREPLAY[1]:
                idx += 1
            continue

        if stripped in _ATTACHMENT_MISSING:
            attachments.append(stripped)
            markers.append("attachment_missing")
            idx += 1
            continue

        if stripped.startswith(_TRANSCRIPTION_PREFIX):
            transcriptions.append(stripped[len(_TRANSCRIPTION_PREFIX) :])
            content_lines.append(stripped)
            idx += 1
            continue

        if stripped.startswith("Sent with "):
            expressive = stripped
            idx += 1
            continue

        if _EDITED_LATER_RE.match(stripped):
            edited_history.append(stripped)
            content_lines.append(stripped)
            idx += 1
            continue

        if _looks_like_path(stripped):
            attachments.append(stripped)
            idx += 1
            continue

        # default: ordinary message text
        content_lines.append(stripped)
        idx += 1

    content = "\n".join(content_lines).strip()
    return {
        "content": content,
        "attachments": attachments,
        "tapbacks": tapbacks,
        "reply_block": "\n".join(reply_lines).strip(),
        "markers": markers,
        "edited_history": edited_history,
        "transcriptions": transcriptions,
        "expressive": expressive,
        "is_deleted": is_deleted,
        "is_reply_target": is_reply_target,
    }


def _parse_tapback(text: str) -> dict[str, str]:
    """Parse one tapback line into {kind, who}. Tolerates the three shapes."""
    if text.startswith("Sticker from ") and text.endswith(" not found!"):
        who = text[len("Sticker from ") : -len(" not found!")]
        return {"kind": "sticker", "who": who, "raw": text}
    m = _TAPBACK_BY_RE.match(text)
    if m:
        return {"kind": m.group("kind").strip(), "who": m.group("who").strip(), "raw": text}
    m = _TAPBACK_FROM_RE.match(text)
    if m:
        return {"kind": m.group("kind").strip(), "who": m.group("who").strip(), "raw": text}
    return {"kind": text, "who": "", "raw": text}


def _sender_role(sender: str) -> str:
    return OWNER if sender == ME else sender


def _direction(sender: str) -> str:
    return "outbound" if sender == ME else "inbound"


def _announcement_record(ann: dict, conv_id: str) -> NormalizedRecord:
    occurred = _parse_ts(ann["ts"])
    text = ann["text"]
    # who = first token(s) up to the verb; keep the whole line as content.
    role = OWNER if text.startswith(("You ", "I ")) else (text.split(" ", 1)[0] or None)
    return NormalizedRecord(
        record_type=RecordType.event,
        source="imessage-txt",
        conversation_id=conv_id,
        role=role,
        participants=[],
        content=text,
        occurred_at=occurred,
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs={
            "platform": "imessage",
            "format": "txt",
            "kind": "announcement",
            "raw_timestamp": ann["ts"],
        },
    )


def parse_txt_text(text: str, conv_id: str = "") -> list[NormalizedRecord]:
    """Parse the full text body of an imessage-exporter TXT file.

    Shared engine: imessage_pdf.py re-uses this after extracting PDF text.
    """
    lines = text.splitlines()
    announcements, blocks = _split_blocks(lines)

    # Discover participants (every distinct non-"Me" sender) for the roster.
    participants: list[str] = [OWNER]
    for blk in blocks:
        s = blk.sender
        if s and s != ME and s not in participants:
            participants.append(s)

    records: list[NormalizedRecord] = []

    for ann in announcements:
        records.append(_announcement_record(ann, conv_id))

    for blk in blocks:
        parsed = _parse_body(blk.body)
        occurred = _parse_ts(_TS_RE.match(blk.header_line).group("ts")) if _TS_RE.match(blk.header_line) else None
        sender = blk.sender or "Unknown"
        is_call = (
            any(m in parsed["content"].lower() for m in ("facetime", "missed call", "outgoing call", "incoming call"))
            and parsed["content"].lower().count("call") > 0
        )
        record_type = RecordType.call if is_call else RecordType.message

        # read-receipt: exporter says "them" when from me, "you"/custom otherwise.
        receipt = None
        if blk.receipt:
            receipt = {
                "reader": (blk.reader or "").strip(),
                "after": (blk.after or "").strip(),
                "raw": blk.receipt,
            }

        content = parsed["content"]
        if not content:
            if parsed["attachments"]:
                content = f"[{len(parsed['attachments'])} attachment(s)]"
            elif parsed["is_deleted"]:
                content = _DELETED
            elif parsed["tapbacks"]:
                content = parsed["tapbacks"][0]["raw"]

        attrs: dict[str, Any] = {
            "platform": "imessage",
            "format": "txt",
            "direction": _direction(sender),
            "raw_timestamp": _TS_RE.match(blk.header_line).group("ts") if _TS_RE.match(blk.header_line) else "",
            "sender_label": sender,
            "attachments": parsed["attachments"],
            "tapbacks": parsed["tapbacks"],
            "edited": bool(parsed["edited_history"]),
            "edited_history": parsed["edited_history"],
            "is_deleted": parsed["is_deleted"],
            "is_reply": parsed["is_reply_target"],
            "markers": parsed["markers"],
        }
        if receipt:
            attrs["read_receipt"] = receipt
        if parsed["expressive"]:
            attrs["expressive"] = parsed["expressive"]
        if parsed["transcriptions"]:
            attrs["transcriptions"] = parsed["transcriptions"]
        if parsed["reply_block"]:
            attrs["reply_thread"] = parsed["reply_block"]

        records.append(
            NormalizedRecord(
                record_type=record_type,
                source="imessage-txt",
                conversation_id=conv_id,
                role=_sender_role(sender),
                participants=participants,
                content=content,
                occurred_at=occurred,
                disclosure_tier=DisclosureTier.contemporaneous,
                attrs=attrs,
            )
        )

    records.sort(key=lambda r: r.occurred_at or datetime.min.replace(tzinfo=timezone.utc))
    return records


def looks_like_imessage_txt(head: str) -> bool:
    """Content sniff: does this text look like an imessage-exporter TXT export?

    Heuristic: at least one bare timestamp header line in the exporter's exact
    format. Cheap and specific — the double-spaced "%b %d, %Y  %l:%M:%S %p"
    shape is distinctive.
    """
    for line in head.splitlines():
        if _HEADER_TS_RE.match(line.rstrip()) or _ANNOUNCEMENT_RE.match(line.rstrip()):
            return True
    return False


@register(
    id="messages.imessage-txt",
    capability="parse.imessage",
    description="ReagentX/imessage-exporter TXT export -> normalized iMessage records (tapbacks, replies, edits, read receipts, attachments preserved)",
    accept=lambda hint, size: hint.lower().endswith(".txt"),
    provenance="custom parser written to imessage-exporter exporters/txt/templates grammar",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    text = path.read_text(encoding="utf-8", errors="replace")
    if not looks_like_imessage_txt(text[:8192]):
        raise ValueError("not an imessage-exporter TXT export (no timestamp header lines found)")

    conv_id = path.stem
    records = parse_txt_text(text, conv_id=conv_id)
    messages = sum(1 for r in records if r.record_type == RecordType.message)
    calls = sum(1 for r in records if r.record_type == RecordType.call)
    events = sum(1 for r in records if r.record_type == RecordType.event)
    return records_out(records, messages=messages, calls=calls, announcements=events)
