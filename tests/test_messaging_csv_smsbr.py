"""SMS Backup & Restore CSV shape — regression for the direction-column gap.

Byline: Claude Code . Fable 5 . 2026-08-02

262 real files use headers (address, readable_date, type, body, read,
contact_name) where `type` IS the direction as a numeric code (1=received,
2=sent). The parser rejected the format outright ("not a messaging CSV")
because readable_date/contact_name were unmapped, and numeric type codes
matched no direction token. The prior lesson applies: the old behavior was
a silent capability hole, so this test pins the fixed mapping.
"""

from __future__ import annotations

from server.tools.parsers.messaging.messaging_csv import (
    _direction,
    looks_like_messages_csv,
    parse_csv_rows,
)

_HEADER = ["address", "readable_date", "type", "body", "read", "contact_name"]


def _rows(*tuples):
    return [dict(zip(_HEADER, t)) for t in tuples]


def test_smsbr_header_is_recognised():
    assert looks_like_messages_csv(_HEADER)


def test_numeric_type_codes_map_to_direction():
    assert _direction({"type": "1"}) == "inbound"
    assert _direction({"type": "2"}) == "outbound"
    for code in ("4", "5", "6"):
        assert _direction({"type": code}) == "outbound"
    # draft: undirected, not guessed
    assert _direction({"type": "3"}) is None


def test_smsbr_rows_parse_end_to_end():
    rows = _rows(
        ("+15551234567", "Jan 3, 2024 4:12:09 PM", "1", "hey are you coming", "1", "Kat"),
        ("+15551234567", "Jan 3, 2024 4:15:44 PM", "2", "yes leaving now", "1", "Kat"),
    )
    records = parse_csv_rows(rows, conv_id="smsbr-test")
    assert len(records) == 2
    inbound, outbound = records
    assert inbound.attrs["direction"] == "inbound"
    assert inbound.role == "Kat"
    assert inbound.content == "hey are you coming"
    assert inbound.occurred_at is not None and inbound.occurred_at.year == 2024
    assert outbound.attrs["direction"] == "outbound"
    assert outbound.role == "owner"
    # forensic contract: original row preserved verbatim
    assert inbound.attrs["raw_row"]["readable_date"] == "Jan 3, 2024 4:12:09 PM"
