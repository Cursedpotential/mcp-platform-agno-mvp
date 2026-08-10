"""RETIRED: server/tools/parsers/messaging/sbv_sms.py::_map_message

Moved here 2026-08-09 (S2 build-and-test-green handoff, task 4c) rather than
deleted, per the workspace never-delete rule (see the workspace root
CLAUDE.md's "Never delete -> _stale/" standing constraint).

WHY THIS IS DEAD: `_map_message` was the per-record mapper for the ORIGINAL
(non-universal) SBV integration. It has ZERO production callers — `grep -rn
"_map_message\\b"` across the repo (2026-08-09) turns up only its own
definition, one comment referencing it, and tests/test_sbv_demotion.py, which
imported and called it directly as its unit-under-test. The live `parse()`
entry point in sbv_sms.py has called `_map_universal_record` (the
import-scoped universal-engine mapper) exclusively since the universal import
engine landed (PR #18, aacf21c "merge(sbv): universal import engine +
governed repair slice"). tests/test_sbv_demotion.py was rewritten in the same
handoff to test `_map_universal_record` instead (and against sms_xml.py's
`_map_sms`/`_map_call`, the fallback parser), per the 2026-08-05 SBV-promotion
ruling (DECISION_LOG D-040, PR #18).

KNOWN BUGS IN THIS RETIRED CODE (do not resurrect without fixing both — they
are exactly what the 2026-08-02 parser-gap review flagged, docs/HANDOFF-
2026-08-02-sbv-chatminer-parser-gap-review.md "2. Primary/fallback record sets
are not equivalent — P0"):

  1. Bodyless-media drop: `text = ...; if not text or text == "null": return
     None` runs BEFORE any attachment is examined, so an attachment-only MMS
     (no caption) is silently dropped — the identical evidence-loss shape as
     the 516-dropped-MMS lesson that sms_xml.py's `_map_sms` was fixed for.

  2. Outbound-role gap: `role = OWNER if raw_type == 2 else other` only
     recognizes type 2 (sent) as owner-authored. Outbox/failed/queued
     (4/5/6) are owner-authored too (sms_xml.py's `_map_sms` and the universal
     path's `_role_for_universal_record` both handle all four); here they
     fall through to `other`, i.e. get misattributed to the counterparty.

Original location: server/tools/parsers/messaging/sbv_sms.py. `_map_message`'s
private helpers (`_counterparty`, `_to_dt`, `_as_int`, `_SMS_TYPE`) are still
used by the LIVE `_map_call` in sbv_sms.py, so they were left in place there
and are only reproduced below (self-contained copy) so this archived module
still runs standalone. NOTE: `sbv_sms._map_call` (distinct from the live
`sms_xml.py::_map_call`) also has zero production callers per the same grep —
it was left in place because moving it was outside this handoff task's scope
(only `_map_message` was named); flagged here for whoever picks that up next.
See sbv_sms.py's module header for the one-line pointer comment back here.
"""

from __future__ import annotations

from typing import Any

from server.contracts.records import DisclosureTier, NormalizedRecord, RecordType
from server.tools._common import parse_timestamp

OWNER = "owner"

_SMS_TYPE = {1: "received", 2: "sent", 3: "draft", 4: "outbox", 5: "failed", 6: "queued"}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_dt(value: Any):
    """SBV returns `date` as epoch milliseconds (number or numeric string) or an
    ISO string. Normalize to a tz-aware datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        ms = _as_int(value)
        return parse_timestamp(ms / 1000.0) if ms > 0 else None
    return parse_timestamp(str(value))


def _counterparty(msg: dict[str, Any]) -> str:
    name = (msg.get("contact_name") or "").strip()
    if name and name.lower() not in ("", "unknown", "(unknown)", "null"):
        return name
    return (msg.get("address") or msg.get("number") or "unknown").strip() or "unknown"


def _map_message(msg: dict[str, Any]) -> NormalizedRecord | None:
    text = (msg.get("body") or msg.get("text") or "").strip()
    if not text or text == "null":
        return None
    raw_type = _as_int(msg.get("type"), 0)
    direction = _SMS_TYPE.get(raw_type, "unknown")
    other = _counterparty(msg)
    role = OWNER if raw_type == 2 else other
    channel = "mms" if (msg.get("media_type") or msg.get("content_type") or msg.get("message_type")) else "sms"
    return NormalizedRecord(
        record_type=RecordType.message,
        source="sms-xml",
        conversation_id=other,
        role=role,
        participants=[OWNER, other],
        content=text,
        occurred_at=_to_dt(msg.get("date")),
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs={
            "channel": channel,
            "direction": direction,
            "raw_type": str(raw_type),
            "address": msg.get("address") or msg.get("number") or "",
            "contact_name": msg.get("contact_name") or "",
            "parser": "sbv",
            "media_type": msg.get("media_type") or "",
            "thread_id": msg.get("thread_id"),
            # H2 per-record custody hash (sha256 of the RAW source XML element,
            # h2-rawelement-v1) as computed by SBV BEFORE normalization. This is
            # the evidence hash — NOT a hash of this NormalizedRecord.
            "content_hash": msg.get("content_hash") or "",
        },
    )
