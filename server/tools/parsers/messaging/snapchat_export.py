"""Atomic tool: Snapchat "My Data" chat_history.json -> NormalizedRecords.

One format, one module, swappable. Part of the messaging evidence lane.

WHY THIS EXISTS: r2:casebible-sorted + casebible-raw hold 948 Snapchat `.html`
and 187 `.json` native export files with no parser of any kind (inventory
2026-09-03). This covers the JSON side.

TWO EXPORT GENERATIONS, BOTH HANDLED
Snapchat's export shape changed and both forms are in the corpus:

  A. conversation-keyed (newer chat_history.json)
     {"username": [ {"From":..,"Media Type":"TEXT","Created(microseconds)":..,
                     "IsSender":true,"Text":".."}, ... ], ...}

  B. history-type-keyed (older / snap_history.json style)
     {"Received Snap History": [ {"From":..,"Media Type":"IMAGE",
                                  "Created":"2018-08-09 14:40:38 UTC"} ],
      "Sent Snap History":     [ {"To":..,  ...} ]}

Field names verified against working open-source parsers rather than guessed
(raleighlittles/Snapchat-Chats-And-Location-Analyzer, verdie-g/snap-data-analyzer).
An unrecognized shape RAISES so the mesh falls back — it never returns an empty
record set, because a silent zero looks identical to "this conversation was
empty" and that is how 516 attachment-only MMS records were once lost.

TIMESTAMPS: `Created` is `"%Y-%m-%d %H:%M:%S %Z"`, which `datetime.fromisoformat`
cannot parse (the trailing " UTC"), so the shared `parse_timestamp` helper is not
sufficient here. `Created(microseconds)` is epoch microseconds. The VERBATIM
source string is preserved in `attrs.source_timestamp_raw` because the fidelity
digest (engine/fidelity) seals the source's own timestamp text, never our
rendering of it.

DIRECTION: `IsSender` is authoritative in form A. In form B direction comes from
which history array the message sat in (Received vs Sent). Direction is sealed
into the fidelity digest, so it is recorded explicitly and left "unknown" rather
than guessed when neither signal is present — a guessed direction sealed into a
digest is a fabricated fact wearing a certificate.

NON-TEXT SNAPS ARE RETAINED. A snap with no text is still evidence that contact
occurred at that moment (D-136: extract everything). Media Type is preserved and
searchable content is synthesized, mirroring how the Facebook parser handles
attachment-only messages.

STANDING LIMITATION, recorded in attrs on every record: Snapchat exports ONLY
messages a participant explicitly SAVED, and never exports sent images/video/
voice. Absence from a Snapchat export therefore proves nothing, and that caveat
must travel with the data rather than living in a doc nobody reads at exhibit
time.

Byline: Claude Code · Opus 5 · 2026-09-03.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.contracts.records import DisclosureTier, NormalizedRecord, RecordType
from server.tools.registry import register
from server.tools._common import records_out
from ._source_parties import enrich_message_parties

# Form B top-level keys, mapped to the direction they imply.
_HISTORY_KEYS = {
    "received snap history": "inbound",
    "sent snap history": "outbound",
    "received chat history": "inbound",
    "sent chat history": "outbound",
}

# The export's own caveat, attached to every record it produces.
_SAVED_ONLY_CAVEAT = (
    "Snapchat exports only messages a participant explicitly saved; sent images, "
    "video and voice are never exported. Absence from this export does not imply "
    "the message did not exist."
)


def _parse_created(raw: Any) -> tuple[datetime | None, str]:
    """(parsed, verbatim). Handles Snapchat's two timestamp encodings.

    Returns the verbatim source text alongside the parsed value because the
    fidelity digest seals the source's own string, not our rendering.
    """
    if raw is None:
        return None, ""
    if isinstance(raw, (int, float)):
        # `Created(microseconds)` — epoch microseconds.
        try:
            return datetime.fromtimestamp(float(raw) / 1_000_000.0, tz=timezone.utc), str(raw)
        except (ValueError, OSError, OverflowError):
            return None, str(raw)
    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                return parsed.replace(tzinfo=timezone.utc), text
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")), text
        except ValueError:
            return None, text
    return None, ""


def _direction(msg: dict, fallback: str) -> str:
    """outbound | inbound | unknown. Never guessed."""
    flag = msg.get("IsSender")
    if isinstance(flag, bool):
        return "outbound" if flag else "inbound"
    if fallback in ("inbound", "outbound"):
        return fallback
    if msg.get("To") and not msg.get("From"):
        return "outbound"
    if msg.get("From") and not msg.get("To"):
        return "inbound"
    return "unknown"


def _handle(msg: dict, conversation: str, direction: str) -> str:
    """The other party's identifier as the source recorded it.

    Never a display label we invented: the fidelity digest seals this value, so
    it must be the source's own username string.
    """
    if direction == "outbound":
        return str(msg.get("To") or conversation or "")
    return str(msg.get("From") or conversation or "")


def _map_message(msg: dict, conversation: str, fallback_direction: str) -> NormalizedRecord | None:
    media_type = str(msg.get("Media Type") or "").strip() or "UNKNOWN"
    direction = _direction(msg, fallback_direction)
    handle = _handle(msg, conversation, direction)
    occurred, verbatim = _parse_created(
        msg.get("Created") if msg.get("Created") is not None else msg.get("Created(microseconds)")
    )
    content = str(msg.get("Text") or "")

    if not content:
        # A snap with no text still proves contact at that moment.
        content = f"[{media_type.lower()} snap]" if media_type != "UNKNOWN" else "[snap]"

    return NormalizedRecord(
        record_type=RecordType.message,
        source="snapchat-json",
        conversation_id=conversation,
        role=handle if direction == "inbound" else "self",
        participants=[p for p in {handle} if p],
        content=content,
        occurred_at=occurred,
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs={
            "platform": "snapchat",
            "media_type": media_type,
            "direction": direction,
            "handle": handle,
            # Verbatim source timestamp for engine/fidelity — never a rendering.
            "source_timestamp_raw": verbatim,
            "is_text": media_type.upper() == "TEXT",
            "export_limitation": _SAVED_ONLY_CAVEAT,
        },
    )


def _iter_conversations(data: dict) -> tuple[list[tuple[str, list, str]], str]:
    """Detect the export generation and yield (conversation, messages, direction).

    Returns ([], "") when the shape is not a Snapchat export so the caller can
    raise rather than silently produce nothing.
    """
    history_hits = [k for k in data if str(k).strip().lower() in _HISTORY_KEYS]
    if history_hits:
        out = [
            (str(k), data[k], _HISTORY_KEYS[str(k).strip().lower()]) for k in history_hits if isinstance(data[k], list)
        ]
        return out, "history-keyed"

    # Conversation-keyed: every value is a list of dicts carrying Snapchat keys.
    conversational: list[tuple[str, list, str]] = []
    for key, value in data.items():
        if not isinstance(value, list):
            continue
        sample = next((item for item in value if isinstance(item, dict)), None)
        if sample is None:
            # An empty conversation is legitimate; keep it, contribute nothing.
            conversational.append((str(key), [], ""))
            continue
        if not ({"Media Type", "Created", "Created(microseconds)", "IsSender", "From", "To"} & set(sample)):
            return [], ""
        conversational.append((str(key), value, ""))
    return conversational, "conversation-keyed" if conversational else ""


@register(
    id="messages.snapchat-json",
    capability="parse.snapchat",
    description=(
        "Snapchat 'My Data' chat_history.json -> normalized messages. Handles both the "
        "conversation-keyed and history-type-keyed export generations; retains non-text "
        "snaps as proof of contact; carries the saved-only export caveat on every record."
    ),
    accept=lambda hint, size: hint.lower().endswith(".json"),
    provenance=(
        "custom Snapchat 'My Data' JSON parser; field names verified against "
        "raleighlittles/Snapchat-Chats-And-Location-Analyzer and verdie-g/snap-data-analyzer"
    ),
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    files = sorted(path.glob("chat_history*.json")) if path.is_dir() else [path]
    if not files:
        raise ValueError(f"no chat_history*.json under {path}")

    records: list[NormalizedRecord] = []
    conversations = 0
    generation = ""
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(data, dict):
            raise ValueError(f"{f.name}: Snapchat chat history must be a JSON object")
        groups, detected = _iter_conversations(data)
        if not detected:
            raise ValueError(
                f"{f.name}: not a Snapchat 'My Data' chat export "
                "(no history-type keys and no conversation carrying Snapchat message keys)"
            )
        generation = generation or detected
        for conversation, messages, fallback_direction in groups:
            conversations += 1
            for msg in messages:
                if isinstance(msg, dict):
                    rec = _map_message(msg, conversation, fallback_direction)
                    if rec is not None:
                        records.append(rec)

    records.sort(key=lambda r: r.occurred_at or datetime.min.replace(tzinfo=timezone.utc))
    undated = sum(1 for r in records if r.occurred_at is None)
    text_only = sum(1 for r in records if r.attrs.get("is_text"))
    unknown_direction = sum(1 for r in records if r.attrs.get("direction") == "unknown")
    records = enrich_message_parties(records, payload)
    return records_out(
        records,
        files=len(files),
        conversations=conversations,
        export_generation=generation,
        text_messages=text_only,
        media_snaps=len(records) - text_only,
        undated=undated,
        unknown_direction=unknown_direction,
    )
