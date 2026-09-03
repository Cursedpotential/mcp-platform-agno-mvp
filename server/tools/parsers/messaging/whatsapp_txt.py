"""Atomic tool: WhatsApp exported `_chat.txt` -> NormalizedRecords.

One format, one module, swappable. Part of the messaging evidence lane.

WHY THIS EXISTS: r2:casebible-sorted + casebible-raw hold 6 `.txt` and 7 `.zip`
WhatsApp exports with no parser for the native `_chat.txt` shape (inventory
2026-09-03). `messaging_csv.py` labels a `whatsapp-csv` variant, but that only
handles a CSV someone already converted.

THE LINE FORMAT

    [12/03/2024, 14:07:33] Katrina: that never happened
    12/03/2024, 14:07 - Katrina: that never happened     (unbracketed variant)

THE LOCALE TRAP — the reason this parser refuses instead of guessing

WhatsApp formats the date using the EXPORTING DEVICE'S LOCALE at export time.
`03/09/2026` is 9 March on a European device and 3 September on a US one. There
is no marker in the file saying which. Silently picking one corrupts an evidence
timeline in a way nobody would notice, and a wrong date on a message is exactly
the kind of error that destroys credibility on cross-examination.

So this parser:
  1. accepts an explicit `day_first` in the payload when the operator knows the
     source device's locale (declared perspective, the D-135 tier-3 case);
  2. otherwise INFERS it from the file — any day > 12 anywhere in the export
     settles the order unambiguously;
  3. and if the whole file is ambiguous (every date component <= 12) it RAISES
     rather than assuming. An ambiguous export is an operator question, not a
     coin flip.

Ambiguity that WAS resolved by inference is reported in stats
(`day_first_basis`), so the basis for every date in the record set is legible
later rather than hidden in a default.

OTHER SHAPES THAT SILENTLY LOSE DATA IF IGNORED

  - CONTINUATION LINES: a multi-line message puts its later lines on their own
    lines with no timestamp header. They belong to the preceding message and are
    appended to it; treating them as junk truncates messages mid-sentence.
  - SENDER NAMES CONTAINING A COLON break a naive split(':') — the sender is
    taken as the shortest prefix up to the FIRST colon that follows the
    timestamp, and the remainder is the body regardless of further colons.
  - SYSTEM EVENTS have no sender at all: "Missed voice call",
    "Messages and calls are end-to-end encrypted", group membership changes.
    A missed call is evidence of a CONTACT ATTEMPT, not noise, so these are kept
    as records with role "system" rather than discarded (D-136: extract
    everything).
  - `<Media omitted>` marks a message whose attachment is not in the export. The
    message still proves contact and is retained, flagged so nobody later reads
    the absent media as an absent message.

The verbatim source timestamp text is preserved in `attrs.source_timestamp_raw`
because engine/fidelity seals the source's own string, never our rendering.

Byline: Claude Code · Opus 5 · 2026-09-03.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.contracts.records import DisclosureTier, NormalizedRecord, RecordType
from server.tools._common import records_out
from server.tools.registry import register

from ._source_parties import enrich_message_parties

# Bracketed (iOS-style) and dash (Android-style) line openers. Both carry
# d/m/y or m/d/y plus a time, optionally with seconds and an AM/PM marker.
_LINE_PATTERNS = (
    re.compile(
        r"^\[(?P<a>\d{1,2})[/.-](?P<b>\d{1,2})[/.-](?P<y>\d{2,4}),\s+"
        r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap]\.?[Mm]\.?)?)\]\s*(?P<rest>.*)$"
    ),
    re.compile(
        r"^(?P<a>\d{1,2})[/.-](?P<b>\d{1,2})[/.-](?P<y>\d{2,4}),\s+"
        r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap]\.?[Mm]\.?)?)\s+-\s*(?P<rest>.*)$"
    ),
)

# Narrow no-break space and LTR marks litter iOS exports.
_INVISIBLES = dict.fromkeys(map(ord, "‎‏‪‬ ⁩⁦"), None)

_MEDIA_OMITTED = "<media omitted>"


def _clean(line: str) -> str:
    return line.translate(_INVISIBLES).rstrip("\n\r")


def _match_opener(line: str) -> re.Match[str] | None:
    for pattern in _LINE_PATTERNS:
        found = pattern.match(line)
        if found:
            return found
    return None


def _resolve_day_first(openers: list[re.Match[str]], declared: bool | None) -> tuple[bool, str]:
    """(day_first, basis). Raises when the file cannot settle it and none was declared."""
    if declared is not None:
        return declared, "declared by operator"
    for found in openers:
        first, second = int(found.group("a")), int(found.group("b"))
        if first > 12:
            return True, "inferred: a first component > 12 appears in the export"
        if second > 12:
            return False, "inferred: a second component > 12 appears in the export"
    raise ValueError(
        "WhatsApp export date order is ambiguous: every date component is <= 12, so "
        "dd/mm and mm/dd cannot be distinguished from the file. Supply day_first "
        "(true for dd/mm, false for mm/dd) from the exporting device's locale. "
        "Refusing to guess, because a wrong date silently corrupts the timeline."
    )


def _parse_when(found: re.Match[str], day_first: bool) -> tuple[datetime | None, str]:
    a, b = int(found.group("a")), int(found.group("b"))
    day, month = (a, b) if day_first else (b, a)
    year = int(found.group("y"))
    if year < 100:
        year += 2000
    raw_time = found.group("time").strip()
    verbatim = f"{found.group('a')}/{found.group('b')}/{found.group('y')}, {raw_time}"

    normalized = raw_time.upper().replace(".", "").replace(" ", "")
    for fmt in ("%I:%M:%S%p", "%I:%M%p", "%H:%M:%S", "%H:%M"):
        try:
            clock = datetime.strptime(normalized, fmt)
        except ValueError:
            continue
        try:
            # Naive local wall-clock as the device wrote it; UTC is asserted for
            # storage only. The verbatim string above is what gets sealed.
            return (
                datetime(year, month, day, clock.hour, clock.minute, clock.second, tzinfo=timezone.utc),
                verbatim,
            )
        except ValueError:
            return None, verbatim
    return None, verbatim


def _split_sender(rest: str) -> tuple[str, str]:
    """(sender, body). '' sender means a system event.

    Splits on the FIRST colon so a sender name containing further colons cannot
    swallow the body, and so a system line (no colon) is recognized as such.
    """
    head, sep, tail = rest.partition(":")
    if not sep or "\n" in head:
        return "", rest.strip()
    sender = head.strip()
    # A very long "sender" is really a colon-bearing system line, not a name.
    if not sender or len(sender) > 80:
        return "", rest.strip()
    return sender, tail.strip()


def _make_record(sender: str, body: str, when: datetime | None, verbatim: str, conv_id: str) -> NormalizedRecord:
    is_system = sender == ""
    media_omitted = _MEDIA_OMITTED in body.lower()
    content = body
    if not content:
        content = "[empty message]"
    return NormalizedRecord(
        record_type=RecordType.message,
        source="whatsapp-txt",
        conversation_id=conv_id,
        role="system" if is_system else sender,
        participants=[] if is_system else [sender],
        content=content,
        occurred_at=when,
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs={
            "platform": "whatsapp",
            "handle": sender,
            "is_system_event": is_system,
            "media_omitted": media_omitted,
            # Verbatim source timestamp for engine/fidelity — never a rendering.
            "source_timestamp_raw": verbatim,
        },
    )


@register(
    id="messages.whatsapp-txt",
    capability="parse.whatsapp",
    description=(
        "WhatsApp exported _chat.txt -> normalized messages. Resolves the locale-dependent "
        "date order by declaration or inference and REFUSES when ambiguous; keeps multi-line "
        "continuations, colon-bearing sender names, system events (missed calls) and "
        "media-omitted markers."
    ),
    accept=lambda hint, size: hint.lower().endswith(".txt"),
    provenance="custom WhatsApp _chat.txt parser (locale-safe date resolution)",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    if path.is_dir():
        files = sorted(path.glob("*chat*.txt")) or sorted(path.glob("*.txt"))
    else:
        files = [path]
    if not files:
        raise ValueError(f"no chat .txt under {path}")

    declared = payload.get("day_first")
    if declared is not None and not isinstance(declared, bool):
        raise ValueError("day_first must be a boolean when supplied (true = dd/mm, false = mm/dd)")

    records: list[NormalizedRecord] = []
    basis = ""
    continuations = 0
    for f in files:
        lines = [_clean(line) for line in f.read_text(encoding="utf-8", errors="replace").splitlines()]
        openers = [m for m in (_match_opener(line) for line in lines) if m is not None]
        if not openers:
            raise ValueError(f"{f.name}: no WhatsApp message lines found (not a _chat.txt export)")

        day_first, basis = _resolve_day_first(openers, declared)
        conv_id = f.stem

        pending: tuple[str, list[str], datetime | None, str] | None = None
        for line in lines:
            found = _match_opener(line)
            if found is None:
                if pending is not None and line.strip():
                    # Continuation of a multi-line message.
                    pending[1].append(line)
                    continuations += 1
                continue
            if pending is not None:
                sender, parts, when, verbatim = pending
                records.append(_make_record(sender, "\n".join(parts).strip(), when, verbatim, conv_id))
            when, verbatim = _parse_when(found, day_first)
            sender, body = _split_sender(found.group("rest"))
            pending = (sender, [body], when, verbatim)
        if pending is not None:
            sender, parts, when, verbatim = pending
            records.append(_make_record(sender, "\n".join(parts).strip(), when, verbatim, conv_id))

    records.sort(key=lambda r: r.occurred_at or datetime.min.replace(tzinfo=timezone.utc))
    system_events = sum(1 for r in records if r.attrs.get("is_system_event"))
    media_omitted = sum(1 for r in records if r.attrs.get("media_omitted"))
    undated = sum(1 for r in records if r.occurred_at is None)
    records = enrich_message_parties(records, payload)
    return records_out(
        records,
        files=len(files),
        day_first_basis=basis,
        continuation_lines=continuations,
        system_events=system_events,
        media_omitted=media_omitted,
        undated=undated,
    )
