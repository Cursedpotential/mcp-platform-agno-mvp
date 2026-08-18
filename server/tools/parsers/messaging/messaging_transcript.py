# Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)
"""Atomic tool: transcript-marker messaging export (.txt / .csv) -> NormalizedRecords.

The owner's vault carries a unified TRANSCRIPT grammar shared by SMS `.txt` exports
AND a mislabeled iMessage "CSV" that is actually a transcript (NOT a tabular table):

    [YYYY-MM-DD HH:MM AM/PM] Speaker:
    <message text, possibly spanning following lines/cells>
    [YYYY-MM-DD HH:MM AM/PM] Speaker:
    ...

Each marker line opens a new message; subsequent non-empty lines/cells are its body
until the next marker. ONE record per message, speakers NEVER blended. Grammar +
record counts PROVEN by PROCESS (specs/imessage-derisk-RESULTS.md): SMS .txt =
810 / 7,406 / 11 msgs; the iMessage transcript-CSV = 7,187 msgs.

ROUTE BY CONTENT, NOT EXTENSION: this parser is offered for both .txt and .csv and
sniffs the marker grammar in parse() — it raises (defers to the mesh) when a file is
not transcript-shaped, so a tabular CSV falls through to messaging_csv.py and a stock
imessage-exporter .txt falls through to imessage_txt.py.

PROVENANCE NOTE: the transcript filename can mislabel the conversation (the
"8102689630" CSV is actually the +18103533592 thread), so conversation_id is derived
from the message CONTENT (the non-owner speaker), not the filename.

HARD-FAIL: if a file is detected as transcript-shaped (>=1 marker) but yields 0
records, raise rather than emit empty — no silent-empty evidence.

Provenance: ported from PROCESS's proven stdlib de-risk harness (parse_csv_transcript)
+ the shared SMS/iMessage transcript-marker grammar. Capability parse.messages-transcript;
siblings messaging_csv.py / sms_xml.py / imessage_{txt,html,pdf}.py.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.contracts.records import DisclosureTier, NormalizedRecord, RecordType
from server.tools.registry import register
from server.tools._common import records_out
from ._source_parties import enrich_message_parties

OWNER = "owner"

# Marker line: "[YYYY-MM-DD HH:MM AM/PM] Speaker:"  (line ends at the speaker colon;
# the body is on the following lines/cells). PROVEN grammar (PROCESS de-risk harness).
_MARKER_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}\s*[AP]M)\]\s*(.*?):\s*$")
_TS_FORMATS = ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S")


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    s = re.sub(r"\s+", " ", raw.strip())
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _cells(path: Path) -> list[str]:
    """Yield the transcript as a flat list of 'cells' (first CSV column per row, or
    each .txt line) so the same marker walk serves both formats."""
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    if path.suffix.lower() == ".csv":
        out: list[str] = []
        for row in csv.reader(raw.splitlines()):
            out.append((row[0] if row else "").strip())
        return out
    return [ln.strip() for ln in raw.splitlines()]


def _is_me(speaker: str) -> bool:
    return speaker.strip().lower() in ("me", "you")


def parse_transcript(cells: list[str], fallback_conv: str) -> list[NormalizedRecord]:
    """Walk the cells: each marker opens a message; non-marker non-empty cells append
    to the current body. conversation_id is derived from content (the non-owner speaker)."""
    rows: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for cell in cells:
        m = _MARKER_RE.match(cell)
        if m:
            if cur is not None:
                rows.append(cur)
            speaker = m.group(2).strip()
            cur = {"speaker": speaker, "is_me": _is_me(speaker), "ts_raw": m.group(1).strip(), "text": ""}
        elif cell and cur is not None:
            cur["text"] = (cur["text"] + " " + cell).strip()
    if cur is not None:
        rows.append(cur)

    # Derive conversation_id from content: the single non-owner speaker if there is one.
    others = [s for s, c in Counter(r["speaker"] for r in rows if not r["is_me"]).most_common()]
    conv_id = others[0] if len(others) == 1 else (fallback_conv or (others[0] if others else fallback_conv))

    records: list[NormalizedRecord] = []
    senders: list[str] = [OWNER]
    for seq, r in enumerate(rows):
        role = OWNER if r["is_me"] else r["speaker"]
        if role != OWNER and role not in senders:
            senders.append(role)
        content = r["text"]
        is_call = (
            bool(content)
            and "call" in content.lower()
            and any(k in content.lower() for k in ("missed call", "facetime", "incoming call", "outgoing call"))
        )
        records.append(
            NormalizedRecord(
                record_type=RecordType.call if is_call else RecordType.message,
                source="messages-transcript",
                conversation_id=conv_id,
                role=role,
                participants=[],  # backfilled below
                content=content,
                occurred_at=_parse_ts(r["ts_raw"]),
                disclosure_tier=DisclosureTier.contemporaneous,
                attrs={
                    "platform": "messages",
                    "format": "transcript",
                    "direction": "outbound" if r["is_me"] else "inbound",
                    "speaker_label": r["speaker"],
                    "raw_timestamp": r["ts_raw"],
                    "sequence_number": seq,
                },
            )
        )

    for rec in records:
        rec.participants = senders
    # Minute-precision timestamps: keep document order within the same minute (seq tiebreak).
    records.sort(
        key=lambda rec: (
            rec.occurred_at or datetime.min.replace(tzinfo=timezone.utc),
            rec.attrs.get("sequence_number", 0),
        )
    )
    return records


@register(
    id="messages.transcript-marker",
    capability="parse.messages-transcript",
    description="Transcript-marker messaging export (.txt/.csv) with '[YYYY-MM-DD HH:MM AM/PM] Speaker:' lines -> normalized records; one record per message, speakers never blended, conversation_id derived from content. Sniffs the marker grammar and defers (raises) for tabular/other formats.",
    accept=lambda hint, size: hint.lower().endswith((".txt", ".csv")),
    provenance="ported from PROCESS de-risk harness parse_csv_transcript + shared SMS/iMessage transcript grammar",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    cells = _cells(path)

    # Content sniff: the transcript marker must appear in the first ~40 non-empty cells,
    # else this isn't a transcript file -> defer to the mesh (tabular CSV / stock txt).
    head = [c for c in cells if c][:40]
    marker_present = any(_MARKER_RE.match(c) for c in head)
    if not marker_present:
        raise ValueError(
            "not a transcript-marker export (no '[YYYY-MM-DD HH:MM AM/PM] Speaker:' line in the head) — falling back"
        )

    records = parse_transcript(cells, fallback_conv=path.stem)
    # Hard-fail: markers detected but nothing parsed -> never emit empty evidence.
    if not records:
        raise RuntimeError(
            f"messages-transcript: {path.name} has transcript markers but parsed 0 records "
            "— refusing to emit empty evidence (silent-empty guard)"
        )

    messages = sum(1 for r in records if r.record_type == RecordType.message)
    calls = sum(1 for r in records if r.record_type == RecordType.call)
    conv = records[0].conversation_id if records else path.stem
    records = enrich_message_parties(records, payload)
    return records_out(records, messages=messages, calls=calls, source="transcript", conversation_id=conv)
